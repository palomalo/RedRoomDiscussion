import argparse
import asyncio
import json
import logging
import pickle
import ssl
from tkinter import *
import queue
import time
import threading
import time
from tkinter import messagebox
from typing import Callable, Deque, Dict, List, Optional, Union, cast
from urllib.parse import urlparse
from tkinter import *
import os
from threading import Thread

import aioquic
from aioquic.asyncio.client import connect
from aioquic.h0.connection import H0_ALPN, H0Connection
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import (
    DataReceived,
    HeadersReceived,
)
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.logger import QuicLogger
from AppFiles.websocketMains.clientClasses.HttpClient import HttpClient
import json
from tkinter import *
import os
from AppFiles.manager.db_topics import Database

try:
    import uvloop
except ImportError:
    uvloop = None

logger = logging.getLogger("client")

HttpConnection = Union[H0Connection, H3Connection]

USER_AGENT = "aioquic/" + aioquic.__version__

creds = 'tempfile.temp'  # This just sets the variable creds to 'tempfile.temp'
db = Database('topics.db')


# URLLL = URL("wss://localhost:4433/ws")


# websocket = WebSocket() 3 required arguments


def getUserAgent():
    return USER_AGENT


def transaction(topic_name, topic_text, parts_list):
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

                # print("Hint: To send a message type and press enter.")

                # ******************************
                # *** ASYNCHRONOUS THREADING ***
                def start_loop(loop):
                    asyncio.set_event_loop(loop)
                    loop.run_forever()

                new_loop = asyncio.new_event_loop()
                t = Thread(target=start_loop, args=(new_loop,))
                t.start()

                async def read_user():
                    # while True:
                    message = add_item(topic_name, topic_text)
                    # message = add_item()
                    await ws.send(message)
                    # CheckLogin()

                asyncio.run_coroutine_threadsafe(read_user(), new_loop)

                # *** STAYS IN MAIN LOOP ***
                while True:
                    messageRec = await ws.recv()
                    print("< " + messageRec)
                    if messageRec == "inserted_item":
                        print("client update list")
                        root = Tk()
                        app = App(root)
                        app.update_text()
                        root.mainloop()

                # *** ASYNCHRONOUS THREADING ***
                # ******************************'''

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
    if os.path.isfile(creds):
        Login()
    else:  # This if else statement checks to see if the file exists. If it does it will go to Login, if not it will go to Signup :)
        Signup()


def Signup():  # This is the signup definition,
    global pwordE  # These globals just make the variables global to the entire script, meaning any definition can use them
    global nameE
    global roots

    roots = Tk()  # This creates the window, just a blank one.
    roots.title('Signup')  # This renames the title of said window to 'signup'
    intruction = Label(roots,
                       text='Please Enter new Credidentials\n')  # This puts a label, so just a piece of text saying 'please enter blah'
    intruction.grid(row=0, column=0,
                    sticky=E)  # This just puts it in the window, on row 0, col 0. If you want to learn more look up a tkinter tutorial :)

    nameL = Label(roots,
                  text='New Username: ')  # This just does the same as above, instead with the text new username.
    pwordL = Label(roots, text='New Password: ')  # ^^
    nameL.grid(row=1, column=0,
               sticky=W)  # Same thing as the instruction var just on different rows. :) Tkinter is like that.
    pwordL.grid(row=2, column=0, sticky=W)  # ^^

    nameE = Entry(roots)  # This now puts a text box waiting for input.
    pwordE = Entry(roots,
                   show='*')  # Same as above, yet 'show="*"' What this does is replace the text with *, like a password box :D
    nameE.grid(row=1, column=1)  # You know what this does now :D
    pwordE.grid(row=2, column=1)  # ^^

    signupButton = Button(roots, text='Signup',
                          command=FSSignup)  # This creates the button with the text 'signup', when you click it, the command 'fssignup' will run. which is the def
    signupButton.grid(columnspan=2, sticky=W)
    roots.mainloop()  # This just makes the window keep open, we will destroy it soon


def FSSignup():
    with open(creds, 'w') as f:  # Creates a document using the variable we made at the top.
        f.write(
            nameE.get())  # nameE is the variable we were storing the input to. Tkinter makes us use .get() to get the actual string.
        f.write('\n')  # Splits the line so both variables are on different lines.
        f.write(pwordE.get())  # Same as nameE just with pword var
        f.close()  # Closes the file

    roots.destroy()  # This will destroy the signup window. :)
    Login()  # This will move us onto the login definition :D


def Login():
    global nameEL
    global pwordEL  # More globals :D
    global rootA
    global chatMsg1

    rootA = Tk()  # This now makes a new window.
    rootA.title('Login')  # This makes the window title 'login'
    rootA.geometry('700x350')
    intruction = Label(rootA, text='Please Login\n')  # More labels to tell us what they do
    intruction.grid(sticky=E)  # Blahdy Blah

    nameL = Label(rootA, text='Username: ')  # More labels
    pwordL = Label(rootA, text='Password: ')  # ^
    nameL.grid(row=1, sticky=W)
    pwordL.grid(row=2, sticky=W)

    nameEL = Entry(rootA)  # The entry input
    pwordEL = Entry(rootA, show='*')
    nameEL.grid(row=1, column=1)
    pwordEL.grid(row=2, column=1)

    loginB = Button(rootA, text='Login',
                    command=CheckLogin)  # This makes the login button, which will go to the CheckLogin def.
    loginB.grid(columnspan=2, sticky=W)

    rmuser = Button(rootA, text='Delete User', fg='red',
                    command=DelUser)  # This makes the deluser button. blah go to the deluser def.
    rmuser.grid(columnspan=2, sticky=W)

    rootA.mainloop()


def CheckLogin():
    with open(creds) as f:
        data = f.readlines()  # This takes the entire document we put the info into and puts it into the data variable
        uname = data[0].rstrip()  # Data[0], 0 is the first line, 1 is the second and so on.
        pword = data[1].rstrip()  # Using .rstrip() will remove the \n (new line) word from before when we input it

    if nameEL.get() == uname and pwordEL.get() == pword:  # Checks to see if you entered the correct data.

        rootA.destroy()
        root = Tk()
        app = App(root)
        root.mainloop()
        # root.destroy()  # optional; see description below


def bluetooth_loop(thread_queue=None, text_input=""):
    time.sleep(15)
    thread_queue.put(text_input)


class App:
    def __init__(self, master):

        self.thread_queue = queue.Queue()
        self.new_thread = threading.Thread(
            target=bluetooth_loop)
        frame = Frame(master)
        frame.pack()
        self.root = frame

        '''self.quit_button = Button(frame, text="QUIT", fg="red", command=frame.quit)
        self.quit_button.pack(side=LEFT)

        self.update_btn = Button(frame, text="Update", command=self.update_text)
        self.update_btn.pack(side=LEFT)
        self.text_label = Label(frame)
        self.text_label.config(text='No message')
        self.text_label.pack(side=RIGHT)
        self.text_input = Entry(frame, width=40)
        self.text_input.pack(side=RIGHT)'''

        # topic name
        self.topic_name = StringVar()

        self.part_label = Label(frame, text='topic Name', font=('bold', 14), pady=20)
        self.part_label.grid(row=0, column=0, sticky=W)
        self.part_entry = Entry(frame, textvariable=self.topic_name)
        self.part_entry.grid(row=0, column=1)
        # topic text
        self.topic_text = StringVar()
        self.customer_label = Label(frame, text='topic text', font=('bold', 14))
        self.customer_label.grid(row=0, column=2, sticky=W)
        self.customer_entry = Entry(frame, textvariable=self.topic_text)
        self.customer_entry.grid(row=0, column=3)

        # Parts List (Listbox)
        self.parts_list = Listbox(frame, height=8, width=50, border=0)
        self.parts_list.grid(row=3, column=0, columnspan=3, rowspan=6, pady=20, padx=20)
        # Create scrollbar
        self.scrollbar = Scrollbar(frame)
        self.scrollbar.grid(row=3, column=3)
        # Set scroll to listbox
        self.parts_list.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.configure(command=self.parts_list.yview)
        # Bind select
        # parts_list.bind('<<ListboxSelect>>', select_item)

        # Buttons
        self.add_btn = Button(frame, text='Add topic', width=12, command=lambda: self.transact())
        self.add_btn.grid(row=2, column=0, pady=20)

        ''' remove_btn = Button(app, text='Remove topic', width=12, command=remove_item)
        remove_btn.grid(row=2, column=1)

        update_btn = Button(app, text='Update topic', width=12, command=update_item)
        update_btn.grid(row=2, column=2)

        clear_btn = Button(app, text='Clear topic input', width=12, command=clear_text)
        clear_btn.grid(row=2, column=3)

        chat_btn = Button(app, text='start Chat', width=12, command=start_chat)
        chat_btn.grid(row=2, column=4)
        chat_btn.grid_remove()'''

        # frame.title('Topic Manager')
        # frame.geometry('700x550')

        # Populate data
        self.update_text()
        # transaction()
        # Start program
        # app.mainloop()

    '''else:
        r = Tk()
        r.title('Login Failed:')
        r.geometry('450x450')
        rlbl = Label(r, text='\n[!] Invalid Login')
        rlbl.pack()
        r.mainloop()'''

    def update_text(self):
        self.parts_list.delete(0, END)
        for row in db.fetch():
            self.parts_list.insert(END, row)

        #self.text_label.config(text='Running loop')
        self.new_thread.start()
        self.root.after(100, self.listen_for_result)

    def listen_for_result(self):
        '''
        Check if there is something in the queue
        '''
        print("listen for result")
        try:
            res = self.thread_queue.get(0)
            print(res)
            #self.text_label.config(text=res)
        except queue.Empty:
            self.root.after(100, self.listen_for_result)

    def transact(self):
        transaction(self.topic_name.get(), self.topic_text.get(), self.parts_list)


def DelUser():
    os.remove(creds)  # Removes the file
    rootA.destroy()  # Destroys the login window
    Signup()  # And goes back to the start!


def add_item(topic_name, topic_text):
    x = '{ "action":"add_item", "topic_name": "' + topic_name + '", "topic_text":"' + topic_text + '"}'
    return json.dumps(x)


# Main program
getuserinput()
