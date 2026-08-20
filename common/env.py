import os
from pathlib import Path

_env_loaded = False


def _load_env():
    global _env_loaded
    if _env_loaded:
        return
    
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / '.env'
    
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=env_path, override=False)
        except ImportError:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        os.environ.setdefault(key, value)
    
    _env_loaded = True


def get_env(key: str, default: str = '') -> str:
    _load_env()
    return os.environ.get(key, default)


def get_env_int(key: str, default: int = 0) -> int:
    _load_env()
    value = os.environ.get(key)
    if value is not None:
        try:
            return int(value)
        except ValueError:
            pass
    return default


def get_env_bool(key: str, default: bool = False) -> bool:
    _load_env()
    value = os.environ.get(key, '').lower()
    return value in ('true', '1', 'yes', 'on')


def get_env_float(key: str, default: float = 0.0) -> float:
    _load_env()
    value = os.environ.get(key)
    if value is not None:
        try:
            return float(value)
        except ValueError:
            pass
    return default


DJANGO_SECRET_KEY = get_env('DJANGO_SECRET_KEY')
DJANGO_DEBUG = get_env_bool('DJANGO_DEBUG', True)
DJANGO_ALLOWED_HOSTS = get_env('DJANGO_ALLOWED_HOSTS', 'localhost')
DJANGO_PORT = get_env_int('DJANGO_PORT', 8000)
DJANGO_CORS_ALLOW_ALL_ORIGINS = get_env_bool('DJANGO_CORS_ALLOW_ALL_ORIGINS', True)
DJANGO_TIME_ZONE = get_env('DJANGO_TIME_ZONE', 'UTC')

ES_HOST = get_env('ES_HOST', 'localhost')
ES_PORT = get_env_int('ES_PORT', 19200)
ES_USER = get_env('ES_USER', 'elastic')
ES_PASSWORD = get_env('ES_PASSWORD', 'password')
ES_SCHEME = get_env('ES_SCHEME', 'http')
ES_USE_SSL = get_env_bool('ES_USE_SSL', False)
ES_VERIFY_CERTS = get_env_bool('ES_VERIFY_CERTS', False)

KAFKA_PORT = get_env_int('KAFKA_PORT', 29092)
KAFKA_BROKERS = get_env('KAFKA_BROKERS', f'localhost:{KAFKA_PORT}')
KAFKA_CONNECT_HOST = get_env('KAFKA_CONNECT_HOST', 'localhost')
KAFKA_CONNECT_PORT = get_env_int('KAFKA_CONNECT_PORT', 8083)

KAFKA_TOPIC_RAW = get_env('KAFKA_TOPIC_RAW', 'log.raw')
KAFKA_TOPIC_STRUCTURED = get_env('KAFKA_TOPIC_STRUCTURED', 'log.structured')
KAFKA_TOPIC_ANALYSIS = get_env('KAFKA_TOPIC_ANALYSIS', 'log.analysis')
KAFKA_TOPIC_RISK = get_env('KAFKA_TOPIC_RISK', 'log.risk')

ES_INDEX_MATCHED_LOGS = get_env('ES_INDEX_MATCHED_LOGS', 'matched_logs')
ES_INDEX_ANALYSIS_REPORTS = get_env('ES_INDEX_ANALYSIS_REPORTS', 'log_analysis_reports')
ES_INDEX_NGINX_RAW = get_env('ES_INDEX_NGINX_RAW', 'nginx-log-raw')

DIFY_BASE_URL = get_env('DIFY_BASE_URL', 'http://localhost/v1')
DIFY_API_KEY = get_env('DIFY_API_KEY', '')
DIFY_TIMEOUT = get_env_int('DIFY_TIMEOUT', 60)

NEXT_PUBLIC_API_BASE = get_env('NEXT_PUBLIC_API_BASE', 'http://localhost:8000')

LOG_LEVEL = get_env('LOG_LEVEL', 'INFO')

ZOOKEEPER_PORT = get_env_int('ZOOKEEPER_PORT', 2181)
KIBANA_PORT = get_env_int('KIBANA_PORT', 5601)

# Agent Service(FastAPI,对内,只服务 Django)
AE_BACKEND_HOST = get_env('AE_BACKEND_HOST', '127.0.0.1')
AE_BACKEND_PORT = get_env_int('AE_BACKEND_PORT', 8001)

# Django 反代目标(Django → FastAPI)
AGENT_FASTAPI_BASE = get_env('AGENT_FASTAPI_BASE', f'http://{AE_BACKEND_HOST}:{AE_BACKEND_PORT}')
