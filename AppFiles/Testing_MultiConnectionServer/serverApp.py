#
# demo application for http3_server.py
#

import datetime
import os
import sqlite3
from urllib.parse import urlencode

import httpbin
from asgiref.wsgi import WsgiToAsgi
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.websockets import WebSocketDisconnect

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


list_of_clients = []

@app.websocket_route("/ws")
async def ws(websocket):
    """
    WebSocket echo endpoint.
    """

    #testing sqlite connestion
    #conn = sqlite3.connect('Database/topics.dp')
    #c = conn.cursor()
    #c.execute("SELECT * FROM topics ORDER BY ROWID ASC LIMIT 1")
    #entry = c.fetchone()
    #entry = entry[0]

    #entry ="haha"



    #print(ws.stream_Id)


    if "chat" in websocket.scope["subprotocols"]:
        subprotocol = "chat"
    else:
        subprotocol = None
    await websocket.accept(subprotocol=subprotocol)

    list_of_clients.append(websocket)
    print(websocket)

    #warte uach LOGIN daten
    # prüfe LOGIN = ? DB









    try:
        while True:


            message = await websocket.receive_text() #+ " (server echo)" #+ entry
            print("Received: " + message)
            #print(len(list_of_clients))

            for clients in list_of_clients:
                #try:
                #print("count")
                await clients.send_text(">" + message)
                #except:
                    #await clients.close()
                    #list_of_clients.remove(clients)

            #await websocket.send_text(message)
    except WebSocketDisconnect:
        pass


app.mount("/httpbin", WsgiToAsgi(httpbin.app))

app.mount("/", StaticFiles(directory=os.path.join(ROOT, "htdocs"), html=True))
