import os
import sys

_services_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _services_path not in sys.path:
    sys.path.insert(0, _services_path)
from common.env import (
    KAFKA_CONNECT_HOST,
    KAFKA_CONNECT_PORT,
    AE_BACKEND_HOST,
    AE_BACKEND_PORT,
)

DEFAULT_CONFIG = {
    "env": {
        "django_port": {"env_key": "DJANGO_PORT", "default": "8000"},
        "frontend_port": {"env_key": "FRONTEND_PORT", "default": "3000"},
    },
    "docker": {
        "compose_file": os.path.join("docker", "docker-compose.yml"),
    },
    "wait": {
        "elasticsearch": {
            "type": "http",
            "host": "localhost",
            "port_env_key": "ES_PORT",
            "default_port": "19200",
            "max_retries": 10,
            "retry_delay": 5,
            "post_delay": 10,
        },
        "kafka": {
            "type": "tcp",
            "host_env_key": "KAFKA_BROKERS",
            "default_host": "localhost",
            "port_env_key": "KAFKA_BROKERS",
            "default_port": "29092",
            "max_retries": 5,
            "retry_delay": 3,
            "post_delay": 4,
        },
        "kafka_connect": {
            "type": "http",
            "host": KAFKA_CONNECT_HOST,
            "default_port": KAFKA_CONNECT_PORT,
            "max_retries": 20,
            "retry_delay": 5,
            "post_delay": 0,
        },
        "mysql": {
            "type": "tcp",
            "host_env_key": "MYSQL_HOST",
            "default_host": "localhost",
            "port_env_key": "MYSQL_PORT",
            "default_port": "13306",
            "max_retries": 30,
            "retry_delay": 2,
            "post_delay": 3,
        },
    },
    "scripts": {
        "kafka_topics": {
            "path": os.path.join("docker", "config", "kafka", "topics", "create-init-topics.py"),
        },
        "init_connectors": {
            "path": os.path.join("docker", "config", "kafka-connect", "init-connectors.py"),
        },
        "es_mapping": {
            "path": os.path.join("docker", "config", "elasticsearch", "creatMapping.py"),
        },
        "django_migrate": {
            "command": "python manage.py makemigrations accounts && python manage.py migrate && python manage.py init_admin",
            "cwd": os.path.join("services", "website", "backend", "v1"),
        },
    },
    "services": [
        {
            "id": "docker",
            "name": "Starting Docker Compose services",
            "type": "docker",
            "description": "Kafka, Elasticsearch, Kibana, Logstash, MySQL",
        },
        {
            "id": "wait_es",
            "name": "Waiting for Elasticsearch to be ready",
            "type": "wait",
            "wait_type": "http",
            "wait_config": "elasticsearch",
        },
        {
            "id": "wait_kafka",
            "name": "Waiting for Kafka to be ready",
            "type": "wait",
            "wait_type": "tcp",
            "wait_config": "kafka",
        },
        {
            "id": "init_kafka_topics",
            "name": "Initializing Kafka Topics",
            "type": "script",
            "script_config": "kafka_topics",
        },
        {
            "id": "es_mapping",
            "name": "Creating Elasticsearch Indexes",
            "type": "script",
            "script_config": "es_mapping",
        },
        {
            "id": "wait_kafka_connect",
            "name": "Waiting for Kafka Connect to be ready",
            "type": "wait",
            "wait_type": "http",
            "wait_config": "kafka_connect",
        },
        {
            "id": "init_kafka_connectors",
            "name": "Initializing Kafka Connect Connectors",
            "type": "script",
            "script_config": "init_connectors",
        },
        {
            "id": "rule_engine",
            "name": "Starting Rule Engine",
            "type": "window",
            "window_title": "RuleEngine",
            "command": "python -m services.ruleEngine.main",
            "cwd": os.path.join("services", "ruleEngine", "..", ".."),
            "post_delay": 5,
            "description": "Processes Kafka logs (input: log.audit, output: log.analysis)",
        },
        {
            "id": "agent",
            "name": "Starting Agent Module",
            "type": "window",
            "window_title": "AgentModule",
            "command": "python main.py",
            "cwd": os.path.join("services", "agent"),
            "post_delay": 3,
            "description": "AI analysis (input: log.analysis)",
        },
        {
            "id": "agent_service",
            "name": "Starting Agent Service (FastAPI)",
            "type": "window",
            "window_title": "AgentService",
            # 必须从项目根目录启动:子进程(MCP Skills)需继承项目根为 cwd,
            # 才能 import common 并解析 services 包
            "command": f"python -m uvicorn services.agent_service.backend.main:app --host {AE_BACKEND_HOST} --port {AE_BACKEND_PORT}",
            "cwd": ".",
            "post_delay": 3,
            "port": AE_BACKEND_PORT,
            "description": "Agent Service (FastAPI, 内部 :8001,反代给 Django)",
        },
        {
            "id": "wait_mysql",
            "name": "Waiting for MySQL to be ready",
            "type": "wait",
            "wait_type": "tcp",
            "wait_config": "mysql",
        },
        {
            "id": "django_migrate",
            "name": "Running Django migrations & init admin",
            "type": "shell",
            "script_config": "django_migrate",
        },
        {
            "id": "django",
            "name": "Starting Django Backend",
            "type": "window",
            "window_title": "DjangoBackend",
            "command": "python manage.py runserver 0.0.0.0:8000",
            "cwd": os.path.join("services", "website", "backend", "v1"),
            "post_delay": 3,
            "port": 8000,
            "description": "Django Backend",
        },
        {
            "id": "frontend",
            "name": "Starting Next.js Frontend",
            "type": "window",
            "window_title": "NextJSFrontend",
            "command": "npm run dev",
            "cwd": os.path.join("services", "website", "frontend", "v1"),
            "post_delay": 0,
            "port": 3000,
            "description": "Next.js Frontend",
        },
    ],
}


class ServiceConfig:
    def __init__(self, config=None):
        self.config = config or DEFAULT_CONFIG
    
    def get_wait_config(self, key):
        return self.config["wait"].get(key, {})
    
    def get_script_config(self, key):
        return self.config["scripts"].get(key, {})
    
    def get_docker_config(self):
        return self.config["docker"]
    
    def get_services(self):
        return self.config["services"]
