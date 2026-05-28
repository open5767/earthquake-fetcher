"""Open-Meteo 天气数据适配器

API 文档: https://open-meteo.com/en/docs
完全免费，无需 API Key，全球覆盖。

支持:
  - 实时预报 (forecast): 未来 16 天逐小时/逐日
  - 历史数据 (archive): 1940 年至今的再分析数据
  - 支持中文天气描述
"""

import logging
from datetime import datetime, timezone
from typing import Iterator, Optional

import requests

from models.weather import WeatherRecord

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HISTORY_URL = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_TIMEOUT = 20

WMO_CODE_MAP = {
    0: "晴天", 1: "少云", 2: "多云", 3: "阴天",
    45: "有雾", 48: "冰雾",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    56: "冻毛毛雨", 57: "冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    77: "雪粒",
    80: "阵雨", 81: "中阵雨", 82: "大阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷暴", 96: "冰雹雷暴", 99: "强冰雹雷暴",
}

CHINA_CITIES = [
    {"name": "北京", "lat": 39.9042, "lon": 116.4074},
    {"name": "上海", "lat": 31.2304, "lon": 121.4737},
    {"name": "广州", "lat": 23.1291, "lon": 113.2644},
    {"name": "成都", "lat": 30.5728, "lon": 104.0668},
    {"name": "昆明", "lat": 25.0389, "lon": 102.7183},
    {"name": "拉萨", "lat": 29.6500, "lon": 91.1000},
    {"name": "乌鲁木齐", "lat": 43.8256, "lon": 87.6168},
    {"name": "西安", "lat": 34.3416, "lon": 108.9398},
    {"name": "武汉", "lat": 30.5928, "lon": 114.3055},
    {"name": "沈阳", "lat": 41.8057, "lon": 123.4315},
    {"name": "哈尔滨", "lat": 45.8038, "lon": 126.5350},
    {"name": "天津", "lat": 39.3434, "lon": 117.3616},
    {"name": "重庆", "lat": 29.4316, "lon": 106.9123},
    {"name": "兰州", "lat": 36.0611, "lon": 103.8343},
    {"name": "西宁", "lat": 36.6171, "lon": 101.7785},
    {"name": "银川", "lat": 38.4872, "lon": 106.2309},
    {"name": "呼和浩特", "lat": 40.8424, "lon": 111.7490},
    {"name": "南宁", "lat": 22.8170, "lon": 108.3665},
    {"name": "海口", "lat": 20.0440, "lon": 110.1999},
    {"name": "福州", "lat": 26.0745, "lon": 119.2965},
    {"name": "合肥", "lat": 31.8206, "lon": 117.2272},
    {"name": "南昌", "lat": 28.6820, "lon": 115.8582},
    {"name": "长沙", "lat": 28.2282, "lon": 112.9388},
    {"name": "贵阳", "lat": 26.6470, "lon": 106.6302},
    {"name": "石家庄", "lat": 38.0428, "lon": 114.5149},
    {"name": "郑州", "lat": 34.7466, "lon": 113.6253},
    {"name": "济南", "lat": 36.6512, "lon": 116.9972},
    {"name": "太原", "lat": 37.8706, "lon": 112.5489},
    {"name": "长春", "lat": 43.8171, "lon": 125.3235},
]


class OpenMeteoAdapter:
    """Open-Meteo 天气数据适配器"""

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SimDataFetcher/1.0"})
        self._timeout = timeout

    def fetch_forecast(self, lat: float, lon: float,
                       location_name: str = "",
                       days: int = 7,
                       hourly: bool = False) -> list[WeatherRecord]:
        """获取未来天气预报"""
        params = {
            "latitude": lat, "longitude": lon,
            "timezone": "Asia/Shanghai",
            "daily": [
                "temperature_2m_max", "temperature_2m_min",
                "precipitation_sum", "precipitation_probability_max",
                "wind_speed_10m_max", "wind_direction_10m_dominant",
                "pressure_msl_mean", "weather_code",
            ],
            "forecast_days": min(days, 16),
        }
        if hourly:
            params["hourly"] = [
                "temperature_2m", "relative_humidity_2m",
                "precipitation", "wind_speed_10m", "wind_direction_10m",
                "pressure_msl", "cloud_cover", "weather_code",
            ]

        logger.info("Open-Meteo 预报: %s (%.2f, %.2f)", location_name or f"{lat},{lon}", lat, lon)

        try:
            resp = self._session.get(FORECAST_URL, params=params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("Open-Meteo 请求失败: %s", e)
            return []

        return self._parse_daily(data, location_name, lat, lon, "forecast")

    def fetch_history(self, lat: float, lon: float,
                      start_date: str, end_date: str,
                      location_name: str = "") -> list[WeatherRecord]:
        """获取历史天气数据 (1940年至今的再分析数据)"""
        params = {
            "latitude": lat, "longitude": lon,
            "start_date": start_date, "end_date": end_date,
            "timezone": "Asia/Shanghai",
            "daily": [
                "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
                "precipitation_sum",
                "wind_speed_10m_max", "wind_direction_10m_dominant",
                "pressure_msl_mean", "weather_code",
            ],
        }

        logger.info("Open-Meteo 历史: %s (%s ~ %s)",
                    location_name or f"{lat},{lon}", start_date, end_date)

        try:
            resp = self._session.get(HISTORY_URL, params=params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("Open-Meteo 历史请求失败: %s", e)
            return []

        return self._parse_daily(data, location_name, lat, lon, "history")

    def _parse_daily(self, data: dict, name: str, lat: float, lon: float,
                     source_type: str) -> list[WeatherRecord]:
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        if not dates:
            return []

        records = []
        for i, date_str in enumerate(dates):
            wmo_code = self._get(daily, "weather_code", i)
            temp_max = self._get(daily, "temperature_2m_max", i)
            temp_min = self._get(daily, "temperature_2m_min", i)
            temp_mean = self._get(daily, "temperature_2m_mean", i)
            precip = self._get(daily, "precipitation_sum", i)
            precip_prob = self._get(daily, "precipitation_probability_max", i)
            wind_speed = self._get(daily, "wind_speed_10m_max", i)
            wind_dir = self._get(daily, "wind_direction_10m_dominant", i)
            pressure = self._get(daily, "pressure_msl_mean", i)

            record_id = f"om-{source_type}-{lat:.2f}-{lon:.2f}-{date_str}"
            # 去重: 同一地点+时间只需一条
            record_id = f"om-{source_type}-{date_str}-{lat:.2f}-{lon:.2f}"

            records.append(WeatherRecord(
                record_id=record_id,
                longitude=lon, latitude=lat,
                location_name=name,
                observation_time=date_str,
                source=f"openmeteo-{source_type}",
                temperature=temp_mean,
                temp_min=temp_min,
                temp_max=temp_max,
                precipitation=precip,
                precipitation_prob=round(precip_prob) if precip_prob is not None else None,
                wind_speed=wind_speed,
                wind_direction=wind_dir,
                pressure=pressure,
                weather_code=wmo_code,
                weather_desc=WMO_CODE_MAP.get(wmo_code or 0, ""),
                raw_data={"daily_slice": f"day_{i}"},
            ))
        return records

    @staticmethod
    def _get(obj: dict, key: str, idx: int) -> Optional[float]:
        arr = obj.get(key, [])
        if arr and idx < len(arr):
            v = arr[idx]
            return float(v) if v is not None else None
        return None

    @staticmethod
    def get_china_cities() -> list[dict]:
        return CHINA_CITIES

    def close(self):
        self._session.close()
