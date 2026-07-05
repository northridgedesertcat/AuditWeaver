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


DJANGO_SECRET_KEY = get_env('DJANGO_SECRET_KEY')
DJANGO_DEBUG = get_env_bool('DJANGO_DEBUG', True)
DJANGO_ALLOWED_HOSTS = get_env('DJANGO_ALLOWED_HOSTS', 'localhost')
DJANGO_PORT = get_env_int('DJANGO_PORT', 8000)

ES_HOST = get_env('ES_HOST', 'localhost')
ES_PORT = get_env_int('ES_PORT', 19200)
ES_USER = get_env('ES_USER', 'elastic')
ES_PASSWORD = get_env('ES_PASSWORD', 'password')
ES_SCHEME = get_env('ES_SCHEME', 'http')

KAFKA_BROKERS = get_env('KAFKA_BROKERS', 'localhost:29092')

DIFY_BASE_URL = get_env('DIFY_BASE_URL', 'http://localhost/v1')
DIFY_API_KEY = get_env('DIFY_API_KEY', '')
DIFY_TIMEOUT = get_env_int('DIFY_TIMEOUT', 60)

NEXT_PUBLIC_API_BASE = get_env('NEXT_PUBLIC_API_BASE', 'http://localhost:8000')

LOG_LEVEL = get_env('LOG_LEVEL', 'INFO')
