"""天气数据持久化 — SQLite"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "simulation_data.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_weather_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weather_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT UNIQUE NOT NULL,
                longitude REAL NOT NULL,
                latitude REAL NOT NULL,
                location_name TEXT DEFAULT '',
                observation_time TEXT NOT NULL,
                source TEXT DEFAULT 'openmeteo',
                temperature REAL,
                temp_min REAL,
                temp_max REAL,
                feels_like REAL,
                precipitation REAL,
                precipitation_prob INTEGER,
                wind_speed REAL,
                wind_direction REAL,
                wind_gust REAL,
                pressure REAL,
                humidity INTEGER,
                cloud_cover INTEGER,
                weather_code INTEGER,
                weather_desc TEXT DEFAULT '',
                visibility REAL,
                uv_index REAL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wx_time ON weather_records(observation_time DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wx_location ON weather_records(latitude, longitude)")
        conn.commit()


def upsert_weather(records: list[dict]) -> int:
    count = 0
    with _get_conn() as conn:
        for r in records:
            cur = conn.execute("""
                INSERT OR IGNORE INTO weather_records
                    (record_id, longitude, latitude, location_name,
                     observation_time, source,
                     temperature, temp_min, temp_max, feels_like,
                     precipitation, precipitation_prob,
                     wind_speed, wind_direction, wind_gust,
                     pressure, humidity,
                     cloud_cover, weather_code, weather_desc,
                     visibility, uv_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["record_id"], r["longitude"], r["latitude"], r.get("location_name", ""),
                r["observation_time"], r.get("source", "openmeteo"),
                r.get("temperature"), r.get("temp_min"), r.get("temp_max"), r.get("feels_like"),
                r.get("precipitation"), r.get("precipitation_prob"),
                r.get("wind_speed"), r.get("wind_direction"), r.get("wind_gust"),
                r.get("pressure"), r.get("humidity"),
                r.get("cloud_cover"), r.get("weather_code"), r.get("weather_desc", ""),
                r.get("visibility"), r.get("uv_index"),
            ))
            if cur.rowcount > 0:
                count += 1
        conn.commit()
    return count


def query_weather(
    page: int = 1, per_page: int = 20,
    location_name: Optional[str] = None,
    start_time: Optional[str] = None, end_time: Optional[str] = None,
    sort_by: str = "observation_time", sort_dir: str = "desc",
) -> tuple[list, int]:
    where = ["1=1"]
    params = []
    if location_name:
        where.append("location_name LIKE ?")
        params.append(f"%{location_name}%")
    if start_time:
        where.append("observation_time >= ?")
        params.append(start_time)
    if end_time:
        where.append("observation_time <= ?")
        params.append(end_time)
    where_clause = " AND ".join(where)

    allowed_sort = {"observation_time", "temperature", "precipitation", "wind_speed", "location_name"}
    sort_by = sort_by if sort_by in allowed_sort else "observation_time"
    sort_dir_clause = "DESC" if sort_dir.lower() == "desc" else "ASC"

    with _get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM weather_records WHERE {where_clause}", params
        ).fetchone()[0]
        offset = (page - 1) * per_page
        rows = conn.execute(
            f"SELECT * FROM weather_records WHERE {where_clause} "
            f"ORDER BY {sort_by} {sort_dir_clause} LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()
    return [dict(r) for r in rows], total


def get_weather_locations() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT location_name, latitude, longitude, COUNT(*) as cnt,
                   MAX(observation_time) as latest
            FROM weather_records
            GROUP BY location_name, latitude, longitude
            ORDER BY location_name
        """).fetchall()
    return [dict(r) for r in rows]


def delete_weather(record_id: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM weather_records WHERE record_id = ?", (record_id,))
        conn.commit()
        return cur.rowcount > 0
