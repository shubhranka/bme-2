import json
import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect, Depends
from ..api.deps import get_current_user
from ..models.user import User


class WebSocketLogManager:
    """Manages WebSocket connections for log streaming."""

    def __init__(self):
        # Store active connections: {run_id: {connection_id: WebSocket}}
        self.active_connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, run_id: str, connection_id: str):
        """Connect a WebSocket to a specific run."""
        await websocket.accept()

        if run_id not in self.active_connections:
            self.active_connections[run_id] = {}

        self.active_connections[run_id][connection_id] = websocket

        # Send confirmation
        await websocket.send_json({
            "type": "connected",
            "run_id": run_id,
            "message": "Connected to test run"
        })

    def disconnect(self, run_id: str, connection_id: str):
        """Disconnect a WebSocket from a run."""
        if run_id in self.active_connections and connection_id in self.active_connections[run_id]:
            del self.active_connections[run_id][connection_id]

            # Clean up empty run_id entries
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]

    async def broadcast_to_run(self, run_id: str, message: dict):
        """Broadcast a message to all connections for a specific run."""
        if run_id in self.active_connections:
            disconnected = []
            for conn_id, websocket in self.active_connections[run_id].items():
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.append(conn_id)

            # Remove disconnected WebSockets
            for conn_id in disconnected:
                self.disconnect(run_id, conn_id)


manager = WebSocketLogManager()


async def subscribe_to_logs(run_id: str):
    """Subscribe to Redis pub/sub for logs from a specific run."""
    redis_client = await redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

    try:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"logs:{run_id}")

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                try:
                    log_entry = json.loads(data)
                    yield log_entry
                except json.JSONDecodeError:
                    yield {"type": "log", "data": data}

    finally:
        await pubsub.unsubscribe(f"logs:{run_id}")
        await redis_client.close()
