"""Single service manifest, resolved after loading the project environment."""

import os
import shutil
import sys


FRONTEND_DIR = os.path.join("services", "website", "frontend", "v1")
BACKEND_DIR = os.path.join("services", "website", "backend", "v1")


class ServiceConfig:
    def __init__(self, env=None, python=None):
        env = os.environ if env is None else env
        python = python or sys.executable
        django_port = int(env.get("DJANGO_PORT", "8000"))
        frontend_port = int(env.get("FRONTEND_PORT", "3000"))
        agent_port = int(env.get("AE_BACKEND_PORT", "8001"))
        agent_host = env.get("AE_BACKEND_HOST", "127.0.0.1")
        probe_host = "127.0.0.1" if agent_host == "0.0.0.0" else agent_host
        node = shutil.which("node") or "node"
        self.services = [
            {
                "id": "rule_engine", "cwd": ".",
                "command": [python, "-m", "services.ruleEngine.main"],
                "startup_grace": 3,
            },
            {
                "id": "agent_service", "cwd": ".",
                "command": [python, "-m", "uvicorn", "services.agent_service.backend.main:app",
                            "--host", agent_host, "--port", str(agent_port)],
                "port": agent_port, "host": probe_host,
                "health_url": f"http://{probe_host}:{agent_port}/agent/health",
            },
            {
                "id": "agent", "cwd": os.path.join("services", "agent"),
                "command": [python, "main.py"], "startup_grace": 3,
            },
            {
                "id": "django", "cwd": BACKEND_DIR,
                "command": [python, "manage.py", "runserver", f"0.0.0.0:{django_port}", "--noreload"],
                "port": django_port, "host": "127.0.0.1",
                "health_url": f"http://localhost:{django_port}/api/v1/health/",
            },
            {
                "id": "frontend", "cwd": FRONTEND_DIR,
                "command": [node, "node_modules/next/dist/bin/next", "dev", "--port", str(frontend_port)],
                "port": frontend_port, "host": "127.0.0.1",
                "health_url": f"http://127.0.0.1:{frontend_port}/login/",
                "startup_timeout": 120,
            },
        ]
        self.steps = [
            {"id": "elasticsearch", "url": f"{env.get('ES_SCHEME', 'http')}://{env.get('ES_HOST', 'localhost')}:{env.get('ES_PORT', '19200')}/"},
            {"id": "kafka", "address": env.get("KAFKA_BROKERS", f"localhost:{env.get('KAFKA_PORT', '29092')}").split(",")[0]},
            {"id": "mysql", "address": f"{env.get('MYSQL_HOST', 'localhost')}:{env.get('MYSQL_PORT', '13306')}"},
            {"id": "kafka_connect", "url": f"http://{env.get('KAFKA_CONNECT_HOST', 'localhost')}:{env.get('KAFKA_CONNECT_PORT', '8083')}/connectors"},
            {"id": "kafka_topics", "command": [python, "docker/config/kafka/topics/create-init-topics.py", "--brokers", env.get("KAFKA_BROKERS", f"localhost:{env.get('KAFKA_PORT', '29092')}")]},
            {"id": "es_mapping", "command": [python, "docker/config/elasticsearch/creatMapping.py"]},
            {"id": "connectors", "command": [python, "docker/config/kafka-connect/init-connectors.py", "--connect-host", env.get("KAFKA_CONNECT_HOST", "localhost"), "--connect-port", env.get("KAFKA_CONNECT_PORT", "8083")]},
            {"id": "django_check", "cwd": BACKEND_DIR, "command": [python, "manage.py", "check"]},
            {"id": "django_migrate", "cwd": BACKEND_DIR, "command": [python, "manage.py", "migrate", "--noinput"]},
        ]

    def get_services(self):
        return self.services

    def get_steps(self, service_ids=None):
        if service_ids is None:
            return self.steps
        dependencies = {
            "rule_engine": {"elasticsearch", "kafka", "kafka_connect", "kafka_topics", "es_mapping", "connectors"},
            "agent": {"elasticsearch", "kafka", "kafka_connect", "kafka_topics", "es_mapping", "connectors", "mysql", "django_check", "django_migrate"},
            "agent_service": {"elasticsearch", "es_mapping", "mysql", "django_check", "django_migrate"},
            "django": {"mysql", "django_check", "django_migrate"},
            "frontend": set(),
        }
        required = set().union(*(dependencies[name] for name in service_ids))
        return [step for step in self.steps if step["id"] in required]
