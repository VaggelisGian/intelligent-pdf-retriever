from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import shutil
import uuid
import json
from src.backend.document_processing.pdf_loader import PDFLoader
from src.backend.document_processing.text_processor import TextProcessor
from src.backend.database.neo4j_client import Neo4jClient
from src.backend.assistant.rag import RAGAssistant
from src.backend.assistant.graph_rag import GraphRAGAssistant
from dotenv import load_dotenv
from src.backend.api.progress import router as progress_router
from src.backend.api.progress import complete_job as progress_complete_job
from src.backend.api.websocket import router as websocket_router
import redis
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
try:
    # Use separate client for health check with short timeouts
    redis_health_client = redis.Redis.from_url(
        redis_url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True
    )
    redis_health_client.ping()
    print(f"Health Check using Redis at: {redis_url}")
except Exception as e:
    print(f"WARNING: Failed to initialize Redis client for health check: {e}")
    redis_health_client = None

# Load environment variables
load_dotenv()

# Initialize router
router = APIRouter()

# Include the progress router
print("DEBUG: Registering WebSocket router")
router.include_router(websocket_router)  # This will be mounted directly in main.py

# Include the progress router with explicit prefix
print("DEBUG: Registering progress router")
# Note: We're explicitly using /progress here, which will become /api/progress when mounted
router.include_router(progress_router, prefix="/progress", tags=["progress"])
print(f"DEBUG: Progress router registered with routes: {[route.path for route in progress_router.routes]}")

# Initialize clients and assistants
rag_assistant = None
graph_rag_assistant = None

class ChatRequest(BaseModel):
    question: str
    use_graph: bool = False

class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = []

@router.get("/health")
async def health_check():
    """Check if all services are ready"""
    neo4j_status = "down"
    try:
        # Check Neo4j connection (use correct host 'neo4j' for docker-compose)
        neo4j_uri_health = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
        neo4j_user_health = os.getenv('NEO4J_USERNAME', 'neo4j')
        neo4j_password_health = os.getenv('NEO4J_PASSWORD', 'vaggpinel')

        neo4j_client_health = Neo4jClient(
            neo4j_uri_health,
            neo4j_user_health,
            neo4j_password_health
        )
        neo4j_client_health.run_query("RETURN 1 as test")
        neo4j_client_health.close()
        neo4j_status = "up"
    except Exception as neo4j_e:
        print(f"Health check Neo4j error: {neo4j_e}")
        neo4j_status = f"down: {type(neo4j_e).__name__}"


    # Check Redis connection using the dedicated health client
    redis_status = "down: client init failed"
    if redis_health_client:
        try:
            redis_health_client.ping()
            redis_status = "up"
        except redis.exceptions.ConnectionError as e:
            redis_status = f"down: ConnectionError: {str(e)}"
        except redis.exceptions.TimeoutError as e:
            redis_status = f"down: TimeoutError: {str(e)}"
        except Exception as e:
            redis_status = f"down: {type(e).__name__}: {str(e)}"

    backend_status = "up" # If this endpoint responds, backend is up
    overall_status = "healthy" if neo4j_status == "up" and redis_status == "up" else "unhealthy"

    if overall_status == "healthy":
         return {"status": overall_status, "services": {"neo4j": neo4j_status, "redis": redis_status, "backend": backend_status}}
    else:
         # Return 503 if unhealthy
         raise HTTPException(status_code=503, detail={"status": overall_status, "services": {"neo4j": neo4j_status, "redis": redis_status, "backend": backend_status}})


# --- Upload Endpoint ---
@router.post("/upload", status_code=200)
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload and process a PDF document"""
    try:
        upload_dir = "data/pdf_files"
        os.makedirs(upload_dir, exist_ok=True)

        job_id = str(uuid.uuid4())
        # Sanitize filename to prevent path traversal issues, although saving locally might be okay here
        safe_filename = os.path.basename(file.filename or f"upload_{job_id}.pdf")
        file_path = os.path.join(upload_dir, safe_filename)

        # Save uploaded file
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as save_e:
             print(f"ERROR saving uploaded file {safe_filename}: {save_e}")
             raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {save_e}")
        finally:
            # Ensure the file object is closed
             if hasattr(file, 'close'):
                 file.close()


        # Add the background task
        background_tasks.add_task(process_pdf, file_path, safe_filename, job_id)

        print(f"Upload successful for {safe_filename}, starting background job {job_id}")
        return {
            "message": "File uploaded and processing started",
            "filename": safe_filename,
            "job_id": job_id
        }
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions
        raise http_exc
    except Exception as e:
        print(f"ERROR during file upload: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error during upload: {type(e).__name__}")


# --- Background PDF Processing Task ---
async def process_pdf(file_path, filename, job_id):
    """Process PDF in the background with progress tracking"""
    # Note: This runs in a separate thread managed by FastAPI/Starlette.
    # It should use the functions from progress.py (create_job, update_job_progress, complete_job)
    # which use the globally initialized redis_client in that module.
    # Avoid creating a new Redis client here if possible.
    from src.backend.api.progress import create_job, update_job_progress # Import here to use shared client

    try:
        print(f"Background task started for job {job_id}, file {filename}")
        # Phase 1: PDF Extraction
        pdf_loader = PDFLoader(os.path.dirname(file_path))
        # Use await since extract_text_from_pdf is now async
        text = await pdf_loader.extract_text_from_pdf(file_path, job_id) # <-- Add await

        if not text:
             print(f"Job {job_id}: No text extracted from PDF {filename}.")
             # Mark job as failed if no text extracted
             progress_complete_job(job_id, "Failed: No text could be extracted from PDF", final_status="failed")
             return # Stop processing

        print(f"Job {job_id}: PDF extraction complete. Text length: {len(text)}")

        # Phase 2: Text Processing and Neo4j Ingestion
        # Update status to indicate start of Phase 2
        # Need a function in progress.py to update status/message without changing page count
        from src.backend.api.progress import redis_client as shared_redis_client # Get shared client
        if shared_redis_client:
            try:
                redis_key = f"job:{job_id}"
                job_data = shared_redis_client.get(redis_key)
                if job_data:
                    job = json.loads(job_data)
                    job["status"] = "processing_neo4j"
                    job["message"] = "Processing text and creating graph..."
                    job["percent_complete"] = 55 # Set baseline for phase 2
                    shared_redis_client.setex(redis_key, 86400, json.dumps(job)) # Keep TTL
                    print(f"Job {job_id}: Updated status to processing_neo4j")
            except Exception as status_update_e:
                 print(f"Job {job_id}: WARNING - Failed to update status to processing_neo4j: {status_update_e}")


        text_processor = TextProcessor()
        sentences = text_processor.process_text(text)
        total_sentences = len(sentences)
        print(f"Job {job_id}: Processed text into {total_sentences} sentences.")

        # Connect to Neo4j (use correct host 'neo4j')
        neo4j_client = Neo4jClient(
            os.getenv('NEO4J_URI', 'bolt://neo4j:7687'),
            os.getenv('NEO4J_USERNAME', 'neo4j'),
            os.getenv('NEO4J_PASSWORD', 'vaggpinel')
        )

        # Create document node
        doc_id = filename.replace('.pdf', '') # Consider more robust ID generation
        neo4j_client.create_node('Document', {'id': doc_id, 'title': filename}) # Don't store full text here

        # Create sentence nodes and relationships with progress updates
        print(f"Job {job_id}: Starting Neo4j ingestion for {total_sentences} sentences...")
        sentences_added_count = 0
        # Import asyncio if not already imported at the top
        import asyncio

        for i, sentence in enumerate(sentences):
            if len(sentence) > 10:  # Skip very short sentences
                sent_id = f"{doc_id}_s{i}"
                neo4j_client.create_node('Sentence', {'id': sent_id, 'content': sentence})
                neo4j_client.run_query(
                    "MATCH (d:Document {id: $doc_id}), (s:Sentence {id: $sent_id}) CREATE (d)-[:CONTAINS]->(s)",
                    {"doc_id": doc_id, "sent_id": sent_id}
                )
                sentences_added_count += 1

                # Update overall progress (Phase 2: 55% to 99%)
                if i % max(1, total_sentences // 20) == 0 or i == total_sentences - 1: # Update ~ every 5%
                    sentence_progress = (i + 1) / total_sentences
                    overall_percent = 55 + int(sentence_progress * 44) # Map to 55-99% range

                    if shared_redis_client:
                        try:
                            redis_key = f"job:{job_id}"
                            job_data = shared_redis_client.get(redis_key)
                            if job_data:
                                job = json.loads(job_data)
                                job["message"] = f"Creating graph: sentence {i+1}/{total_sentences}"
                                job["percent_complete"] = min(overall_percent, 99) # Cap at 99 until truly done
                                job["status"] = "processing_neo4j"
                                shared_redis_client.setex(redis_key, 86400, json.dumps(job)) # Keep TTL
                                # Log less frequently in backend
                                if i % max(1, total_sentences // 5) == 0 or i == total_sentences -1:
                                     print(f"Neo4j Progress: Job {job_id} - {i+1}/{total_sentences} sentences ({overall_percent}%)")
                        except Exception as neo4j_prog_e:
                             print(f"Job {job_id}: WARNING - Failed to update Neo4j progress in Redis: {neo4j_prog_e}")

            # Yield control after processing each sentence (or batch if you implement batching)
            await asyncio.sleep(0) # <-- Add this line

        print(f"Job {job_id}: Finished Neo4j ingestion. Added {sentences_added_count} sentences.")
        neo4j_client.close()

        # Mark job as fully complete (uses complete_job from progress.py)
        progress_complete_job(job_id, "Processing complete - ready for querying", final_status="completed")
        print(f"Background task finished successfully for job: {job_id}")

    except Exception as e:
        # ... (error handling remains the same) ...
        error_message = f"Error during processing: {type(e).__name__}: {str(e)}"
        print(f"ERROR in background task for job {job_id}: {error_message}")
        import traceback
        traceback.print_exc()
        # Mark job as failed
        progress_complete_job(job_id, error_message, final_status="failed")


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest):
    """Chat with the RAG or Graph RAG assistant"""
    try:
        global rag_assistant, graph_rag_assistant
        
        if request.use_graph:
            # Use Graph RAG
            if graph_rag_assistant is None:
                graph_rag_assistant = GraphRAGAssistant()
            
            response = graph_rag_assistant.query(request.question)
            return ChatResponse(answer=response, sources=[])
        else:
            # Use standard RAG
            if rag_assistant is None:
                rag_assistant = RAGAssistant()
            
            response = rag_assistant.query(request.question)
            return ChatResponse(answer=response["result"], sources=[doc.page_content for doc in response.get("source_documents", [])])
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))