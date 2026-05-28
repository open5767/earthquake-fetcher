"""OSM Overpass API 道路数据适配器

API 文档: https://wiki.openstreetmap.org/wiki/Overpass_API
免费、无需注册、全球覆盖。

限制: 单次查询最多返回约 2,000 个要素，大面积需分块查询。
"""

import logging
import math
from typing import Iterator

import requests

from models.road import RoadRecord, HIGHWAY_LEVEL_MAP

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT = 45


class OsmRoadAdapter:
    """OSM 道路数据适配器"""

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SimDataFetcher/1.0 (research)"})
        self._timeout = timeout

    def fetch_by_bbox(self, south: float, west: float,
                      north: float, east: float,
                      bbox_name: str = "") -> list[RoadRecord]:
        """
        按矩形区域查询道路数据。

        Args:
            south, west, north, east: 矩形边界 (WGS84)
            bbox_name: 区域名称标签
        """
        # 限制每次返回 500 条
        query = (
            f'[out:json][timeout:{self._timeout}];'
            f'way[highway]({south},{west},{north},{east});'
            f'out body geom 500;'
        )

        logger.info("OSM 道路查询: %s (%.2f,%.2f ~ %.2f,%.2f)",
                    bbox_name or "自定义区域", south, west, north, east)

        try:
            resp = self._session.post(OVERPASS_URL, data=query, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("OSM Overpass 请求失败: %s", e)
            return []

        elements = data.get("elements", [])
        logger.info("OSM 返回 %d 条道路", len(elements))

        records = []
        for elem in elements:
            tags = elem.get("tags", {})
            highway = tags.get("highway", "")
            name = tags.get("name", "")
            if not highway:
                continue

            # 计算几何
            geom = elem.get("geometry", [])
            mid_idx = len(geom) // 2
            mid_lon = geom[mid_idx]["lon"] if geom else 0
            mid_lat = geom[mid_idx]["lat"] if geom else 0

            # 计算线段长度
            length = self._calc_length(geom)

            road_id = f"osm-road-{elem['id']}"

            lanes_raw = tags.get("lanes", "")
            try:
                lanes = int(lanes_raw) if lanes_raw else None
            except ValueError:
                lanes = None

            maxspeed_raw = tags.get("maxspeed", "")
            try:
                max_speed = int(maxspeed_raw) if maxspeed_raw else None
            except ValueError:
                max_speed = None

            records.append(RoadRecord(
                road_id=road_id,
                name=name,
                highway_level=highway,
                highway_level_cn=HIGHWAY_LEVEL_MAP.get(highway, highway),
                surface=tags.get("surface", ""),
                lanes=lanes,
                oneway=tags.get("oneway", ""),
                max_speed=max_speed,
                length_m=round(length, 1) if length else None,
                longitude=round(mid_lon, 6),
                latitude=round(mid_lat, 6),
                coordinates_json=str([[p["lon"], p["lat"]] for p in geom]),
                source="osm",
                bbox=bbox_name or f"{south},{west},{north},{east}",
                raw_tags=dict(tags),
            ))
        return records

    @staticmethod
    def _calc_length(geom: list) -> float:
        """粗略计算线段长度 (米) — 球面余弦公式"""
        if len(geom) < 2:
            return 0
        total = 0.0
        for i in range(len(geom) - 1):
            lat1 = math.radians(geom[i]["lat"])
            lat2 = math.radians(geom[i + 1]["lat"])
            dlat = lat2 - lat1
            dlon = math.radians(geom[i + 1]["lon"] - geom[i]["lon"])
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            total += 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return total

    def close(self):
        self._session.close()
