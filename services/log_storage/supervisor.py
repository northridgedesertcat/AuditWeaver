"""Run independent workers with bounded restart delay and a workspace-local stop signal."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from common import env

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "logs/log-storage"


def stop():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / "stop").touch()


def run():
    if not env.get_env_bool("STORAGE_ENABLED"):
        raise RuntimeError("Set STORAGE_ENABLED=true after storage initialization")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    lock = (RUNTIME / "supervisor.lock").open("a+b")
    if os.name == "nt":
        import msvcrt
        lock.seek(0)
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stop_file = RUNTIME / "stop"
    stop_file.unlink(missing_ok=True)
    children, handles, retry = {}, {}, {}
    running = True
    def shutdown(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        while running and not stop_file.exists():
            for sink in ("ck", "es"):
                for kind in ("raw", "events"):
                    key = (sink, kind)
                    process = children.get(key)
                    if process is not None and process.poll() is not None:
                        handles.pop(key).close()
                        children.pop(key)
                        retry[key] = time.monotonic() + 10
                    if key not in children and time.monotonic() >= retry.get(key, 0):
                        handle = (RUNTIME / f"{sink}-{kind}.log").open("ab")
                        handles[key] = handle
                        children[key] = subprocess.Popen(
                            [sys.executable, "-m", "services.log_storage", "worker", "--sink", sink, "--kind", kind],
                            cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                        )
            if env.get_env_bool("ES_CLEANUP_ENABLED"):
                key = ("cleanup", "loop")
                process = children.get(key)
                if process is not None and process.poll() is not None:
                    handles.pop(key).close()
                    children.pop(key)
                    retry[key] = time.monotonic() + 10
                if key not in children and time.monotonic() >= retry.get(key, 0):
                    handle = (RUNTIME / "cleanup.log").open("ab")
                    handles[key] = handle
                    children[key] = subprocess.Popen([sys.executable, "-m", "services.log_storage", "cleanup-loop"],
                        cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            time.sleep(1)
    finally:
        for process in children.values():
            if process.poll() is None:
                process.terminate()
        for process in children.values():
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for handle in handles.values():
            handle.close()
        lock.close()
