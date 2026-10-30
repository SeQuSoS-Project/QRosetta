"""The shared runner or compiler scaffolding around ``_isolated_fixture.sleeps_from_circuit``,
served by uvicorn on 127.0.0.1 (V7-08 tests):
python -m tests.unit._watcher_server <runner|compiler> <loop> <http> <port>."""

import sys

import uvicorn
from fastapi import FastAPI

from qrosetta_commons.compile_service import register_compiler_endpoint
from qrosetta_commons.helpers import register_runner_endpoints
from tests.unit import _isolated_fixture as fx


def build(kind: str) -> FastAPI:
    app = FastAPI()
    if kind == "runner":
        register_runner_endpoints(app, fx.sleeps_from_circuit, fx.sleeps_from_circuit, max_concurrent=1)
    else:
        register_compiler_endpoint(app, fx.sleeps_from_circuit, max_concurrent=1)
    return app


if __name__ == "__main__":
    kind, loop, http, port = sys.argv[1:5]
    uvicorn.run(build(kind), host="127.0.0.1", port=int(port), loop=loop, http=http, log_level="warning")
