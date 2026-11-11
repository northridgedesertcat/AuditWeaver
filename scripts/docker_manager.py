"""Docker Compose v2 commands with explicit project and environment paths."""

import os
from pathlib import Path
import subprocess


class DockerManager:
    def __init__(self, project_dir=None):
        self.project_dir = Path(project_dir or Path(__file__).resolve().parents[1])

    def command(self, *args, profiles=()):
        cmd = ["docker", "compose", "--project-directory", str(self.project_dir / "docker")]
        env_file = self.project_dir / ".env"
        if env_file.exists():
            cmd += ["--env-file", str(env_file)]
        cmd += ["-f", str(self.project_dir / "docker" / "docker-compose.yml")]
        if os.environ.get("STORAGE_ENABLED", "false").lower() in {"true", "1", "yes", "on"}:
            profiles = (*profiles, "log-storage")
        for profile in dict.fromkeys(profiles):
            cmd += ["--profile", profile]
        return [*cmd, *args]

    def run(self, *args, profiles=(), capture=False):
        return subprocess.run(
            self.command(*args, profiles=profiles), cwd=self.project_dir,
            check=True, text=True, encoding="utf-8", errors="replace",
            capture_output=capture,
        )

    def start_services(self, profiles=()):
        self.run("up", "-d", "--wait", "--wait-timeout", "180", profiles=profiles)

    def stop_services(self):
        # Stop containers without deleting containers, networks or persistent data.
        self.run("stop", profiles=("tools", "log-storage"))

    def check_docker_running(self):
        return subprocess.run(
            ["docker", "info"], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).returncode == 0
