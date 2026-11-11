from common.log_query.clients import ck_client, database, decode_ck_time
from common.log_query.types import KINDS
from .contract import check_identity


class ClickHouseStore:
    def __init__(self, client=None):
        self.client = client or ck_client(writer=True)

    def existing(self, kind, ids):
        if not ids:
            return {}
        result = self.client.query(
            f"SELECT * FROM {database()}.{KINDS[kind]} FINAL WHERE record_id IN {{ids:Array(String)}}",
            parameters={"ids": list(ids)},
        )
        rows = {}
        for row in result.named_results():
            row["event_time"] = decode_ck_time(row["event_time"])
            if isinstance(row["payload_hash"], bytes):
                row["payload_hash"] = row["payload_hash"].decode("ascii")
            if row["record_id"] in rows and rows[row["record_id"]]["event_time"] != row["event_time"]:
                from common.log_query.types import QueryUnavailable
                raise QueryUnavailable("record_id has conflicting event times in the archive")
            rows[row["record_id"]] = row
        return rows

    def write(self, kind, rows):
        if not rows:
            return
        known = self.existing(kind, {r["record_id"] for r in rows})
        for row in rows:
            previous = known.get(row["record_id"])
            if previous:
                check_identity(kind, previous, row)
            if previous is None or row["version"] >= previous["version"]:
                known[row["record_id"]] = row
        columns = list(rows[0])
        self.client.insert(
            f"{database()}.{KINDS[kind]}", [[r[c] for c in columns] for r in rows],
            column_names=columns, settings={"async_insert": 0},
        )
