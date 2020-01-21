import asyncio
import time
from collections import deque
from email.utils import formatdate
from typing import Callable, Deque, Dict, Optional, Union

import wsproto
import wsproto.events
from aioquic.h3.events import DataReceived, H3Event

from AppFiles.http3_server import HttpConnection
from AppFiles.http3_server import AsgiApplication
from AppFiles.http3_server import SERVER_NAME
from serverClasses.HttpRequestHandler import HttpRequestHandler
from serverClasses.websocketDIr.QuicLoggerCustom import application


class WebSocketHandler:
    def __init__(
            self,
            connection: HttpConnection,
            scope: Dict,
            stream_id: int,
            transmit: Callable[[], None],
    ):
        self.closed = False
        self.connection = connection
        self.http_event_queue: Deque[DataReceived] = deque()
        self.queue: asyncio.Queue[Dict] = asyncio.Queue()
        self.scope = scope
        self.stream_id = stream_id
        self.transmit = transmit
        self.websocket: Optional[wsproto.Connection] = None

        print("connection: \n")
        print(connection)
        print("http_event_queue: \n")
        print("stream_id\n")
        print(stream_id)
        print("transmit\n")
        print(transmit)
        print("scope: \n")
        print(scope)



    def http_event_received(self, event: H3Event) -> None:
        if isinstance(event, DataReceived) and not self.closed:
            if self.websocket is not None:
                self.websocket.receive_data(event.data)

                for ws_event in self.websocket.events():
                    self.websocket_event_received(ws_event)
            else:
                # delay event processing until we get `websocket.accept`
                # from the ASGI application
                self.http_event_queue.append(event)

    def websocket_event_received(self, event: wsproto.events.Event) -> None:
        if isinstance(event, wsproto.events.TextMessage):
            self.queue.put_nowait({"type": "websocket.receive", "text": event.data})
            print("received msg")
            print(event.data)
        elif isinstance(event, wsproto.events.Message):
            self.queue.put_nowait({"type": "websocket.receive", "bytes": event.data})
            print("received msg")
            print(event.data)
        elif isinstance(event, wsproto.events.CloseConnection):
            self.queue.put_nowait({"type": "websocket.disconnect", "code": event.code})
            print("received msg")
            print(event.code)


    async def run_asgi(self, app: AsgiApplication) -> None:
        self.queue.put_nowait({"type": "websocket.connect"})

        try:
            await application(self.scope, self.receive, self.send)
        finally:
            if not self.closed:
                await self.send({"type": "websocket.close", "code": 1000})

    async def receive(self) -> Dict:
        return await self.queue.get()

    async def send(self, message: Dict):
        data = b""
        end_stream = False
        if message["type"] == "websocket.accept":
            subprotocol = message.get("subprotocol")

            self.websocket = wsproto.Connection(wsproto.ConnectionType.SERVER)

            headers = [
                (b":status", b"200"),
                (b"server", SERVER_NAME.encode()),
                (b"date", formatdate(time.time(), usegmt=True).encode()),
            ]
            if subprotocol is not None:
                headers.append((b"sec-websocket-protocol", subprotocol.encode()))
            self.connection.send_headers(stream_id=self.stream_id, headers=headers)

            # consume backlog
            while self.http_event_queue:
                self.http_event_received(self.http_event_queue.popleft())

        elif message["type"] == "websocket.close":
            if self.websocket is not None:
                data = self.websocket.send(
                    wsproto.events.CloseConnection(code=message["code"])
                )
            else:
                self.connection.send_headers(
                    stream_id=self.stream_id, headers=[(b":status", b"403")]
                )
            end_stream = True
        elif message["type"] == "websocket.send":
            if message.get("text") is not None:
                data = self.websocket.send(
                    wsproto.events.TextMessage(data=message["text"])
                )
            elif message.get("bytes") is not None:
                data = self.websocket.send(
                    wsproto.events.Message(data=message["bytes"])
                )

        if data:
            self.connection.send_data(
                stream_id=self.stream_id, data=data, end_stream=end_stream
            )
        if end_stream:
            self.closed = True
        self.transmit()


Handler = Union[HttpRequestHandler, WebSocketHandler]
