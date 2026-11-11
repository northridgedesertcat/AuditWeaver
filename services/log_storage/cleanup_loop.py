import json
import logging
import signal
import time
from pathlib import Path

from common import env
from common.log_query.clients import es_client
from common.log_query.types import utcnow
from .archive import cleanup, index_window
from .clickhouse import ClickHouseStore
from .metadata import DjangoMetadata

logger = logging.getLogger(__name__)


def run():
    running = True
    def shutdown(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    es, metadata = es_client(), DjangoMetadata()
    due = 0
    while running:
        if time.monotonic() >= due:
            try:
                names = es.indices.get(index="auditweaver-raw-hot-*,auditweaver-events-hot-*", allow_no_indices=True)
                for index in names:
                    _, _, end = index_window(index)
                    from datetime import timedelta
                    if end > utcnow() - timedelta(days=env.get_env_int("LOG_HOT_RETENTION_DAYS", 7)):
                        continue
                    execute = env.get_env_bool("ES_CLEANUP_ENABLED") and not env.get_env_bool("ES_CLEANUP_DRY_RUN", True)
                    evidence_path = env.get_env("ES_CLEANUP_BACKUP_EVIDENCE")
                    evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8")) if evidence_path else None
                    try:
                        result = cleanup(es, ClickHouseStore() if execute else None, metadata, index, execute=execute, backup=evidence)
                        logger.info("Cleanup: %s", result)
                    except Exception:
                        logger.exception("Cleanup blocked for %s; index retained", index)
            except Exception:
                logger.exception("Cleanup cycle failed; no further indexes deleted")
            due = time.monotonic() + max(60, env.get_env_int("ES_CLEANUP_INTERVAL_SECONDS", 3600))
        time.sleep(1)
