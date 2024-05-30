from http_parser import generate_http_status, http_status, HTTPRequest, HTTPRequestParser, HTTPResponse, ParsingError
from typing import Callable
from threading import Thread
import socket
import os


WEB_SERVER_NAME = 'pegasus'


Address = tuple[str, int]
Client = tuple[socket.socket, Address]

OnRequest = Callable[[HTTPRequest, Address], HTTPResponse]


class WebServer:
    __slots__ = ('addr', 'on_request', 'backlog', 'max_threads', '_thread_pool', '_free_thread_slots', '_socket')

    def __init__(self, addr: Address, on_request: OnRequest, max_threads: int | None = None, backlog: int | None = 1024) -> None:
        assert max_threads is None or max_threads > 0
        assert backlog is None or backlog >= 0

        if max_threads is None:
            max_threads = (os.cpu_count() or 1) * 2

        self.addr: Address = addr
        self.on_request: OnRequest = on_request
        self.backlog: int | None = backlog
        self.max_threads: int = max_threads

        self._thread_pool: list[Thread | None] = [None for _ in range(max_threads)]
        self._free_thread_slots: set[int] = set(range(max_threads))

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR | socket.SO_REUSEPORT, 1)
        self._socket.bind(addr)

    def __enter__(self) -> 'WebServer':
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        self._socket.close()
        for thread in self._thread_pool:
            if thread is None:
                continue

            thread.join(timeout=10)

            if thread.is_alive():
                assert not thread.is_alive(), f'WARNING: Thread "{thread.name}" could not end.'

    @staticmethod
    def _serialize_http_response(http_response: HTTPResponse) -> bytes:
        http_response['headers'].extend((
            ('server', WEB_SERVER_NAME),
            ('connection', 'close'),
        ))

        response = b'HTTP/1.1 %s\r\n' % http_response['status'].encode()

        has_content_length = False
        for key, value in http_response['headers']:
            key = key.lower()

            if key == 'content-length':
                has_content_length = True

            response += b'%s: %s\r\n' % (key.encode(), value.encode())

        if http_response['body'] is None:
            return response + b'\r\n'

        if not has_content_length:
            response += b'content-length: %d\r\n' % len(http_response['body'])

        return response + b'\r\n' + http_response['body']

    @staticmethod
    def _log_client(addr: Address, request: HTTPRequest, response: HTTPResponse) -> None:
        print(f"INFO: {addr[0]}:{addr[1]} - \"{request['method']} {request['url']} HTTP/1.1\" {response['status']}")

    @staticmethod
    def _log_client_error(addr: Address, response: HTTPResponse) -> None:
        log = f"ERROR: {addr[0]}:{addr[1]} - {response['status']}"

        if response['body']:
            log += f" - {response['body'].decode()}"

        print(log)

    def _handle_client_thread(self, client: Client, slot: int) -> None:
        socket, addr = client
        socket.settimeout(5)

        parser = HTTPRequestParser()

        response: HTTPResponse | None = None

        try:
            while not parser.completed:
                try:
                    data = socket.recv(1024)
                except TimeoutError:
                    response = {
                        'status': generate_http_status(http_status.HTTP_408_REQUEST_TIMEOUT),
                        'headers': [],
                        'body': None
                    }
                    break

                if data == b'':
                    response = {
                        'status': generate_http_status(http_status.HTTP_400_BAD_REQUEST),
                        'headers': [],
                        'body': b'Empty package received.\n'
                    }
                    break

                error = parser.feed(data)
                if error:
                    body = (error.msg + '\n') if error.msg and error.msg[-1] != '\n' else error.msg
                    response = {
                        'status': generate_http_status(error.status),
                        'headers': [],
                        'body': body.encode()
                    }
                    break

            if response is None:
                request = parser.get_result()
                response = self.on_request(request, addr)
                self._log_client(addr, request, response)
            else:
                self._log_client_error(addr, response)

            serialized_response = self._serialize_http_response(response)
            socket.sendall(serialized_response)

        finally:
            self._free_thread_slots.add(slot)
            socket.close()

    def listen(self) -> None:
        if self.backlog is None:
            self._socket.listen()
        else:
            self._socket.listen(self.backlog)

        print(f'INFO: Listen at "{self.addr[0]}:{self.addr[1]}"')
        print(f'INFO: Threads: {self.max_threads}')

        slot: int | None = None
        try:
            while True:
                while not self._free_thread_slots:
                    pass

                client = self._socket.accept()
                slot = self._free_thread_slots.pop()

                t = Thread(target=self._handle_client_thread, args=(client, slot), daemon=False)
                t.start()

                self._thread_pool[slot] = t
        finally:
            if slot is not None:
                self._free_thread_slots.add(slot)
