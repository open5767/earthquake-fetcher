#!/usr/bin/env python3
"""Flask Web 管理后台 — 地震仿真数据管理"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import os

from flask import Flask, jsonify, render_template, request, send_from_directory

from adapters.usgs import UsgsAdapter
from config import USGS_TIMEOUT, DEFAULT_MIN_MAGNITUDE, CHINA_BOUNDS
from db import init_db, upsert_events, query_events, get_event_by_id, delete_event, get_stats, get_map_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("web")

app = Flask(__name__)

# ---- 初始化 ----
init_db()


# ===================== 页面路由 =====================

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/events")
def event_list():
    return render_template("list.html")


@app.route("/events/<event_id>")
def event_detail(event_id):
    ev = get_event_by_id(event_id)
    if not ev:
        return render_template("404.html"), 404
    return render_template("detail.html", event=ev)


# ===================== API 路由 =====================

@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())


@app.route("/api/events")
def api_events():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    min_mag = request.args.get("min_mag", type=float)
    max_mag = request.args.get("max_mag", type=float)
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    place = request.args.get("place")
    sort_by = request.args.get("sort_by", "time")
    sort_dir = request.args.get("sort_dir", "desc")

    rows, total = query_events(
        page=page, per_page=per_page,
        min_mag=min_mag, max_mag=max_mag,
        start_time=start_time, end_time=end_time,
        place_search=place, sort_by=sort_by, sort_dir=sort_dir,
    )

    return jsonify({
        "data": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


@app.route("/api/map")
def api_map():
    min_mag = request.args.get("min_mag", 0, type=float)
    return jsonify(get_map_data(min_mag=min_mag))


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    """手动触发数据拉取"""
    data = request.get_json() or {}
    days = data.get("days", 7)
    min_mag = data.get("min_mag", DEFAULT_MIN_MAGNITUDE)
    region = data.get("region", "global")

    end_time = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_time = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    if region == "china":
        min_lat, max_lat = CHINA_BOUNDS["min_latitude"], CHINA_BOUNDS["max_latitude"]
        min_lon, max_lon = CHINA_BOUNDS["min_longitude"], CHINA_BOUNDS["max_longitude"]
    else:
        min_lat, max_lat = data.get("min_lat", -90), data.get("max_lat", 90)
        min_lon, max_lon = data.get("min_lon", -180), data.get("max_lon", 180)

    adapter = UsgsAdapter(timeout=USGS_TIMEOUT)
    try:
        events = list(adapter.fetch(
            start_time=start_time,
            end_time=end_time,
            min_magnitude=min_mag,
            min_latitude=min_lat,
            max_latitude=max_lat,
            min_longitude=min_lon,
            max_longitude=max_lon,
        ))
    finally:
        adapter.close()

    new_count = upsert_events([e.to_dict() for e in events])

    logger.info("拉取完成: API返回%d条, 新增入库%d条", len(events), new_count)

    return jsonify({
        "ok": True,
        "fetched": len(events),
        "new": new_count,
        "message": f"USGS 返回 {len(events)} 条，新增入库 {new_count} 条",
    })


@app.route("/api/events/<event_id>", methods=["DELETE"])
def api_delete_event(event_id):
    ok = delete_event(event_id)
    return jsonify({"ok": ok}), 200 if ok else 404


# ===================== 离线瓦片服务 =====================

TILES_ROOT = Path(__file__).parent / "static" / "tiles"


@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def serve_tile(z: int, x: int, y: int):
    """提供本地缓存的瓦片"""
    tile_path = TILES_ROOT / str(z) / str(x) / f"{y}.png"
    if tile_path.exists():
        return send_from_directory(tile_path.parent, tile_path.name)
    return "", 404


@app.route("/api/tile-status")
def tile_status():
    """检查瓦片缓存状态"""
    if not TILES_ROOT.exists():
        return jsonify({"available": False, "count": 0, "size_mb": 0})

    pngs = list(TILES_ROOT.rglob("*.png"))
    total_bytes = sum(f.stat().st_size for f in pngs) if pngs else 0
    return jsonify({
        "available": len(pngs) > 0,
        "count": len(pngs),
        "size_mb": round(total_bytes / 1024 / 1024, 1),
    })


# ===================== 启动 =====================

if __name__ == "__main__":
    print("\n  地震数据管理后台: http://127.0.0.1:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
