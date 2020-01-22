from AppFiles.websocketMains.clientClasses.URL import URL
from typing import Callable, Deque, Dict, List, Optional, Union, cast


class HttpRequest:
    def __init__(
            self, method: str, url: URL, content: bytes = b"", headers: Dict = {}
    ) -> None:
        self.content = content
        self.headers = headers
        self.method = method
        self.url = url
        print("Method2 url")
