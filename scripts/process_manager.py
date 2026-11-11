"""Manage only this checkout's processes, checking identity before stopping them."""

from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import subprocess
import time

import psutil


class ProcessManager:
    def __init__(self, project_dir):
        self.project_dir = Path(project_dir).resolve()
        self.state_dir = self.project_dir / ".run"
        self.log_dir = self.project_dir / "logs" / "services"
        self.children = {}

    @contextmanager
    def locked(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with (self.state_dir / "manager.lock").open("a+b") as handle:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as error:
                    raise RuntimeError("Another start/stop command is already running.") from error
            else:
                import fcntl
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise RuntimeError("Another start/stop command is already running.") from error
            try:
                yield
            finally:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def state_path(self, service_id):
        return self.state_dir / f"{service_id}.json"

    def log_path(self, service_id):
        return self.log_dir / f"{service_id}.log"

    def read_state(self, service_id):
        path = self.state_path(service_id)
        if not path.exists():
            return None
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(state, dict)
                    or type(state.get("pid")) is not int or state["pid"] <= 0
                    or type(state.get("create_time")) not in (int, float)
                    or not math.isfinite(state["create_time"]) or state["create_time"] <= 0):
                raise ValueError("invalid process identity")
            return state
        except (ValueError, OSError) as error:
            raise RuntimeError(f"Cannot read {path}; inspect it before starting again.") from error

    def process(self, service_id):
        state = self.read_state(service_id)
        if not state:
            return None
        child = self.children.get(service_id)
        if child is not None and child.poll() is not None:
            return None
        try:
            process = psutil.Process(state["pid"])
            if process.create_time() != state["create_time"]:
                return None
            if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                return process
        except (psutil.NoSuchProcess, KeyError, TypeError):
            return None
        except psutil.AccessDenied as error:
            raise RuntimeError(f"Cannot inspect the process for {service_id}; check process permissions.") from error
        return None

    def start(self, service):
        service_id = service["id"]
        if self.process(service_id) is not None:
            return False
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1"}
        with self.log_path(service_id).open("ab") as output:
            output.write(f"\n--- Starting {service_id} at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n".encode())
            output.flush()
            child = subprocess.Popen(
                service["command"], cwd=self.project_dir / service.get("cwd", "."),
                env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
        self.children[service_id] = child
        try:
            process = psutil.Process(child.pid)
            state = {"pid": child.pid, "create_time": process.create_time()}
            path = self.state_path(service_id)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(state), encoding="utf-8")
            temporary.replace(path)
        except BaseException as error:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=10)
            if isinstance(error, psutil.NoSuchProcess):
                raise RuntimeError(f"{service_id} exited immediately.\n{self.tail(service_id, 30)}") from error
            raise
        return True

    def stop(self, service_id):
        process = self.process(service_id)
        if process is None:
            # A stale PID can belong to an unrelated process. Never signal it.
            self.state_path(service_id).unlink(missing_ok=True)
            return
        try:
            children = process.children(recursive=True)
        except psutil.NoSuchProcess:
            children = []
        targets = [process, *children]
        for target in targets:
            try:
                target.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(targets, timeout=5)
        for target in alive:
            try:
                target.kill()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(alive, timeout=5)
        if alive:
            raise RuntimeError(f"Could not stop all processes for {service_id}.")
        child = self.children.pop(service_id, None)
        if child is not None:
            child.wait(timeout=5)
        self.state_path(service_id).unlink(missing_ok=True)

    def tail(self, service_id, lines=50):
        from collections import deque
        path = self.log_path(service_id)
        if not path.exists():
            return f"No log yet: {path}\n"
        with path.open(encoding="utf-8", errors="replace") as log:
            return "".join(deque(log, maxlen=lines))
