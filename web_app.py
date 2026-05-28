#!/usr/bin/env python3
"""Flask Web 管理后台 — 仿真数据自动获取模块 (多数据源)

已接入模块:
  - 地震事件: USGS + 中国地震台网 (CENC)
  - 天气数据: Open-Meteo (全球免费, 无 API Key)
  - 断层数据: 中国活动断层数据库 (CAFD/CN-faults)
  - 道路数据: OSM Overpass API (免费, 全球)
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

# ---- 地震适配器 ----
from adapters.usgs import UsgsAdapter
from adapters.cenc import CencAdapter
from db import init_db, upsert_events, query_events, get_event_by_id, delete_event, get_stats, get_map_data

# ---- 天气适配器 ----
from adapters.weather_openmeteo import OpenMeteoAdapter, CHINA_CITIES
from db_weather import init_weather_db, upsert_weather, query_weather, get_weather_locations, delete_weather

# ---- 断层适配器 ----
from adapters.fault_cn import CNActiveFaultAdapter
from db_fault import init_fault_db, upsert_faults, query_faults, get_fault_map_data, delete_fault

# ---- 道路适配器 ----
from adapters.road_osm import OsmRoadAdapter
from db_road import init_road_db, upsert_roads, query_roads, get_road_stats, delete_road

# ---- 区域划分适配器 ----
from adapters.zone_gadm import GadmAdapter
from db_zone import init_zone_db, upsert_zones, query_zones, get_zone_map_data, get_zone_stats, delete_zone

from config import USGS_TIMEOUT, DEFAULT_MIN_MAGNITUDE, CHINA_BOUNDS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("web")

app = Flask(__name__)

# ---- 初始化所有数据库 ----
init_db()
init_weather_db()
init_fault_db()
init_road_db()
init_zone_db()

# 断层数据首次自动填充
try:
    from db_fault import _get_conn
    c = _get_conn().execute("SELECT COUNT(*) FROM fault_records").fetchone()[0]
    if c == 0:
        adapter = CNActiveFaultAdapter()
        faults = adapter.fetch_all()
        upsert_faults([f.to_dict() for f in faults])
        logger.info("断层数据初始化: %d 条", len(faults))
except Exception as e:
    logger.warning("断层数据初始化跳过: %s", e)


# ===================== 模块注册 =====================

MODULES = [
    {"key": "eq",    "name": "地震事件", "icon": "🌍", "endpoint": "eq_dashboard"},
    {"key": "wx",    "name": "天气数据", "icon": "🌤", "endpoint": "wx_dashboard"},
    {"key": "fault", "name": "断层数据", "icon": "🏔", "endpoint": "fault_list"},
    {"key": "road",  "name": "道路数据", "icon": "🛣", "endpoint": "road_list_page"},
    {"key": "zone",  "name": "区域划分", "icon": "🗺", "endpoint": "zone_page"},
]

@app.context_processor
def inject_modules():
    return {"modules": MODULES}


# ==================== 首页 ====================

@app.route("/")
def index():
    return render_template("dashboard.html")


# ==================== 地震模块 ====================

@app.route("/earthquake")
def eq_dashboard():
    return render_template("dashboard.html")


@app.route("/earthquake/list")
def eq_list():
    return render_template("list.html")


@app.route("/earthquake/<event_id>")
def eq_detail(event_id):
    ev = get_event_by_id(event_id)
    if not ev:
        return render_template("404.html"), 404
    return render_template("detail.html", event=ev)


# ==================== 天气模块 ====================

@app.route("/weather")
def wx_dashboard():
    return render_template("weather.html")


@app.route("/weather/list")
def wx_list():
    return render_template("weather_list.html")


# ==================== 断层模块 ====================

@app.route("/fault")
def fault_list():
    return render_template("fault.html")


# ==================== 地震 API ====================

@app.route("/api/eq/stats")
def api_eq_stats():
    source = request.args.get("source")
    return jsonify(get_stats(source=source))


@app.route("/api/eq/events")
def api_eq_events():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    min_mag = request.args.get("min_mag", type=float)
    max_mag = request.args.get("max_mag", type=float)
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    place = request.args.get("place")
    source = request.args.get("source")
    sort_by = request.args.get("sort_by", "time")
    sort_dir = request.args.get("sort_dir", "desc")

    rows, total = query_events(
        page=page, per_page=per_page, min_mag=min_mag, max_mag=max_mag,
        start_time=start_time, end_time=end_time, place_search=place,
        source=source, sort_by=sort_by, sort_dir=sort_dir,
    )
    return jsonify({
        "data": rows, "total": total, "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


@app.route("/api/eq/map")
def api_eq_map():
    min_mag = request.args.get("min_mag", 0, type=float)
    source = request.args.get("source")
    return jsonify(get_map_data(min_mag=min_mag, source=source))


@app.route("/api/eq/fetch", methods=["POST"])
def api_eq_fetch():
    data = request.get_json() or {}
    source = data.get("source", "usgs")
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

    if source == "cenc":
        adapter = CencAdapter(timeout=USGS_TIMEOUT)
    else:
        adapter = UsgsAdapter(timeout=USGS_TIMEOUT)

    events = list(adapter.fetch(
        start_time=start_time, end_time=end_time, min_magnitude=min_mag,
        min_latitude=min_lat, max_latitude=max_lat,
        min_longitude=min_lon, max_longitude=max_lon,
    ))
    adapter.close()
    new_count = upsert_events([e.to_dict() for e in events])

    label = "中国地震台网" if source == "cenc" else "USGS"
    return jsonify({"ok": True, "source": source, "fetched": len(events),
                    "new": new_count, "message": f"{label} 返回 {len(events)} 条，新增入库 {new_count} 条"})


@app.route("/api/eq/events/<event_id>", methods=["DELETE"])
def api_eq_delete(event_id):
    ok = delete_event(event_id)
    return jsonify({"ok": ok}), 200 if ok else 404


# ==================== 天气 API ====================

@app.route("/api/wx/fetch", methods=["POST"])
def api_wx_fetch():
    """拉取中国主要城市天气数据"""
    data = request.get_json() or {}
    days = data.get("days", 7)
    city_filter = data.get("cities", [])  # 可选: 指定城市名列表

    adapter = OpenMeteoAdapter()
    all_records = []
    cities_processed = 0

    for city in CHINA_CITIES:
        if city_filter and city["name"] not in city_filter:
            continue
        try:
            records = adapter.fetch_forecast(
                lat=city["lat"], lon=city["lon"],
                location_name=city["name"], days=days,
            )
            all_records.extend(records)
            cities_processed += 1
        except Exception as e:
            logger.warning("天气拉取失败 %s: %s", city["name"], e)

    adapter.close()

    new_count = upsert_weather([r.to_dict() for r in all_records]) if all_records else 0

    return jsonify({
        "ok": True,
        "cities": cities_processed,
        "fetched": len(all_records),
        "new": new_count,
        "message": f"处理 {cities_processed} 个城市, 返回 {len(all_records)} 条天气记录, 新增 {new_count} 条",
    })


@app.route("/api/wx/fetch_point", methods=["POST"])
def api_wx_fetch_point():
    """拉取指定坐标的天气数据 — 地图点击选点"""
    data = request.get_json() or {}
    lat = data.get("lat", 0)
    lon = data.get("lon", 0)
    name = data.get("name", f"{lat:.2f},{lon:.2f}")
    days = data.get("days", 7)

    adapter = OpenMeteoAdapter()
    try:
        records = adapter.fetch_forecast(lat=lat, lon=lon, location_name=name, days=days)
    finally:
        adapter.close()

    new_count = upsert_weather([r.to_dict() for r in records]) if records else 0

    return jsonify({
        "ok": True,
        "name": name,
        "fetched": len(records),
        "new": new_count,
        "message": f"坐标 ({lat:.2f}, {lon:.2f}) 返回 {len(records)} 条预报, 新增 {new_count} 条",
    })


@app.route("/api/wx/records")
def api_wx_records():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 30, type=int)
    location = request.args.get("location")
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    sort_by = request.args.get("sort_by", "observation_time")
    sort_dir = request.args.get("sort_dir", "desc")

    rows, total = query_weather(
        page=page, per_page=per_page, location_name=location,
        start_time=start_time, end_time=end_time,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    return jsonify({
        "data": rows, "total": total, "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


@app.route("/api/wx/locations")
def api_wx_locations():
    return jsonify(get_weather_locations())


@app.route("/api/wx/records/<record_id>", methods=["DELETE"])
def api_wx_delete(record_id):
    ok = delete_weather(record_id)
    return jsonify({"ok": ok}), 200 if ok else 404


# ==================== 断层 API ====================

@app.route("/api/fault/list")
def api_fault_list():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    name = request.args.get("name")
    slip_type = request.args.get("slip_type")
    min_mag = request.args.get("min_mag", type=float)
    sort_by = request.args.get("sort_by", "name")
    sort_dir = request.args.get("sort_dir", "asc")

    rows, total = query_faults(
        page=page, per_page=per_page, name_search=name,
        slip_type=slip_type, min_mag=min_mag,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    return jsonify({
        "data": rows, "total": total, "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


@app.route("/api/fault/map")
def api_fault_map():
    return jsonify(get_fault_map_data())


@app.route("/api/fault/<fault_id>", methods=["DELETE"])
def api_fault_delete(fault_id):
    ok = delete_fault(fault_id)
    return jsonify({"ok": ok}), 200 if ok else 404


# ==================== 道路模块 ====================

@app.route("/road")
def road_list_page():
    return render_template("road.html")


@app.route("/api/road/fetch", methods=["POST"])
def api_road_fetch():
    """按矩形区域拉取 OSM 道路数据"""
    data = request.get_json() or {}
    south = data.get("south", 39.9)
    west = data.get("west", 116.3)
    north = data.get("north", 40.0)
    east = data.get("east", 116.5)
    name = data.get("name", "自定义区域")

    adapter = OsmRoadAdapter()
    try:
        records = adapter.fetch_by_bbox(south, west, north, east, bbox_name=name)
    finally:
        adapter.close()

    new_count = upsert_roads([r.to_dict() for r in records]) if records else 0
    return jsonify({
        "ok": True, "fetched": len(records), "new": new_count,
        "message": f"区域「{name}」返回 {len(records)} 条道路, 新增 {new_count} 条",
    })


@app.route("/api/road/list")
def api_road_list():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 30, type=int)
    name = request.args.get("name")
    level = request.args.get("level")
    sort_by = request.args.get("sort_by", "length_m")
    sort_dir = request.args.get("sort_dir", "desc")

    rows, total = query_roads(
        page=page, per_page=per_page, name_search=name,
        highway_level=level, sort_by=sort_by, sort_dir=sort_dir,
    )
    return jsonify({
        "data": rows, "total": total, "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


@app.route("/api/road/stats")
def api_road_stats():
    return jsonify(get_road_stats())


@app.route("/api/road/<road_id>", methods=["DELETE"])
def api_road_delete(road_id):
    ok = delete_road(road_id)
    return jsonify({"ok": ok}), 200 if ok else 404


# ==================== 区域划分模块 ====================

@app.route("/zone")
def zone_page():
    return render_template("zone.html")


@app.route("/api/zone/load", methods=["POST"])
def api_zone_load():
    """从 GADM 下载中国省级行政区划 + 抗震设防属性"""
    adapter = GadmAdapter()
    try:
        records = adapter.fetch_china_provinces()
    finally:
        adapter.close()

    new_count = upsert_zones([r.to_dict() for r in records]) if records else 0
    return jsonify({
        "ok": True, "fetched": len(records), "new": new_count,
        "message": f"GADM 返回 {len(records)} 个省级区域, 新增 {new_count} 个",
    })


@app.route("/api/zone/list")
def api_zone_list():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    name = request.args.get("name")
    level = request.args.get("level")
    pga_min = request.args.get("pga_min", type=float)
    sort_by = request.args.get("sort_by", "name")
    sort_dir = request.args.get("sort_dir", "asc")

    rows, total = query_zones(
        page=page, per_page=per_page, name_search=name,
        level=level, pga_min=pga_min, sort_by=sort_by, sort_dir=sort_dir,
    )
    return jsonify({
        "data": rows, "total": total, "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


@app.route("/api/zone/map")
def api_zone_map():
    return jsonify(get_zone_map_data())


@app.route("/api/zone/stats")
def api_zone_stats():
    return jsonify(get_zone_stats())


@app.route("/api/zone/<zone_id>", methods=["DELETE"])
def api_zone_delete(zone_id):
    ok = delete_zone(zone_id)
    return jsonify({"ok": ok}), 200 if ok else 404


# ==================== 离线瓦片 ====================

TILES_ROOT = Path(__file__).parent / "static" / "tiles"


@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def serve_tile(z, x, y):
    tile_path = TILES_ROOT / str(z) / str(x) / f"{y}.png"
    if tile_path.exists():
        return send_from_directory(tile_path.parent, tile_path.name)
    return "", 404


@app.route("/api/tile-status")
def tile_status():
    if not TILES_ROOT.exists():
        return jsonify({"available": False, "count": 0, "size_mb": 0})
    pngs = list(TILES_ROOT.rglob("*.png"))
    total_bytes = sum(f.stat().st_size for f in pngs) if pngs else 0
    return jsonify({"available": len(pngs) > 0, "count": len(pngs),
                    "size_mb": round(total_bytes / 1024 / 1024, 1)})


# ==================== 启动 ====================

if __name__ == "__main__":
    print("\n  仿真数据自动获取模块: http://127.0.0.1:5000")
    print("    - 地震事件: /earthquake")
    print("    - 天气数据: /weather")
    print("    - 断层数据: /fault\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
