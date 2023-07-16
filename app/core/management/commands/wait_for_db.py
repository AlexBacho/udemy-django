"""
Django command to wait for the DB to be available.
"""
import time
from typing import Any, Optional

from psycopg2 import OperationalError as Psycopg2Error

from django.db.utils import OperationalError
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Command to wait for database."""

    def handle(self, *args: Any, **options: Any) -> Optional[str]:
        self.stdout.write("Waiting for database.")
        db_up = False
        while not db_up:
            try:
                self.check(databases=["default"])
                db_up = True
            except (Psycopg2Error, OperationalError):
                self.stdout.write("DB not yet available. Sleeping for 1s")
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS("Database ready."))
