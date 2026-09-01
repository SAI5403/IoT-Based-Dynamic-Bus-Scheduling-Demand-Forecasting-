import usocket
import ussl

class Response:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text

    def close(self):
        pass

def get(url):
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
        s = ussl.wrap_socket(s, server_hostname=host)

    request = "GET {} HTTP/1.0\r\nHost: {}\r\nngrok-skip-browser-warning: true\r\nConnection: close\r\n\r\n".format(path, host)
    s.write(request.encode())

    raw = b""
    while True:
        chunk = s.read(1024)
        if not chunk:
            break
        raw += chunk
    s.close()

    if b"\r\n\r\n" in raw:
        headers, body = raw.split(b"\r\n\r\n", 1)
    else:
        headers = raw
        body = b""

    status_line = headers.split(b"\r\n")[0]
    try:
        status_code = int(status_line.split(b" ")[1])
    except:
        status_code = 500

    return Response(status_code, body.decode().strip())