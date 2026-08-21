"""
Tiny module with which you can:
    - parse URLs
    - send http requests,
    - get the response,
    - and stream it too!

smolurl follows redirects; you can change the redirect limit by changing
smolurl.REDIR_LIMIT (defaults to 5).

smolurl supports HTTP/1.0 with SSL/TLS.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from collections.abc import MutableMapping
from abc import ABC, abstractmethod
from compression import gzip, zstd, zlib
from contextlib import asynccontextmanager
from http import HTTPStatus
import io
import os
import ssl
import sys
import http
import socket
import asyncio
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
    "zstd": zstd.decompress,
    "deflate": _deflate,
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

    def __init__(self, a=None, **kw):
        self._items = []
        if a:
            self.extend(a)
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

def _decomp(text, headers):
    if "Content-Encoding" in headers:
        encs = map(str.strip, headers["Content-Encoding"].split(","))

        for enc in encs:
            if enc in ACCEPT_ENCODINGS:
                text = ACCEPT_ENCODINGS[enc](text)
            else:
                if enc == "br":
                    raise ValueError("Can not decode 'br' encoding "
                                     "because the brotli module was "
                                     "not installed. Please install "
                                     "it to fix the issue.")

                raise ValueError(f"Unknown encoding: {enc}")
    return text

def _charset(headers):
    charset = "latin1"
    if "Content-Type" in headers:
        match = content_type_regex.match(headers["Content-Type"])
        if match and match["charset"]:
            charset = match["charset"]
    return charset

@dataclass
class Request:
    """A dataclass representing a request."""
    url: str
    method: str = "GET"
    headers: Headers = field(default_factory=Headers)
    data: str = ""

@dataclass(frozen=True)
class Response:
    """A dataclass representing a response."""
    url: str
    status: int
    reason: str
    headers: Headers
    body: bytes

    @property
    def ok(self) -> bool:
        return self.status < 400

    def unwrap(self):
        if not self.ok:
            status_info = http.HTTPStatus(self.status)
            raise ValueError(f"{self.status} {status_info.phrase}: {
                             status_info.description} (body: {self.body})")

        return self

    def expect(self, msg):
        if not self.ok:
            raise ValueError(f"{msg} ({self.status} {
                             http.HTTPStatus(self.status).phrase})")
        return self

    def decmp(self):
        return _decomp(self.body, self.headers)

    def text(self):
        return self.decmp().decode(_charset(self.headers), errors="replace")

@dataclass(frozen=True)
class StreamingResponse:
    """A dataclass representing a streamed response."""
    url: str
    status: int
    reason: str
    headers: Headers
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

    @property
    def ok(self) -> bool:
        return self.status < 400

    async def unwrap(self):
        if not self.ok:
            status_info = http.HTTPStatus(self.status)
            err_body = await self.body()
            await self.__aexit__()
            
            raise ValueError(f"{self.status} {status_info.phrase}: {
                             status_info.description} (body: {err_body})")

        return self

    async def expect(self, msg):
        if not self.ok:
            await self.__aexit__()
            raise ValueError(f"{msg} ({self.status} {
                             http.HTTPStatus(self.status).phrase})")
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except: pass

    async def iterbody(self):
        while True:
            line = await self.reader.readline()
            if not line:
                break
            yield line

    __aiter__ = iterbody

    async def itertext(self):
        charset = _charset(self.headers)

        async for line in self:
            yield line.decode(charset, errors="replace")

    async def body(self):
        x = b""
        async for ln in self:
            x += ln
        return x

    async def decmp(self):
        return _decomp(await self.body(), self.headers)

    async def text(self):
        return (await self.decmp()).decode(_charset(self.headers),
                                           errors="replace")

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
        return replace(self, **kwargs)

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
    Keyword "basic". This will break sometimes.
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

    def parse_set_cookie(self, set_cookie: str, parsed_url: ParsedURL):
        """Parses a Set-Cookie header."""
        parts = [p.strip() for p in set_cookie.split(";")]
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
                        expires = datetime.strptime(
                            value, "%a, %d %b %Y %H:%M:%S GMT"
                        )
                    except:
                        expires = None
                case "Max-Age":
                    try:
                        expires = datetime.now() + timedelta(
                            seconds=int(value)
                        )
                    except:
                        expires = None

        self.add_cookie(key, value, domain=domain, path=path, expires=expires)

    def get_cookie(self, parsed_url: ParsedURL):
        """Gets a string for the Cookie header."""
        return "; ".join([
            f"{c["key"]}={c["value"]}"
            for c in self.cookies[parsed_url.hostname][parsed_url.pathname]
        ])

    def refresh(self):
        """Throws out cookies that have become too stale."""
        for domain in self.cookies.values():
            for path in domain.values():
                path[:] = [
                    c for c in path if not
                    (c['expires'] and datetime.now() >= c['expires'])
                ]

    def sessionend(self):
        """Deletes session cookies."""
        for domain in self.cookies.values():
            for path in domain.values():
                path[:] = [c for c in path if not c['expires']]

    def process(self, res: Response):
        parsed_url = parse_url(res.url)
        for set_cookie in res.headers.getall("Set-Cookie"):
            self.parse_set_cookie(set_cookie, parsed_url)

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
    """
    Given a parent URL and a relative URL, returns an absolute 
    URL (as a ParsedURL).
    """
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

def _parse_http_headers(raw_headers):
    raw_headers = raw_headers.decode("latin1").split("\r\n")
    top = raw_headers.pop(0)
    headers = Headers([
        tuple(map(str.strip, x.split(":", 1))) for x in raw_headers
    ])

    _, status, reason = top.split(" ", 2)
    status = int(status)

    return ((status, reason), headers)

def _prep_http_request(parsed_url, request):
    headers = request.headers.copy()
    headers.setdefault("Host", parsed_url.hostname)
    headers.setdefault("User-Agent", "smolurl")
    headers.setdefault("Connection", "close")
    headers.setdefault("Accept", "*/*")
    if request.data:
        headers.setdefault("Content-Type",
                           "application/x-www-form-urlencoded")
        headers.setdefault("Content-Length", str(len(request.data)))

    fullpath = (parsed_url.pathname or "/") + \
               ("?" + parsed_url.querystr if parsed_url.querystr else "")

    top_line = f"{request.method} {fullpath} HTTP/1.0"
    header_lines = "\r\n".join([f"{k}: {v}" for k, v in headers.items()])

    return f"{top_line}\r\n{header_lines}\r\n\r\n{request.data}"

def urlopen(request_or_url: str | Request,
            *, follow_redirects: bool = True, processor: Processor = None,
            _redir=0) -> Response:
    """Creates a request and fetches the response."""
    if isinstance(request_or_url, str):
        request = Request(request_or_url)
    else:
        request = replace(request_or_url)

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
        s.send(_prep_http_request(parsed_url, request)
               .encode("latin1", errors="replace"))

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

        (status, reason), headers = _parse_http_headers(raw_headers)

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
#
async def aurlopen(request_or_url: str | Request,
                   *, follow_redirects: bool = True,
                   _redir=0) -> Response:
    """Creates a request and streams the response asynchronously."""
    if isinstance(request_or_url, str):
        request = Request(request_or_url)
    else:
        request = replace(request_or_url)

    parsed_url = parse_url(request.url)

    is_https = parsed_url.protocol == "https"
    if parsed_url.protocol not in ("http", "https"):
        raise ValueError(f"Unsupported protocol: {parsed_url.protocol}")

    port = parsed_url.port or (443 if is_https else 80)
    reader, writer = await asyncio.open_connection(
        parsed_url.hostname, port, ssl=is_https
    )

    request.headers["Accept-Encoding"] = "identity"

    writer.write(_prep_http_request(parsed_url, request)
                 .encode("latin1", errors="replace"))
    await writer.drain()

    raw_headers = b""
    while True:
        line = await reader.readline()
        if not line or line == b"\r\n":
            break
        raw_headers += line

    (status, reason), headers = _parse_http_headers(raw_headers.strip())

    if follow_redirects and 300 <= status < 400:
        # some people hate standards and send a 3xx without Location
        if "Location" in headers:
            writer.close()
            await writer.wait_closed()

            if _redir > REDIR_LIMIT:
                raise RuntimeError("Too many redirects")

            return await aurlopen(
                unparse_url(absolute_url(parsed_url, headers["Location"])),
                follow_redirects=True, _redir=_redir+1
            )

    return StreamingResponse(
        url=request.url,
        status=status,
        reason=reason,
        headers=headers,
        reader=reader,
        writer=writer
    )

@asynccontextmanager
async def make_sse_stream(request_or_url: str | Request,
                          *, follow_redirects: bool = True):
    class _SSEStream:
        @dataclass
        class EventContext:
            evt: str = "message"
            data: list[str] = field(default_factory=list)

        def __init__(self, res):
            self.res = res
            self.onf = {}
            self.ondefault = lambda evt, payload: None

        def on(self, evt, do):
            self.onf[evt] = do

        async def loop(self):
            ctx = _SSEStream.EventContext()
            async for ln in self.res.itertext():
                if not ln:  # end of event
                    if ctx.data:
                        payload = "\n".join(ctx.data)
                        if ctx.evt in self.onf:
                            self.onf[ctx.evt](payload)
                        else:
                            self.ondefault(ctx.evt, payload)
                    ctx = _SSEStream.EventContext()
                    continue

                if ln.startswith(":"):
                    continue  # comment line

                if ":" not in ln:
                    continue  # malformed

                tp, data = ln.split(":", 1)
                data = data.lstrip()  # strip leading space per SSE spec

                if tp == "event":
                    ctx.evt = data
                elif tp == "data":
                    ctx.data.append(data)
                else:
                    continue # not going to worry about retry or id

            if ctx.data:
                payload = "\n".join(ctx.data)
                if ctx.evt in self.onf:
                    self.onf[ctx.evt](payload)
                else:
                    self.ondefault(ctx.evt, payload)

    async with await (await aurlopen(
        request_or_url, follow_redirects=follow_redirects
    )).unwrap() as res:
        yield _SSEStream(res)