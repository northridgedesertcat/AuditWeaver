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
                        # 剥离行内注释(对齐 python-dotenv:仅引号外的 ' #' 之后为注释)
                        if value and value[0] in ('"', "'"):
                            quote = value[0]
                            end = value.find(quote, 1)
                            if end != -1:
                                value = value[1:end]
                        elif ' #' in value:
                            value = value[:value.find(' #')].rstrip()
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

# ========== 分析后端切换(services/agent 管线) ==========
ANALYSIS_BACKEND = get_env('ANALYSIS_BACKEND', 'dify')  # dify | langgraph

# LangGraph 后端 → agent_service 内网地址(默认复用 AGENT_FASTAPI_BASE)
AGENT_SERVICE_BASE_URL = get_env('AGENT_SERVICE_BASE_URL', AGENT_FASTAPI_BASE)
AGENT_SERVICE_TIMEOUT = get_env_int('AGENT_SERVICE_TIMEOUT', DIFY_TIMEOUT)

# MySQL
MYSQL_HOST = get_env('MYSQL_HOST', 'localhost')
MYSQL_PORT = get_env_int('MYSQL_PORT', 13306)
MYSQL_DATABASE = get_env('MYSQL_DATABASE', 'auditweaver')
MYSQL_USER = get_env('MYSQL_USER', 'auditweaver')
MYSQL_PASSWORD = get_env('MYSQL_PASSWORD', 'auditweaver')
MYSQL_ROOT_PASSWORD = get_env('MYSQL_ROOT_PASSWORD', 'rootpass')

# Redis(Docker 单容器,对外端口 16379)
# ⚠️ 密码无默认值:redis 模式下未配置 REDIS_URL/REDIS_PASSWORD 时应 fast fail,不静默使用弱密码
REDIS_URL = get_env('REDIS_URL')
REDIS_PASSWORD = get_env('REDIS_PASSWORD')
REDIS_PORT = get_env_int('REDIS_PORT', 16379)

# Agent Service 会话历史(LangGraph checkpointer)
# memory(默认):进程内 MemorySaver,不依赖 Redis;redis:使用 RedisSaver 持久化到 Redis。
# AE_MEMORY_REDIS_URL 不给弱默认值:redis 模式下未配置时由启动检查 / redis.py fast fail,
# 不静默连到无密码的 localhost:6379。
AE_MEMORY_BACKEND = get_env('AE_MEMORY_BACKEND', 'memory')
AE_MEMORY_REDIS_URL = get_env('AE_MEMORY_REDIS_URL')

# JWT
JWT_SECRET_KEY = get_env('JWT_SECRET_KEY') or DJANGO_SECRET_KEY
JWT_ACCESS_TTL_MINUTES = get_env_int('JWT_ACCESS_TTL_MINUTES', 15)
JWT_REFRESH_TTL_DAYS = get_env_int('JWT_REFRESH_TTL_DAYS', 1)
JWT_ROTATE_REFRESH = get_env_bool('JWT_ROTATE_REFRESH', True)
JWT_BLACKLIST_AFTER_ROTATE = get_env_bool('JWT_BLACKLIST_AFTER_ROTATE', True)

# 初始管理员账号(首次启动用,后续改密需在 admin 后台)
INITIAL_ADMIN_USERNAME = get_env('INITIAL_ADMIN_USERNAME', 'admin')
INITIAL_ADMIN_PASSWORD = get_env('INITIAL_ADMIN_PASSWORD', 'admin123456')
INITIAL_ADMIN_EMAIL = get_env('INITIAL_ADMIN_EMAIL', 'admin@auditweaver.local')
