"""Command-line maintenance: `python -m prompt_studio.cli <command>`.

Commands:
  init-db                 create the data directory and run migrations
  backup                  create a database backup
  list-backups            list backups
  validate-backup NAME    validate a backup
  restore-backup NAME     restore a backup (asks for confirmation; stop the app first)
"""

from __future__ import annotations

import argparse
import sys

from .config import get_settings
from .db import dispose_engine, init_db
from .services.backup_service import RESTORE_CONFIRM, BackupService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prompt_studio.cli", description="Prompt Studio maintenance")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    sub.add_parser("backup")
    sub.add_parser("list-backups")
    v = sub.add_parser("validate-backup")
    v.add_argument("name")
    r = sub.add_parser("restore-backup")
    r.add_argument("name")
    r.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    args = parser.parse_args(argv)
    settings = get_settings()

    init_db()
    try:
        if args.cmd == "init-db":
            print(f"Database ready: {settings.db_path}")
        elif args.cmd == "backup":
            print(f"Created {BackupService().create().name} in {settings.backups_dir}")
        elif args.cmd == "list-backups":
            for b in BackupService().list():
                print(f"{b.name}\t{b.size_bytes} bytes\t{b.created_at.isoformat()}")
        elif args.cmd == "validate-backup":
            res = BackupService().validate(args.name)
            for c in res.checks:
                print(f"{'OK ' if c['ok'] else 'FAIL'} {c['name']}: {c['detail']}")
            return 0 if res.valid else 1
        elif args.cmd == "restore-backup":
            if not args.yes:
                answer = input(f"Type {RESTORE_CONFIRM} to replace {settings.db_path} with {args.name}: ")
                if answer != RESTORE_CONFIRM:
                    print("Aborted.")
                    return 1
            out = BackupService().restore(args.name, RESTORE_CONFIRM)
            print(f"Restored {out['restored']}. Safety backup: {out['safety_backup']}")
    finally:
        dispose_engine()
    return 0


if __name__ == "__main__":
    sys.exit(main())
