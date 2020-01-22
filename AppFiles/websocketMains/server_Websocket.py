import argparse
import asyncio
import importlib
import logging

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h0.connection import H0_ALPN, H0Connection
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.quic.configuration import QuicConfiguration

from serverClasses.websocketDIr.QuicLoggerCustom import QuicLoggerCustom
from serverClasses.websocketDIr.SessionTicketStore import SessionTicketStore


def transaction():
    print("password correct - ")
    print("run server")

    try:
        import uvloop
    except ImportError:
        uvloop = None

    if __name__ == "__main__":
        parser = argparse.ArgumentParser(description="QUIC server")
        print("if __name__ == __main_")
        parser.add_argument(
            "app",
            type=str,
            nargs="?",
            default="serverApp:app",
            help="the ASGI application as <module>:<attribute>",
        )
        parser.add_argument(
            "-c",
            "--certificate",
            type=str,
            required=True,
            help="load the TLS certificate from the specified file",
        )
        parser.add_argument(
            "--host",
            type=str,
            default="::",
            help="listen on the specified address (defaults to ::)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=4433,
            help="listen on the specified port (defaults to 4433)",
        )
        parser.add_argument(
            "-k",
            "--private-key",
            type=str,
            required=True,
            help="load the TLS private key from the specified file",
        )
        parser.add_argument(
            "-l",
            "--secrets-log",
            type=str,
            help="log secrets to a file, for use with Wireshark",
        )
        parser.add_argument(
            "-q", "--quic-log", type=str, help="log QUIC events to a file in QLOG format"
        )
        parser.add_argument(
            "-r",
            "--stateless-retry",
            action="store_true",
            help="send a stateless retry for new connections",
        )
        parser.add_argument(
            "-v", "--verbose", action="store_true", help="increase logging verbosity"
        )
        args = parser.parse_args()

        logging.basicConfig(
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            level=logging.DEBUG if args.verbose else logging.INFO,
        )

        # import ASGI application
        module_str, attr_str = args.app.split(":", maxsplit=1)
        print(attr_str)
        print(module_str)
        module = importlib.import_module(module_str)
        application = getattr(module, attr_str)

        # create QUIC logger
        if args.quic_log:
            quic_logger = QuicLoggerCustom(args.quic_log)
        else:
            quic_logger = None

        # open SSL log file
        if args.secrets_log:
            secrets_log_file = open(args.secrets_log, "a")
        else:
            secrets_log_file = None

        configuration = QuicConfiguration(
            alpn_protocols=H3_ALPN + H0_ALPN + ["siduck"],
            is_client=False,
            max_datagram_frame_size=65536,
            quic_logger=quic_logger,
            secrets_log_file=secrets_log_file,
        )

        # load SSL certificate and key
        configuration.load_cert_chain(args.certificate, args.private_key)

        ticket_store = SessionTicketStore()

        if uvloop is not None:
            uvloop.install()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            serve(
                args.host,
                args.port,
                configuration=configuration,
                session_ticket_fetcher=ticket_store.pop,
                session_ticket_handler=ticket_store.add,
                stateless_retry=args.stateless_retry,
            )
        )
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass


def getuserinput():

    userInput = "";
    print("Start")
    while "pw1234" not in userInput:
        userInput = input("to start a connection type in password")
        userInput = userInput.lower()
        if "pw1234" not in userInput and "1234" not in userInput:
            print("password not valid: try again or type 'exit' to close window")
        if "exit" in userInput:
            print("Good bye")
    transaction()

#Main program
getuserinput()