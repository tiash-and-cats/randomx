"""
Tiny module with which you can:
    - parse URLs
    - send HTTP requests (with Content-Encoding),
    - get the response,
    - and stream it too!

smolurl follows redirects; you can change the redirect limit by setting
smolurl.REDIR_LIMIT (defaults to 5).

smolurl supports HTTP/1.0 with SSL/TLS.

The core functionallity is built from the ground up using just 'socket'.
The 'http' module is only imported for it's HTTPStatus enum.

It has some optional features:
    - Brotli ('br') decoding [needs 'brotli' or 'brotlicffi' modules]
    - Zstandard ('zstd') decoding [needs either Python >= 3.14 or
      'backports.zstd' or 'zstandard' modules]
    - Mozilla CA bundle using 'certifi'

Print smolurl.support for a quick summary of which optional features
are active in your environment.

OLD API NOTICE: There is a new API based on namespaces. The old API
with top-level things is available, but it is just aliases to the new
API now.

======== Quickstart! ======

smolurl is organized into namespaces:
    - 'smolurl.parse': URL parsing
    - 'smolurl.request': sending HTTP requests and getting 
    - 'smolurl.processors': A Processor is a class that processes the
      Response before returning it to the end user.
    - Some stuff is still on the top level.

To send an HTTP request and get the response:

>>> import smolurl
>>> smolurl.request.urlopen("http://docs.python.org")
request.Response(url='https://docs.python.org/3/', status=200, \
reason='OK', headers=Headers([('Connection', 'close'), \
('Content-Length', '...'), ('server', 'nginx'), \
('content-type', 'text/html'), ...]), body=b'...')

To stream the response:

>>> import smolurl, asyncio
>>> ar = asyncio.run(smolurl.request.aurlopen("http://docs.python.org"))
>>> ar
request.StreamingResponse(url='https://docs.python.org/3/', \
status=200, reason='OK', headers=Headers([('Connection', 'close'), \
('Content-Length', '...'), ('server', 'nginx'), \
('content-type', 'text/html'), ...

(Of course, you wouldn't actually use asyncio.run like that in a real
case, that is just so doctest can test it.)

StreamingResponses are asynchronous iterators, so you can iterate over
it, which is equivalent to iterating over the result of it's .itertext()
method.

To parse a URL:

>>> smolurl.parse.parse_url("https://example.org/oops?x=1#demo")
parse.ParsedURL(protocol='https', hostname='example.org', port=None, \
pathname='/oops', querystr='x=1', fragment='demo')
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from collections.abc import MutableMapping
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Literal
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
import gzip
import zlib
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

class _supportmeta(type):
    def __repr__(self):
        s = []
        
        if self.BROTLI_TYPE != "none":
            s.append(f"using {self.BROTLI_TYPE} for 'br' (Brotli) decoding "
                     f"backend")
        if self.ZSTD_TYPE != "none":
            s.append(f"using {self.ZSTD_TYPE} for 'zstd' (Zstandard) "
                     f"decoding backend")

        if self.CERTIFI_CERTS:
            s.append("using Mozilla CA bundle from certifi")
        
        if not s:
            s.append("no optional features available")
        
        return "\n".join([f"- {x}" for x in s])

def _namespace(cls=None, no_repr=False):
    import inspect
    
    class _reprnsmeta(type):
        def __repr__(self):
            return f"<namespace {self.__module__ + "." + self.__name__!r} \
in {inspect.getmodule(self)!r}>"
    
    def __new__(*_):
        """
        Create and return a new object.
        This raises a NotImplementedError as you can't initialize
        an instance of a namespace.
        """
        raise NotImplementedError("support cannot be instantiated")

    def inner(cls):
        cls.__new__ = __new__
        
        if not no_repr:
            name = cls.__name__
            bases = cls.__bases__
            
            namespace = dict(cls.__dict__)
            
            for slot in namespace.get("__slots__", ()):
                namespace.pop(slot, None)
            
            return _reprnsmeta(name, bases, namespace)
        
        return cls

    if cls is None:
        return inner
    else:
        return inner(cls)

@_namespace(no_repr=True)
class support(metaclass=_supportmeta):
    """
    Namespace of optional features.
    
    BROTLI_TYPE is the module used to provide 'br' (Brotli) decompression
    or 'none'.
    
    CERTIFI_CERTS is True if the certifi module is available.
    
    ZSTD_TYPE is the module used to provide Zstandard decompression for the
    'zstd' encoding or 'none'.
    
    repr(smolurl.support) returns a nice bullet point showing the info
    at a glance.
    """
    CERTIFI_CERTS: bool = False

    BROTLI_TYPE: Literal[
        "brotli", "brotlicffi", "none"
    ] = "none"

    ZSTD_TYPE: Literal[
        "compression.zstd", "backports.zstd", "zstandard", "none"
    ] = "none"

del _supportmeta

def _deflate(data):
    try:
        return zlib.decompress(data)
    except zlib.error:
        return zlib.decompress(data, -15)

ACCEPT_ENCODINGS = {
    "gzip": gzip.decompress,
    "deflate": _deflate,
}

del _deflate

try:
    from compression import zstd
    ACCEPT_ENCODINGS["zstd"] = zstd.decompress
    support.ZSTD_TYPE = "compression.zstd"
except ModuleNotFoundError:
    try:
        from backports import zstd
        ACCEPT_ENCODINGS["zstd"] = zstd.decompress
        support.ZSTD_TYPE = "backports.zstd"
    except ModuleNotFoundError:
        try:
            import zstandard as zstd
            ACCEPT_ENCODINGS["zstd"] = zstd.decompress
            support.ZSTD_TYPE = "zstandard"
        except ModuleNotFoundError:
            pass

try:
    import brotli
    ACCEPT_ENCODINGS["br"] = brotli.decompress
    support.BROTLI_TYPE = "brotli"
except ModuleNotFoundError:
    try:
        import brotlicffi as brotli
        ACCEPT_ENCODINGS["br"] = brotli.decompress
        support.BROTLI_TYPE = "brotlicffi"
    except ModuleNotFoundError:
        pass

try:
    import certifi
    SSL_CERT = certifi.where()
    support.CERTIFI_CERTS = True
except ModuleNotFoundError:
    SSL_CERT = None

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

    >>> h = Headers()
    >>> h["Content-Type"] = "text/html"
    >>> h["content-type"]
    'text/html'

    >>> h.add("Set-Cookie", "a=1")
    >>> h.add("Set-Cookie", "b=2")
    >>> h.getall("set-cookie")
    ['a=1', 'b=2']

    >>> h.getone("set-cookie")
    Traceback (most recent call last):
        ...
    KeyError: "Multiple values match 'set-cookie': ['a=1', 'b=2']"

    >>> h.mixed()
    {'Content-Type': 'text/html', 'Set-Cookie': ['a=1', 'b=2']}

    >>> h.dict_of_lists()
    {'Content-Type': ['text/html'], 'Set-Cookie': ['a=1', 'b=2']}

    >>> del h["CONTENT-TYPE"]
    >>> "content-type" in h
    False
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
        Create a Headers that is a view on the given list
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
        encs = [
            enc.strip().lower() 
            for enc in reversed(headers["Content-Encoding"].split(","))
            if enc.strip()
        ]

        for enc in encs:
            if enc in ACCEPT_ENCODINGS:
                text = ACCEPT_ENCODINGS[enc](text)
            else:
                raise ValueError(f"Unknown encoding: {enc}")

    return text

def _charset(headers):
    charset = "latin1"
    if "Content-Type" in headers:
        match = content_type_regex.match(headers["Content-Type"])
        if match and match["charset"]:
            charset = match["charset"]
    return charset

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

def _ssl_context():
    context = ssl.create_default_context()
    
    if SSL_CERT:
        context.load_verify_locations(SSL_CERT)
    
    return context

@_namespace
class request:
    """A namespace of helpers for sending HTTP requests."""
    
    @dataclass
    class Request:
        """A dataclass representing a request."""
        url: str
        method: str = "GET"
        headers: Headers = field(default_factory=Headers)
        data: str = ""

    @dataclass(frozen=True)
    class Response:
        r"""
        A dataclass representing a response.
        
        >>> import gzip
        >>> from smolurl import Response, Headers

        # Construct a gzip-compressed response
        >>> data = b"hello world"
        >>> encoded = gzip.compress(data)
        >>> r = Response(
        ...     url="http://example.com",
        ...     status=200,
        ...     reason="OK",
        ...     headers=Headers([("Content-Encoding", "gzip"), 
        ...                     ("Content-Type", "text/plain")]),
        ...     body=encoded,
        ... )
        ...

        # ok property
        >>> r.ok
        True

        # unwrap returns self if ok
        >>> r.unwrap() is r
        True

        # expect returns self if ok
        >>> r.expect("must succeed") is r
        True

        # decmp returns raw bytes
        >>> r.decmp()
        b'hello world'

        # text returns decoded string
        >>> r.text()
        'hello world'

        # iterbody splits by newline
        >>> r = Response(url="", status=200, reason="OK", headers=Headers(),
        ... body="a\nb".encode())
        ...
        >>> list(r.iterbody())
        [b'a', b'b']

        # itertext splits by newline
        >>> list(r.itertext())
        ['a', 'b']
        """
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
                                 status_info.description}")

            return self

        def expect(self, msg):
            if not self.ok:
                raise ValueError(f"{msg} ({self.status} {
                                 http.HTTPStatus(self.status).phrase})")
            return self

        def decmp(self):
            return _decomp(self.body, self.headers)

        def text(self):
            return self.decmp().decode(
                _charset(self.headers), errors="replace"
            )
        
        # for consistency with StreamingResponse
        def iterbody(self):
            return self.decmp().split(b"\n")
        
        __iter__ = iterbody
        
        def itertext(self):
            return self.text().split("\n")

    @dataclass(frozen=True)
    class StreamingResponse:
        """
        A dataclass representing a streamed response.
        
        >>> import asyncio, gzip
        >>> from smolurl import StreamingResponse, Headers

        # Prepare a fake StreamReader with gzip-compressed data
        >>> async def make_reader(data):
        ...     reader = asyncio.StreamReader()
        ...     reader.feed_data(gzip.compress(data))
        ...     reader.feed_eof()
        ...     return reader
        ...
        >>> reader = asyncio.run(make_reader(b"stream test"))

        # Dummy writer
        >>> class DummyWriter:
        ...     def close(self): pass
        ...     async def wait_closed(self): pass
        ...
        >>> writer = DummyWriter()

        >>> s = StreamingResponse(
        ...     url="http://example.com",
        ...     status=200,
        ...     reason="OK",
        ...     headers=Headers([("Content-Encoding", "gzip"), ("Content-Type", "text/plain")]),
        ...     reader=reader,
        ...     writer=writer,
        ... )
        ...

        # ok property
        >>> s.ok
        True

        # unwrap returns self if ok
        >>> s.unwrap() is s
        True

        # decmp returns raw bytes
        >>> asyncio.run(s.decmp())
        b'stream test'

        # text returns decoded string
        >>> asyncio.run(s.text())
        'stream test'
        """
        url: str
        status: int
        reason: str
        headers: Headers
        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter

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

    def urlopen(request_or_url: str | Request,
                *, follow_redirects: bool = True, 
                processor: processor.Processor = None, _redir=0) -> Response:
        """Creates a request and fetches the response."""
        if isinstance(request_or_url, str):
            req = request.Request(request_or_url)
        else:
            req = replace(request_or_url)

        parsed_url = parse.parse_url(req.url)

        is_https = parsed_url.protocol == "https"
        if parsed_url.protocol not in ("http", "https"):
            raise ValueError(f"Unsupported protocol: {parsed_url.protocol}")

        port = parsed_url.port or (443 if is_https else 80)

        raw_socket = socket.socket()
        raw_socket.connect((parsed_url.hostname, port))

        if is_https:
            context = _ssl_context()
            s = context.wrap_socket(raw_socket, 
                                    server_hostname=parsed_url.hostname)
        else:
            s = raw_socket

        try:
            s.send(_prep_http_request(parsed_url, req)
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

                return request.urlopen(
                    parse.unparse_url(
                        parse.absolute_url(parsed_url, headers["Location"])
                    ),
                    follow_redirects=follow_redirects,
                    processor=processor,
                    _redir=_redir+1
                )

        res = request.Response(
            url=req.url,
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
            req = request.Request(request_or_url)
        else:
            req = replace(request_or_url)

        parsed_url = parse.parse_url(req.url)

        is_https = parsed_url.protocol == "https"
        if parsed_url.protocol not in ("http", "https"):
            raise ValueError(f"Unsupported protocol: {parsed_url.protocol}")

        port = parsed_url.port or (443 if is_https else 80)
        
        if is_https:
            ssl_ = _ssl_context()
        else:
            ssl_ = False
        
        reader, writer = await asyncio.open_connection(
            parsed_url.hostname, port, ssl=ssl_
        )

        req.headers["Accept-Encoding"] = "identity"

        writer.write(_prep_http_request(parsed_url, req)
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

                return await request.aurlopen(
                    parse.unparse_url(
                        parse.absolute_url(parsed_url, headers["Location"])
                    ),
                    follow_redirects=True, _redir=_redir+1
                )

        return request.StreamingResponse(
            url=req.url,
            status=status,
            reason=reason,
            headers=headers,
            reader=reader,
            writer=writer
        )

@_namespace
class parse:
    """Namespace of helpers for parsing URLs."""
    
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

        return parse.ParsedURL(
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
            parent = parse.parse_url(parent)

        # Already absolute
        if "://" in relative:
            return parse.parse_url(relative)

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
        return parse.parse_url(base + new_path)

@_namespace
class processors:
    """Namespace of classes to handle Processors."""
    
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

    async with (await request.aurlopen(
        request_or_url, follow_redirects=follow_redirects
    )).unwrap() as res:
        yield _SSEStream(res)

# Legacy aliases
CookieJar = processors.CookieJar
ParsedURL = parse.ParsedURL
Processor = processors.Processor
Request = request.Request
Response = request.Response
StreamingResponse = request.StreamingResponse

urlopen = request.urlopen
aurlopen = request.aurlopen
parse_url = parse.parse_url
unparse_url = parse.unparse_url
absolute_url = parse.absolute_url

__all__ = [
    "request", "processors", "parse", 
    
    "CookieJar", "ParsedURL", "Processor", "Request", "Response",
    "StreamingResponse", "urlopen", "aurlopen", "parse_url",
    "unparse_url", "absolute_url"
]

if __name__ == "__main__":
    import doctest
    print("doctesting smolurl!")
    doctest.testmod(optionflags=doctest.ELLIPSIS)