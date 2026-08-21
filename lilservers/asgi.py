import io
import os
import h11
import sys
import traceback
import asyncio
from .base import server_protocol, main
from .smolurl import parse_url

def make_protocol(app):
    @server_protocol
    async def asgi_callback_handler(self, request):
        try:
            method = request.method.decode("ascii")
            raw_target = request.target.decode("ascii")
            http_version = f"HTTP/{request.http_version.decode('ascii')}"
            parsed_url = parse_url("http://localhost" + raw_target)
            
            body_consumed = False
            
            scope = {
                "type": "http",
                "asgi": {
                    "version": "3.0",
                    "spec_version": "2.5"
                },
                "http_version": request.http_version.decode("ascii"),
                "method": method.upper(),
                "path": parsed_url.pathname,
                "query_string": (parsed_url.querystr or "").encode("ascii"),
                "headers": request.headers  # h11 already supplies (bytes, bytes)
            }
            
            async def receive():
                nonlocal body_consumed
                if body_consumed:
                    # ASGI specification requirement: signal EOF on subsequent calls
                    return {
                        "type": "http.request",
                        "body": b"",
                        "more_body": False
                    }
                
                body_consumed = True
                return {
                    "type": "http.request",
                    "body": await self.read_body(),
                    "more_body": False
                }
            
            async def send(msg):
                nonlocal body_consumed
                
                assert "type" in msg
                match msg["type"]:
                    case "http.response.start":
                        assert "status" in msg
                        
                        raw_headers = msg.get("headers", [])
                        headers = []
                        has_connection = False
                        
                        for k, v in raw_headers:
                            k_low = k.lower()
                            if k_low == b"connection":
                                has_connection = True
                            headers.append((k_low, v))
                        
                        if not has_connection:
                            headers.append((b"connection", b"close"))
                        
                        self.send_bytes(self.conn.send(h11.Response(
                            status_code=msg["status"], headers=headers
                        )))
                        
                    case "http.response.body":
                        body_consumed = True
                        body_chunk = msg.get("body", b"")
                        if body_chunk:
                            self.send_bytes(self.conn.send(
                                h11.Data(data=body_chunk)
                            ))
                        
                    case tp:
                        if tp.startswith("websocket."):
                            raise OSError("Oops, lilservers does not support "
                                          "WebSockets right now. Try again "
                                          "later.")
                        else:
                            raise OSError(f"Unknown msg type: {tp}")
             
            await app(scope, receive, send)
            
        except Exception as e:
            traceback.print_exception(e, file=sys.stderr)
            self.send_simple_response(500, b"Internal Server Error")
            
    return asgi_callback_handler
#
async def demo_app(scope, receive, send):
    if scope['type'] != 'http':
        return

    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [(b'content-type', b'text/plain; charset=utf-8')],
    })

    body = ['Hello, ASGI!\n\n-- Scope Details --\n']
    for key, value in sorted(scope.items()):
        body.append(f'{key}: {value}\n')

    await send({
        'type': 'http.response.body',
        'body': ''.join(body).encode('utf-8'),
    })
#
if __name__ == "__main__":
    asyncio.run(main(make_protocol(demo_app)))