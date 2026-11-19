"""Trace SDK transport message objects on the real MCP IO boundary.

These are actual protocol packets captured before sending / after receipt,
not reconstructed or simulated from the tool result. No raw patient records
are persisted to disk by this module.
"""
from __future__ import annotations

import anyio


class PacketTrace:
    def __init__(self):
        self.events: list[dict] = []

    def append(self, direction: str, item) -> None:
        if isinstance(item, BaseException):
            return
        message = getattr(item, "message", item)
        if hasattr(message, "model_dump"):
            packet = message.model_dump(by_alias=True, mode="json", exclude_unset=True)
        elif isinstance(message, dict):
            packet = message
        else:
            return
        if isinstance(packet, dict) and "root" in packet and len(packet) == 1:
            packet = packet["root"]
        self.events.append({"direction": direction, "packet": packet})


class ReadTap:
    def __init__(self, stream, trace: PacketTrace):
        self.stream = stream
        self.trace = trace

    async def __aenter__(self):
        # The MCP SDK's JSONRPCDispatcher enters both stream objects.
        # Forward context-management to the real AnyIO stream so that its
        # lifetime and cleanup semantics remain unchanged.
        await self.stream.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self.stream.__aexit__(exc_type, exc_value, traceback)

    @property
    def last_context(self):
        # Preserve context propagation for context-aware receive streams.
        return getattr(self.stream, "last_context", None)

    async def receive(self):
        item = await self.stream.receive()
        self.trace.append("server → client", item)
        return item

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self.receive()
        except anyio.EndOfStream:
            raise StopAsyncIteration from None


class WriteTap:
    def __init__(self, stream, trace: PacketTrace):
        self.stream = stream
        self.trace = trace

    async def __aenter__(self):
        await self.stream.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self.stream.__aexit__(exc_type, exc_value, traceback)

    async def send(self, item):
        await self.stream.send(item)
        self.trace.append("client → server", item)
