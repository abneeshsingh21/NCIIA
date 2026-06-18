"""
WebSocket Handler for Real-time Updates
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from nciia.utils import get_logger

websocket_router = APIRouter()
logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for live updates."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("websocket_connected", total=len(self.active_connections))
    
    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        logger.info("websocket_disconnected", total=len(self.active_connections))
    
    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        dead = set()
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.add(conn)
        for d in dead:
            self.active_connections.discard(d)
    
    async def send_to(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """Send message to specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error("websocket_send_failed", error=str(e))


manager = ConnectionManager()


@websocket_router.websocket("/live")
async def websocket_live(websocket: WebSocket):
    """Main WebSocket endpoint for live updates."""
    await manager.connect(websocket)
    
    try:
        # Send welcome message
        await manager.send_to(websocket, {
            "type": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Connected to N-CIIA live feed",
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                try:
                    message = json.loads(data)
                    await handle_client_message(websocket, message)
                except json.JSONDecodeError:
                    await manager.send_to(websocket, {
                        "type": "error",
                        "message": "Invalid JSON",
                    })
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_to(websocket, {
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def handle_client_message(websocket: WebSocket, message: dict[str, Any]) -> None:
    """Handle incoming client messages."""
    msg_type = message.get("type")
    
    if msg_type == "subscribe":
        # Subscribe to specific events
        await manager.send_to(websocket, {
            "type": "subscribed",
            "topics": message.get("topics", []),
        })
    
    elif msg_type == "ping":
        await manager.send_to(websocket, {"type": "pong"})
    
    else:
        await manager.send_to(websocket, {
            "type": "ack",
            "received": msg_type,
        })


# Event broadcasting functions
async def broadcast_signal_detected(signal_data: dict[str, Any]) -> None:
    """Broadcast new signal detection to all clients."""
    await manager.broadcast({
        "type": "signal_detected",
        "timestamp": datetime.utcnow().isoformat(),
        "data": signal_data,
    })


async def broadcast_threat_update(persona_id: str, threat_data: dict[str, Any]) -> None:
    """Broadcast threat score update."""
    await manager.broadcast({
        "type": "threat_update",
        "timestamp": datetime.utcnow().isoformat(),
        "persona_id": persona_id,
        "data": threat_data,
    })


async def broadcast_persona_activity(persona_id: str, activity: dict[str, Any]) -> None:
    """Broadcast new persona activity."""
    await manager.broadcast({
        "type": "persona_activity",
        "timestamp": datetime.utcnow().isoformat(),
        "persona_id": persona_id,
        "data": activity,
    })
