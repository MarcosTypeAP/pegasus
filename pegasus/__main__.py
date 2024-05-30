from http_parser import HTTP_STATUS_PHRASES, HTTPHeader, HTTPRequest, HTTPResponse, http_status
from web_server import WEB_SERVER_NAME, Address, WebServer
from wsgi_server import wsgi_server
from types import ModuleType
from typing import TYPE_CHECKING, Any, Iterable, NoReturn
import socket
import argparse
import os
import sys


if TYPE_CHECKING:
    from _typeshed.wsgi import WSGIApplication, WSGIEnvironment, StartResponse


def echo_wsgi_app(environ: 'WSGIEnvironment', start_response: 'StartResponse') -> Iterable[bytes]:
    headers: list[HTTPHeader] = []

    if environ['REQUEST_METHOD'] == 'GET':
        start_response(f'200 {HTTP_STATUS_PHRASES[200]}', [], None)
        return []

    body = environ['wsgi.input'].read()

    if body:
        headers.extend((
            ('content-length', str(len(body))),
            ('content-type', 'text/plain'),
        ))

    start_response(f'200 {HTTP_STATUS_PHRASES[200]}', headers, None)
    return [body]


def handle_request_echo(request: HTTPRequest, addr: Address) -> HTTPResponse:
    status = http_status.HTTP_200_OK

    if request['method'].upper() == 'GET' or request['body'] is None:
        return {
            'status': '%d %s' % (status, HTTP_STATUS_PHRASES[status]),
            'headers': [],
            'body': None
        }

    return {
        'status': '%d %s' % (status, HTTP_STATUS_PHRASES[status]),
        'headers': [
            ('content-length', str(len(request['body']))),
            ('content-type', 'text/plain'),
        ],
        'body': request['body']
    }


def get_args() -> argparse.Namespace:
    def raise_argument_error(msg: str, data: Any | None = None) -> NoReturn:
        if data is not None:
            msg = f"{msg}: '{data}'"
        raise argparse.ArgumentTypeError(msg)

    def type_dir(path: str) -> str:
        if not os.path.isdir(path):
            raise_argument_error('Directory does not exist', path)

        return path

    def type_address(addr: str) -> str:
        try:
            socket.getaddrinfo(addr, None, socket.AF_INET, socket.SOCK_STREAM)
        except socket.gaierror as error:
            raise_argument_error(error.strerror, addr)

        return addr

    def type_port(port_raw: str) -> int:
        try:
            port = int(port_raw)
        except ValueError as error:
            raise_argument_error(error.args[0])

        if port < 0 or port > 65535:
            raise_argument_error('Port must be 0-65535', port)

        return port

    def type_threads(threads_raw: str) -> int:
        try:
            threads = int(threads_raw)
        except ValueError as error:
            raise_argument_error(error.args[0])

        if threads <= 0:
            raise_argument_error('The minimum is 1', threads)

        return threads

    def type_backlog(backlog_raw: str) -> int | None:
        try:
            backlog = int(backlog_raw)
        except ValueError as error:
            raise_argument_error(error.args[0])

        return backlog if backlog >= 0 else None

    arg_parser = argparse.ArgumentParser(WEB_SERVER_NAME, description='A blazingly fast WSGI web server.')
    arg_parser.add_argument(
        '--chdir',
        metavar='DIR',
        type=type_dir,
        default=os.getcwd(),
        help=(
            'Change directory. '
            f'Uses the current working directory by default. [{os.getcwd()}]'
        )
    )
    arg_parser.add_argument(
        'app',
        nargs='?',
        metavar='MODULE:APP',
        help='WSGI application to be used. Uses an echo app by default.'
    )
    arg_parser.add_argument(
        '--host',
        metavar='ADDR',
        default='0.0.0.0',
        type=type_address,
        help='Address to which the server will bind. [0.0.0.0]'
    )
    arg_parser.add_argument(
        '--port',
        metavar='PORT',
        type=type_port,
        default=8080,
        help='Port to which the server will bind. [8080]'
    )
    arg_parser.add_argument(
        '--threads',
        metavar='INT',
        type=type_threads,
        default=(os.cpu_count() or 1) * 2,
        help=(
            'The maximum number of active threads handling requests. '
            f'Uses os.cpu_count() * 2 by default. [{(os.cpu_count() or 1) * 2}]'
        )
    )
    arg_parser.add_argument(
        '--backlog',
        metavar='INT',
        type=type_backlog,
        default=1024,
        help=(
            'The maximum number of pending connections before refusing new connections. '
            'If negative, a default reasonable value is chosen by the system. [1024]'
        )
    )
    return arg_parser.parse_args()


def get_wsgi_application(app_module_path: str) -> 'WSGIApplication':
    module_path, app_name = app_module_path.split(':', 1)

    curr: ModuleType = __import__(module_path)

    for module in module_path.split('.')[1:]:
        curr = getattr(curr, module)

    return getattr(curr, app_name)


def main() -> None:
    args = get_args()

    server_addr = (args.host, args.port)
    app: 'WSGIApplication' = echo_wsgi_app

    if args.app:
        if args.chdir:
            os.chdir(args.chdir)
            sys.path.insert(1, os.getcwd())

        app = get_wsgi_application(args.app)

    def handle_request(request: HTTPRequest, request_addr: Address) -> HTTPResponse:
        return wsgi_server(app, request, request_addr, server_addr)

    with WebServer(server_addr, on_request=handle_request, max_threads=args.threads, backlog=args.backlog) as server:
        server.listen()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
