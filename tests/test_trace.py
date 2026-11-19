import asyncio
from clinical_mcp.client.tracing import PacketTrace, ReadTap, WriteTap


class FakePacket:
    def __init__(self, packet):
        self.packet = packet

    def model_dump(self, **kwargs):
        return self.packet


class FakeSessionMessage:
    def __init__(self, packet):
        self.message = FakePacket(packet)


class FakeStream:
    def __init__(self, payload):
        self.payload = payload

    async def receive(self):
        return self.payload

    async def send(self, payload):
        self.payload = payload


def test_real_message_object_tap():
    async def run():
        packet = FakeSessionMessage({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
        stream = FakeStream(packet)
        trace = PacketTrace()
        await WriteTap(stream, trace).send(packet)
        await ReadTap(stream, trace).receive()
        return trace.events
    events = asyncio.run(run())
    assert events[0]["packet"]["method"] == "tools/list"
    assert events[0]["direction"] == "client → server"
    assert events[1]["direction"] == "server → client"


def test_taps_support_async_context_managers_and_cleanup():
    """SDK v2 dispatch enters *both* streams via `async with`."""
    import anyio

    async def run():
        send, receive = anyio.create_memory_object_stream(2)
        trace = PacketTrace()
        wrapped_send = WriteTap(send, trace)
        wrapped_receive = ReadTap(receive, trace)
        packet = FakeSessionMessage({"jsonrpc": "2.0", "id": 5, "method": "initialize"})
        async with wrapped_send, wrapped_receive:
            await wrapped_send.send(packet)
            got = await wrapped_receive.receive()
            assert got is packet
        assert trace.events[0]["packet"]["method"] == "initialize"
        assert trace.events[1]["packet"]["method"] == "initialize"
        assert send._closed and receive._closed

    asyncio.run(run())
