from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.backend.api.endpoints import router as api_router
from src.backend.api.websocket import router as websocket_router

app = FastAPI()

# Add CORS middleware with WebSocket support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Initialize any resources needed at startup
    pass

@app.on_event("shutdown")
async def shutdown_event():
    # Clean up resources on shutdown
    pass

# Include API routers
app.include_router(api_router, prefix="/api", tags=["api"])

# Mount WebSocket routes directly (without the /api prefix)
app.include_router(websocket_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)