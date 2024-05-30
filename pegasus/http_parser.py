from typing import Literal, TypedDict


class http_status:
    HTTP_200_OK = 200

    HTTP_400_BAD_REQUEST = 400
    HTTP_408_REQUEST_TIMEOUT = 408
    HTTP_411_LENGTH_REQUIRED = 411

    HTTP_500_INTERNAL_SERVER_ERROR = 500
    HTTP_501_NOT_IMPLEMENTED = 501
    HTTP_505_HTTP_VERSION_NOT_SUPPORTED = 505


HTTP_STATUS_PHRASES: dict[int, str] = {
    200: 'OK',

    400: 'Bad Request',
    408: 'Request Timeout',
    411: 'Length Required',

    500: 'Internal Server Error',
    501: 'Not Implemented',
    505: 'HTTP Version Not Supported',
}


def generate_http_status(status: int) -> str:
    return '%d %s' % (status, HTTP_STATUS_PHRASES[status])


class ParsingError(Exception):
    def __init__(self, status: int, msg: str, data: bytes | str | None = None) -> None:
        self.status = status

        if data:
            if isinstance(data, bytes):
                data = data.decode()

            msg += f": '{data}'"

        self.msg = msg


HTTPMethod = Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
HTTPHeader = tuple[str, str]


HTTP_METHODS: tuple[HTTPMethod, ...] = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')


class HTTPRequest(TypedDict):
    method: HTTPMethod
    url: str
    headers: list[HTTPHeader]
    body: bytes | None


class HTTPResponse(TypedDict):
    status: str
    headers: list[HTTPHeader]
    body: bytes | None


class HTTPRequestParser:
    __slots__ = ('_method', '_url', '_headers', '_body', '_reached_end_of_headers', '_content_length', '_buf', 'completed')

    def __init__(self) -> None:
        self._method: HTTPMethod | None = None
        self._url: str | None = None
        self._headers: list[HTTPHeader] = []
        self._body: bytes | None = None

        self._reached_end_of_headers: bool = False
        self._content_length: int | None = None
        self._buf: bytes = b''
        self.completed: bool = False

    def get_line(self, data: bytes) -> bytes | None:
        line, *rest = data.split(b'\r\n', 1)
        if not rest:
            self._buf = line
            return

        self._buf = rest[0]

        if line == b'':
            self._reached_end_of_headers = True
            if self._content_length is None:
                self.completed = True

            self._feed()
            return

        return line

    def parse_status_line(self, data: bytes) -> None:
        line = self.get_line(data)

        if not line:
            return

        method, url, version, *rest = line.split(b' ')

        if rest:
            raise ParsingError(http_status.HTTP_400_BAD_REQUEST, 'Invalid status line.')

        method_ = method.decode()
        if method_ not in HTTP_METHODS:
            raise ParsingError(http_status.HTTP_501_NOT_IMPLEMENTED, 'Unsupported HTTP method', method)
        self._method = method_

        url_ = url.decode()
        if not url_.startswith('/'):
            raise ParsingError(http_status.HTTP_400_BAD_REQUEST, 'Invalid path', url)
        self._url = url_

        if not version.startswith(b'HTTP/1.') and version[-1:-2] not in b'01':
            raise ParsingError(http_status.HTTP_505_HTTP_VERSION_NOT_SUPPORTED, 'Unsupported HTTP protocol version', version)

        self._feed()

    def parse_header(self, data: bytes) -> None:
        line = self.get_line(data)

        if not line:
            return

        name_value = line.split(b':', 1)

        if len(name_value) == 1:
            raise ParsingError(http_status.HTTP_400_BAD_REQUEST, 'Invalid header', line)

        name = name_value[0].lower().decode()
        value = name_value[1].strip(b' ').decode()

        if name.find(' ') != -1:
            raise ParsingError(http_status.HTTP_400_BAD_REQUEST, 'Header names cannot have spaces', name)

        if name == 'content-length':
            if not value.isnumeric():
                raise ParsingError(http_status.HTTP_400_BAD_REQUEST, 'Invalid "Content-Length" value', value)

            self._content_length = int(value)

        self._headers.append((name, value))
        self._feed()

    def feed_body(self, data: bytes) -> None:
        if self._content_length is None:
            raise ParsingError(http_status.HTTP_400_BAD_REQUEST, '"Content-Length" header required.')

        if not self._body:
            self._body = b''

        left = self._content_length - len(self._body)

        self._body += data[:left]

        if len(self._body) >= self._content_length:
            assert len(self._body) == self._content_length
            self.completed = True

    def _feed(self, data: bytes | None = None) -> None:
        if not data and not self._buf or self.completed:
            return

        if not data:
            data = self._buf
            self._buf = b''

        if self._method is None:
            self.parse_status_line(data)
            return

        if not self._reached_end_of_headers:
            self.parse_header(data)
            return

        self.feed_body(data)

    def feed(self, data: bytes) -> ParsingError | None:
        try:
            self._feed(data)
        except ParsingError as error:
            return error
        except RecursionError:
            return ParsingError(http_status.HTTP_500_INTERNAL_SERVER_ERROR, 'Could not process that many headers.')

    def get_result(self) -> HTTPRequest:
        if not self.completed:
            raise Exception('Getting the result before parsing is complete.')

        assert self._method
        assert self._url

        return {
            'method': self._method,
            'url': self._url,
            'headers': self._headers,
            'body': self._body
        }
