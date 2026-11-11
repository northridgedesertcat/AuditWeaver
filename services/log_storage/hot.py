import json
from datetime import timedelta
from pathlib import Path

import yaml

from common import env
from common.log_query.clients import es_client
from common.log_query.types import QueryUnavailable, utcnow
from .contract import check_identity

ALIASES = {"raw": "auditweaver-raw-hot", "events": "auditweaver-events-hot"}
ROOT = Path(__file__).resolve().parents[2]


def install_templates(es):
    for kind, legacy in (("raw", "nginx-log-raw"), ("events", "matched_logs")):
        with (ROOT / "docker/config/elasticsearch/mappings" / f"{legacy}.yaml").open(encoding="utf-8") as handle:
            template = yaml.safe_load(handle)
        template["mappings"]["properties"]["_storage"] = {"properties": {
            "record_id": {"type": "keyword"}, "payload_hash": {"type": "keyword"},
            "source_kind": {"type": "keyword"}, "source_topic": {"type": "keyword"},
            "source_partition": {"type": "integer"}, "source_offset": {"type": "long"},
            "version": {"type": "long"}, "attack_types": {"type": "keyword"},
        }}
        template["aliases"] = {ALIASES[kind]: {}}
        es.indices.put_index_template(name=ALIASES[kind], body={
            "index_patterns": [ALIASES[kind] + "-*"], "priority": 200, "template": template,
        })
        index = ALIASES[kind] + utcnow().strftime("-%Y.%m.%d")
        if not es.indices.exists(index=index):
            es.indices.create(index=index)


class HotStore:
    def __init__(self, es=None, clock=utcnow):
        self.es = es or es_client()
        self.clock = clock

    def write(self, kind, rows):
        cutoff = self.clock() - timedelta(days=env.get_env_int("LOG_HOT_RETENTION_DAYS", 7))
        actions, selected = [], []
        for row in rows:
            if row["event_time"] < cutoff:
                continue
            selected.append(row)
            actions.append({"index": {
                "_index": ALIASES[kind] + row["event_time"].strftime("-%Y.%m.%d"),
                "_id": row["record_id"], "version": row["version"], "version_type": "external_gte",
            }})
            payload = json.loads(row["raw_payload"])
            payload["_storage"] = {k: row[k] for k in (
                "record_id", "payload_hash", "source_kind", "source_topic", "source_partition", "source_offset", "version", "attack_types"
            )}
            actions.append(payload)
        if not actions:
            return
        # Realtime GET sees writes before refresh and prevents immutable-body conflicts on replay.
        existing = self.es.mget(docs=[{"_index": actions[i * 2]["index"]["_index"], "_id": row["record_id"]} for i, row in enumerate(selected)])["docs"]
        if len(existing) != len(selected) or any(doc.get("error") for doc in existing):
            # A missing daily index is expected before its first bulk creates it.
            errors = [doc.get("error", {}) for doc in existing if doc.get("error")]
            if len(existing) != len(selected) or any(e.get("type") != "index_not_found_exception" for e in errors):
                raise QueryUnavailable("ES identity lookup is incomplete")
        known = {}
        for row, doc in zip(selected, existing):
            previous = known.get(row["record_id"])
            if previous is None and doc.get("found"):
                from .archive import row_from_hit
                previous = row_from_hit(kind, doc)
            if previous:
                check_identity(kind, previous, row)
            if previous is None or row["version"] >= previous["version"]:
                known[row["record_id"]] = row
        response = self.es.bulk(operations=actions)
        items = response.get("items", [])
        if len(items) != len(selected):
            raise QueryUnavailable("Incomplete ES bulk response")
        for row, item in zip(selected, items):
            result = item["index"]
            code = result["status"]
            if 200 <= code < 300:
                continue
            if code == 409:
                # External version conflict only means a newer version is already persisted.
                current = self.es.get(index=result["_index"], id=row["record_id"])
                if current["_version"] > row["version"]:
                    continue
            if code == 403 and row["event_time"] < self.clock() - timedelta(days=env.get_env_int("LOG_HOT_RETENTION_DAYS", 7)):
                continue
            raise QueryUnavailable(f"ES bulk item failed: {result}")
