from flask import Flask, request
from typing import Any


METHODS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')


app = Flask(__name__)


def create_echo_response(url_params: list[str] = []) -> dict[str, Any]:
    return {
        'url_params': url_params,
        'query_params': request.args,
        'body': request.get_data(as_text=True)
    }


@app.get('/')
def index():
    return 'Blazingly Fast!\n'


@app.route('/echo', methods=METHODS)
def echo():
    return create_echo_response()


@app.route('/echo/<param1>', methods=METHODS)
@app.route('/echo/<param1>/<param2>', methods=METHODS)
@app.route('/echo/<param1>/<param2>/<param3>', methods=METHODS)
def echo_2_url_param(**params: str):
    return create_echo_response(list(params.values()))
