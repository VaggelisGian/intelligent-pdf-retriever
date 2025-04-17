from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# Import assistant classes directly
from src.backend.assistant.rag import RAGAssistant
from src.backend.assistant.graph_rag import GraphRAGAssistant
# Import router AFTER app creation below
# REMOVE: from src.backend.api.websocket import router as websocket_router

app = FastAPI(title="Intelligent PDF Retriever Backend")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for simplicity, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define state attributes for type hinting (optional but good practice)
class AppState:
    rag_assistant_instance: Optional[RAGAssistant] = None
    graph_rag_assistant_instance: Optional[GraphRAGAssistant] = None

app.state = AppState() # Initialize state

@app.on_event("startup")
async def startup_event():
    print("Initializing Assistants on startup...")
    # Initialize with default LLM settings here
    # Store instances in app.state
    app.state.rag_assistant_instance = RAGAssistant()
    app.state.graph_rag_assistant_instance = GraphRAGAssistant()
    print("Assistants initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    # Add cleanup logic if needed
    print("Shutting down backend.")

# Import and include the router AFTER app and state are defined
from src.backend.api.endpoints import router as api_router
app.include_router(api_router, prefix="/api")

# REMOVE: Mount WebSocket routes directly (without the /api prefix)
# REMOVE: app.include_router(websocket_router)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Intelligent PDF Retriever Backend"}

# If running directly (for local testing without docker-compose uvicorn command)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)