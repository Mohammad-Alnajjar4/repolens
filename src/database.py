import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List
from src.config import DB_PATH


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                source_type TEXT NOT NULL,
                total_loc INTEGER NOT NULL,
                function_count INTEGER NOT NULL,
                average_complexity REAL NOT NULL,
                max_complexity INTEGER NOT NULL,
                warning_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()


def save_scan(report: Dict[str, Any], source_type: str = "snippet", db_path: str = DB_PATH) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            '''INSERT INTO scans (filename, source_type, total_loc, function_count,
               average_complexity, max_complexity, warning_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                report["filename"],
                source_type,
                report["total_loc"],
                report["function_count"],
                report["average_complexity"],
                report["max_complexity"],
                len(report["warnings"]),
                created_at,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_scans(limit: int = 20, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


def delete_scan(scan_id: int, db_path: str = DB_PATH) -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
        conn.commit()
        return cursor.rowcount > 0
