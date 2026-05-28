"""SQLite 数据持久化 — 地震事件 CRUD，兼容 USGS + CENC 双数据源"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "earthquake.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS earthquake_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                time TEXT NOT NULL,
                longitude REAL NOT NULL,
                latitude REAL NOT NULL,
                depth_km REAL DEFAULT 0,
                magnitude REAL DEFAULT 0,
                mag_type TEXT DEFAULT '',
                place TEXT DEFAULT '',
                source TEXT DEFAULT 'usgs',
                url TEXT DEFAULT '',
                felt INTEGER,
                cdi REAL,
                mmi REAL,
                alert TEXT,
                tsunami INTEGER DEFAULT 0,
                significance INTEGER DEFAULT 0,
                intensity INTEGER DEFAULT 0,
                intensity_label TEXT DEFAULT '',
                report_time TEXT,
                event_type TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # 兼容旧表结构 — 如果缺少 CENC 字段则自动补齐
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(earthquake_events)")}
        for col, col_type in [
            ("intensity", "INTEGER DEFAULT 0"),
            ("intensity_label", "TEXT DEFAULT ''"),
            ("report_time", "TEXT"),
            ("event_type", "TEXT DEFAULT ''"),
        ]:
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE earthquake_events ADD COLUMN {col} {col_type}")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_eq_time ON earthquake_events(time DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_eq_mag ON earthquake_events(magnitude DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_eq_source ON earthquake_events(source)")
        conn.commit()


def upsert_events(events: list[dict]) -> int:
    """批量 upsert，按 event_id 去重，返回新增条数"""
    count = 0
    with get_conn() as conn:
        for e in events:
            cur = conn.execute("""
                INSERT OR IGNORE INTO earthquake_events
                    (event_id, time, longitude, latitude, depth_km,
                     magnitude, mag_type, place, source, url,
                     felt, cdi, mmi, alert, tsunami, significance,
                     intensity, intensity_label, report_time, event_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                e["event_id"], e["time"], e["longitude"], e["latitude"],
                e["depth_km"], e["magnitude"], e["mag_type"], e["place"],
                e["source"], e["url"], e.get("felt"), e.get("cdi"),
                e.get("mmi"), e.get("alert"), e.get("tsunami"),
                e.get("significance"),
                e.get("intensity", 0), e.get("intensity_label", ""),
                e.get("report_time"), e.get("event_type", ""),
            ))
            if cur.rowcount > 0:
                count += 1
        conn.commit()
    return count


def query_events(
    page: int = 1,
    per_page: int = 20,
    min_mag: Optional[float] = None,
    max_mag: Optional[float] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    place_search: Optional[str] = None,
    source: Optional[str] = None,
    sort_by: str = "time",
    sort_dir: str = "desc",
) -> tuple[list, int]:
    """分页查询 + 过滤 + 排序，返回 (rows, total_count)"""
    where = ["1=1"]
    params = []

    if min_mag is not None:
        where.append("magnitude >= ?")
        params.append(min_mag)
    if max_mag is not None:
        where.append("magnitude <= ?")
        params.append(max_mag)
    if start_time:
        where.append("time >= ?")
        params.append(start_time)
    if end_time:
        where.append("time <= ?")
        params.append(end_time)
    if place_search:
        where.append("place LIKE ?")
        params.append(f"%{place_search}%")
    if source:
        where.append("source = ?")
        params.append(source)

    where_clause = " AND ".join(where)

    allowed_sort = {"time", "magnitude", "depth_km", "significance", "intensity"}
    if sort_by not in allowed_sort:
        sort_by = "time"
    sort_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"

    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM earthquake_events WHERE {where_clause}", params
        ).fetchone()[0]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"SELECT * FROM earthquake_events WHERE {where_clause} "
            f"ORDER BY {sort_by} {sort_dir} LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()

    return [dict(r) for r in rows], total


def get_event_by_id(event_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM earthquake_events WHERE event_id = ?", (event_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_event(event_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM earthquake_events WHERE event_id = ?", (event_id,)
        )
        conn.commit()
        return cur.rowcount > 0


def get_stats(source: Optional[str] = None) -> dict:
    with get_conn() as conn:
        if source:
            total = conn.execute(
                "SELECT COUNT(*) FROM earthquake_events WHERE source = ?", (source,)
            ).fetchone()[0]
        else:
            total = conn.execute("SELECT COUNT(*) FROM earthquake_events").fetchone()[0]

        if total == 0:
            return {
                "total": 0, "max_mag": 0, "min_mag": 0, "avg_depth": 0,
                "last_fetch": None, "latest_event_time": None,
                "mag_distribution": {"m7plus": 0, "m6_7": 0, "m5_6": 0, "m4_5": 0, "m3minus": 0},
                "source_breakdown": {},
            }

        base_where = f"WHERE source = '{source}'" if source else ""

        mag_stats = conn.execute(
            f"SELECT MAX(magnitude), MIN(magnitude), AVG(depth_km) FROM earthquake_events {base_where}"
        ).fetchone()
        last = conn.execute(
            f"SELECT MAX(time) FROM earthquake_events {base_where}"
        ).fetchone()[0]
        last_fetch = conn.execute(
            f"SELECT MAX(created_at) FROM earthquake_events {base_where}"
        ).fetchone()[0]
        mag_dist = conn.execute(f"""
            SELECT
                SUM(CASE WHEN magnitude >= 7.0 THEN 1 ELSE 0 END) as m7,
                SUM(CASE WHEN magnitude >= 6.0 AND magnitude < 7.0 THEN 1 ELSE 0 END) as m6,
                SUM(CASE WHEN magnitude >= 5.0 AND magnitude < 6.0 THEN 1 ELSE 0 END) as m5,
                SUM(CASE WHEN magnitude >= 4.0 AND magnitude < 5.0 THEN 1 ELSE 0 END) as m4,
                SUM(CASE WHEN magnitude < 4.0 THEN 1 ELSE 0 END) as m3
            FROM earthquake_events {base_where}
        """).fetchone()

        # 数据源分布
        src_rows = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM earthquake_events GROUP BY source"
        ).fetchall()
        source_breakdown = {r["source"]: r["cnt"] for r in src_rows}

    return {
        "total": total,
        "max_mag": round(mag_stats[0], 1) if mag_stats[0] else 0,
        "min_mag": round(mag_stats[1], 1) if mag_stats[1] else 0,
        "avg_depth": round(mag_stats[2], 1) if mag_stats[2] else 0,
        "latest_event_time": last,
        "last_fetch": last_fetch,
        "mag_distribution": {
            "m7plus": mag_dist["m7"] or 0,
            "m6_7": mag_dist["m6"] or 0,
            "m5_6": mag_dist["m5"] or 0,
            "m4_5": mag_dist["m4"] or 0,
            "m3minus": mag_dist["m3"] or 0,
        },
        "source_breakdown": source_breakdown,
    }


def get_map_data(min_mag: float = 0, source: Optional[str] = None) -> list[dict]:
    with get_conn() as conn:
        if source:
            rows = conn.execute(
                "SELECT event_id, time, longitude, latitude, depth_km, magnitude, place, source "
                "FROM earthquake_events WHERE magnitude >= ? AND source = ? "
                "ORDER BY time DESC LIMIT 500",
                (min_mag, source),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT event_id, time, longitude, latitude, depth_km, magnitude, place, source "
                "FROM earthquake_events WHERE magnitude >= ? "
                "ORDER BY time DESC LIMIT 500",
                (min_mag,),
            ).fetchall()
    return [dict(r) for r in rows]
