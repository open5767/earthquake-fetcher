"""区域划分数据持久化 — SQLite"""

import sqlite3
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "simulation_data.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_zone_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS zone_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                name_en TEXT DEFAULT '',
                level TEXT DEFAULT 'province',
                parent_id TEXT DEFAULT '',
                longitude REAL DEFAULT 0,
                latitude REAL DEFAULT 0,
                coordinates_json TEXT DEFAULT '',
                seismic_pga REAL,
                seismic_intensity TEXT DEFAULT '',
                seismic_desc TEXT DEFAULT '',
                source TEXT DEFAULT 'gadm',
                area_km2 REAL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_zone_name ON zone_records(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_zone_level ON zone_records(level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_zone_pga ON zone_records(seismic_pga)")
        conn.commit()


def upsert_zones(records: list[dict]) -> int:
    count = 0
    with _get_conn() as conn:
        for r in records:
            cur = conn.execute("""
                INSERT OR IGNORE INTO zone_records
                    (zone_id, name, name_en, level, parent_id,
                     longitude, latitude, coordinates_json,
                     seismic_pga, seismic_intensity, seismic_desc,
                     source, area_km2)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["zone_id"], r.get("name", ""), r.get("name_en", ""),
                r.get("level", "province"), r.get("parent_id", ""),
                r["longitude"], r["latitude"], r.get("coordinates_json", ""),
                r.get("seismic_pga"), r.get("seismic_intensity", ""),
                r.get("seismic_desc", ""),
                r.get("source", "gadm"), r.get("area_km2"),
            ))
            if cur.rowcount > 0:
                count += 1
        conn.commit()
    return count


def query_zones(
    page: int = 1, per_page: int = 30,
    name_search: Optional[str] = None,
    level: Optional[str] = None,
    pga_min: Optional[float] = None,
    sort_by: str = "name", sort_dir: str = "asc",
) -> tuple[list, int]:
    where = ["1=1"]
    params = []
    if name_search:
        where.append("(name LIKE ? OR name_en LIKE ?)")
        params.extend([f"%{name_search}%", f"%{name_search}%"])
    if level:
        where.append("level = ?")
        params.append(level)
    if pga_min is not None:
        where.append("seismic_pga >= ?")
        params.append(pga_min)
    where_clause = " AND ".join(where)

    allowed = {"name", "seismic_pga", "level"}
    sort_by = sort_by if sort_by in allowed else "name"
    sort_dir_clause = "DESC" if sort_dir.lower() == "desc" else "ASC"

    with _get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM zone_records WHERE {where_clause}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM zone_records WHERE {where_clause} "
            f"ORDER BY {sort_by} {sort_dir_clause} LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page],
        ).fetchall()
    return [dict(r) for r in rows], total


def get_zone_map_data() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT zone_id, name, longitude, latitude, "
            "seismic_pga, seismic_intensity, level FROM zone_records"
        ).fetchall()
    return [dict(r) for r in rows]


def get_zone_stats() -> dict:
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM zone_records").fetchone()[0]
        if total == 0:
            return {"total": 0, "levels": {}, "pga_distribution": {}}
        level_rows = conn.execute(
            "SELECT level, COUNT(*) as cnt FROM zone_records GROUP BY level"
        ).fetchall()
        pga_rows = conn.execute(
            "SELECT seismic_intensity, COUNT(*) as cnt "
            "FROM zone_records GROUP BY seismic_intensity ORDER BY seismic_pga DESC"
        ).fetchall()
        return {
            "total": total,
            "levels": {r["level"]: r["cnt"] for r in level_rows},
            "pga_distribution": {r["seismic_intensity"] or "未知": r["cnt"] for r in pga_rows},
        }


def delete_zone(zone_id: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM zone_records WHERE zone_id = ?", (zone_id,))
        conn.commit()
        return cur.rowcount > 0
