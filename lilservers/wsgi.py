import io
import os
import h11
import sys
import traceback
import asyncio
from .base import server_protocol, main

def make_protocol(app):
    @server_protocol
    async def wsgi_callback_handler(self, request):
        try:
            body_bytes = await self.read_body()
            
            method = request.method.decode("ascii")
            raw_target = request.target.decode("ascii")
            http_version = f"HTTP/{request.http_version.decode('ascii')}"
            path, _, query_string = raw_target.partition("?")

            environ = {
                **os.environ,
                "REQUEST_METHOD": method,
                "SCRIPT_NAME": "",
                "PATH_INFO": path,
                "QUERY_STRING": query_string,
                "SERVER_NAME": "localhost",
                "SERVER_PORT": "80",
                "SERVER_PROTOCOL": http_version,
                "wsgi.version": (1, 0),
                "wsgi.url_scheme": "http",
                "wsgi.input": io.BytesIO(body_bytes),
                "wsgi.errors": sys.stderr,
                "wsgi.multithread": True,
                "wsgi.multiprocess": False,
                "wsgi.run_once": False,
            }

            for key, val in request.headers:
                k_str = key.decode("ascii").upper().replace("-", "_")
                v_str = val.decode("latin1")
                if k_str == "CONTENT_TYPE":
                    environ["CONTENT_TYPE"] = v_str
                elif k_str == "CONTENT_LENGTH":
                    environ["CONTENT_LENGTH"] = v_str
                else:
                    environ[f"HTTP_{k_str}"] = v_str

            def run_wsgi():
                status_line = "200 OK"
                response_headers = []

                def start_response(status, hdrs, exc_info=None):
                    nonlocal status_line, response_headers
                    status_line = status
                    response_headers = hdrs
                    return lambda b: None

                try:
                    iterable = app(environ, start_response)
                    return status_line, response_headers, iterable
                except Exception as e:
                    traceback.print_exception(e, file=sys.stderr)
                    return "500 Internal Server Error", \
                           [("Content-Type", "text/plain")], \
                           [b"Internal Server Error"]

            loop = asyncio.get_running_loop()
            status_line, resp_headers, body_chunks = \
                await loop.run_in_executor(None, run_wsgi)

            try:
                status_code = int(status_line.split(" ", 1)[0])
            except (ValueError, IndexError):
                status_code = 500

            h11_headers = [
                (k.encode("ascii"), v.encode("latin1")) 
                for k, v in resp_headers
            ]
            h11_headers.append((b"server", b"lilservers"))
            h11_headers.append((b"connection", b"close"))

            self.send_bytes(self.conn.send(
                h11.Response(status_code=status_code, headers=h11_headers)
            ))
            for chunk in body_chunks:
                self.send_bytes(self.conn.send(h11.Data(data=chunk)))
                
            print("request completed:", method, raw_target, repr(status_line))
        except Exception as e:
            traceback.print_exception(e)
    
    return wsgi_callback_handler
#
if __name__ == "__main__":
    from wsgiref.simple_server import demo_app
    asyncio.run(main(make_protocol(demo_app)))