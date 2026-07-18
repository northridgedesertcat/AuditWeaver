import os
import logging

from .utils import get_project_dir, run_command

logger = logging.getLogger(__name__)


class DockerManager:
    def __init__(self, compose_file=None):
        self.project_dir = get_project_dir()
        if compose_file is None:
            self.compose_file = os.path.join(self.project_dir, 'docker', 'docker-compose.yml')
        else:
            self.compose_file = compose_file
    
    def start_services(self):
        logger.info(f"Starting Docker Compose services: {self.compose_file}")
        cmd = f'docker-compose -f "{self.compose_file}" up -d'
        success, stdout, stderr = run_command(cmd)
        if success:
            logger.info("Docker Compose services started successfully")
            return True
        else:
            logger.error(f"Failed to start Docker Compose: {stderr}")
            return False
    
    def stop_services(self):
        logger.info(f"Stopping Docker Compose services: {self.compose_file}")
        cmd = f'docker-compose -f "{self.compose_file}" down'
        success, stdout, stderr = run_command(cmd)
        if success:
            logger.info("Docker Compose services stopped successfully")
            return True
        else:
            logger.error(f"Failed to stop Docker Compose: {stderr}")
            return False
    
    def restart_services(self):
        logger.info(f"Restarting Docker Compose services: {self.compose_file}")
        if self.stop_services() and self.start_services():
            logger.info("Docker Compose services restarted successfully")
            return True
        return False
    
    def list_services(self):
        logger.info("Listing Docker Compose services")
        cmd = f'docker-compose -f "{self.compose_file}" ps'
        success, stdout, stderr = run_command(cmd, capture_output=True)
        if success:
            logger.info(f"Services:\n{stdout}")
            return stdout
        else:
            logger.error(f"Failed to list services: {stderr}")
            return None
    
    def logs(self, service_name=None, tail=100):
        logger.info(f"Getting logs for service: {service_name or 'all'}")
        cmd = f'docker-compose -f "{self.compose_file}" logs'
        if service_name:
            cmd += f' {service_name}'
        cmd += f' --tail={tail}'
        success, stdout, stderr = run_command(cmd, capture_output=True)
        if success:
            return stdout
        else:
            logger.error(f"Failed to get logs: {stderr}")
            return None
    
    def check_docker_running(self):
        logger.info("Checking if Docker is running")
        cmd = 'docker info'
        success, stdout, stderr = run_command(cmd, capture_output=True)
        return success
    
    def check_docker_compose_installed(self):
        logger.info("Checking if Docker Compose is installed")
        cmd = 'docker-compose --version'
        success, stdout, stderr = run_command(cmd, capture_output=True)
        return success
    
    def pull_images(self):
        logger.info(f"Pulling images for Docker Compose: {self.compose_file}")
        cmd = f'docker-compose -f "{self.compose_file}" pull'
        success, stdout, stderr = run_command(cmd)
        if success:
            logger.info("Images pulled successfully")
            return True
        else:
            logger.error(f"Failed to pull images: {stderr}")
            return False