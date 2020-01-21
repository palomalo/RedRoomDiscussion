import argparse
import asyncio
import json
import logging
import pickle
import ssl
import sys
import time
from collections import deque
from typing import Callable, Deque, Dict, List, Optional, Union, cast
from urllib.parse import urlparse

import wsproto
import wsproto.events

import aioquic
from aioquic.asyncio.client import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h0.connection import H0_ALPN, H0Connection
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import (
    DataReceived,
    H3Event,
    HeadersReceived,
    PushPromiseReceived,
)
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent
from aioquic.quic.logger import QuicLogger

# main test params: --ca-certs ../Keys/pycacert.pem https://localhost:4433/
from AppFiles.websocketMains.clientClasses.URL import URL
from AppFiles.websocketMains.clientClasses.HttpRequest import HttpRequest
from AppFiles.websocketMains.clientClasses.WebSocket import WebSocket

try:
    import uvloop
except ImportError:
    uvloop = None

logger = logging.getLogger("client")

HttpConnection = Union[H0Connection, H3Connection]

USER_AGENT = "aioquic/" + aioquic.__version__

URLLL = URL("wss://localhost:4433/ws")


# websocket = WebSocket() 3 required arguments


def getUserAgent():
    return USER_AGENT


def transaction(userChat):
    print("password correct - ")
    print("run client")
    print(userChat)

    class HttpClient(QuicConnectionProtocol):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.pushes: Dict[int, Deque[H3Event]] = {}
            self._http: Optional[HttpConnection] = None
            self._request_events: Dict[int, Deque[H3Event]] = {}
            self._request_waiter: Dict[int, asyncio.Future[Deque[H3Event]]] = {}
            self._websockets: Dict[int, WebSocket] = {}

            if self._quic.configuration.alpn_protocols[0].startswith("hq-"):
                self._http = H0Connection(self._quic)
            else:
                self._http = H3Connection(self._quic)

        async def get(self, url: str, headers: Dict = {}) -> Deque[H3Event]:
            """
            Perform a GET request.
            """
            return await self._request(
                HttpRequest(method="GET", url=URL(url), headers=headers)
            )

        async def post(self, url: str, data: bytes, headers: Dict = {}) -> Deque[H3Event]:
            """
            Perform a POST request.
            """
            return await self._request(
                HttpRequest(method="POST", url=URLLL, content=data, headers=headers)
            )

        async def websocket(self, url: str, subprotocols: List[str] = []) -> WebSocket:
            """
            Open a WebSocket.
            """
            request = HttpRequest(method="CONNECT", url=URLLL)
            stream_id = self._quic.get_next_available_stream_id()
            websocket = WebSocket(
                http=self._http, stream_id=stream_id, transmit=self.transmit
            )

            self._websockets[stream_id] = websocket

            headers = [
                (b":method", b"CONNECT"),
                (b":scheme", b"https"),
                (b":authority", request.url.authority.encode()),
                (b":path", request.url.full_path.encode()),
                (b":protocol", b"websocket"),
                (b"user-agent", USER_AGENT.encode()),
                (b"sec-websocket-version", b"13"),
            ]
            if subprotocols:
                headers.append(
                    (b"sec-websocket-protocol", ", ".join(subprotocols).encode())
                )
            self._http.send_headers(stream_id=stream_id, headers=headers)

            self.transmit()

            return websocket

        def http_event_received(self, event: H3Event):
            if isinstance(event, (HeadersReceived, DataReceived)):
                stream_id = event.stream_id
                if stream_id in self._request_events:
                    # http
                    self._request_events[event.stream_id].append(event)
                    if event.stream_ended:
                        request_waiter = self._request_waiter.pop(stream_id)
                        request_waiter.set_result(self._request_events.pop(stream_id))

                elif stream_id in self._websockets:
                    # websocket
                    websocket = self._websockets[stream_id]
                    websocket.http_event_received(event)

                elif event.push_id in self.pushes:
                    # push
                    self.pushes[event.push_id].append(event)

            elif isinstance(event, PushPromiseReceived):
                self.pushes[event.push_id] = deque()
                self.pushes[event.push_id].append(event)

        def quic_event_received(self, event: QuicEvent):
            #  pass event to the HTTP layer
            if self._http is not None:
                for http_event in self._http.handle_event(event):
                    self.http_event_received(http_event)

        async def _request(self, request: HttpRequest):
            stream_id = self._quic.get_next_available_stream_id()
            self._http.send_headers(
                stream_id=stream_id,
                headers=[
                            (b":method", request.method.encode()),
                            (b":scheme", request.url.scheme.encode()),
                            (b":authority", request.url.authority.encode()),
                            (b":path", request.url.full_path.encode()),
                            (b"user-agent", USER_AGENT.encode()),
                        ]
                        + [(k.encode(), v.encode()) for (k, v) in request.headers.items()],
            )
            self._http.send_data(stream_id=stream_id, data=request.content, end_stream=True)

            waiter = self._loop.create_future()
            self._request_events[stream_id] = deque()
            self._request_waiter[stream_id] = waiter
            self.transmit()

            return await asyncio.shield(waiter)

    async def perform_http_request(
            client: HttpClient, url: str, data: str, print_response: bool
    ) -> None:
        # perform request
        start = time.time()
        if data is not None:
            http_events = await client.post(
                url,
                data=data.encode(),
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        else:
            http_events = await client.get(url)
        elapsed = time.time() - start

        # print speed
        octets = 0
        for http_event in http_events:
            if isinstance(http_event, DataReceived):
                octets += len(http_event.data)
        logger.info(
            "Received %d bytes in %.1f s (%.3f Mbps)"
            % (octets, elapsed, octets * 8 / elapsed / 1000000)
        )

        # print response
        if print_response:
            for http_event in http_events:
                if isinstance(http_event, HeadersReceived):
                    headers = b""
                    for k, v in http_event.headers:
                        headers += k + b": " + v + b"\r\n"
                    if headers:
                        sys.stderr.buffer.write(headers + b"\r\n")
                        sys.stderr.buffer.flush()
                elif isinstance(http_event, DataReceived):
                    sys.stdout.buffer.write(http_event.data)
                    sys.stdout.buffer.flush()

    def save_session_ticket(ticket):
        """
        Callback which is invoked by the TLS engine when a new session ticket
        is received.
        """
        logger.info("New session ticket received")
        if args.session_ticket:
            with open(args.session_ticket, "wb") as fp:
                pickle.dump(ticket, fp)

    async def run(
            configuration: QuicConfiguration,
            url: str,
            data: str,
            parallel: int,
            print_response: bool,
    ) -> None:
        # parse URL
        parsed = urlparse(url)
        assert parsed.scheme in (
            "https",
            "wss",
        ), "Only https:// or wss:// URLs are supported."
        if ":" in parsed.netloc:
            host, port_str = parsed.netloc.split(":")
            port = int(port_str)
        else:
            host = parsed.netloc
            port = 443

        async with connect(
                host,
                port,
                configuration=configuration,
                create_protocol=HttpClient,
                session_ticket_handler=save_session_ticket,
        ) as client:
            client = cast(HttpClient, client)

            if parsed.scheme == "wss":
                ws = await client.websocket(url, subprotocols=["chat", "superchat"])

                # send some messages and receive reply
                for i in range(2):
                    message = "Hello {}, WebSocket!".format(i)
                    message = userChat
                    print("> " + message)
                    await ws.send(message)

                    message = await ws.recv()
                    print("< " + message)

                await ws.close()
            else:
                # perform request
                coros = [
                    perform_http_request(
                        client=client, url=url, data=data, print_response=print_response
                    )
                    for i in range(parallel)
                ]
                await asyncio.gather(*coros)

    if __name__ == "__main__":
        parser = argparse.ArgumentParser(description="HTTP/3 client")
        parser.add_argument("url", type=str, help="the URL to query (must be HTTPS)")
        parser.add_argument(
            "--ca-certs", type=str, help="load CA certificates from the specified file"
        )
        parser.add_argument(
            "-d", "--data", type=str, help="send the specified data in a POST request"
        )
        parser.add_argument(
            "-k",
            "--insecure",
            action="store_true",
            help="do not validate server certificate",
        )
        parser.add_argument("--legacy-http", action="store_true", help="use HTTP/0.9")
        parser.add_argument(
            "-q", "--quic-log", type=str, help="log QUIC events to a file in QLOG format"
        )
        parser.add_argument(
            "-l",
            "--secrets-log",
            type=str,
            help="log secrets to a file, for use with Wireshark",
        )
        parser.add_argument(
            "--parallel", type=int, default=1, help="perform this many requests in parallel"
        )
        parser.add_argument(
            "--print-response", action="store_true", help="print response headers and body"
        )
        parser.add_argument(
            "-s",
            "--session-ticket",
            type=str,
            help="read and write session ticket from the specified file",
        )
        parser.add_argument(
            "-v", "--verbose", action="store_true", help="increase logging verbosity"
        )

        args = parser.parse_args()

        logging.basicConfig(
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            level=logging.DEBUG if args.verbose else logging.INFO,
        )

        # prepare configuration
        configuration = QuicConfiguration(
            is_client=True, alpn_protocols=H0_ALPN if args.legacy_http else H3_ALPN
        )
        if args.ca_certs:
            configuration.load_verify_locations(args.ca_certs)
        if args.insecure:
            configuration.verify_mode = ssl.CERT_NONE
        if args.quic_log:
            configuration.quic_logger = QuicLogger()
        if args.secrets_log:
            configuration.secrets_log_file = open(args.secrets_log, "a")
        if args.session_ticket:
            try:
                with open(args.session_ticket, "rb") as fp:
                    configuration.session_ticket = pickle.load(fp)
            except FileNotFoundError:
                pass

        if uvloop is not None:
            uvloop.install()
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(
                run(
                    configuration=configuration,
                    url=args.url,
                    data=args.data,
                    parallel=args.parallel,
                    print_response=args.print_response,
                )
            )
        finally:
            if configuration.quic_logger is not None:
                with open(args.quic_log, "w") as logger_fp:
                    json.dump(configuration.quic_logger.to_dict(), logger_fp, indent=4)


def getuserinput():
    userInput = ""
    userinput = ""
    print("Start")
    while "pw1234" not in userInput:
        userInput = input("to start a connection type in password")
        userInput = userInput.lower()
        if "pw1234" not in userInput and "1234" not in userInput:
            print("password not valid: try again or type 'exit' to close window")
        if "exit" in userInput:
            print("Good bye")

    # while "exit" not in userinput:
    userChat = input("startChat")
    userChat = userChat.lower()
    transaction(userChat)


# Main program
getuserinput()
