import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import psutil

import dev
from scripts.config import ServiceConfig
from scripts.docker_manager import DockerManager
from scripts.process_manager import ProcessManager
from scripts.utils import redis_readiness_check, tcp_ready, wait_until


class ConfigTests(unittest.TestCase):
    def test_custom_ports_and_interpreter(self):
        config = ServiceConfig({"DJANGO_PORT": "8800", "FRONTEND_PORT": "3300",
                                "AE_BACKEND_PORT": "8801", "MYSQL_PORT": "13307"}, python="test-python")
        services = {service["id"]: service for service in config.get_services()}
        self.assertEqual(services["django"]["port"], 8800)
        self.assertIn("0.0.0.0:8800", services["django"]["command"])
        self.assertEqual(services["frontend"]["port"], 3300)
        self.assertEqual(services["agent_service"]["port"], 8801)
        self.assertEqual(services["agent"]["command"][0], "test-python")
        self.assertIn("13307", next(step for step in config.get_steps() if step["id"] == "mysql")["address"])

    def test_agent_service_precedes_analysis_worker(self):
        ids = [service["id"] for service in ServiceConfig({}).get_services()]
        self.assertLess(ids.index("agent_service"), ids.index("agent"))

    def test_database_checks_and_migration_are_ordered(self):
        ids = [step["id"] for step in ServiceConfig({}).get_steps()]
        self.assertLess(ids.index("mysql"), ids.index("django_check"))
        self.assertLess(ids.index("django_check"), ids.index("django_migrate"))

    def test_frontend_can_run_without_initializing_infrastructure(self):
        self.assertEqual(ServiceConfig({}).get_steps(["frontend"]), [])

    def test_unknown_service_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Unknown services"):
            dev.select_services(ServiceConfig({}), ["old_rules_matching"])

    def test_environment_is_resolved_at_construction(self):
        with patch.dict(os.environ, {"DJANGO_PORT": "8765"}):
            config = ServiceConfig()
        self.assertEqual(next(service for service in config.get_services() if service["id"] == "django")["port"], 8765)


class ReadinessTests(unittest.TestCase):
    def test_wait_failure_is_bounded(self):
        self.assertFalse(wait_until(lambda: False, timeout=0))

    def test_tcp_checks_the_requested_port(self):
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen()
            self.assertTrue(tcp_ready(f"127.0.0.1:{server.getsockname()[1]}"))

    def test_memory_mode_does_not_connect_to_redis(self):
        with patch("scripts.utils.check_redis_ready") as check:
            self.assertEqual(redis_readiness_check("memory", ""), (True, ""))
            check.assert_not_called()

    def test_redis_password_is_url_decoded(self):
        with patch("scripts.utils.check_redis_ready", return_value=(True, "", "")) as check:
            self.assertEqual(redis_readiness_check("redis", "redis://user:p%40ss@localhost:16379/0"), (True, ""))
            check.assert_called_once_with("localhost", 16379, "p@ss", username="user")

    def test_bad_memory_mode_fails(self):
        self.assertEqual(redis_readiness_check("typo", ""), (False, "config_error"))

    def test_readiness_failure_prevents_initialization_commands(self):
        config = Mock()
        config.get_steps.return_value = [
            {"id": "mysql", "address": "127.0.0.1:13306"},
            {"id": "django_migrate", "command": [sys.executable, "manage.py", "migrate"]},
        ]
        with patch("scripts.utils.wait_until", return_value=False), patch("dev.run") as run:
            with self.assertRaisesRegex(RuntimeError, "mysql"):
                dev.initialize(config, ["django"])
            run.assert_not_called()

    def test_failed_migration_propagates(self):
        config = Mock()
        config.get_steps.return_value = [{"id": "django_migrate", "command": ["python", "manage.py", "migrate"]}]
        with patch("dev.run", side_effect=subprocess.CalledProcessError(1, "migrate")):
            with self.assertRaises(subprocess.CalledProcessError):
                dev.initialize(config, ["django"])

    def test_early_exit_reports_log(self):
        manager = Mock()
        manager.process.return_value = None
        manager.tail.return_value = "missing dependency"
        with self.assertRaisesRegex(RuntimeError, "missing dependency"):
            dev.wait_for_process(manager, {"id": "test"})


class DockerTests(unittest.TestCase):
    def test_explicit_env_path_and_modern_compose(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").touch()
            command = DockerManager(root).command("config", "--quiet")
            self.assertEqual(command[:2], ["docker", "compose"])
            self.assertIn(str(root / ".env"), command)
            self.assertIn(str(root / "docker" / "docker-compose.yml"), command)

    def test_start_waits_for_health(self):
        docker = DockerManager()
        with patch.object(docker, "run") as run:
            docker.start_services()
            self.assertIn("--wait", run.call_args.args)

    def test_stop_preserves_volumes(self):
        docker = DockerManager()
        with patch.object(docker, "run") as run:
            docker.stop_services()
            self.assertEqual(run.call_args.args, ("stop",))


class LifecycleTests(unittest.TestCase):
    def test_failed_start_rolls_back_only_new_processes(self):
        config = ServiceConfig({})
        manager = Mock()
        manager.process.return_value = None
        manager.start.side_effect = [False, True]
        args = argparse.Namespace(services=["rule_engine", "agent_service"], no_docker=True, tools=False)
        with patch("dev.ROOT") as root, patch.dict(os.environ, {"DJANGO_SECRET_KEY": "test", "AE_LLM_MODEL": "test-model"}), \
                patch("scripts.utils.tcp_ready", return_value=False), patch("dev.initialize"), \
                patch("dev.wait_for_process", side_effect=[None, RuntimeError("failed")]):
            root.__truediv__.return_value.exists.return_value = True
            with self.assertRaisesRegex(RuntimeError, "failed"):
                dev.start_services(config, manager, Mock(), args)
        manager.stop.assert_called_once_with("agent_service")

    def test_initialization_failure_starts_no_business_process(self):
        config = ServiceConfig({})
        manager = Mock()
        manager.process.return_value = None
        args = argparse.Namespace(services=["agent"], no_docker=True, tools=False)
        with patch("dev.ROOT") as root, patch.dict(os.environ, {"DJANGO_SECRET_KEY": "test"}), \
                patch("dev.initialize", side_effect=RuntimeError("migration failed")):
            root.__truediv__.return_value.exists.return_value = True
            with self.assertRaisesRegex(RuntimeError, "migration failed"):
                dev.start_services(config, manager, Mock(), args)
        manager.start.assert_not_called()

    def test_service_stop_does_not_stop_docker(self):
        docker = Mock()
        dev.stop_services(ServiceConfig({}), Mock(), docker,
                          argparse.Namespace(services=["frontend"], no_docker=False))
        docker.stop_services.assert_not_called()

    def test_repeated_start_does_not_repeat_initialization(self):
        config = ServiceConfig({})
        manager = Mock()
        manager.process.return_value = Mock()
        manager.start.return_value = False
        args = argparse.Namespace(services=["frontend"], no_docker=True, tools=False)
        with patch("dev.initialize") as initialize, patch("dev.wait_for_process"), \
                patch("dev.probe_service", return_value=True):
            dev.start_services(config, manager, Mock(), args)
        initialize.assert_called_once_with(config, [])


class ProcessIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="auditweaver test ")
        self.addCleanup(self.directory.cleanup)
        self.manager = ProcessManager(self.directory.name)
        self.service = {"id": "probe", "command": [sys.executable, "-u", "-c", "import time; print('probe ready'); time.sleep(60)"], "cwd": "."}
        self.addCleanup(self.manager.stop, "probe")

    def test_start_status_logs_duplicate_start_and_stop(self):
        self.assertTrue(self.manager.start(self.service))
        self.assertIsNotNone(self.manager.process("probe"))
        self.assertFalse(self.manager.start(self.service))
        deadline = time.monotonic() + 10
        while "probe ready" not in self.manager.tail("probe") and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIn("probe ready", self.manager.tail("probe"))
        # A second invocation can stop the process, without holding a Popen object.
        ProcessManager(self.directory.name).stop("probe")
        self.manager.children["probe"].wait(timeout=5)
        self.assertIsNone(self.manager.process("probe"))
        self.assertFalse(self.manager.state_path("probe").exists())

    def test_reused_pid_does_not_stop_unrelated_process(self):
        self.manager.state_dir.mkdir()
        process = psutil.Process()
        self.manager.state_path("probe").write_text(json.dumps({"pid": process.pid, "create_time": process.create_time() - 100}), encoding="utf-8")
        with patch.object(psutil.Process, "terminate") as terminate:
            self.manager.stop("probe")
            terminate.assert_not_called()

    def test_process_tree_is_stopped(self):
        child_code = "import time; time.sleep(60)"
        self.service["command"] = [sys.executable, "-u", "-c",
                                   f"import subprocess, sys, time; child=subprocess.Popen([sys.executable, '-c', {child_code!r}]); print(child.pid); time.sleep(60)"]
        self.manager.start(self.service)
        deadline = time.monotonic() + 10
        child = None
        while time.monotonic() < deadline:
            process = self.manager.process("probe")
            children = process.children() if process else []
            if children:
                child = children[0]
                break
            time.sleep(0.05)
        self.assertIsNotNone(child)
        self.manager.stop("probe")
        self.assertFalse(child.is_running() and child.status() != psutil.STATUS_ZOMBIE)

    def test_concurrent_lifecycle_command_is_rejected(self):
        with self.manager.locked():
            with self.assertRaisesRegex(RuntimeError, "already running"):
                with ProcessManager(self.directory.name).locked():
                    self.fail("Second lock must not succeed")

    def test_corrupted_state_is_not_silently_overwritten(self):
        self.manager.state_dir.mkdir()
        self.manager.state_path("broken").write_text("invalid json", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Cannot read"):
            self.manager.process("broken")

    def test_invalid_identity_is_not_silently_overwritten(self):
        self.manager.state_dir.mkdir()
        for identity in ({}, {"pid": -1, "create_time": 100}, {"pid": 1, "create_time": "yesterday"}):
            self.manager.state_path("broken").write_text(json.dumps(identity), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Cannot read"):
                self.manager.process("broken")


if __name__ == "__main__":
    unittest.main()
