import sqlite3
import pathlib
from contextlib import contextmanager
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

DB_PATH = pathlib.Path(__file__).parent / "formazioni.db"
SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


@contextmanager
def db():
    con = get_connection()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    """Create tables if they don't exist yet (first run)."""
    if not DB_PATH.exists():
        with get_connection() as con:
            con.executescript(SCHEMA_PATH.read_text())
            con.commit()


def calc_scadenza(data_esecuzione: str, periodicita_anni: int | None) -> str | None:
    """Return ISO expiry date from execution date + years, or None."""
    if not periodicita_anni or not data_esecuzione:
        return None
    try:
        dt = date.fromisoformat(data_esecuzione)
        exp = dt + relativedelta(years=periodicita_anni)
        return exp.isoformat()
    except ValueError:
        return None


def calc_scadenza_mesi(data_visita: str, durata_mesi: int | None) -> str | None:
    """Return ISO expiry date from visit date + months.
    Supports any duration: 3, 6, 12, 24 months, etc.
    Returns None if durata_mesi is None (visita straordinaria senza scadenza).
    """
    if not durata_mesi or not data_visita:
        return None
    try:
        dt = date.fromisoformat(data_visita)
        exp = dt + relativedelta(months=durata_mesi)
        return exp.isoformat()
    except ValueError:
        return None


def calc_stato(data_scadenza: str | None) -> str:
    """Derive status label from expiry date."""
    if not data_scadenza:
        return "valido"
    try:
        exp = date.fromisoformat(data_scadenza)
        today = date.today()
        diff = (exp - today).days
        if diff < 0:
            return "scaduto"
        if diff <= 60:
            return "in_scadenza"
        return "valido"
    except ValueError:
        return "valido"
