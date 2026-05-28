"""中国地震台网 (CENC) 数据适配器

数据来源: Wolfx API — 代理封装中国地震台网中心公开数据
接口: https://api.wolfx.jp/cenc_eqlist.json
说明: 返回最近 10 条正式测定/自动测定地震速报数据，含中文地名和中国烈度

中国地震烈度与震级对照 (参考 GB/T 17742-2008):
  1度: 无感，仅仪器记录
  2度: 室内个别静止中的人有感觉
  3度: 室内少数人有感觉，悬挂物轻微摆动
  4度: 室内多数人有感，室外少数人，门窗作响
  5度: 室内多数人、室外少数人，睡觉的人惊醒
  6度: 多数人站立不稳，器皿倾倒，房屋轻微损坏
  7度: 轻度破坏，房屋局部破坏，地表出现裂缝
  8度: 中等破坏，房屋结构受损，多数人惊慌
  9度: 严重破坏，房屋大量损坏，地面严重变形
  10度: 毁灭性破坏，大多数房屋倒塌
  11度: 灾难性破坏，几乎全部建筑物毁坏
  12度: 山河改观，一切建筑物毁坏
"""

import logging
from datetime import datetime, timezone
from typing import Iterator

import requests

from adapters.base import EarthquakeAdapter
from models.earthquake import EarthquakeEvent

logger = logging.getLogger(__name__)

CENC_API_URL = "https://api.wolfx.jp/cenc_eqlist.json"
REQUEST_TIMEOUT = 15

INTENSITY_LABELS = {
    1: "Ⅰ度(无感)", 2: "Ⅱ度(微感)", 3: "Ⅲ度(微感)",
    4: "Ⅳ度(有感)", 5: "Ⅴ度(惊醒)", 6: "Ⅵ度(惊慌)",
    7: "Ⅶ度(破坏)", 8: "Ⅷ度(破坏)", 9: "Ⅸ度(严重)",
    10: "Ⅹ度(毁灭)", 11: "Ⅺ度(灾难)", 12: "Ⅻ度(山崩地裂)",
}

EVENT_TYPE_LABELS = {
    "reviewed": "正式测定",
    "automatic": "自动测定",
}


class CencAdapter(EarthquakeAdapter):
    """中国地震台网适配器 — 速报数据"""

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "EarthquakeFetcher/1.0 (research project)"
        })
        self._timeout = timeout

    def fetch(self, start_time: str = "", end_time: str = "",
              min_magnitude: float = 0.0,
              min_latitude: float = -90, max_latitude: float = 90,
              min_longitude: float = -180, max_longitude: float = 180) -> Iterator[EarthquakeEvent]:
        """
        从中国地震台网拉取速报数据。

        注意: CENC 公开接口仅返回最新一批速报(约 30 天内)，不支持自定义时间范围。
        传入的 start_time/end_time 仅用于客户端侧过滤。
        """
        logger.info("CENC 查询速报数据 (Wolfx API)")

        try:
            resp = self._session.get(CENC_API_URL, timeout=self._timeout)
            resp.raise_for_status()
            raw_data = resp.json()
        except requests.RequestException as e:
            logger.error("CENC API 请求失败: %s", e)
            return

        items = self._parse_response(raw_data)
        logger.info("CENC 返回 %d 条速报", len(items))

        for item in items:
            ev = self._parse_item(item)

            # 客户端侧过滤
            if ev.magnitude < min_magnitude:
                continue
            if not (min_latitude <= ev.latitude <= max_latitude):
                continue
            if not (min_longitude <= ev.longitude <= max_longitude):
                continue
            if start_time and ev.time.isoformat() < start_time:
                continue
            if end_time and ev.time.isoformat() > end_time:
                continue

            yield ev

    def _parse_response(self, raw_data: dict) -> list[dict]:
        """解析 Wolfx API 响应 — 键名为 No1, No2, ..., NoN"""
        items = []
        for key, value in raw_data.items():
            if key.startswith("No") and isinstance(value, dict):
                value["_no"] = int(key[2:])
                items.append(value)
        items.sort(key=lambda x: x["_no"])
        return items

    def _parse_item(self, item: dict) -> EarthquakeEvent:
        event_id = item.get("EventID", "")

        # 时间: "2026-05-21 10:15:02"
        time_str = item.get("time", "")
        try:
            event_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            event_time = event_time.replace(tzinfo=timezone.utc)
        except ValueError:
            event_time = datetime.now(timezone.utc)

        # 速报时间
        report_str = item.get("ReportTime", "")
        try:
            report_time = datetime.strptime(report_str, "%Y-%m-%d %H:%M:%S")
            report_time = report_time.replace(tzinfo=timezone.utc)
        except ValueError:
            report_time = None

        try:
            magnitude = float(item.get("magnitude", "0"))
        except (ValueError, TypeError):
            magnitude = 0.0

        try:
            depth = float(item.get("depth", "0"))
        except (ValueError, TypeError):
            depth = 0.0

        try:
            lat = float(item.get("latitude", "0"))
        except (ValueError, TypeError):
            lat = 0.0

        try:
            lon = float(item.get("longitude", "0"))
        except (ValueError, TypeError):
            lon = 0.0

        try:
            intensity = int(item.get("intensity", "0"))
        except (ValueError, TypeError):
            intensity = 0

        event_type = item.get("type", "")
        event_type_cn = EVENT_TYPE_LABELS.get(event_type, event_type)
        intensity_label = INTENSITY_LABELS.get(intensity, f"{intensity}度") if intensity else ""

        place = item.get("location") or item.get("placeName") or ""

        return EarthquakeEvent(
            event_id=event_id,
            time=event_time,
            longitude=lon,
            latitude=lat,
            depth_km=depth,
            magnitude=magnitude,
            mag_type="M",
            place=place,
            source="cenc",
            url=f"http://www.ceic.ac.cn/history/{event_id}",
            alert=None,
            tsunami=0,
            significance=0,
            intensity=intensity,
            report_time=report_time.isoformat() if report_time else None,
            event_type=event_type_cn,
            intensity_label=intensity_label,
            raw_data=item,
        )

    def close(self):
        self._session.close()
