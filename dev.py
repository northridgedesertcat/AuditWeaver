"""Cross-platform development entry point. Run `python dev.py --help`."""

import argparse
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent


def parse_args(argv):
    parser = argparse.ArgumentParser(description="AuditWeaver development tools")
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("start", "stop", "status", "logs"):
        command = commands.add_parser(action)
        command.add_argument("services", nargs="*", help="Service IDs; default: all")
        if action in ("start", "stop", "status"):
            command.add_argument("--no-docker", action="store_true", help="Leave Docker lifecycle to you")
        if action == "start":
            command.add_argument("--tools", action="store_true", help="Also start Kibana")
        if action == "logs":
            command.add_argument("--tail", type=int, default=50)
            command.add_argument("--follow", action="store_true")
    commands.add_parser("doctor", help="Check the local environment without starting services")
    check = commands.add_parser("check", help="Run offline unit, type and code checks")
    check.add_argument("--python-only", action="store_true")
    check.add_argument("--build", action="store_true", help="Also build the frontend")
    return parser.parse_args(argv)


def run(command, cwd=ROOT, **kwargs):
    kwargs.setdefault("env", {**os.environ, "PYTHONUTF8": "1"})
    return subprocess.run(command, cwd=cwd, check=True, **kwargs)


def select_services(config, names):
    services = config.get_services()
    unknown = set(names) - {service["id"] for service in services}
    if unknown:
        raise RuntimeError(f"Unknown services: {', '.join(sorted(unknown))}")
    return [service for service in services if not names or service["id"] in names]


def probe_service(service):
    from scripts.utils import http_ready
    return not service.get("health_url") or http_ready(service["health_url"])


def wait_for_process(manager, service):
    service_id = service["id"]
    deadline = time.monotonic() + service.get("startup_timeout", 60)
    started = time.monotonic()
    while time.monotonic() < deadline:
        if manager.process(service_id) is None:
            raise RuntimeError(f"{service_id} exited during startup.\n{manager.tail(service_id, 30)}")
        if service.get("health_url"):
            if probe_service(service):
                return
        elif time.monotonic() - started >= service.get("startup_grace", 3):
            return
        time.sleep(0.25)
    raise RuntimeError(f"{service_id} did not become ready.\n{manager.tail(service_id, 30)}")


def initialize(config, service_ids):
    from scripts.utils import http_ready, tcp_ready, wait_until, redis_readiness_check
    for step in config.get_steps(service_ids):
        print(f"[init] {step['id']}", flush=True)
        if "command" in step:
            run(step["command"], cwd=ROOT / step.get("cwd", "."), timeout=180)
        else:
            probe = (lambda: http_ready(step["url"])) if "url" in step else (lambda: tcp_ready(step["address"]))
            if not wait_until(probe, timeout=120):
                raise RuntimeError(f"Dependency {step['id']} is not ready. Startup aborted.")
    if "agent_service" not in service_ids:
        return
    ready, _ = redis_readiness_check(
        os.environ.get("AE_MEMORY_BACKEND", "memory"), os.environ.get("AE_MEMORY_REDIS_URL", ""),
    )
    if not ready:
        raise RuntimeError("Agent Redis readiness check failed.")


def start_services(config, manager, docker, args):
    services = select_services(config, args.services)
    needs_backend = any(service["id"] != "frontend" for service in services)
    if needs_backend and not (ROOT / ".env").exists():
        raise RuntimeError("Missing .env. Copy .env.example to .env and configure it first.")
    if needs_backend and not os.environ.get("DJANGO_SECRET_KEY"):
        raise RuntimeError("DJANGO_SECRET_KEY must be set in .env or the environment.")
    if any(service["id"] == "agent_service" for service in services) and not os.environ.get("AE_LLM_MODEL"):
        raise RuntimeError("AE_LLM_MODEL must be configured before starting Agent Service.")
    from scripts.utils import tcp_ready
    # Detect conflicts before starting containers or running migrations.
    pending = []
    for service in services:
        if manager.process(service["id"]) is not None:
            continue
        pending.append(service["id"])
        if service.get("port") and tcp_ready(f"{service['host']}:{service['port']}"):
            raise RuntimeError(f"Port {service['port']} is already in use by an unmanaged process ({service['id']}).")
    if not args.no_docker:
        docker.start_services(profiles=("tools",) if args.tools else ())
    initialize(config, pending)
    started = []
    try:
        for service in services:
            print(f"[start] {service['id']}", flush=True)
            if manager.start(service):
                started.append(service["id"])
            wait_for_process(manager, service)
        for service in services:
            if manager.process(service["id"]) is None or not probe_service(service):
                raise RuntimeError(f"{service['id']} failed before startup completed.\n{manager.tail(service['id'], 30)}")
    except BaseException:
        for service_id in reversed(started):
            try:
                manager.stop(service_id)
            except Exception as error:
                print(f"[cleanup] {service_id}: {error}", file=sys.stderr)
        raise
    print("Selected services started. Workers passed a process-survival check, not an end-to-end pipeline check.")
    for service in services:
        print(f"  {service['id']}: {service.get('health_url', 'running (worker)')}")
    print(f"Logs: {manager.log_dir}")


def stop_services(config, manager, docker, args):
    errors = []
    for service in reversed(select_services(config, args.services)):
        try:
            manager.stop(service["id"])
            print(f"[stop] {service['id']}")
        except Exception as error:
            errors.append(f"{service['id']}: {error}")
    if errors:
        raise RuntimeError("\n".join(errors))
    if not args.no_docker and not args.services:
        docker.stop_services()


def show_status(config, manager, docker, args):
    healthy = True
    for service in select_services(config, args.services):
        process = manager.process(service["id"])
        ready = process is not None and probe_service(service)
        state = "running" if ready else "unhealthy" if process else "stopped"
        print(f"{service['id']:16} {state:10} {f'PID {process.pid}' if process else ''}")
        healthy = healthy and ready
    if not args.no_docker:
        try:
            docker.run("ps", "--all", profiles=("tools",))
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"Docker status unavailable: {error}", file=sys.stderr)
            healthy = False
    return 0 if healthy else 1


def show_logs(config, manager, args):
    services = select_services(config, args.services)
    if args.tail < 1:
        raise RuntimeError("--tail must be at least 1")
    offsets = {}
    for service in services:
        name = service["id"]
        path = manager.log_path(name)
        # Capture the offset first so writes during the initial tail are not lost.
        offsets[name] = path.stat().st_size if path.exists() else 0
        print(f"--- {name} ---\n{manager.tail(name, args.tail)}", end="", flush=True)
    while args.follow:
        for service in services:
            name = service["id"]
            path = manager.log_path(name)
            if path.exists():
                with path.open("rb") as stream:
                    if path.stat().st_size < offsets[name]:
                        offsets[name] = 0
                    stream.seek(offsets[name])
                    data = stream.read()
                    offsets[name] = stream.tell()
                if data:
                    print(f"[{name}] {data.decode('utf-8', errors='replace')}", end="", flush=True)
        time.sleep(0.3)


def doctor(docker):
    from scripts.config import FRONTEND_DIR
    from importlib.metadata import PackageNotFoundError, version
    checks = [("Python >=3.12", sys.version_info >= (3, 12)),
              ("Isolated Python environment", sys.prefix != sys.base_prefix),
              ("Project .env exists", (ROOT / ".env").exists()),
              ("DJANGO_SECRET_KEY configured", bool(os.environ.get("DJANGO_SECRET_KEY"))),
              ("REDIS_PASSWORD configured", bool(os.environ.get("REDIS_PASSWORD"))),
              ("AE_LLM_MODEL configured for Agent Service", bool(os.environ.get("AE_LLM_MODEL")))]
    print(f"Python: {sys.executable}")
    for package in ("Django", "django-cors-headers", "psutil", "uvicorn", "confluent-kafka", "langchain-mcp-adapters"):
        try:
            print(f"  {package}: {version(package)}")
        except PackageNotFoundError:
            checks.append((f"{package} installed", False))
    for binary in ("node", "npm", "docker"):
        checks.append((f"{binary} available", shutil.which(binary) is not None))
    if shutil.which("node"):
        node = subprocess.check_output(["node", "--version"], text=True).strip()
        parts = tuple(int(part) for part in node.lstrip("v").split("."))
        checks.append((f"Node {node}: 22.13+ (22.x) or 24+",
                       (parts[0] == 22 and parts >= (22, 13, 0)) or parts[0] >= 24))
    checks.append(("Frontend dependencies installed", (ROOT / FRONTEND_DIR / "node_modules" / ".bin" / "next").exists()))
    if shutil.which("docker"):
        checks.append(("Docker engine running", docker.check_docker_running()))
    for label, ok in checks:
        print(f"[{'OK' if ok else 'MISSING'}] {label}")
    return 0 if all(ok for _, ok in checks) else 1


def check_project(args):
    from scripts.config import BACKEND_DIR, FRONTEND_DIR
    run([sys.executable, "-m", "pip", "check"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "scripts/tests", "-v"])
    run([sys.executable, "-m", "unittest", "core.stable.retry.test_retry",
         "core.stable.circuit_breaker.test_circuit_breaker", "services.ruleEngine.tests.test_pipeline", "-v"])
    for test in ("test_main_retry.py", "test_main_degradation.py"):
        run([sys.executable, str(ROOT / "services" / "agent" / "tests" / test), "-v"])
    env = {**os.environ, "DJANGO_SECRET_KEY": os.environ.get("DJANGO_SECRET_KEY") or "offline-check-only-not-for-deployment"}
    run([sys.executable, "manage.py", "check"], cwd=ROOT / BACKEND_DIR, env=env)
    if not args.python_only:
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            raise RuntimeError("npm not found. Install Node.js 22 LTS.")
        for command in ("test", "check", "build") if args.build else ("test", "check"):
            run([npm, "run", command], cwd=ROOT / FRONTEND_DIR)
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if python.exists() and Path(sys.prefix).resolve() != python.parent.parent.resolve():
        return subprocess.call([str(python), str(ROOT / "dev.py"), *argv])
    if sys.version_info < (3, 12):
        print("Python 3.12+ required; Python 3.13 recommended.", file=sys.stderr)
        return 1
    if args.action == "start" and sys.prefix == sys.base_prefix:
        print("Create and install a virtual environment first: python -m venv .venv", file=sys.stderr)
        return 1
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
        from scripts.docker_manager import DockerManager
        docker = DockerManager(ROOT)
        if args.action == "doctor":
            return doctor(docker)
        if args.action == "check":
            return check_project(args)
        from scripts.config import ServiceConfig
        from scripts.process_manager import ProcessManager
        config, manager = ServiceConfig(), ProcessManager(ROOT)
        if args.action == "status":
            return show_status(config, manager, docker, args)
        if args.action == "logs":
            show_logs(config, manager, args)
        else:
            with manager.locked():
                if args.action == "start":
                    start_services(config, manager, docker, args)
                else:
                    stop_services(config, manager, docker, args)
        return 0
    except ImportError as error:
        print(f"Missing Python dependency: {error}. Run python -m pip install -r requirements.txt in .venv.", file=sys.stderr)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
