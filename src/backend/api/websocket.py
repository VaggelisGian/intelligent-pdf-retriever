from fastapi import WebSocket, WebSocketDisconnect, APIRouter
import json
import asyncio
from typing import Dict, List

router = APIRouter()

# Store active connections by job ID
active_connections: Dict[str, List[WebSocket]] = {}

@router.websocket("/ws/progress/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint that clients connect to for receiving real-time updates
    Each client connects to a specific job_id they want to track
    """
    print(f"DEBUG: WebSocket connection request received for job: {job_id}")
    await websocket.accept()
    print(f"DEBUG: WebSocket connection accepted for job: {job_id}")
    
    # Register connection
    if job_id not in active_connections:
        active_connections[job_id] = []
    active_connections[job_id].append(websocket)
    
    print(f"WebSocket: New connection established for job: {job_id}")
    print(f"DEBUG: Total active connections: {sum(len(conns) for conns in active_connections.values())}")
    
    try:
        # Keep the connection alive and handle client messages
        while True:
            data = await websocket.receive_text()
            # Handle ping messages to keep connection alive
            if data == "ping":
                print(f"DEBUG: Ping received from client for job: {job_id}")
                await websocket.send_text("pong")
            else:
                print(f"DEBUG: Received message from client: {data[:50]}...")
            
    except WebSocketDisconnect:
        print(f"DEBUG: WebSocket disconnect detected for job: {job_id}")
        # Clean up when client disconnects
        if job_id in active_connections:
            active_connections[job_id].remove(websocket)
            if not active_connections[job_id]:
                del active_connections[job_id]
        print(f"WebSocket: Connection closed for job: {job_id}")
    except Exception as e:
        print(f"DEBUG: WebSocket error: {type(e).__name__}: {e}")
        # Cleanup
        if job_id in active_connections and websocket in active_connections[job_id]:
            active_connections[job_id].remove(websocket)
            
async def broadcast_progress(job_id: str, data: dict):
    """
    Broadcasts progress updates to all clients watching a specific job
    This function is called by the progress tracking module when progress changes
    """
    if job_id in active_connections:
        print(f"DEBUG: Found {len(active_connections[job_id])} connections for job {job_id}")
        for connection in active_connections[job_id]:
            try:
                await connection.send_json(data)
                print(f"DEBUG: Sent progress update for job {job_id}: {data.get('percent_complete')}%")
            except Exception as e:
                print(f"DEBUG: Error broadcasting to client: {type(e).__name__}: {e}")