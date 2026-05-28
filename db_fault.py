"""断层数据持久化 — SQLite"""

import sqlite3
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "simulation_data.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_fault_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fault_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fault_id TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                name_en TEXT DEFAULT '',
                location_desc TEXT DEFAULT '',
                longitude REAL DEFAULT 0,
                latitude REAL DEFAULT 0,
                strike REAL,
                dip REAL,
                dip_direction REAL,
                length_km REAL,
                width_km REAL,
                slip_rate REAL,
                slip_type TEXT DEFAULT '',
                rake REAL,
                activity_age TEXT DEFAULT '',
                activity_level TEXT DEFAULT '',
                last_event TEXT DEFAULT '',
                recurrence_interval INTEGER,
                max_magnitude REAL,
                segmentation TEXT DEFAULT '',
                coordinates_wkt TEXT DEFAULT '',
                coordinates_json TEXT DEFAULT '',
                source TEXT DEFAULT 'cafd',
                source_url TEXT DEFAULT '',
                reference TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fault_name ON fault_records(name)")
        conn.commit()


def upsert_faults(records: list[dict]) -> int:
    count = 0
    with _get_conn() as conn:
        for r in records:
            cur = conn.execute("""
                INSERT OR IGNORE INTO fault_records
                    (fault_id, name, name_en, location_desc,
                     longitude, latitude,
                     strike, dip, dip_direction, length_km, width_km,
                     slip_rate, slip_type, rake,
                     activity_age, activity_level,
                     last_event, recurrence_interval,
                     max_magnitude, segmentation,
                     coordinates_wkt, coordinates_json,
                     source, source_url, reference)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["fault_id"], r.get("name", ""), r.get("name_en", ""), r.get("location_desc", ""),
                r["longitude"], r["latitude"],
                r.get("strike"), r.get("dip"), r.get("dip_direction"),
                r.get("length_km"), r.get("width_km"),
                r.get("slip_rate"), r.get("slip_type", ""), r.get("rake"),
                r.get("activity_age", ""), r.get("activity_level", ""),
                r.get("last_event", ""), r.get("recurrence_interval"),
                r.get("max_magnitude"), r.get("segmentation", ""),
                r.get("coordinates_wkt", ""), r.get("coordinates_json", ""),
                r.get("source", "cafd"), r.get("source_url", ""), r.get("reference", ""),
            ))
            if cur.rowcount > 0:
                count += 1
        conn.commit()
    return count


def query_faults(
    page: int = 1, per_page: int = 20,
    name_search: Optional[str] = None,
    slip_type: Optional[str] = None,
    min_mag: Optional[float] = None,
    sort_by: str = "name", sort_dir: str = "asc",
) -> tuple[list, int]:
    where = ["1=1"]
    params = []
    if name_search:
        where.append("(name LIKE ? OR name_en LIKE ?)")
        params.extend([f"%{name_search}%", f"%{name_search}%"])
    if slip_type:
        where.append("slip_type LIKE ?")
        params.append(f"%{slip_type}%")
    if min_mag is not None:
        where.append("max_magnitude >= ?")
        params.append(min_mag)
    where_clause = " AND ".join(where)

    allowed = {"name", "length_km", "slip_rate", "max_magnitude", "activity_age"}
    sort_by = sort_by if sort_by in allowed else "name"
    sort_dir_clause = "DESC" if sort_dir.lower() == "desc" else "ASC"

    with _get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM fault_records WHERE {where_clause}", params
        ).fetchone()[0]
        offset = (page - 1) * per_page
        rows = conn.execute(
            f"SELECT * FROM fault_records WHERE {where_clause} "
            f"ORDER BY {sort_by} {sort_dir_clause} LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()
    return [dict(r) for r in rows], total


def get_fault_map_data() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT fault_id, name, longitude, latitude, strike, length_km, "
            "slip_type, max_magnitude FROM fault_records"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_fault(fault_id: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM fault_records WHERE fault_id = ?", (fault_id,))
        conn.commit()
        return cur.rowcount > 0
