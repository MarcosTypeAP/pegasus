from http_parser import HTTPHeader, HTTPRequest, HTTPResponse
from typing import TYPE_CHECKING, Callable
import socket
import io
import sys


Address = tuple[str, int]
Client = tuple[socket.socket, Address]

OnRequest = Callable[[HTTPRequest, Address], HTTPResponse]

if TYPE_CHECKING:
    from _typeshed import OptExcInfo
    from _typeshed.wsgi import WSGIApplication, WSGIEnvironment


def run_wsgi_application(app: 'WSGIApplication', environ: 'WSGIEnvironment') -> HTTPResponse:
    status = ''
    headers: list[HTTPHeader] = []
    body = b''

    def write_body(data: bytes) -> int:
        nonlocal body
        body += data
        return len(data)

    def start_response(status_: str, headers_: list[HTTPHeader], exc_info: 'OptExcInfo | None' = None) -> Callable[[bytes], int]:
        nonlocal status, headers

        if status:
            raise Exception('`start_response` called tweice.')

        status = status_
        headers = headers_

        return write_body

    body += b''.join(app(environ, start_response))
    assert status

    return {
        'status': status,
        'headers': headers,
        'body': body or None
    }


def wsgi_server(app: 'WSGIApplication', request: HTTPRequest, request_addr: Address, server_addr: Address) -> HTTPResponse:
    wsgi_input = io.BytesIO(request['body'] or b'')
    environ: 'WSGIEnvironment' = {
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'http',
        'wsgi.input': wsgi_input,
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': True,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
        'REQUEST_METHOD': request['method'],
        'RAW_URI': request['url'],
        'REMOTE_ADDR': request_addr[0],
        'REMOTE_PORT': request_addr[1],
        'SERVER_NAME': server_addr[0],
        'SERVER_PORT': server_addr[1],
        'SERVER_PROTOCOL': 'HTTP/1.1'
    }

    path_info, *query_string = request['url'].split('?', 1)
    environ['PATH_INFO'] = path_info
    if query_string:
        environ['QUERY_STRING'] = query_string[0]

    for key, value in request['headers']:
        environ['HTTP_' + key.upper().replace('-', '_')] = value

    if request['body']:
        environ['CONTENT_LENGTH'] = environ.get('HTTP_CONTENT_LENGTH') or len(request['body'])

    try:
        return run_wsgi_application(app, environ)
    finally:
        wsgi_input.close()
