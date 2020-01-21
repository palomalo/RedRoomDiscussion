from typing import Callable, Deque, Dict, List, Optional, Union, cast

from aioquic.h0.connection import H0_ALPN, H0Connection
from aioquic.h3.connection import H3_ALPN, H3Connection


def connection():
    return HttpConnection


class HttpConnection(object):
    HttpConnection = Union[H0Connection, H3Connection]
