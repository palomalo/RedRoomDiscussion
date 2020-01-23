import argparse
import asyncio
import json
import logging
import pickle
import ssl
import sys
from sys import stdin
import time
import os
from collections import deque
from typing import Callable, Deque, Dict, List, Optional, Union, cast
from urllib.parse import urlparse

from threading import Thread
import PySimpleGUI as sg
import time

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
# outside server test params: --print-response https://cloudflare-quic.com/
# opening a websocket: --print-response --ca-certs Keys/pycacert.pem wss://localhost:4433/ws


try:
    import uvloop
except ImportError:
    uvloop = None

logger = logging.getLogger("client")

HttpConnection = Union[H0Connection, H3Connection]

USER_AGENT = "aioquic/" + aioquic.__version__


class URL:
    def __init__(self, url: str):
        parsed = urlparse(url)

        self.authority = parsed.netloc
        self.full_path = parsed.path
        if parsed.query:
            self.full_path += "?" + parsed.query
        self.scheme = parsed.scheme


class HttpRequest:
    def __init__(
            self, method: str, url: URL, content: bytes = b"", headers: Dict = {}
    ) -> None:
        self.content = content
        self.headers = headers
        self.method = method
        self.url = url


class WebSocket:
    def __init__(
            self, http: HttpConnection, stream_id: int, transmit: Callable[[], None]
    ) -> None:
        self.http = http
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.stream_id = stream_id
        self.subprotocol: Optional[str] = None
        self.transmit = transmit
        self.websocket = wsproto.Connection(wsproto.ConnectionType.CLIENT)

    async def close(self, code=1000, reason="") -> None:
        """
        Perform the closing handshake.
        """
        data = self.websocket.send(
            wsproto.events.CloseConnection(code=code, reason=reason)
        )
        self.http.send_data(stream_id=self.stream_id, data=data, end_stream=True)
        self.transmit()

    async def recv(self) -> str:
        """
        Receive the next message.
        """
        return await self.queue.get()

    async def send(self, message: str):
        """
        Send a message.
        """
        assert isinstance(message, str)

        data = self.websocket.send(wsproto.events.TextMessage(data=message))
        self.http.send_data(stream_id=self.stream_id, data=data, end_stream=False)
        self.transmit()

    def http_event_received(self, event: H3Event):
        if isinstance(event, HeadersReceived):
            for header, value in event.headers:
                if header == b"sec-websocket-protocol":
                    self.subprotocol = value.decode()
        elif isinstance(event, DataReceived):
            self.websocket.receive_data(event.data)

        for ws_event in self.websocket.events():
            self.websocket_event_received(ws_event)

    def websocket_event_received(self, event: wsproto.events.Event) -> None:
        if isinstance(event, wsproto.events.TextMessage):
            self.queue.put_nowait(event.data)


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
            HttpRequest(method="POST", url=URL(url), content=data, headers=headers)
        )

    async def websocket(self, url: str, subprotocols: List[str] = []) -> WebSocket:
        """
        Open a WebSocket.
        """
        request = HttpRequest(method="CONNECT", url=URL(url))
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
        #  pass event to the HTTP layer
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
    print(ticket)
    if args.session_ticket:
        with open(args.session_ticket, "wb") as fp:
            pickle.dump(ticket, fp)


async def threaded_GUI(ws):
    sg.theme('DarkAmber')  # Add a touch of color
    # All the stuff inside your window.
    layout = [[sg.Text('Some text on Row 1')],
              [sg.Text('Enter something on Row 2'), sg.InputText()],
              [sg.Button('Ok'), sg.Button('Cancel')]]

    # Create the Window
    window = sg.Window('Window Title', layout)
    # Event Loop to process "events" and get the "values" of the inputs
    while True:
        event, values = window.read()
        if event in (None, 'Cancel'):  # if user closes window or clicks cancel
            break
        print('GUI ', values)
        print("my value")
        print(values[0])

        # receive command for specific action
        await ws.send(values[0])

    message = await ws.receive_text()
    if "add topic" in message:
        print("add topic received")
        await add_topic(ws)
        window.close()

    await ws.send(message)

    window.close()


async def add_topic(ws):
    sg.theme('DarkAmber')  # Add a touch of color
    # All the stuff inside your window.
    layout = [[sg.Text('Add topic')],
              [sg.Text('Enter topic name'), sg.InputText()],
              [sg.Text('Enter text'), sg.InputText()],
              [sg.Button('Ok'), sg.Button('Cancel')]]

    # Create the Window
    window = sg.Window('Add topic', layout)
    # Event Loop to process "events" and get the "values" of the inputs
    while True:
        event, values = window.read()
        if event in (None, 'Cancel'):  # if user closes window or clicks cancel
            break
        print('GUI ', values)
        print("my value")
        print(values[0])

        # receive command for specific action
        await ws.send(values)

    message = await ws.receive_text()
    await ws.send(message)

    window.close()


async def getUserGUI(ws):
    sg.theme('DarkAmber')  # Add a touch of color
    # All the stuff inside your window.
    layout = [[sg.Text('user')],
              [sg.Text('Enter something on Row 2'), sg.InputText()],
              [sg.Button('Ok'), sg.Button('Cancel')]]

    # Create the Window
    window = sg.Window('Window Title', layout)
    # Event Loop to process "events" and get the "values" of the inputs
    while True:
        event, values = window.read()
        if event in (None, 'Cancel'):  # if user closes window or clicks cancel
            break
        print('GUI ', values)
        print("my value")
        print(values[0])

        if "get user" in values:
            await ws.send(values[0])

    message = await ws.receive_text()
    if "get user" in message:
        await ws.send(message)

    window.close()

async def send_message(ws, message):
    await ws.send(message)


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

            # print(ws.stream_id)

            # os.system('clear')
            # send some messages and receive reply
            # while input("Type your message: ") != "exit":

            def start_loop(loop):
                asyncio.set_event_loop(loop)
                loop.run_forever()

            new_loop = asyncio.new_event_loop()
            t = Thread(target=start_loop, args=(new_loop,))
            t.start()

            new_loop2 = asyncio.new_event_loop()
            t2 = Thread(target=start_loop, args=(new_loop2,))
            t2.start()

            def more_work(x):
                print("More work %s" % x)
                time.sleep(x)
                print("Finished more work %s" % x)

            async def read_server():
                # ws = await client.websocket(url, subprotocols=["chat", "superchat"])
                while True:
                    messageRec = await ws.recv()
                    print("< " + messageRec)

            async def read_user():
                # ws = await client.websocket(url, subprotocols=["chat", "superchat"])
                while True:
                    print("listening to user")
                    message = stdin.readline()
                    await ws.send(message)
                    print("I sent: " + message)

            # new_loop.call_soon_threadsafe(read_server())
            # new_loop2.call_soon_threadsafe(read_user())

            # asyncio.run_coroutine_threadsafe(read_server(), new_loop)
            asyncio.run_coroutine_threadsafe(threaded_GUI(ws), new_loop2)

            while True:
                messageRec = await ws.recv()
                print("< " + messageRec)

            # futures = [...]
            # loop = asyncio.get_event_loop()
            # loop.run_until_complete(asyncio.wait(futures))
            # loop.run_forever(read_server(ws))
            # loop.run_until_complete(read_server(ws))

            # tasks = [asyncio.ensure_future(read_server(ws)),
            #         asyncio.ensure_future(read_user(ws))]

            # loop.run_until_complete(asyncio.gather(*tasks))

            # while True:
            # '.run(read_server(ws))

            # message = stdin.readline()
            # if message == "":
            #    continue
            # else:
            #    await ws.send(message)

            # messageRec = await ws.recv()
            # if messageRec != "":
            #    print("< " + messageRec)
            # message = input("Type your message: ")
            # await ws.send(message)
            # messageRec = await ws.recv()
            # task = [print("< " + messageRec)]
            # await asyncio.wait(task)
            # print("< " + messageRec)
            # await ws.close()
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
