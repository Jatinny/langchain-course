"""WebSocket handler for real-time notifications."""
import asyncio
import json
import logging
from typing import Dict, Set
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from jose import JWTError

from common.config import settings
from common.security import verify_access_token

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per user."""

    def __init__(self) -> None:
        # user_id -> set of websockets
        self._connections: Dict[str, Set[WebSocket]] = {}
        # Track all connections for broadcasting
        self._all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(websocket)
        self._all_connections.add(websocket)
        logger.info("WebSocket connected", user_id=user_id, total=len(self._all_connections))

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        self._all_connections.discard(websocket)
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info("WebSocket disconnected", user_id=user_id, total=len(self._all_connections))

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a message to all connections for a specific user."""
        if user_id not in self._connections:
            return
        payload = json.dumps(message, default=str)
        dead_connections = set()
        for websocket in self._connections[user_id].copy():
            try:
                await websocket.send_text(payload)
            except Exception:
                dead_connections.add(websocket)
        for ws in dead_connections:
            self.disconnect(ws, user_id)

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all connected clients."""
        payload = json.dumps(message, default=str)
        dead_connections = set()
        for websocket in self._all_connections.copy():
            try:
                await websocket.send_text(payload)
            except Exception:
                dead_connections.add(websocket)
        for ws in dead_connections:
            self._all_connections.discard(ws)

    @property
    def active_connections(self) -> int:
        return len(self._all_connections)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint with JWT auth."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        token_data = verify_access_token(token)
    except Exception:
        await websocket.close(code=4003, reason="Invalid token")
        return

    user_id = token_data.user_id
    await manager.connect(websocket, user_id)

    # Send welcome message
    await websocket.send_json({
        "type": "connected",
        "data": {
            "user_id": user_id,
            "message": "Connected to RecruitAI real-time events",
        }
    })

    try:
        while True:
            # Keep connection alive with ping/pong
            data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            if data == "ping":
                await websocket.send_text("pong")
    except asyncio.TimeoutError:
        # Send keepalive
        try:
            await websocket.send_json({"type": "ping"})
        except Exception:
            manager.disconnect(websocket, user_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error("WebSocket error", user_id=user_id, error=str(e))
        manager.disconnect(websocket, user_id)


# Kafka event dispatcher — listens to all topics and pushes to WS clients
async def kafka_to_websocket_dispatcher():
    """Background task that routes Kafka events to WebSocket clients."""
    import asyncio
    from common.kafka_client import KafkaConsumerClient

    consumer = KafkaConsumerClient(
        topics=settings.kafka_topics,
        group_id="websocket-dispatcher",
    )

    EVENT_TYPE_MAP = {
        settings.topic_employer_discovered: "employer_discovered",
        settings.topic_employer_qualified: "employer_qualified",
        settings.topic_recruiter_found: "recruiter_found",
        settings.topic_outreach_sent: "outreach_sent",
        settings.topic_outreach_replied: "outreach_replied",
        settings.topic_candidate_matched: "candidate_matched",
        settings.topic_candidate_submitted: "candidate_submitted",
        settings.topic_placement_confirmed: "placement_confirmed",
        settings.topic_commission_earned: "commission_earned",
    }

    async def handle_event(event: dict):
        topic = event.get("_topic", "unknown")
        event_type = EVENT_TYPE_MAP.get(topic, topic)
        user_id = event.get("user_id")

        ws_message = {
            "type": event_type,
            "data": {k: v for k, v in event.items() if not k.startswith("_")},
        }

        if user_id:
            await manager.send_to_user(user_id, ws_message)
        else:
            await manager.broadcast(ws_message)

    for topic in settings.kafka_topics:
        consumer.register_handler(topic, handle_event)

    await consumer.start_consuming()
