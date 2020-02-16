# RedRoomDiscussionChannel

This is a student project at [University of Applied Sciences FH Campus Wien](https://www.fh-campuswien.ac.at/en/study-courses/technik-master/software-design-and-engineering.html) implementing IETF QUIC protocol according to the draft no. 24 with [aioquic](https://github.com/aiortc/aioquic).

## Prerequisites

Python 3.6 and OpenSSL on Linux: 
```
sudo apt-get install python3.6
sudo apt-get install libssl-dev
```
and the aioquic library with its dependancies:
```
$ pip install aiofiles 
$ pip install asgiref 
$ pip install httpbin 
$ pip install starlette 
$ pip install wsproto
$ pip install aioquic
```
## Use Case, Design and Project Progress
The use case, desing and step by step project progress are documented in [ProjectProgressDocs](https://github.com/palomalo/RedRoomDiscussion/tree/dev/ProjectProgressDocs)

##Testing the Websocket Handling and Simultaneous Messaging 
You can test the messaging system by running multi-connection server test- app:
```
$ python AppFiles/Testing_MultiConnectionServer/server_(multi-connect).py --certificate Keys/ssl_cert.pem --private-key Keys/ssl_key.pem
``` 
then running the asynchronous multi-threading client app 
```
$ python AppFiles/Testing_MultiConnectionServer/client_1_(asynchronous).py --print-response --ca-certs Keys/pycacert.pem wss://localhost:4433/ws
```
and finally running a faulty client with a blocked message queue for demostration
```
$ python AppFiles/Testing_MultiConnectionServer/client_2_(blocked msg queue).py --print-response --ca-certs Keys/pycacert.pem wss://localhost:4433/ws
``` 


## Licence
All rights reserved