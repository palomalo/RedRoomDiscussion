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
    print(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            print("Received from " + message)
            # await websocket.send_text(message)
            # await websocket.send(message)

            #TODO: Login und Themenauswahl müssen vom Messaging
            # gesondert behandelt werden, weil messages an alle
            # aktive Clients weitergegeben werden.
            #if type(message) == str:
                #await websocket.send_json(results)

            for clients in list_of_clients:
                try:
                    await clients.send_text(message + " client")
                    if "get topics" in message:
                        db = Topics()
                        results = db.getAllTopics()
                        # await clients.send_text(websocket)
                        await clients.send_json(results)

                    if "get user" in message:
                        userDB = UserDB()
                        allUser = userDB.getAlluser()
                        # await clients.send_text(websocket)
                        await clients.send_json(allUser)

                    if "add topic" in message:
                        await websocket.send_text("add topic")
                        new_topic = await websocket.receive_json()
                        topic_db = Topics()
                        topic_db.insert_topic(new_topic[0], new_topic[1])

                except:
                    await clients.close()
                    list_of_clients.remove(clients)

    except WebSocketDisconnect:
        pass


app.mount("/httpbin", WsgiToAsgi(httpbin.app))

app.mount("/", StaticFiles(directory=os.path.join(ROOT, "../htdocs"), html=True))
