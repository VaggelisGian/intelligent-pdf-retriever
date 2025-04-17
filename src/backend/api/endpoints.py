from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Request # Added Request
from pydantic import BaseModel
from typing import Dict, Any, List, Optional # Added Optional
import os
import shutil
import chardet
import uuid
import json
import redis
import asyncio
import traceback
from dotenv import load_dotenv
import src.backend.api.models
from src.backend.api.progress import redis_client as shared_redis_client
from src.backend.api.progress import router as progress_router
from src.backend.api.progress import create_job, update_job_progress, update_job_status, progress_complete_job, complete_job_sync # Corrected import

from src.backend.document_processing.pdf_loader import PDFLoader
from src.backend.document_processing.text_processor import TextProcessor
from src.backend.database.neo4j_client import Neo4jClient
from src.backend.assistant.rag import RAGAssistant # Keep for type hinting if needed
from src.backend.assistant.graph_rag import GraphRAGAssistant # Keep for type hinting if needed

from langchain_openai import ChatOpenAI, OpenAIEmbeddings # Added OpenAIEmbeddings


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
print("DEBUG: Registering progress router")
router.include_router(progress_router, prefix="/progress", tags=["progress"])
print(f"DEBUG: Progress router registered with routes: {[route.path for route in progress_router.routes]}")

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
                await file.close()


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
async def process_document(file_path, filename, job_id): # Rename to process_document
    """Process PDF or TXT document in the background with progress tracking"""
    from src.backend.api.progress import create_job, update_job_progress, update_job_status # Import update_job_status

    text = ""
    total_items = 0 # Pages for PDF, Chunks for TXT
    is_pdf = filename.lower().endswith(".pdf")

    try:
        print(f"Background task started for job {job_id}, file {filename}")

        if is_pdf:
            # --- PDF Extraction ---
            pdf_loader = PDFLoader(os.path.dirname(file_path))
            # Use await since extract_text_from_pdf is now async
            text = await pdf_loader.extract_text_from_pdf(file_path, job_id) # This already calls create_job
            if not text:
                 print(f"Job {job_id}: No text extracted from PDF {filename}.")
                 await progress_complete_job(job_id, "Failed: No text could be extracted from PDF", final_status="failed")
                 return # Stop processing
            print(f"Job {job_id}: PDF extraction complete. Text length: {len(text)}")
            # total_items is handled by create_job inside extract_text_from_pdf

        else:
            # --- TXT Reading ---
            print(f"Job {job_id}: Reading TXT file {filename}")
            try:
                # Detect encoding
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                    detected_encoding = chardet.detect(raw_data)['encoding'] or 'utf-8' # Default to utf-8

                with open(file_path, 'r', encoding=detected_encoding) as f:
                    text = f.read()
                # Initialize progress for TXT (total_items will be chunk count later)
                create_job(job_id, filename, total_pages=1) # Use 1 page initially for TXT
                await update_job_progress(job_id, 1) # Mark reading as complete (1/1 page)
                print(f"Job {job_id}: TXT reading complete. Text length: {len(text)}")
            except Exception as read_e:
                print(f"Job {job_id}: Error reading TXT file {filename}: {read_e}")
                await progress_complete_job(job_id, f"Failed: Error reading TXT file: {read_e}", final_status="failed")
                return # Stop processing

        # --- Phase 2: Text Chunking and Neo4j Ingestion ---
        await update_job_status(job_id, status="chunking", message="Chunking document text...") # Update status

        text_processor = TextProcessor()
        # Use chunking instead of sentence splitting
        chunks = text_processor.process_text(text) # Now returns chunks
        total_items = len(chunks) # Update total_items to chunk count
        print(f"Job {job_id}: Processed text into {total_items} chunks.")

        # Update total pages in Redis job info if it was a TXT file
        if not is_pdf and shared_redis_client:
             redis_key = f"job:{job_id}"
             job_data = shared_redis_client.get(redis_key)
             if job_data:
                 try:
                     job = json.loads(job_data)
                     job["total_pages"] = total_items # Re-purpose total_pages for chunks
                     job["message"] = f"Processing {total_items} chunks..."
                     shared_redis_client.setex(redis_key, 86400, json.dumps(job))
                 except Exception as redis_update_e:
                     print(f"Job {job_id}: Failed to update total chunk count in Redis: {redis_update_e}")


        if not chunks:
            print(f"Job {job_id}: No chunks generated from the text.")
            await progress_complete_job(job_id, "Completed: No text chunks generated after processing.", final_status="completed") # Consider completed if no chunks
            return

        # Connect to Neo4j
        neo4j_client = Neo4jClient(
            os.getenv('NEO4J_URI', 'bolt://neo4j:7687'),
            os.getenv('NEO4J_USERNAME', 'neo4j'),
            os.getenv('NEO4J_PASSWORD', 'vaggpinel')
        )

        # Create document node
        doc_id = filename.rsplit('.', 1)[0] # More robust way to remove extension
        neo4j_client.run_query(
             "MERGE (d:Document {id: $doc_id}) ON CREATE SET d.title = $title",
             {'doc_id': doc_id, 'title': filename}
        )

        # --- Embeddings and Neo4j Ingestion ---
        await update_job_status(job_id, status="embedding_neo4j", message="Generating embeddings and storing in Neo4j...")

        # Initialize Embeddings client pointing to LM Studio (same as process_documents.py)
        lm_studio_api_base = "http://host.docker.internal:1234/v1" # Use host.docker.internal for Docker
        lm_studio_api_key = "lm-studio"
        embeddings_client = OpenAIEmbeddings(
            openai_api_key=lm_studio_api_key,
            openai_api_base=lm_studio_api_base,
            chunk_size=50 # Or make configurable
        )

        chunks_added_count = 0
        batch_size = 50 # Configurable batch size for Neo4j/Embedding

        for i in range(0, total_items, batch_size):
            batch_chunks = chunks[i : i + batch_size]
            if not batch_chunks: continue

            # Generate embeddings
            try:
                batch_embeddings = embeddings_client.embed_documents(batch_chunks)
            except Exception as emb_e:
                print(f"Job {job_id}: Error generating embeddings for batch starting at index {i}: {emb_e}")
                # Optionally skip or retry
                continue

            if len(batch_embeddings) != len(batch_chunks):
                print(f"Job {job_id}: Warning: Embedding count mismatch for batch {i}.")
                continue

            # Prepare data for Neo4j
            batch_params = []
            for j, chunk_text in enumerate(batch_chunks):
                chunk_index = i + j # Overall index of the chunk
                chunk_id = f'{doc_id}_c{chunk_index}' # Use 'c' for chunk
                batch_params.append({
                    'doc_id': doc_id,
                    'chunk_id': chunk_id,
                    'content': chunk_text,
                    'embedding': batch_embeddings[j]
                })

            # Add to Neo4j
            if batch_params:
                try:
                    # Use MERGE for idempotency, rename Sentence to Chunk
                    neo4j_client.run_query(
                        """
                        UNWIND $batch as row
                        MATCH (d:Document {id: row.doc_id})
                        MERGE (c:Chunk {id: row.chunk_id})
                        ON CREATE SET c.content = row.content, c.embedding = row.embedding
                        ON MATCH SET c.embedding = row.embedding
                        MERGE (d)-[:CONTAINS]->(c)
                        """,
                        {'batch': batch_params}
                    )
                    chunks_added_count += len(batch_params)

                    # Update progress based on chunks processed
                    percent_complete = int((chunks_added_count / total_items) * 100)
                    await update_job_status(
                        job_id,
                        status="embedding_neo4j",
                        message=f"Storing chunk {chunks_added_count}/{total_items}",
                        percent_complete=percent_complete,
                        current_page=chunks_added_count # Re-use current_page for chunks processed
                    )

                except Exception as neo_e:
                    print(f"Job {job_id}: Error executing Neo4j batch query for batch starting at index {i}: {neo_e}")
                    # Optionally skip or retry
                    continue

            await asyncio.sleep(0) # Yield control

        print(f"Job {job_id}: Finished Neo4j ingestion. Added/Updated {chunks_added_count} chunks.")
        neo4j_client.close()

        # --- Final Step: Create Vector Index ---
        # This should ideally be done once after processing, maybe not per-job
        # Or ensure it's idempotent. Let's keep it in process_documents.py for now.

        await progress_complete_job(job_id, "Processing complete - ready for querying", final_status="completed")
        print(f"Background task finished successfully for job: {job_id}")

    except Exception as e:
        error_message = f"Error during processing: {type(e).__name__}: {str(e)}"
        print(f"ERROR in background task for job {job_id}: {error_message}")
        import traceback
        traceback.print_exc()
        await progress_complete_job(job_id, error_message, final_status="failed")


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(request: Request, chat_request: ChatRequest): # Add Request to parameters
    """Chat with the RAG or Graph RAG assistant, allowing parameter overrides"""

    # Access assistants from app state via request
    rag_assistant_instance = request.app.state.rag_assistant_instance
    graph_rag_assistant_instance = request.app.state.graph_rag_assistant_instance

    if rag_assistant_instance is None or graph_rag_assistant_instance is None:
         # Should not happen if startup event worked, but handle defensively
         raise HTTPException(status_code=503, detail="Assistants not initialized")

    try:
        # --- LLM Configuration ---
        lm_studio_api_base = "http://host.docker.internal:1234/v1" # Use host.docker.internal inside docker
        lm_studio_api_key = "lm-studio"

        # Default LLM parameters
        llm_params = {
            "temperature": 0.1, # Default temperature
            "max_tokens": 512, # Default max tokens
        }
        # Override defaults with request parameters if provided
        if chat_request.temperature is not None:
            llm_params["temperature"] = chat_request.temperature
        if chat_request.max_tokens is not None:
            llm_params["max_tokens"] = chat_request.max_tokens

        # Create a potentially customized LLM instance for this request
        llm_instance = ChatOpenAI(
            openai_api_key=lm_studio_api_key,
            openai_api_base=lm_studio_api_base,
            temperature=llm_params["temperature"],
            max_tokens=llm_params["max_tokens"]
        )
        print(f"Using LLM for chat with params: {llm_params}")

        # --- Update Assistants with request-specific LLM ---
        rag_assistant_instance.update_llm(llm_instance)
        graph_rag_assistant_instance.update_llm(llm_instance)

        # --- Perform Query ---
        if chat_request.use_graph:
            print("Using Graph RAG Assistant")
            result = graph_rag_assistant_instance.query(chat_request.question)
            answer = result.get("result", "Could not retrieve answer from graph.")
            sources = [] # GraphQAChain doesn't easily provide sources
        else:
            print("Using Standard RAG Assistant")
            result = rag_assistant_instance.query(chat_request.question)
            answer = result.get("result", "Could not retrieve answer.")
            sources = [doc.page_content for doc in result.get("source_documents", [])]

        return ChatResponse(answer=answer, sources=sources)

    except Exception as e:
        print(f"ERROR during chat: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error during chat: {type(e).__name__}")