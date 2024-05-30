# Pegasus
A blazingly fast WSGI web server written from scratch ([gunicorn](https://github.com/benoitc/gunicorn) killer).

# Benchmarks
These benchmarks prove the superiority of [pegasus](https://github.com/MarcosTypeAP/pegasus) over [gunicorn](https://github.com/benoitc/gunicorn).

Testing 400 simultaneous connections for 10 seconds using [wrk](https://github.com/wg/wrk)*.

### Pegasus
```shell
$ python3 pegasus --host 127.0.0.1 flaskapp:app > /dev/null
```
```shell
wrk -t4 -c400 -d10s http://127.0.0.1:8080
Running 10s test @ http://127.0.0.1:8080
  4 threads and 400 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   135.90ms   18.20ms 258.12ms   89.91%
    Req/Sec   734.05    172.34     1.01k    66.75%
  29248 requests in 10.07s, 3.65MB read
Requests/sec:   2904.97
Transfer/sec:    371.63KB
```
<sub>_*Benchmark done on Ubuntu Server with an i5 7400 and 16 GB of RAM_</sub>

### Gunicorn
```shell
$ gunicorn --bind 127.0.0.1:8080 flaskapp:app 2> /dev/null
```
```shell
wrk -t4 -c400 -d10s http://127.0.0.1:8080
Running 10s test @ http://127.0.0.1:8080
  4 threads and 400 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     1.02s   565.36ms   1.99s    58.47%
    Req/Sec    37.13     18.68   131.00     82.69%
  1214 requests in 10.08s, 200.36KB read
  Socket errors: connect 0, read 0, write 0, timeout 978
Requests/sec:    120.46
Transfer/sec:     19.88KB
```
<sub>_*Benchmark done on a Windows Vista PC without any reinstallation and continuous use for 13 years with a Celeron G1610 and 2 GB of RAM_</sub>

### Conclusion
Obviously, as you can see **pegasus**** is far superior with a 24x performance increase*.

<sub>*_The details of how benchmarking is done are negligible because of how superior pegasus is._</sub>
<br/>
<sub>**_It is not recommended to use pegasus in production, nor in development. Just use gunicorn._</sub>

# Installation
```shell
$ git clone https://github.com/MarcosTypeAP/pegasus.git
$ cd pegasus
```

# Usage
```shell
$ python3 pegasus --help
usage: pegasus [-h] [--chdir DIR] [--host ADDR] [--port PORT] [--threads INT] [--backlog INT] [MODULE:APP]

A blazingly fast WSGI web server.

positional arguments:
  MODULE:APP     WSGI application to be used. Uses an echo app by default.

options:
  -h, --help     show this help message and exit
  --chdir DIR    Change directory. Uses the current working directory by default. [/tmp/pegasus]
  --host ADDR    Address to which the server will bind. [0.0.0.0]
  --port PORT    Port to which the server will bind. [8080]
  --threads INT  The maximum number of active threads handling requests. Uses os.cpu_count() * 2 by default. [8]
  --backlog INT  The maximum number of pending connections before refusing new connections.
                 If negative, a default reasonable value is chosen by the system. [1024]
```

### Example (default echo WSGI app)
```shell
# Shell 1
$ python3 pegasus --host 127.0.0.1
INFO: Listen at "127.0.0.1:8080"
INFO: Threads: 8
INFO: 127.0.0.1:55058 - "POST / HTTP/1.1" 200 OK
```

```shell
# Shell 2
$ curl -X POST "http://127.0.0.1:8080" -d '{"foo": "echo", "bar": 69}' -s | jq
{
  "foo": "echo",
  "bar": 69
}
```

### Example (echo Flask app)
```shell
# Create a virtual environment and install Flask
$ python3 -m venv .venv
$ source .venv/bin/activate
$ python3 -m pip install -U Flask
```

```shell
# Shell 1
$ python3 pegasus --host 127.0.0.1 flaskapp:app
INFO: Listen at "127.0.0.1:8080"
INFO: Threads: 8
INFO: 127.0.0.1:60644 - "GET / HTTP/1.1" 200 OK
INFO: 127.0.0.1:32848 - "POST /echo/a/b/c?foo=echo&bar=69 HTTP/1.1" 200 OK
```

```shell
# Shell 2
$ curl "http://127.0.0.1:8080"
Blazingly Fast!

$ curl -X POST "http://127.0.0.1:8080/echo/a/b/c?foo=echo&bar=69" -d "Some data" -s | jq
{
  "body": "Some data",
  "query_params": {
    "bar": "69",
    "foo": "echo"
  },
  "url_params": [
    "a",
    "b",
    "c"
  ]
}
```
