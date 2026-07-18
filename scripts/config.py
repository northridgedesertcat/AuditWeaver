import os

DEFAULT_CONFIG = {
    "env": {
        "es_port": {"env_key": "ES_PORT", "default": "19200"},
        "kafka_brokers": {"env_key": "KAFKA_BROKERS", "default": "localhost:29092"},
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
            "host": "localhost",
            "port_env_key": "KAFKA_BROKERS",
            "default_port": "29092",
            "max_retries": 5,
            "retry_delay": 3,
            "post_delay": 4,
        },
        "kafka_connect": {
            "type": "http",
            "host": "localhost",
            "default_port": "8083",
            "max_retries": 20,
            "retry_delay": 5,
            "post_delay": 0,
        },
    },
    "scripts": {
        "es_mapping": {
            "path": os.path.join("docker", "config", "elasticsearch", "creatMapping.py"),
        },
    },
    "connectors": {
        "log_structured_sink": {
            "path": os.path.join("docker", "config", "kafka-connect", "connectors", "log-structured-sink.json"),
            "connect_host": "localhost",
            "connect_port": 8083,
        },
    },
    "services": [
        {
            "id": "docker",
            "name": "Starting Docker Compose services",
            "type": "docker",
            "description": "Kafka, Elasticsearch, Kibana, Logstash",
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
            "id": "kafka_connect_connector",
            "name": "Creating Kafka Connect Connectors",
            "type": "connector",
            "connector_config": "log_structured_sink",
        },
        {
            "id": "rules_matching",
            "name": "Starting Rules Matching Engine",
            "type": "window",
            "window_title": "RulesMatching",
            "command": "python main.py",
            "cwd": os.path.join("services", "rulesMatching"),
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
    
    def get_env_config(self, key):
        return self.config["env"].get(key, {})
    
    def get_wait_config(self, key):
        return self.config["wait"].get(key, {})
    
    def get_script_config(self, key):
        return self.config["scripts"].get(key, {})
    
    def get_connector_config(self, key):
        return self.config["connectors"].get(key, {})
    
    def get_docker_config(self):
        return self.config["docker"]
    
    def get_services(self):
        return self.config["services"]
    
    def get_service_by_id(self, service_id):
        for service in self.config["services"]:
            if service["id"] == service_id:
                return service
        return None
    
    def add_service(self, service):
        self.config["services"].append(service)
    
    def remove_service(self, service_id):
        self.config["services"] = [s for s in self.config["services"] if s["id"] != service_id]
    
    def update_service(self, service_id, updates):
        for service in self.config["services"]:
            if service["id"] == service_id:
                service.update(updates)
                return True
        return False