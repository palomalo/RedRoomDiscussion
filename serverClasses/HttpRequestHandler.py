import asyncio
import time
from email.utils import formatdate
from typing import Callable, Dict, cast

from aioquic.asyncio import QuicConnectionProtocol
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import DataReceived, H3Event, HeadersReceived
from aioquic.h3.exceptions import NoAvailablePushIDError

from serverClasses.HttpServerProtocol import HttpServerProtocol
from AppFiles.http3_server import HttpConnection
from AppFiles.http3_server import AsgiApplication
from AppFiles.http3_server import SERVER_NAME

from serverClasses.websocketDIr.QuicLoggerCustom import application


class HttpRequestHandler:
    def __init__(
            self,
            *,
            authority: bytes,
            connection: HttpConnection,
            protocol: QuicConnectionProtocol,
            scope: Dict,
            stream_ended: bool,
            stream_id: int,
            transmit: Callable[[], None],
    ):
        self.authority = authority
        self.connection = connection
        self.protocol = protocol
        self.queue: asyncio.Queue[Dict] = asyncio.Queue()
        self.scope = scope
        self.stream_id = stream_id
        self.transmit = transmit

        if stream_ended:
            self.queue.put_nowait({"type": "http.request"})


def http_event_received(self, event: H3Event):
    if isinstance(event, DataReceived):
        self.queue.put_nowait(
            {
                "type": "http.request",
                "body": event.data,
                "more_body": not event.stream_ended,
            }
        )
    elif isinstance(event, HeadersReceived) and event.stream_ended:
        self.queue.put_nowait(
            {"type": "http.request", "body": b"", "more_body": False}
        )


async def run_asgi(self, app: AsgiApplication) -> None:
    await application(self.scope, self.receive, self.send)


async def receive(self) -> Dict:
    return await self.queue.get()


async def send(self, message: Dict):
    if message["type"] == "http.response.start":
        connection.send_headers(
            stream_id=self.stream_id,
            headers=[
                        (b":status", str(message["status"]).encode()),
                        (b"server", SERVER_NAME.encode()),
                        (b"date", formatdate(time.time(), usegmt=True).encode()),
                    ]
                    + [(k, v) for k, v in message["headers"]],
        )
    elif message["type"] == "http.response.body":
        connection.send_data(
            stream_id=self.stream_id,
            data=message.get("body", b""),
            end_stream=not message.get("more_body", False),
        )
    elif message["type"] == "http.response.push" and isinstance(
            connection, H3Connection
    ):
        request_headers = [
                              (b":method", b"GET"),
                              (b":scheme", b"https"),
                              (b":authority", self.authority),
                              (b":path", message["path"].encode()),
                          ] + [(k, v) for k, v in message["headers"]]

        # send push promise
        try:
            push_stream_id = connection.send_push_promise(
                stream_id=self.stream_id, headers=request_headers
            )
        except NoAvailablePushIDError:
            return

        # fake request
        cast(HttpServerProtocol, self.protocol).http_event_received(
            HeadersReceived(
                headers=request_headers, stream_ended=True, stream_id=push_stream_id
            )
        )
    self.transmit()
