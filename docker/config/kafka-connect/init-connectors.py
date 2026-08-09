#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AuditWeaver - Kafka Connect Connector Initializer

Reads connector JSON files from the connectors/ subdirectory and creates
connectors via the Kafka Connect REST API.  Existing connectors (including
stale / FAILED ones) are deleted and recreated for a clean state.

Usage:
    python init-connectors.py
    python init-connectors.py --connect-host localhost --connect-port 8083
    python init-connectors.py --dry-run
    python init-connectors.py --list-only
    python init-connectors.py --single connectors/log-structured-sink.json
"""

import argparse
import json
import sys
import http.client
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('init-connectors')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_connect_defaults():
    """Try to resolve Kafka Connect host/port from the project .env file."""
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent.parent
    env_file = project_root / '.env'

    host = 'localhost'
    port = 8083

    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, _, val = line.partition('=')
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key == 'KAFKA_CONNECT_HOST' and val:
                        host = val
                    if key == 'KAFKA_CONNECT_PORT' and val:
                        port = int(val)
        except Exception:
            pass

    return host, port


def discover_connector_files(connectors_dir: Path) -> list:
    """Find all JSON connector config files in the given directory."""
    if not connectors_dir.exists():
        log.error(f"Connectors directory not found: {connectors_dir}")
        return []

    files = sorted(connectors_dir.glob('*.json'))
    if not files:
        log.warning(f"No connector JSON files found in {connectors_dir}")
    return files


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

class ConnectConnectionError(Exception):
    """Raised when Kafka Connect is unreachable or returns an unexpected response."""
    pass


class ConnectAPIError(ConnectConnectionError):
    """Raised when Kafka Connect responds but with an unexpected HTTP status."""
    pass


def check_connector_exists(connector_name, connect_host='localhost', connect_port=8083):
    """Check if a connector already exists on the Kafka Connect cluster.

    Returns:
        True  — connector exists (HTTP 200) or is in an unhealthy state (HTTP 409)
        False — connector does not exist (HTTP 404)

    Raises:
        ConnectAPIError       — unexpected HTTP status from Kafka Connect
        ConnectConnectionError — cannot reach Kafka Connect at all
    """
    try:
        conn = http.client.HTTPConnection(connect_host, connect_port, timeout=10)
        conn.request('GET', f'/connectors/{connector_name}')
        response = conn.getresponse()
        conn.close()
        if response.status == 200:
            return True
        if response.status == 404:
            return False
        if response.status == 409:
            log.warning(
                "Connector '%s' exists but is in an unhealthy state "
                "(HTTP 409 — may be FAILED or REBALANCING)",
                connector_name,
            )
            return True
        raise ConnectAPIError(
            f"Kafka Connect returned unexpected HTTP {response.status} "
            f"when checking connector '{connector_name}'"
        )
    except (ConnectionRefusedError, OSError, TimeoutError) as e:
        raise ConnectConnectionError(
            f"Cannot reach Kafka Connect at {connect_host}:{connect_port}: {e}"
        ) from e


def list_all_connectors(connect_host='localhost', connect_port=8083):
    """Return the set of connector names already on the cluster.

    Raises:
        ConnectAPIError       — unexpected HTTP status from Kafka Connect
        ConnectConnectionError — cannot reach Kafka Connect at all
    """
    try:
        conn = http.client.HTTPConnection(connect_host, connect_port, timeout=10)
        conn.request('GET', '/connectors')
        response = conn.getresponse()
        body = response.read().decode('utf-8')
        conn.close()
        if response.status == 200:
            return set(json.loads(body))
        raise ConnectAPIError(
            f"Kafka Connect returned unexpected HTTP {response.status} "
            f"when listing connectors"
        )
    except (ConnectionRefusedError, OSError, TimeoutError) as e:
        raise ConnectConnectionError(
            f"Cannot reach Kafka Connect at {connect_host}:{connect_port}: {e}"
        ) from e


def _delete_connector(connector_name, connect_host='localhost', connect_port=8083):
    """Delete a connector by name. Logs result; does not raise on failure."""
    try:
        conn = http.client.HTTPConnection(connect_host, connect_port, timeout=10)
        conn.request('DELETE', f'/connectors/{connector_name}')
        response = conn.getresponse()
        conn.close()
        if response.status in (200, 204):
            log.info("Deleted existing connector '%s'", connector_name)
            return True
        else:
            log.warning(
                "Failed to delete connector '%s' (HTTP %s)",
                connector_name, response.status,
            )
            return False
    except (ConnectionRefusedError, OSError, TimeoutError) as e:
        log.warning(
            "Cannot reach Kafka Connect while trying to delete connector '%s': %s",
            connector_name, e,
        )
        return False


def create_connector(connector_config_path, connect_host='localhost', connect_port=8083):
    """Create a single connector from its JSON config file.  Idempotent.

    If the connector already exists (including in a stale / FAILED state),
    it is deleted first and then recreated from the JSON definition.

    Raises:
        ConnectConnectionError — cannot reach Kafka Connect at all
    """
    with open(connector_config_path, 'r', encoding='utf-8') as f:
        connector_config = json.load(f)

    connector_name = connector_config.get('name', '')
    if not connector_name:
        log.warning("No 'name' field in %s, skipping", connector_config_path)
        return False

    if check_connector_exists(connector_name, connect_host, connect_port):
        log.info(
            "Connector '%s' already exists, deleting to recreate from config...",
            connector_name,
        )
        _delete_connector(connector_name, connect_host, connect_port)

    conn = http.client.HTTPConnection(connect_host, connect_port, timeout=10)
    headers = {'Content-Type': 'application/json'}
    conn.request('POST', '/connectors', body=json.dumps(connector_config), headers=headers)
    response = conn.getresponse()
    response_body = response.read().decode('utf-8')
    conn.close()

    if response.status == 201:
        log.info("[OK]   Connector '%s' created successfully", connector_name)
        return True
    if response.status == 409:
        log.info("[SKIP] Connector '%s' already exists (HTTP 409)", connector_name)
        return True

    log.error(
        "[FAIL] Connector '%s' creation failed. HTTP %s: %s",
        connector_name, response.status, response_body,
    )
    return False


def show_status(connector_files, connect_host='localhost', connect_port=8083):
    """Print status of each connector file against the cluster.

    Raises:
        ConnectAPIError       — unexpected HTTP status from Kafka Connect
        ConnectConnectionError — cannot reach Kafka Connect at all
    """
    existing = list_all_connectors(connect_host, connect_port)
    log.info("=" * 60)
    log.info("Connector status on cluster:")
    log.info("=" * 60)
    for fpath in connector_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            name = cfg.get('name', '<unnamed>')
        except Exception:
            name = fpath.stem
        state = "EXISTS" if name in existing else "MISSING"
        log.info(f"  [{state:7s}] {name}")
    log.info("=" * 60)


def create_all_connectors(connector_files, connect_host='localhost', connect_port=8083,
                          dry_run=False):
    """Create or recreate all connectors from their JSON definitions.

    Existing connectors are deleted and recreated to guarantee a clean state.

    Raises:
        ConnectAPIError       — unexpected HTTP status from Kafka Connect
        ConnectConnectionError — cannot reach Kafka Connect at all

    Returns (success_count, total_count).
    """
    if not connector_files:
        log.info("No connector files to process.")
        return 0, 0

    if dry_run:
        log.info(f"[DRY-RUN] Would process {len(connector_files)} connector file(s).")
        return len(connector_files), len(connector_files)

    success = 0
    for fpath in connector_files:
        log.info(f"Processing: {fpath.name}")
        if create_connector(fpath, connect_host, connect_port):
            success += 1

    log.info(f"Done. {success}/{len(connector_files)} connector(s) ready.")
    return success, len(connector_files)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    script_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description='Initialize AuditWeaver Kafka Connect connectors from JSON files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--connect-host',
        default=None,
        help='Kafka Connect REST host (default: auto-detect from .env or localhost)',
    )
    parser.add_argument(
        '--connect-port',
        type=int,
        default=None,
        help='Kafka Connect REST port (default: auto-detect from .env or 8083)',
    )
    parser.add_argument(
        '--connectors-dir',
        default=str(script_dir / 'connectors'),
        help='Directory containing connector JSON files (default: %(default)s)',
    )
    parser.add_argument(
        '--single',
        default=None,
        help='Process a single connector JSON file (relative to project root or absolute)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without actually creating anything',
    )
    parser.add_argument(
        '--list-only',
        action='store_true',
        help='Only show current connector status, do not create anything',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable debug-level logging',
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    default_host, default_port = resolve_connect_defaults()
    connect_host = args.connect_host or default_host
    connect_port = args.connect_port or default_port

    log.info(f"Kafka Connect: {connect_host}:{connect_port}")

    if args.single:
        single_path = Path(args.single)
        if not single_path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            single_path = project_root / single_path
        if not single_path.exists():
            log.error(f"Connector file not found: {single_path}")
            sys.exit(1)
        connector_files = [single_path]
    else:
        connectors_dir = Path(args.connectors_dir)
        connector_files = discover_connector_files(connectors_dir)

    log.info(f"Found {len(connector_files)} connector file(s)")

    try:
        if args.list_only:
            show_status(connector_files, connect_host, connect_port)
        else:
            show_status(connector_files, connect_host, connect_port)
            success, total = create_all_connectors(
                connector_files, connect_host, connect_port, dry_run=args.dry_run
            )
            show_status(connector_files, connect_host, connect_port)
            if success < total:
                sys.exit(1)
    except ConnectAPIError as e:
        log.error(str(e))
        log.error(
            "Kafka Connect responded with an unexpected status. "
            "The service may be starting up or in an inconsistent state — "
            "wait a moment and try again."
        )
        sys.exit(1)
    except ConnectConnectionError as e:
        log.error(str(e))
        log.error("Cannot reach Kafka Connect. Verify the service is running and accessible.")
        sys.exit(1)


if __name__ == '__main__':
    main()