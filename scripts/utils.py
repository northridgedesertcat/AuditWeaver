import os
import subprocess
import time
import socket
import http.client
import logging
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_project_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env_file(env_path=None):
    if env_path is None:
        project_dir = get_project_dir()
        env_path = os.path.join(project_dir, '.env')
    
    if not os.path.exists(env_path):
        logger.warning(f"Env file not found: {env_path}")
        return
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value
                logger.debug(f"Loaded env: {key}={value}")


def get_env(key, default=None):
    return os.environ.get(key, default)


def wait_for_http_service(host_port, max_retries=40, retry_delay=5):
    host, port = host_port.split(':')
    port = int(port)
    
    for attempt in range(1, max_retries + 1):
        try:
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('GET', '/')
            response = conn.getresponse()
            if response.status == 200:
                conn.close()
                return True
            conn.close()
        except Exception:
            pass
        
        logger.info(f"          Waiting for HTTP service... (attempt {attempt}/{max_retries})")
        time.sleep(retry_delay)
    
    return False


def wait_for_tcp_service(host_port, max_retries=10, retry_delay=3):
    host, port = host_port.split(':')
    port = int(port)
    
    for attempt in range(1, max_retries + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            sock.close()
            return True
        except Exception:
            pass
        
        logger.info(f"          Waiting for TCP service... (attempt {attempt}/{max_retries})")
        time.sleep(retry_delay)

    return False


def check_redis_ready(host, port, password=None, max_retries=5, retry_delay=3):
    """用 socket 直连 Redis 做 AUTH+PING 就绪检查(不依赖 redis-py)。

    返回 (ready, error_type, detail):
      ready=True,  error_type="",            detail=""      → 就绪
      ready=False, error_type="auth_failed", detail=resp    → 密码/认证配置错误(应 fast fail,不重试)
      ready=False, error_type="not_ready",   detail=""      → 连接不可达(有限 retry 后仍失败)
    """
    for attempt in range(1, max_retries + 1):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))

            def _send(cmd_bytes):
                sock.sendall(cmd_bytes)
                return sock.recv(1024).decode(errors='replace').strip()

            if password:
                auth_cmd = (
                    f"*2\r\n$4\r\nAUTH\r\n${len(password)}\r\n{password}\r\n"
                ).encode()
                resp = _send(auth_cmd)
                if not resp.startswith('+OK'):
                    # -WRONGPASS / -NOAUTH / 其他错误 → 认证配置问题,不重试
                    return False, "auth_failed", resp

            resp = _send(b"*1\r\n$4\r\nPING\r\n")
            if resp.startswith('+PONG'):
                return True, "", ""
            return False, "auth_failed", resp
        except (socket.error, OSError):
            if attempt < max_retries:
                logger.info(f"          Waiting for Redis... (attempt {attempt}/{max_retries})")
                time.sleep(retry_delay)
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
    return False, "not_ready", ""


def redis_readiness_check(memory_backend, redis_url):
    """根据 AE_MEMORY_BACKEND 决定是否检查 Redis。

    memory → 跳过(Redis 非启动依赖)
    redis  → 检查;失败 fast fail,不偷偷 fallback MemorySaver(避免 session state 不一致)
    """
    if memory_backend != 'redis':
        print(f"          AE_MEMORY_BACKEND={memory_backend}, skip Redis readiness check")
        return True, ""

    if not redis_url:
        print_error("AE_MEMORY_BACKEND=redis but AE_MEMORY_REDIS_URL not configured")
        return False, "config_error"

    parsed = urlparse(redis_url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 6379
    password = parsed.password

    if not password:
        print_error("Redis URL missing password (redis mode requires authentication)")
        return False, "config_error"

    ready, err_type, detail = check_redis_ready(host, port, password)
    if ready:
        print_success(f"Redis ready at {host}:{port}")
        return True, ""

    if err_type == "auth_failed":
        print_error(f"Redis AUTH failed (password/config error): {detail}")
        return False, "auth_failed"

    print_error(f"Redis not ready at {host}:{port} after retries")
    return False, "not_ready"


def run_command(cmd, cwd=None, shell=True, capture_output=False):
    logger.debug(f"Running command: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=shell,
            capture_output=capture_output,
            text=True,
            encoding='utf-8'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        return False, "", str(e)


def run_python_script(script_path, cwd=None):
    python_cmd = 'python'
    cmd = f'{python_cmd} {script_path}'
    return run_command(cmd, cwd=cwd)


def start_new_window(cmd, window_title="", cwd=None):
    if os.name == 'nt':
        cmd = f'start "{window_title}" cmd /k {cmd}'
        return run_command(cmd, cwd=cwd)
    else:
        cmd = f'xterm -T "{window_title}" -e "{cmd}; exec bash" &'
        return run_command(cmd, cwd=cwd)


def print_step(step_num, total_steps, title):
    print()
    print(f"[STEP {step_num}/{total_steps}] {title}")


def print_success(message):
    print(f"          {message}")


def print_warning(message):
    print(f"          WARNING: {message}")


def print_error(message):
    print(f"          ERROR: {message}")


def print_separator():
    print("=" * 48)


def print_header():
    print()
    print_separator()
    print("    AuditWeaver - One-click Startup")
    print_separator()
    print()


def resolve_host(host_env_key, default_host):
    if host_env_key:
        env_value = get_env(host_env_key, default_host)
        if ':' in env_value:
            return env_value.split(':')[0]
        return env_value
    return default_host


def resolve_port(port_env_key, default_port):
    if port_env_key:
        env_value = get_env(port_env_key, default_port)
        if ':' in env_value:
            return env_value.split(':')[-1]
        return env_value
    return default_port


def run_service(service, project_dir, service_config, docker_manager=None):
    service_type = service.get("type")
    
    if service_type == "docker":
        if docker_manager:
            success = docker_manager.start_services()
            if not success:
                print_error("Failed to start Docker Compose!")
                return False
            print_success("Docker Compose started")
        return True
    
    elif service_type == "wait":
        wait_config_key = service.get("wait_config")
        wait_type = service.get("wait_type", "tcp")
        
        wait_config = service_config.get_wait_config(wait_config_key)
        
        host_env_key = wait_config.get("host_env_key")
        default_host = wait_config.get("default_host", "localhost")
        host = resolve_host(host_env_key, default_host)
        
        port_env_key = wait_config.get("port_env_key")
        default_port = wait_config.get("default_port", "80")
        max_retries = wait_config.get("max_retries", 10)
        retry_delay = wait_config.get("retry_delay", 5)
        post_delay = wait_config.get("post_delay", 0)
        
        port = resolve_port(port_env_key, default_port)
        host_port = f"{host}:{port}"
        
        if wait_type == "http":
            ready = wait_for_http_service(host_port, max_retries, retry_delay)
        else:
            ready = wait_for_tcp_service(host_port, max_retries, retry_delay)
        
        if not ready:
            print_warning(f"Service may not be fully ready, continuing anyway...")
        else:
            print_success(f"Service is ready!")
            if post_delay > 0:
                print(f"          Waiting extra {post_delay} seconds for stabilization...")
                time.sleep(post_delay)
        return True
    
    elif service_type == "script":
        script_config_key = service.get("script_config")
        
        script_config = service_config.get_script_config(script_config_key)
        
        script_path = script_config.get("path", "")
        full_script_path = os.path.join(project_dir, script_path)
        
        print(f"          Script: {full_script_path}")
        success, stdout, stderr = run_python_script(full_script_path, cwd=project_dir)
        if not success:
            print_error(f"Failed to execute script!")
            return False
        else:
            print_success("Script executed successfully!")
            return True
    
    elif service_type == "shell":
        script_config_key = service.get("script_config")
        script_config = service_config.get_script_config(script_config_key)
        command = script_config.get("command", "")
        cwd_relative = script_config.get("cwd", "")
        full_cwd = os.path.join(project_dir, cwd_relative)
        print(f"          Path: {full_cwd}")
        print(f"          Cmd:  {command}")
        success, stdout, stderr = run_command(command, cwd=full_cwd)
        if not success:
            print_error(f"Failed to execute: {stderr}")
            return False
        print_success("Command executed successfully!")
        return True

    elif service_type == "redis_check":
        # memory 模式:Redis 非启动依赖,跳过检查
        # redis 模式:Redis 是 Agent session state 依赖,失败 fast fail,不偷偷 fallback MemorySaver
        from common.env import AE_MEMORY_BACKEND, AE_MEMORY_REDIS_URL
        ready, err_type = redis_readiness_check(AE_MEMORY_BACKEND, AE_MEMORY_REDIS_URL)
        return ready

    elif service_type == "window":
        window_title = service.get("window_title", "")
        command = service.get("command", "")
        cwd_relative = service.get("cwd", "")
        post_delay = service.get("post_delay", 0)
        
        full_cwd = os.path.join(project_dir, cwd_relative)
        print(f"          Path: {full_cwd}")
        
        success, stdout, stderr = start_new_window(command, window_title, cwd=full_cwd)
        if success:
            print_success(f"Started -> Window: {window_title}")
        else:
            print_warning(f"Failed to start {window_title}!")
            return False
        
        if post_delay > 0:
            time.sleep(post_delay)
        return True
    
    else:
        print_warning(f"Unknown service type: {service_type}")
        return False