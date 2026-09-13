import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.utils import (
    get_project_dir, load_env_file,
    print_step, print_success, print_warning, print_error,
    print_separator, print_header, run_service
)
from scripts.docker_manager import DockerManager
from scripts.config import DEFAULT_CONFIG, ServiceConfig


def print_service_summary(services):
    print()
    print("Service List:")
    for service in services:
        description = service.get("description", "")
        port = service.get("port")
        if port:
            print(f"  - {description}: http://localhost:{port}")
        elif description:
            print(f"  - {description}")
    print()


def main():
    print_header()
    
    project_dir = get_project_dir()
    
    load_env_file()
    
    docker_manager = DockerManager()
    
    service_config = ServiceConfig(DEFAULT_CONFIG)
    services = service_config.get_services()
    total_steps = len(services)
    
    for step_num, service in enumerate(services, 1):
        service_name = service.get("name", "Unknown Service")
        print_step(step_num, total_steps, service_name)
        
        if service.get("type") == "docker":
            print("          This may take a few minutes...")
        
        success = run_service(service, project_dir, service_config, docker_manager)
        
        if not success:
            service_type = service.get("type")
            if service_type in ("docker", "script", "redis_check"):
                print_error(f"Critical service '{service_name}' failed to start. Aborting.")
                input("Press Enter to exit...")
                return
            elif service_type == "window":
                print_warning(f"Window service '{service_name}' failed to start, continuing...")
    
    print()
    print_separator()
    print("    All services started!")
    print_separator()
    
    print_service_summary(services)
    
    print("To stop all services, run: stop.bat")
    print()
    
    input("Press Enter to exit...")


if __name__ == '__main__':
    main()