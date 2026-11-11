from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from common import env
from common.log_query.clients import ck_client, database, es_client
from common.log_query.types import QueryError, parse_time


def initialize():
    from .hot import install_templates
    client = ck_client(admin=True)
    sql = (Path(__file__).resolve().parents[2] / "docker/config/clickhouse/001_logs.sql").read_text(encoding="utf-8")
    for statement in sql.format(database=database()).split(";"):
        if statement.strip():
            client.command(statement)
    for role, grant in (("READER", "SELECT"), ("WRITER", "SELECT, INSERT")):
        username = env.get_env(f"CK_{role}_USER", f"auditweaver_{role.lower()}")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", username):
            raise QueryError("Invalid ClickHouse user identifier")
        password = env.get_env(f"CK_{role}_PASSWORD")
        if not password:
            raise QueryError(f"CK_{role}_PASSWORD is required")
        client.command(f"CREATE USER IF NOT EXISTS {username} IDENTIFIED WITH sha256_password BY {{password:String}}", parameters={"password": password})
        client.command(f"GRANT {grant} ON {database()}.* TO {username}")
    install_templates(es_client())


def main():
    parser = argparse.ArgumentParser(description="AuditWeaver log hot/cold storage")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create CK tables, users and ES templates; run Django migrations first")
    worker = sub.add_parser("worker")
    worker.add_argument("--sink", choices=["ck", "es"], required=True)
    worker.add_argument("--kind", choices=["raw", "events"], required=True)
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--index", required=True)
    backfill.add_argument("--kind", choices=["raw", "events"], required=True)
    backfill.add_argument("--start", required=True)
    backfill.add_argument("--end", required=True)
    backfill.add_argument("--copy-hot", action="store_true")
    backfill.add_argument("--source-bounds", type=Path, help="Recorded final legacy connector next-offset vector (JSON)")
    clean = sub.add_parser("cleanup")
    clean.add_argument("--index", required=True)
    clean.add_argument("--execute", action="store_true")
    clean.add_argument("--backup-evidence", type=Path)
    sub.add_parser("status")
    certify = sub.add_parser("certify-coverage")
    certify.add_argument("--kind", choices=["raw", "events"], required=True)
    certify.add_argument("--start", default="1970-01-01T00:00:00Z")
    certify.add_argument("--handoff", type=Path, required=True)
    hot = sub.add_parser("certify-hot")
    hot.add_argument("--kind", choices=["raw", "events"], required=True)
    hot.add_argument("--handoff", type=Path, required=True)
    sub.add_parser("supervise")
    sub.add_parser("stop")
    sub.add_parser("cleanup-loop")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.command == "init":
        initialize()
        print("Storage initialized; existing connectors and data were not changed")
    elif args.command == "cleanup-loop":
        from .cleanup_loop import run
        run()
    elif args.command in {"supervise", "stop"}:
        from .supervisor import run, stop
        run() if args.command == "supervise" else stop()
    elif args.command == "worker":
        from .worker import run
        run(args.sink, args.kind)
    elif args.command == "status":
        from .metadata import models
        m = models()
        print(json.dumps({"checkpoints": list(m.Checkpoint.objects.values()), "unresolved_gaps": m.Gap.objects.filter(resolved=False).count(),
                          "manifests": list(m.ArchiveManifest.objects.values())}, default=str, indent=2))
    else:
        from .archive import backfill, cleanup, certify_coverage, certify_hot
        from .clickhouse import ClickHouseStore
        from .metadata import DjangoMetadata
        if args.command == "certify-hot":
            result = certify_hot(es_client(), args.kind, json.loads(args.handoff.read_text(encoding="utf-8")))
        elif args.command == "certify-coverage":
            result = certify_coverage(es_client(), ClickHouseStore(), DjangoMetadata(), args.kind,
                                      parse_time(args.start), json.loads(args.handoff.read_text(encoding="utf-8")))
        elif args.command == "backfill":
            start, end = parse_time(args.start), parse_time(args.end)
            if start >= end:
                raise QueryError("Invalid backfill window")
            bounds = json.loads(args.source_bounds.read_text(encoding="utf-8")) if args.source_bounds else None
            result = backfill(es_client(), ClickHouseStore(), args.index, args.kind, start, end, copy_hot=args.copy_hot, source_bounds=bounds)
        else:
            backup = json.loads(args.backup_evidence.read_text(encoding="utf-8")) if args.backup_evidence else None
            result = cleanup(es_client(), ClickHouseStore() if args.execute else None, DjangoMetadata(), args.index, execute=args.execute, backup=backup)
        print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
