"""道路数据持久化 — SQLite"""

import sqlite3
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "simulation_data.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_road_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS road_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                road_id TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                highway_level TEXT DEFAULT '',
                highway_level_cn TEXT DEFAULT '',
                surface TEXT DEFAULT '',
                lanes INTEGER,
                oneway TEXT DEFAULT '',
                max_speed INTEGER,
                length_m REAL,
                longitude REAL DEFAULT 0,
                latitude REAL DEFAULT 0,
                coordinates_json TEXT DEFAULT '',
                source TEXT DEFAULT 'osm',
                bbox TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_road_name ON road_records(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_road_level ON road_records(highway_level)")
        conn.commit()


def upsert_roads(records: list[dict]) -> int:
    count = 0
    with _get_conn() as conn:
        for r in records:
            cur = conn.execute("""
                INSERT OR IGNORE INTO road_records
                    (road_id, name, highway_level, highway_level_cn,
                     surface, lanes, oneway, max_speed, length_m,
                     longitude, latitude, coordinates_json, source, bbox)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["road_id"], r.get("name", ""),
                r.get("highway_level", ""), r.get("highway_level_cn", ""),
                r.get("surface", ""), r.get("lanes"), r.get("oneway", ""),
                r.get("max_speed"), r.get("length_m"),
                r["longitude"], r["latitude"],
                r.get("coordinates_json", ""), r.get("source", "osm"), r.get("bbox", ""),
            ))
            if cur.rowcount > 0:
                count += 1
        conn.commit()
    return count


def query_roads(
    page: int = 1, per_page: int = 30,
    name_search: Optional[str] = None,
    highway_level: Optional[str] = None,
    sort_by: str = "length_m", sort_dir: str = "desc",
) -> tuple[list, int]:
    where = ["1=1"]
    params = []
    if name_search:
        where.append("name LIKE ?")
        params.append(f"%{name_search}%")
    if highway_level:
        where.append("highway_level = ?")
        params.append(highway_level)
    where_clause = " AND ".join(where)

    allowed = {"name", "length_m", "highway_level", "lanes", "max_speed"}
    sort_by = sort_by if sort_by in allowed else "length_m"
    sort_dir_clause = "DESC" if sort_dir.lower() == "desc" else "ASC"

    with _get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM road_records WHERE {where_clause}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM road_records WHERE {where_clause} "
            f"ORDER BY {sort_by} {sort_dir_clause} LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page],
        ).fetchall()
    return [dict(r) for r in rows], total


def get_road_stats() -> dict:
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM road_records").fetchone()[0]
        if total == 0:
            return {"total": 0, "total_length_km": 0, "levels": {}}
        total_len = conn.execute(
            "SELECT SUM(length_m) FROM road_records"
        ).fetchone()[0] or 0
        level_rows = conn.execute(
            "SELECT highway_level_cn, COUNT(*) as cnt "
            "FROM road_records GROUP BY highway_level_cn ORDER BY cnt DESC"
        ).fetchall()
        return {
            "total": total,
            "total_length_km": round(total_len / 1000, 1),
            "levels": {r["highway_level_cn"] or "未分类": r["cnt"] for r in level_rows},
        }


def delete_road(road_id: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM road_records WHERE road_id = ?", (road_id,))
        conn.commit()
        return cur.rowcount > 0
