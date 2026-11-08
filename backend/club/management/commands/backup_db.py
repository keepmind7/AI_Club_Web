import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

KEEP = 7


class Command(BaseCommand):
    help = "SQLite DB를 data/backups/db-YYYYMMDD.sqlite3로 백업하고 최근 7개만 남긴다."

    def handle(self, *args, **options):
        db = Path(settings.DATABASES["default"]["NAME"])
        backup_dir = db.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        dest = backup_dir / f"db-{timezone.localdate():%Y%m%d}.sqlite3"
        # sqlite3 backup()은 실행 중인 DB도 일관된 상태로 복사한다.
        src, dst = sqlite3.connect(db), sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        for old in sorted(backup_dir.glob("db-*.sqlite3"))[:-KEEP]:
            old.unlink()
        self.stdout.write(f"백업 완료: {dest}")
