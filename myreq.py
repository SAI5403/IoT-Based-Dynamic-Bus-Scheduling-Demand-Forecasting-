import usocket
try:
    import ussl as ssl
except ImportError:
    import ssl


class Response:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text

    def close(self):
        pass


def _request(method, url, data=None, headers={}):
    if url.startswith("https://"):
        url = url[8:]
        port = 443
        use_ssl = True
    elif url.startswith("http://"):
        url = url[7:]
        port = 80
        use_ssl = False
    else:
        raise ValueError("URL must start with http:// or https://")

    if "/" in url:
        host, path = url.split("/", 1)
        path = "/" + path
    else:
        host = url
        path = "/"

    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)

    addr = usocket.getaddrinfo(host, port)[0][-1]
    s = usocket.socket()
    s.settimeout(10)
    s.connect(addr)

    if use_ssl:
        s = ssl.wrap_socket(s, server_hostname=host)

    # ==================================
    # Build header lines (NO blank line yet)
    # ==================================
    header_lines = "Host: {}\r\n".format(host)
    header_lines += "ngrok-skip-browser-warning: true\r\n"
    header_lines += "Connection: close\r\n"

    # Caller-supplied headers
    for k, v in headers.items():
        header_lines += "{}: {}\r\n".format(k, v)

    # Body
    body = ""
    if data is not None:
        body = data
        # Content-Length must be inside headers, before the blank line
        header_lines += "Content-Length: {}\r\n".format(len(body))

    # Blank line separates headers from body
    request = "{} {} HTTP/1.0\r\n{}\r\n{}".format(
        method, path, header_lines, body
    )

    s.write(request.encode())

    raw = b""
    while True:
        chunk = s.read(1024)
        if not chunk:
            break
        raw += chunk
    s.close()

    if b"\r\n\r\n" in raw:
        headers_raw, resp_body = raw.split(b"\r\n\r\n", 1)
    else:
        headers_raw = raw
        resp_body = b""

    status_line = headers_raw.split(b"\r\n")[0]
    try:
        status_code = int(status_line.split(b" ")[1])
    except Exception:
        status_code = 500

    return Response(status_code, resp_body.decode().strip())


def get(url, headers={}):
    return _request("GET", url, headers=headers)


def post(url, data=None, headers={}):
    return _request("POST", url, data=data, headers=headers)