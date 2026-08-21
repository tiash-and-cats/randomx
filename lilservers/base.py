# base.py
import asyncio
import h11

def server_protocol(handle_http):
    class _Protocol(asyncio.Protocol):
        _handle_http_raw = handle_http
        
        def __init__(self):
            self.conn = h11.Connection(h11.SERVER)
            self.transport = None
            
            # Internal queues/futures to pass body data to the async task
            self._body_queue = asyncio.Queue()
            self._current_task = None

        def connection_made(self, transport):
            self.transport = transport

        def data_received(self, data):
            self.conn.receive_data(data)
            self.handle_events()

        def handle_events(self):
            while True:
                try:
                    event = self.conn.next_event()
                except h11.RemoteProtocolError:
                    self.send_simple_response(400, b"Bad Request")
                    self.close_connection()
                    return

                if event is h11.NEED_DATA or event is h11.PAUSED:
                    break

                if isinstance(event, h11.Request):
                    self._body_queue = asyncio.Queue()
                    self._current_task = asyncio.create_task(
                        self._handle_http_raw(event)
                    )
                
                elif isinstance(event, h11.Data):
                    self._body_queue.put_nowait(event.data)
                
                elif isinstance(event, h11.EndOfMessage):
                    # Signal to our read_body loop that no more chunks
                    # are coming
                    self._body_queue.put_nowait(None)
                    # Automatically schedule final socket cleanups when
                    # the task finishes
                    self._current_task.add_done_callback(
                        lambda _: self.finish_response()
                    )

        async def read_body(self):
            """
            Awaited by the user app to safely stream or aggregate the
            full body.
            """
            chunks = []
            while True:
                chunk = await self._body_queue.get()
                if chunk is None:  # EndOfMessage sentinel reached
                    break
                chunks.append(chunk)
            return b"".join(chunks)

        def finish_response(self):
            try:
                if self.conn.our_state not in (
                    h11.CLOSED, h11.SWITCHED_PROTOCOL
                ):
                    self.send_bytes(self.conn.send(h11.EndOfMessage()))
            except h11.ProtocolError:
                pass
            self.close_connection()

        def send_simple_response(self, status, message):
            try:
                headers = [
                    (b"content-length", str(len(message)).encode("ascii"))
                ]
                self.send_bytes(self.conn.send(
                    h11.Response(status_code=status, headers=headers)
                ))
                self.send_bytes(self.conn.send(h11.Data(data=message)))
                self.send_bytes(self.conn.send(h11.EndOfMessage()))
            except Exception:
                pass

        def send_bytes(self, data):
            if data and self.transport:
                self.transport.write(data)

        def close_connection(self):
            if self.conn.our_state is h11.CLOSED or self.conn.their_state is h11.CLOSED:
                if self.transport:
                    self.transport.close()
                    
    return _Protocol
#
@server_protocol
async def thing(self, request):
    # Prepare a simple plain text response
    body = b"Hello from lilservers.base.thing!"
    
    # Send the HTTP response headers
    headers = [
        (b"content-type", b"text/plain"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"connection", b"close"),
    ]
    response_event = h11.Response(status_code=200, headers=headers)
    self.send_bytes(self.conn.send(response_event))

    # Send the HTTP body data
    data_event = h11.Data(data=body)
    self.send_bytes(self.conn.send(data_event))
#
async def main(proto=thing, port=8080):
    loop = asyncio.get_running_loop()
    server = await loop.create_server(proto, host="127.0.0.1", port=port)
    async with server:
        print("Serving on http://localhost:8080/")
        await server.serve_forever()
#
if __name__ == "__main__":
    asyncio.run(main())