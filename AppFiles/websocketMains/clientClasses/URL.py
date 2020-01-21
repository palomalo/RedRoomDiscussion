from urllib.parse import urlparse

class URL:
    def __init__(self, url: str):
        parsed = urlparse(url)

        self.authority = parsed.netloc
        self.full_path = parsed.path
        if parsed.query:
            self.full_path += "?" + parsed.query
        self.scheme = parsed.scheme
        print("Method1 url")
        print(url)