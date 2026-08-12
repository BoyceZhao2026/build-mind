#!/usr/bin/env python3
import os
import signal
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
(LOGS / "model-calls.jsonl").touch(exist_ok=True)


def start(command: list[str], cwd: Path, log_name: str) -> tuple[subprocess.Popen, object]:
    stream = (LOGS / log_name).open("a", encoding="utf-8", buffering=1)
    stream.write("\n=== starting: " + " ".join(command) + " ===\n")
    environment = os.environ.copy()
    environment["NO_PROXY"] = "*"
    environment["no_proxy"] = "*"
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=stream,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return process, stream


api, api_log = start(
    [str(ROOT / "api" / ".venv" / "bin" / "uvicorn"), "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    ROOT / "api",
    "api.log",
)
web, web_log = start(["npm", "run", "dev"], ROOT / "web", "web.log")
processes = [api, web]


def stop(*_: object) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
print("Demo started: http://localhost:3000")
print(f"API log: {LOGS / 'api.log'}")
print(f"Web log: {LOGS / 'web.log'}")
print(f"Model log: {LOGS / 'model-calls.jsonl'}")

try:
    while all(process.poll() is None for process in processes):
        signal.pause()
finally:
    stop()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    api_log.close()
    web_log.close()
    failed = [process.returncode for process in processes if process.returncode not in (0, -signal.SIGTERM)]
    sys.exit(1 if failed else 0)
