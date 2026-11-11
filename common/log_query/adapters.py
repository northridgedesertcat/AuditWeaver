from __future__ import annotations

import json

from common import env
from .clients import ck_client, database, es_client, decode_ck_time
from .types import KINDS, QueryError, QueryUnavailable, millis, parse_time


class ElasticsearchReader:
    def __init__(self, client=None):
        self.client = client or es_client()

    def index(self, kind, hot):
        if hot:
            return "auditweaver-raw-hot" if kind == "raw" else "auditweaver-events-hot"
        return (env.get_env("AE_SKILL_ES_INDEX_RAW", env.ES_INDEX_NGINX_RAW) if kind == "raw"
                else env.get_env("AE_SKILL_ES_INDEX_EVENTS", env.ES_INDEX_MATCHED_LOGS))

    def query(self, spec, start, end, hot):
        prefix = "" if spec.kind == "raw" else "log_context."
        timestamp = "@timestamp" if spec.kind == "raw" else "log_context.timestamp"
        filters = [{"range": {timestamp: {"gte": millis(start), "lt": millis(end)}}}]
        for key, value in spec.filters.items():
            if key == "path":
                escaped = value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")
                filters.append({"wildcard": {prefix + "path": {"value": "*" + escaped + "*"}}})
            elif key == "q":
                escaped = value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")
                filters.append({"bool": {"should": [
                    {"term": {prefix + "ip": value}} if self._is_ip(value) else {"match_none": {}},
                    {"wildcard": {prefix + "path": {"value": "*" + escaped + "*"}}},
                    {"term": {"event_id": value}},
                ], "minimum_should_match": 1}})
            elif key == "attack_type":
                if hot:
                    filters.append({"term": {"_storage.attack_types": value}})
                else:
                    # Legacy keyword holds comma-separated attack types.
                    filters.append({"script": {"script": {
                        "source": "for (def v : doc['attack_type']) { for (def t : v.splitOnToken(',')) { if (t.trim().equals(params.v)) return true; } } return false;",
                        "params": {"v": value},
                    }}})
            else:
                field = "event_id" if key == "event_id" else prefix + key
                filters.append({"term": {field: int(value) if key == "status" else value}})
        return {"bool": {"filter": filters}}

    @staticmethod
    def _is_ip(value):
        import ipaddress
        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            return False

    def fetch(self, spec, start, end, limit, after=None, pit=None, hot=False):
        timestamp = "@timestamp" if spec.kind == "raw" else "log_context.timestamp"
        opened = pit is None
        if opened:
            pit = self.client.open_point_in_time(index=self.index(spec.kind, hot), keep_alive="5m")["id"]
        body = {
            "size": limit, "query": self.query(spec, start, end, hot),
            "pit": {"id": pit, "keep_alive": "5m"}, "track_total_hits": False,
            "sort": [{timestamp: {"order": "desc", "format": "epoch_millis"}},
                     {"_storage.record_id" if hot else "event_id": {"order": "desc", "missing": "_last"}},
                     {"_shard_doc": "desc"}],
        }
        if after:
            body["search_after"] = after
        try:
            result = self.client.search(body=body)
            if result.get("timed_out") or result.get("_shards", {}).get("failed", 0):
                raise QueryUnavailable("ES returned incomplete results")
            pit = result.get("pit_id", pit)
            return [{"payload": h["_source"], "after": h["sort"]} for h in result["hits"]["hits"]], pit
        except Exception:
            self.close(pit)
            raise

    def close(self, pit):
        if pit:
            self.client.close_point_in_time(id=pit)

    def count(self, spec, start, end, hot=False):
        result = self.client.count(index=self.index(spec.kind, hot), query=self.query(spec, start, end, hot))
        if result.get("_shards", {}).get("failed", 0):
            raise QueryUnavailable("ES count has failed shards")
        return result["count"]

    def groups(self, spec, start, end, dimension, hot=False):
        prefix = "" if spec.kind == "raw" else "log_context."
        field = prefix + dimension
        after, rows = None, []
        while True:
            composite = {"size": 1000, "sources": [{"value": {"terms": {"field": field}}}]}
            if after:
                composite["after"] = after
            result = self.client.search(index=self.index(spec.kind, hot), body={
                "size": 0, "query": self.query(spec, start, end, hot), "aggs": {"groups": {"composite": composite}},
            })
            if result.get("timed_out") or result.get("_shards", {}).get("failed", 0):
                raise QueryUnavailable("ES aggregation is incomplete")
            agg = result["aggregations"]["groups"]
            rows.extend((b["key"]["value"], b["doc_count"]) for b in agg["buckets"])
            if len(rows) > env.get_env_int("LOG_QUERY_MAX_GROUPS", 100000):
                raise QueryError("Too many aggregate groups; narrow the time range")
            after = agg.get("after_key")
            if not after or not agg["buckets"]:
                return rows

    def hourly(self, spec, start, end, hot=False):
        timestamp = "@timestamp" if spec.kind == "raw" else "log_context.timestamp"
        result = self.client.search(index=self.index(spec.kind, hot), body={
            "size": 0, "query": self.query(spec, start, end, hot),
            "aggs": {"hours": {"date_histogram": {"field": timestamp, "fixed_interval": "1h", "min_doc_count": 1}}},
        })
        if result.get("timed_out") or result.get("_shards", {}).get("failed", 0):
            raise QueryUnavailable("ES histogram is incomplete")
        return [(b["key"], b["doc_count"]) for b in result["aggregations"]["hours"]["buckets"]]


class ClickHouseReader:
    def __init__(self, client=None):
        self.client = client or ck_client()

    def where(self, spec, start, end):
        clauses = ["event_time >= {start:DateTime64(3, 'UTC')}", "event_time < {end:DateTime64(3, 'UTC')}"]
        # Plain datetime binding in clickhouse-connect drops fractional seconds.
        parameters = {"start": parse_time(start).strftime("%Y-%m-%d %H:%M:%S.%f"),
                      "end": parse_time(end).strftime("%Y-%m-%d %H:%M:%S.%f")}
        for key, value in spec.filters.items():
            parameters[key] = int(value) if key == "status" else value
            if key == "path":
                clauses.append("position(path, {path:String}) > 0")
            elif key == "q":
                clauses.append("(ip = {q:String} OR position(path, {q:String}) > 0 OR event_id = {q:String})")
            elif key == "attack_type":
                clauses.append("has(attack_types, {attack_type:String})")
            else:
                clauses.append(key + " = {" + key + (":UInt16}" if key == "status" else ":String}"))
        return " AND ".join(clauses), parameters

    def fetch(self, spec, start, end, limit, after=None, pit=None, hot=False):
        where, params = self.where(spec, start, end)
        if after:
            where += " AND (event_time, record_id) < ({last:DateTime64(3, 'UTC')}, {id:String})"
            params.update(last=parse_time(after[0]).strftime("%Y-%m-%d %H:%M:%S.%f"), id=after[1])
        params["limit"] = limit
        result = self.client.query(
            f"SELECT event_time, record_id, raw_payload FROM {database()}.{KINDS[spec.kind]} FINAL "
            f"WHERE {where} ORDER BY event_time DESC, record_id DESC LIMIT {{limit:UInt32}}", parameters=params,
        )
        return [{"payload": json.loads(raw), "after": [decode_ck_time(t).isoformat(), rid]} for t, rid, raw in result.result_rows], None

    def count(self, spec, start, end, hot=False):
        where, params = self.where(spec, start, end)
        return self.client.query(f"SELECT count() FROM {database()}.{KINDS[spec.kind]} FINAL WHERE {where}", parameters=params).result_rows[0][0]

    def groups(self, spec, start, end, dimension, hot=False):
        if dimension not in {"ip", "path", "status", "method"}:
            raise QueryError("Unsupported dimension")
        where, params = self.where(spec, start, end)
        params["limit"] = env.get_env_int("LOG_QUERY_MAX_GROUPS", 100000) + 1
        result = self.client.query(
            f"SELECT {dimension}, count() AS n FROM {database()}.{KINDS[spec.kind]} FINAL "
            f"WHERE {where} AND {dimension} IS NOT NULL GROUP BY {dimension} LIMIT {{limit:UInt32}}", parameters=params,
        ).result_rows
        if len(result) == params["limit"]:
            raise QueryError("Too many aggregate groups; narrow the range")
        return result

    def hourly(self, spec, start, end, hot=False):
        where, params = self.where(spec, start, end)
        return self.client.query(
            f"SELECT toUnixTimestamp64Milli(toDateTime64(toStartOfHour(event_time), 3, 'UTC')), count() "
            f"FROM {database()}.{KINDS[spec.kind]} FINAL WHERE {where} GROUP BY 1 ORDER BY 1", parameters=params,
        ).result_rows

    def close(self, pit):
        pass
