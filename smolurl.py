"""
Tiny module with which you can:
    - send http requests
    - parse URLs
    
smolurl follows redirects; you can change the redirect limit by changing 
smolurl.REDIR_LIMIT (defaults to 5).

smolurl supports HTTP/1.0 with SSL/TLS.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections.abc import MutableMapping
from abc import ABC, abstractmethod
from compression import gzip, zstd, zlib
from http import HTTPStatus
import io
import os
import ssl
import sys
import http
import socket
import traceback
import threading
import posixpath
import json
import re

url_regex = re.compile(r"^(?P<protocol>[a-zA-Z][a-zA-Z0-9+.-]*)(?::\/\/)"
                       r"(?P<hostname>[a-zA-Z0-9.-]+|\[[0-9a-fA-F:.]+\])"
                       r"(?::(?P<port>[0-9]+))?(?:(?P<path>\/[^?\n]*)(?:(?:\?)"
                       r"(?P<query>[^#\n]*)?)?(?:(?:\#)(?P<frag>.*)?)?)?$")

content_type_regex = re.compile(r"^(?P<type>[A-Za-z0-9.+-]+\/[A-Za-z0-9.+-]+)"
                                r"(?:;\s?charset=(?P<charset>[A-Za-z0-9._-]+))"
                                r"?$")

REDIR_LIMIT = 5

def _deflate(data):
    try:
        return zlib.decompress(data)
    except zlib.error:
        return zlib.decompress(data, -15)

ACCEPT_ENCODINGS = {
    "gzip": gzip.decompress,
    "deflate": _deflate,
    "zstd": zstd.decompress,
}

del _deflate

try:
    import brotli
    ACCEPT_ENCODINGS["br"] = brotli.decompress
except ModuleNotFoundError:
    pass

# ========= This section of code has been modified from webob.multidict
# Original copyright:
# (c) 2005 Ian Bicking and contributors; written for Paste
# (http://pythonpaste.org) Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php

def _hide_passwd(items):
    for k, v in items:
        if ('password' in k
            or 'passwd' in k
            or 'pwd' in k
        ):
            yield k, '******'
        else:
            yield k, v

class Headers(MutableMapping):
    """
    A specialized dictionary for storing request/response headers.
    Each key can have multiple values and keys are accessed
    case-insensitively.
    """

    def __init__(self, *args, **kw):
        if len(args) > 1:
            raise TypeError("Headers can only be initialized with one "
                            "positional argument")
        if args:
            if hasattr(args[0], 'iteritems'):
                items = list(args[0].iteritems())
            elif hasattr(args[0], 'items'):
                items = list(args[0].items())
            else:
                items = list(args[0])
            self._items = items
        else:
            self._items = []
        if kw:
            self._items.extend(kw.items())

    @classmethod
    def view_list(cls, lst):
        """
        Create a dict that is a view on the given list
        """
        if not isinstance(lst, list):
            raise TypeError(
                "%s.view_list(obj) takes only actual list objects, not %r"
                % (cls.__name__, lst))
        obj = cls()
        obj._items = lst
        return obj

    def __getitem__(self, key):
        for k, v in reversed(self._items):
            if k.lower() == key.lower():
                return v
        raise KeyError(key)

    def __setitem__(self, key, value):
        try:
            del self[key]
        except KeyError:
            pass
        self._items.append((key, value))

    def add(self, key, value):
        """
        Add the key and value, not overwriting any previous value.
        """
        self._items.append((key, value))

    def getall(self, key):
        """
        Return a list of all values matching the key (may be an empty list)
        """
        return [v for k, v in self._items if k.lower() == key.lower()]

    def getone(self, key):
        """
        Get one value matching the key, raising a KeyError if multiple
        values were found.
        """
        v = self.getall(key)
        if not v:
            raise KeyError('Key not found: %r' % key)
        if len(v) > 1:
            raise KeyError('Multiple values match %r: %r' % (key, v))
        return v[0]

    def mixed(self):
        """
        Returns a dictionary where the values are either single
        values, or a list of values when a key/value appears more than
        once in this dictionary.  This is similar to the kind of
        dictionary often used to represent the variables in a web
        request.
        """
        result = {}
        multi = {}
        for key, value in self.items():
            if key in result:
                # We do this to not clobber any lists that are
                # *actual* values in this dictionary:
                if key in multi:
                    result[key].append(value)
                else:
                    result[key] = [result[key], value]
                    multi[key] = None
            else:
                result[key] = value
        return result

    def dict_of_lists(self):
        """
        Returns a dictionary where each key is associated with a list of values.
        """
        r = {}
        for key, val in self.items():
            r.setdefault(key, []).append(val)
        return r

    def __delitem__(self, key):
        items = self._items
        found = False
        for i in range(len(items)-1, -1, -1):
            if items[i][0].lower() == key.lower():
                del items[i]
                found = True
        if not found:
            raise KeyError(key)

    def __contains__(self, key):
        for k, v in self._items:
            if k.lower() == key.lower():
                return True
        return False

    has_key = __contains__

    def clear(self):
        del self._items[:]

    def copy(self):
        return self.__class__(self)

    def setdefault(self, key, default=None):
        for k, v in self._items:
            if key == k:
                return v
        self._items.append((key, default))
        return default

    def pop(self, key, *args):
        if len(args) > 1:
            raise TypeError("pop expected at most 2 arguments, got %s"
                             % repr(1 + len(args)))
        for i in range(len(self._items)):
            if self._items[i][0] == key:
                v = self._items[i][1]
                del self._items[i]
                return v
        if args:
            return args[0]
        else:
            raise KeyError(key)

    def popitem(self):
        return self._items.pop()

    def extend(self, other=None, **kwargs):
        if other is None:
            pass
        elif hasattr(other, 'items'):
            self._items.extend(other.items())
        elif hasattr(other, 'keys'):
            for k in other.keys():
                self._items.append((k, other[k]))
        else:
            for k, v in other:
                self._items.append((k, v))
        if kwargs:
            self.update(kwargs)

    def __repr__(self):
        items = map('(%r, %r)'.__mod__, _hide_passwd(self.items()))
        return '%s([%s])' % (self.__class__.__name__, ', '.join(items))

    def __len__(self):
        return len(self._items)

    ##
    ## All the iteration:
    ##

    def iterkeys(self):
        for k, v in self._items:
            yield k

    keys = iterkeys

    __iter__ = iterkeys

    def iteritems(self):
        return iter(self._items)

    items = iteritems

    def itervalues(self):
        for k, v in self._items:
            yield v

    values = itervalues

# ========= End of modified webob.multidict code ======================

@dataclass
class Request:
    """A dataclass representing a request."""
    url: str
    method: str = "GET"
    headers: dict = field(default_factory=dict)
    data: str = ""
    
@dataclass(frozen=True)
class Response:
    """A dataclass representing a response."""
    status: int
    reason: str
    headers: Headers
    body: bytes
    url: str | None = None

    @property
    def ok(self) -> bool:
        return self.status < 400

    def unwrap(self):
        if not self.ok:
            status_info = http.HTTPStatus(self.status)
            raise ValueError(f"{self.status} {status_info.phrase}: {
                             status_info.description}")
        
        return self

    def expect(self, msg):
        if not self.ok:
            raise ValueError(f"{msg} ({self.status} {
                             http.HTTPStatus(self.status).phrase})")
        return self

    def decmp(self):
        text = self.body
        
        if "Content-Encoding" in self.headers:
            encs = map(str.strip, self.headers["Content-Encoding"].split(","))
            
            for enc in encs:
                if enc in ACCEPT_ENCODINGS:
                    text = ACCEPT_ENCODINGS[enc](text)
                else:
                    if enc == "br":
                        raise ValueError("Can not decode 'br' encoding because"
                                         " the brotli module was not installed"
                                         ". Please install it to fix the issue"
                                         ".")
                    raise ValueError(f"Unknown encoding: {enc}")
        
        return text
    
    def text(self):
        text = self.decmp()
        
        charset = None
        
        if "Content-Type" in self.headers:
            match = content_type_regex.match(self.headers["Content-Type"])
            if match and match["charset"]:
                charset = match["charset"]
        
        text = text.decode(charset or "latin1", errors="replace")
        
        return text

@dataclass(frozen=True)
class ParsedURL:
    """A dataclass representing a parsed URL."""
    protocol: str
    hostname: str
    port: int | None
    pathname: str | None
    querystr: str | None
    fragment: str | None
    
    def replace(self, **kwargs) -> "ParsedURL":
        """Return a copy of this ParsedURL with some fields replaced."""
        fields = {
            "protocol": self.protocol,
            "hostname": self.hostname,
            "port": self.port,
            "pathname": self.pathname,
            "querystr": self.querystr,
            "fragment": self.fragment,
        }
        fields.update(kwargs)
        return ParsedURL(**fields)

class Processor(ABC):
    """
    A Processor is a class that processes the Response before returning it 
    to the end user.
    """
    
    @abstractmethod
    def process(self, response: Response):
        pass

class CookieJar(Processor):
    """
    A Processor that implements a basic cookie jar.
    """
    def __init__(self):
        self.cookies = {}
        
    def add_cookie(self, key: str, value: str, domain: str, 
                   path: str, *, expires: datetime | None = None):
        """Adds a cookie."""
        x = self.cookies.setdefault(domain, {}).setdefault(path, [])
        x[:] = [c for c in x if not c["key"] == key]
        x.append({
            "key": key,
            "value": value,
            "domain": domain,
            "path": path,
            "expires": expires,
        })
        
    def parse_Set_Cookie(self, Set_Cookie: str, parsed_url: ParsedURL):
        """Parses a Set-Cookie header."""
        parts = [p.strip() for p in Set_Cookie.split(";")]
        key, value = parts[0].split("=", 1)
        options = [p.split("=", 1) if "=" in p else (p, None) for p in parts[1:]]
        path = parsed_url.pathname
        domain = parsed_url.hostname
        expires = None
        for option, value in options:
            match option:
                case "Path":
                    path = value
                case "Domain":
                    domain = value
                case "Expires":
                    try:
                        expires = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S GMT")
                    except:
                        expires = None
                case "Max-Age":
                    try:
                        expires = datetime.now() + timedelta(seconds=int(value))
                    except:
                        expires = None
        self.add_cookie(key, value, domain=domain, path=path, expires=expires)
    
    def get_Cookie(self, parsed_url: ParsedURL):
        """Gets a string for the Cookie header."""
        return "; ".join([
            f"{c["key"]}={c["value"]}" 
            for c in self.cookies[parsed_url.hostname][parsed_url.pathname]
        ])
    
    def refresh(self):
        """Throws out cookies that have become too stale."""
        for domain in self.cookies.values():
            for path in domain.values():
                path[:] = [c for c in path if not (c['expires'] and datetime.now() >= c['expires'])]
    
    def sessionend(self):
        """Deletes session cookies."""
        for domain in self.cookies.values():
            for path in domain.values():
                path[:] = [c for c in path if not c['expires']]
    
    def process(self, res: Response):
        parsed_url = parse_url(res.url)
        for Set_Cookie in res.headers.getall("Set-Cookie"):
            self.parse_Set_Cookie(Set_Cookie, parsed_url)

def parse_url(url: str) -> ParsedURL:
    """Parses a URL into individual components and returns a ParsedURL."""
    m = url_regex.match(url)
    if not m:
        raise ValueError(f"Invalid URL: {url}")

    protocol = m.group("protocol")
    hostname = m.group("hostname")
    port = m.group("port")
    path = m.group("path")
    query = m.group("query")
    frag = m.group("frag")

    return ParsedURL(
        protocol=protocol,
        hostname=hostname,
        port=int(port) if port else None,
        pathname=path or None,
        querystr=query or None,
        fragment=frag or None,
    )
    
def unparse_url(parsed_url: ParsedURL) -> str:
    """Joins a parsed URL back into a string."""
    url = f"{parsed_url.protocol}://{parsed_url.hostname}"
    if parsed_url.port: url += f":{parsed_url.port}"
    if parsed_url.pathname: url += parsed_url.pathname
    if parsed_url.querystr: url += f"?{parsed_url.querystr}"
    if parsed_url.fragment: url += f"#{parsed_url.fragment}"
    return url
    
def absolute_url(parent: str | ParsedURL, relative: str) -> ParsedURL:
    """Given a parent URL and a relative URL, returns an absolute URL (as a ParsedURL)."""
    if isinstance(parent, str):
        parent = parse_url(parent)

    # Already absolute
    if "://" in relative:
        return parse_url(relative)

    base = f"{parent.protocol}://{parent.hostname}"
    if parent.port:
        base += f":{parent.port}"

    # Root-relative
    if relative.startswith("/"):
        return parse_url(base + relative)

    # Query-only
    if relative.startswith("?"):
        return parse_url(base + (parent.pathname or "/") + relative)

    # Fragment-only
    if relative.startswith("#"):
        frag_url = base + (parent.pathname or "/")
        if parent.querystr:
            frag_url += "?" + parent.querystr
        frag_url += relative
        return parse_url(frag_url)

    # Otherwise: relative to current path
    path = parent.pathname or "/"
    # Ensure we have a directory base
    if not path.endswith("/"):
        path = path.rsplit("/", 1)[0] + "/"
    # Normalize with posixpath to handle ../ and ./ segments
    new_path = posixpath.normpath(path + relative)
    return parse_url(base + new_path)

def _parse_raw_hdrs(raw_headers):
    headers_list = [[y.strip() for y in x.split(":", 1)] for x in raw_headers]
    headers = Headers()
    for k, v in headers_list:
        headers.add(k, v)
    return headers

def urlopen(request_or_url: str | Request, 
            *, follow_redirects: bool = True, processor: Processor = None, 
            _redir=0) -> Response:
    """Creates a request and fetches the response."""
    if isinstance(request_or_url, str):
        request = Request(request_or_url)
    else:
        request = request_or_url
        
    parsed_url = parse_url(request.url)
    
    is_https = parsed_url.protocol == "https"
    if parsed_url.protocol not in ("http", "https"):
        raise ValueError(f"Unsupported protocol: {parsed_url.protocol}")

    port = parsed_url.port or (443 if is_https else 80)
    
    raw_socket = socket.socket()
    raw_socket.connect((parsed_url.hostname, port))
    
    if is_https:
        context = ssl.create_default_context()
        s = context.wrap_socket(raw_socket, server_hostname= \
                                parsed_url.hostname)
    else:
        s = raw_socket
    
    try:
        headers = request.headers.copy()
        headers.setdefault("Host", parsed_url.hostname)
        headers.setdefault("User-Agent", "smolurl")
        headers.setdefault("Connection", "close")
        headers.setdefault("Accept", "*/*")
        headers.setdefault("Accept-Encoding", ", ".join(ACCEPT_ENCODINGS.keys()))
        if request.data:
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            headers.setdefault("Content-Length", str(len(request.data)))
        
        fullpath = (parsed_url.pathname or "/") + \
                   ("?" + parsed_url.querystr if parsed_url.querystr else "")
                   
        top_line = f"{request.method} {fullpath} HTTP/1.0"
        header_lines = "\r\n".join([f"{k}: {v}" for k, v in headers.items()])
        http_request = f"{top_line}\r\n{header_lines}\r\n\r\n{request.data}"
        s.send(http_request.encode("latin1", errors="replace"))
        
        data = b""
        while True:
            chunk = s.recv(256)
            if not chunk: break
            data += chunk
            if b"\r\n\r\n" in data: break
            
        parts = data.split(b"\r\n\r\n", 1)
        if len(parts) == 2:
            raw_headers, body = parts
        else:
            raw_headers, body = parts[0], b""

        raw_headers = raw_headers.decode("latin1").split("\r\n")
        top = raw_headers.pop(0)
        headers = _parse_raw_hdrs(raw_headers)
        
        if "Content-Length" in headers:
            length = int(headers["Content-Length"])
            while len(body) < length:
                chunk = s.recv(length - len(body))
                if not chunk: break
                body += chunk
        else:
            # Fallback: Read until EOF if no Content-Length is provided
            while True:
                chunk = s.recv(4096)
                if not chunk: 
                    break
                body += chunk
    finally:
        try:
            s.close()
        except NameError:
            raw_socket.close()
        except Exception:
            pass
        
    _, status, reason = top.split(" ", 2)
    status = int(status)
    
    if follow_redirects and 300 <= status < 400:
        # some people hate standards and send a 3xx without Location
        if "Location" in headers:
            if _redir > REDIR_LIMIT:
                raise RuntimeError("Too many redirects")
                
            return urlopen(
                unparse_url(absolute_url(parsed_url, headers["Location"])),
                follow_redirects=follow_redirects,
                processor=processor,
                _redir=_redir+1
            )
    
    res = Response(
        url=request.url,
        status=status,
        reason=reason,
        headers=headers,
        body=body
    )
    
    if processor:
        processor.process(res)
    
    return res

def wsgi_wrap(app):
    class _WSGIWrapper:
        def __init__(self, app):
            self._app = app
            self._code = 200
            self._reason = "OK"
            self._headers = Headers()
            self._wbuf = io.BytesIO()

        def __call__(self, req):
            it = self._app(self._wsgi_environ(req), self._wsgi_start_response)
            
            for x in it:
                self._wbuf.write(x)
            
            return Response(
                status=self._code,
                reason=self._reason,
                headers=self._headers,
                body=self._wbuf.getvalue()
            )

        def _wsgi_environ(self, req):
            url = parse_url(req.url)
            environ = {
                **os.environ,
                "REQUEST_METHOD": req.method,
                "SCRIPT_NAME": "",
                "PATH_INFO": url.pathname,
                "QUERY_STRING": url.querystr,
                "SERVER_NAME": "localhost",
                "SERVER_PORT": "80",
                "SERVER_PROTOCOL": "HTTP/1.0",
                "wsgi.version": (1, 0),
                "wsgi.url_scheme": "http",
                "wsgi.input": io.BytesIO(req.data.encode("latin1", 
                              errors="replace")),
                "wsgi.errors": sys.stderr,
                "wsgi.multithread": False,
                "wsgi.multiprocess": False,
                "wsgi.run_once": False,
                **{
                    f"HTTP_{k.upper().replace("-", "_")}": ", ".join(
                    req.headers.getall(k)) for k in req.headers.keys()
                }
            }
            
            if "Content-Type" in req.headers:
                environ["CONTENT_TYPE"] = req.headers["Content-Type"]
            
            if "Content-Length" in req.headers:
                environ["CONTENT_LENGTH"] = req.headers["Content-Length"]
            
            return environ

        def _wsgi_start_response(self, status, headers, exc_info=None):
            code, reason = status.split(" ", 1)
            self._code = int(code)
            self._reason = reason
            self._headers.extend(headers)
            
            return self._wbuf.write

    def handler(req):
        return _WSGIWrapper(app)(req)

    return handler

def http_server(handler, host="127.0.0.1", port=8080, use_threading=True):
    s = socket.socket()
    s.bind((host, port))
    s.listen(5)
    print(f"Serving on {host}:{port}")
    
    def thread(conn):
        try:
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
            headers = _parse_raw_hdrs(raw_headers)

            if "Content-Length" in headers:
                length = int(headers["Content-Length"])
                while len(body_bytes) < length:
                    chunk = conn.recv(length - len(body_bytes))
                    if not chunk: break
                    body_bytes += chunk

            method, path, _ = top.split(" ", 2)
            req = Request(url=f"http://{host}:{port}{path}", method=method,
                          headers=headers, data=body_bytes.decode("latin1", 
                          errors="replace"))

            try:
                res = handler(req)
            except Exception as e:
                res = Response(
                    status=500,
                    reason="Internal Server Error",
                    headers=Headers({"Content-Type": "text/plain; charset=utf-8"}),
                    body=b"An error has occurred. Please contact the server administrator."
                )
                traceback.print_exception(e, file=sys.stderr)

            headers = res.headers.copy()
            headers.setdefault("Server", "smolurl")
            headers.setdefault("Connection", "close")
            headers["Content-Length"] = str(len(res.body))

            top_line = f"HTTP/1.0 {res.status} {res.reason}"
            header_lines = "\r\n".join([f"{k}: {v}" for k, v in headers.items()])
            http_res = f"{top_line}\r\n{header_lines}\r\n\r\n".encode("latin1") + res.body

            conn.sendall(http_res)
            conn.close()

            print("request:", req.method, req.url, repr(f"{res.status} {res.reason}"))
        except ConnectionResetError:
            pass
    
    while True:
        try:
            conn, addr = s.accept()
            if use_threading:
                threading.Thread(target=thread, args=(conn,)).start()
            else:
                thread(conn)
        except KeyboardInterrupt:
            return