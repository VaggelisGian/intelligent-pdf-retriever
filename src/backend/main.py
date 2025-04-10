from fastapi import FastAPI
from src.backend.api.endpoints import router as api_router

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Initialize any resources needed at startup
    pass

@app.on_event("shutdown")
async def shutdown_event():
    # Clean up resources on shutdown
    pass

app.include_router(api_router, prefix="/api", tags=["api"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)