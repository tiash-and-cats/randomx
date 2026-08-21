import io, os, sys, socket, threading, traceback

UNSUPPORTED_VERSION = (
    "HTTP/1.1 505 HTTP Version Not Supported\r\n"
    "Server: wsgiserver\r\n"
    "Connection: close\r\n"
    "Content-Type: text/plain; charset=utf-8\r\n"
    f"Content-Length: {len("HTTP Version Not Supported")}\r\n"
    "\r\n"
    "HTTP Version Not Supported"
).encode("latin1")

def serve(app, host="127.0.0.1", port=8080, use_threading=True):
    s = socket.socket()
    s.bind((host, port))
    s.listen(5)
    print(f"Serving WSGI app on {host}:{port}")

    def handle(conn):
        try:
            # Read request headers
            data = b""
            while True:
                chunk = conn.recv(256)
                if not chunk: break
                data += chunk
                if b"\r\n\r\n" in data: break

            parts = data.split(b"\r\n\r\n", 1)
            raw_headers, body_bytes = parts if len(parts) == 2 else (parts[0], b"")
            raw_headers = raw_headers.decode("latin1").split("\r\n")
            top = raw_headers.pop(0)
            headers = {}
            for line in raw_headers:
                if line:
                    k, v = line.split(":", 1)
                    k = k.lower().strip()
                    
                    if k in headers:
                        headers[k].append(v.strip())
                    else:
                        headers[k] = [v.strip()]

            # Handle body
            if "Content-Length" in headers:
                length = int(headers["Content-Length"])
                while len(body_bytes) < length:
                    chunk = conn.recv(length - len(body_bytes))
                    if not chunk: break
                    body_bytes += chunk

            method, path, http_version = top.split(" ", 2)
            
            if http_version not in {"HTTP/1.0", "HTTP/1.1"}:
                conn.sendall(UNSUPPORTED_VERSION)
                return

            # Build WSGI environ
            environ = {
                **os.environ,
                "REQUEST_METHOD": method,
                "SCRIPT_NAME": "",
                "PATH_INFO": path.split("?", 1)[0],
                "QUERY_STRING": path.split("?", 1)[1] if "?" in path else "",
                "SERVER_NAME": host,
                "SERVER_PORT": str(port),
                "SERVER_PROTOCOL": http_version,
                "wsgi.version": (1, 0),
                "wsgi.url_scheme": "http",
                "wsgi.input": io.BytesIO(body_bytes),
                "wsgi.errors": sys.stderr,
                "wsgi.multithread": use_threading,
                "wsgi.multiprocess": False,
                "wsgi.run_once": False,
            }
            for k, v in headers.items():
                environ[f"HTTP_{k.upper().replace('-', '_')}"] = ", ".join(v)
            if "Content-Type" in headers:
                environ["CONTENT_TYPE"] = headers["Content-Type"]
            if "Content-Length" in headers:
                environ["CONTENT_LENGTH"] = headers["Content-Length"]

            # Call WSGI app
            status_line = "200 OK"
            response_headers = []

            def start_response(status, hdrs, exc_info=None):
                nonlocal status_line, response_headers
                status_line = status
                response_headers = hdrs
                return lambda b: None

            try:
                itr = app(environ, start_response)
            except Exception as e:
                traceback.print_exception(e, file=sys.stderr)
                status_line = "500 Internal Server Error"
                response_headers = [("Content-Type", "text/plain; charset=utf-8")]
                itr = [b"An error has occurred."]

            response_headers.append(("Server", "wsgiserver"))
            response_headers.append(("Connection", "close"))

            # Build HTTP response
            code, reason = status_line.split(" ", 1)
            top_line = f"{http_version} {code} {reason}"
            header_lines = "\r\n".join([f"{k}: {v}" for k, v in response_headers])
            http_hdrs = f"{top_line}\r\n{header_lines}\r\n\r\n".encode("latin1")

            conn.sendall(http_hdrs)

            # Stream chunks
            for chunk in itr:
                conn.sendall(chunk)
                
            conn.close()

            print("request:", method, path, repr(status_line))
        except ConnectionResetError:
            print("connection interrupted")

    while True:
        try:
            conn, addr = s.accept()
            if use_threading:
                threading.Thread(target=handle, args=(conn,)).start()
            else:
                handle(conn)
        except KeyboardInterrupt:
            return