#
# demo application for http3_server.py
#

import datetime
import os
import sqlite3
import json
from urllib.parse import urlencode

import httpbin
from asgiref.wsgi import WsgiToAsgi
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocketDisconnect

from AppFiles.websocketMains.DB.Topics import Topics
from AppFiles.websocketMains.DB.UserDB import UserDB

from tkinter import *
import os
from tkinter import messagebox
from AppFiles.manager.db_topics import Database

ROOT = os.path.dirname(__file__)
LOGS_PATH = os.path.join(ROOT, "htdocs", "logs")
QVIS_URL = "https://qvis.edm.uhasselt.be/"

templates = Jinja2Templates(directory=os.path.join(ROOT, "templates"))
app = Starlette()


@app.route("/")
async def homepage(request):
    """
    Simple homepage.
    """
    await request.send_push_promise("/style.css")
    return templates.TemplateResponse("index.html", {"request": request})


@app.route("/echo", methods=["POST"])
async def echo(request):
    """
    HTTP echo endpoint.
    """
    content = await request.body()
    media_type = request.headers.get("content-type")
    return Response(content, media_type=media_type)


@app.route("/logs/?")
async def logs(request):
    """
    Browsable list of QLOG files.
    """
    logs = []
    for name in os.listdir(LOGS_PATH):
        if name.endswith(".qlog"):
            s = os.stat(os.path.join(LOGS_PATH, name))
            file_url = "https://" + request.headers["host"] + "/logs/" + name
            logs.append(
                {
                    "date": datetime.datetime.utcfromtimestamp(s.st_mtime).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "file_url": file_url,
                    "name": name[:-5],
                    "qvis_url": QVIS_URL
                                + "?"
                                + urlencode({"file": file_url})
                                + "#/sequence",
                    "size": s.st_size,
                }
            )
    return templates.TemplateResponse(
        "logs.html",
        {
            "logs": sorted(logs, key=lambda x: x["date"], reverse=True),
            "request": request,
        },
    )


@app.route("/{size:int}")
def padding(request):
    """
    Dynamically generated data, maximum 50MB.
    """
    size = min(50000000, request.path_params["size"])
    return PlainTextResponse("Z" * size)


# *** Multi connection server ***
# Array to store socket references
# of all established connections
list_of_clients = []

creds = 'tempfile.temp'  # This just sets the variable creds to 'tempfile.temp'
db = Database('topics.db')


def populate_list(parts_list):
    parts_list.delete(0, END)
    for row in db.fetch():
        parts_list.insert(END, row)


def add_item(topic_name, topic_text):
    db.insert(topic_name, topic_text)
    # parts_list.delete(0, END)
    # parts_list.insert(END, (topic_name.get(), topic_text.get()))
    # clear_text()
    # populate_list()


'''
def select_item(event):
    try:
        global selected_item

        index = parts_list.curselection()[0]
        selected_item = parts_list.get(index)
        chat_btn.grid()

        part_entry.delete(0, END)
        part_entry.insert(END, selected_item[1])
        customer_entry.delete(0, END)
        customer_entry.insert(END, selected_item[2])

    except IndexError:
        pass


def remove_item():
    db.remove(selected_item[0])
    clear_text()
    populate_list()


def update_item():
    db.update(selected_item[0], topic_name.get(), topic_text.get())
    populate_list()


def send_msg(chat_msg):
    # print(topic_name.get())
    print(chat_msg.get())


def start_chat():
    app.destroy()
    chat = Tk()
    chat.title(selected_item)
    chat.geometry('700x450')

    chat_msg = StringVar()
    chat_label = Label(chat, text='chat Msg', font=('bold', 14), pady=20)
    chat_label.grid(row=0, column=0, sticky=W)
    chat_entry = Entry(chat, textvariable=chat_msg)
    chat_entry.grid(row=0, column=1)

    chat_btn_send = Button(chat, text='send Msg', width=12, command=lambda: send_msg(chat_msg))
    chat_btn_send.grid(row=0, column=2, pady=20)

    # Start program
    chat.mainloop()


def clear_text():
    part_entry.delete(0, END)
    customer_entry.delete(0, END)'''


@app.websocket_route("/ws")
async def ws(websocket):
    """
    WebSocket echo endpoint.
    """

    if "chat" in websocket.scope["subprotocols"]:
        subprotocol = "chat"
    else:
        subprotocol = None
    await websocket.accept(subprotocol=subprotocol)

    # *** Multi connection server ***
    # add to array of socket references
    list_of_clients.append(websocket)
    # json = websocket.receive_json()

    print(websocket)

    try:
        while True:
            message = await websocket.receive_json()
            jsonM = json.loads(message)
            print("Received from " + message)
            for key, value in jsonM.items():
                print(key, value)

            print(jsonM["action"])
            # await websocket.send_text(message)
            # await websocket.send(message)

            for clients in list_of_clients:
                try:
                    if jsonM["action"] == "add_item":
                        # await clients.send_text("ssssssssaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
                        db.insert(jsonM["topic_name"], jsonM["topic_text"])
                        await clients.send_text("inserted_item")

                    if jsonM["action"] == "populate_list":
                        await clients.send_text("topic list update")

                    #await clients.send_text(message + " client")

                except:
                    await clients.close()
                    list_of_clients.remove(clients)

    except WebSocketDisconnect:
        pass


'''
def start_chat():
    app.destroy()
    chat = Tk()
    chat.title(selected_item)
    chat.geometry('700x450')

    chatMsg = StringVar()
    chat_label = Label(chat, text='chat Msg', font=('bold', 14), pady=20)
    chat_label.grid(row=0, column=0, sticky=W)
    chat_entry = Entry(chat, textvariable=chatMsg)
    chat_entry.grid(row=0, column=1)

    chat_btn_send = Button(chat, text='send Msg', width=12, command=send_msg)
    chat_btn_send.grid(row=0, column=2, pady=20)

    # Start program
    chat.mainloop()'''

app.mount("/httpbin", WsgiToAsgi(httpbin.app))

app.mount("/", StaticFiles(directory=os.path.join(ROOT, "../htdocs"), html=True))
