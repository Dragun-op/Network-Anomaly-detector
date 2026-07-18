"""
Minimal WebSocket broadcast so the frontend's "Live" indicator is actually
true: the replay worker calls `manager.broadcast(incident_json)` the
instant it writes a new incident, and every connected browser gets it
without polling.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)

    async def broadcast(self, payload: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(json.dumps(payload, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws/incidents")
async def incidents_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # we don't expect client messages, but need to await something
            # so the server notices a disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
