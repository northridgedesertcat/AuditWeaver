import os
import subprocess
import time
import socket
import http.client
import logging

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
        
        host = wait_config.get("host", "localhost")
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
            print_warning(f"Failed to execute script!")
        else:
            print_success("Script executed successfully!")
        return True
    
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
        
        if post_delay > 0:
            time.sleep(post_delay)
        return True
    
    else:
        print_warning(f"Unknown service type: {service_type}")
        return False