"""USGS Earthquake Catalog API 适配器

API 文档: https://earthquake.usgs.gov/fdsnws/event/1/
无需注册，无需 API Key，全球免费使用。

限制:
  - 普通请求: 每 30 秒 1 次 (实际上日常使用足够)
  - 单次最多返回 20,000 条
  - 时间范围建议控制在 30 天内 (超过会自动分页)
"""

import logging
from datetime import datetime, timezone
from typing import Iterator

import requests

from adapters.base import EarthquakeAdapter
from models.earthquake import EarthquakeEvent

logger = logging.getLogger(__name__)

USGS_QUERY_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
REQUEST_TIMEOUT = 30  # seconds


class UsgsAdapter(EarthquakeAdapter):
    """USGS 地震目录适配器"""

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "EarthquakeFetcher/1.0 (research project)"
        })
        self._timeout = timeout

    def fetch(self, start_time: str, end_time: str,
              min_magnitude: float = 0.0,
              min_latitude: float = -90, max_latitude: float = 90,
              min_longitude: float = -180, max_longitude: float = 180) -> Iterator[EarthquakeEvent]:

        params = {
            "format": "geojson",
            "starttime": start_time,
            "endtime": end_time,
            "minmagnitude": min_magnitude,
            "minlatitude": min_latitude,
            "maxlatitude": max_latitude,
            "minlongitude": min_longitude,
            "maxlongitude": max_longitude,
            "orderby": "time",
        }

        logger.info("USGS 查询: %s ~ %s, M≥%.1f", start_time, end_time, min_magnitude)

        try:
            resp = self._session.get(USGS_QUERY_URL, params=params, timeout=self._timeout)
            resp.raise_for_status()
            geojson = resp.json()
        except requests.RequestException as e:
            logger.error("USGS API 请求失败: %s", e)
            return

        features = geojson.get("features", [])
        metadata = geojson.get("metadata", {})
        logger.info("USGS 返回 %d 条事件 (总数: %d)", len(features), metadata.get("count", 0))

        for feature in features:
            yield self._parse_feature(feature)

    def _parse_feature(self, feature: dict) -> EarthquakeEvent:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [0, 0, 0])

        event_id = props.get("ids", "") or props.get("code", "") or feature.get("id", "")
        if event_id.startswith(","):
            event_id = event_id[1:]

        time_ms = props.get("time") or 0
        event_time = datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc)

        return EarthquakeEvent(
            event_id=event_id,
            time=event_time,
            longitude=coords[0] if len(coords) > 0 else 0,
            latitude=coords[1] if len(coords) > 1 else 0,
            depth_km=coords[2] if len(coords) > 2 else 0,
            magnitude=props.get("mag") or 0.0,
            mag_type=props.get("magType") or "",
            place=props.get("place") or "",
            source="usgs",
            url=props.get("url") or "",
            felt=props.get("felt"),
            cdi=props.get("cdi"),
            mmi=props.get("mmi"),
            alert=props.get("alert"),
            tsunami=int(props.get("tsunami") or 0),
            significance=props.get("sig") or 0,
            raw_data=props,
        )

    def close(self):
        self._session.close()
