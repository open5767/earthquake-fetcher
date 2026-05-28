"""天气数据模型 — 区域气象观测与预报数据

数据来源: Open-Meteo (全球免费) / 中国气象局 (data.cma.cn)
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class WeatherRecord:
    """单条天气观测/预报记录"""

    record_id: str                        # 记录唯一标识
    longitude: float                      # 经度 (WGS84)
    latitude: float                       # 纬度 (WGS84)
    location_name: str = ""               # 地点名称 (中文)
    observation_time: str = ""            # 观测/预报时间 (ISO 8601)
    source: str = "openmeteo"             # 数据来源

    # 温度 (℃)
    temperature: Optional[float] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    feels_like: Optional[float] = None    # 体感温度

    # 降水
    precipitation: Optional[float] = None  # 降水量 (mm)
    precipitation_prob: Optional[int] = None  # 降水概率 (%)

    # 风
    wind_speed: Optional[float] = None     # 风速 (km/h)
    wind_direction: Optional[float] = None  # 风向 (度, 0=北)
    wind_gust: Optional[float] = None      # 阵风风速 (km/h)

    # 气压与湿度
    pressure: Optional[float] = None       # 海平面气压 (hPa)
    humidity: Optional[int] = None         # 相对湿度 (%)

    # 天空状况
    cloud_cover: Optional[int] = None      # 云量 (%)
    weather_code: Optional[int] = None     # WMO 天气码
    weather_desc: str = ""                 # 天气描述 (中文)

    # 其他
    visibility: Optional[float] = None     # 能见度 (km)
    uv_index: Optional[float] = None       # 紫外线指数

    raw_data: dict = field(default_factory=dict, repr=False)

    @property
    def wind_direction_cn(self) -> str:
        """风向度数 → 中文方位"""
        if self.wind_direction is None:
            return ""
        dirs = ["北", "东北偏北", "东北", "东北偏东", "东", "东南偏东",
                "东南", "东南偏南", "南", "西南偏南", "西南", "西南偏西",
                "西", "西北偏西", "西北", "西北偏北"]
        idx = round(self.wind_direction / 22.5) % 16
        return dirs[idx]

    @property
    def weather_icon(self) -> str:
        """WMO 天气码 → 中文简写"""
        code_map = {
            0: "晴", 1: "少云", 2: "多云", 3: "阴",
            45: "雾", 48: "冰雾",
            51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
            61: "小雨", 63: "中雨", 65: "大雨",
            71: "小雪", 73: "中雪", 75: "大雪",
            80: "阵雨", 81: "中阵雨", 82: "大阵雨",
            95: "雷暴", 96: "冰雹雷暴", 99: "强冰雹雷暴",
        }
        return code_map.get(self.weather_code or 0, "未知")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["wind_direction_cn"] = self.wind_direction_cn
        d["weather_icon"] = self.weather_icon
        d.pop("raw_data", None)
        return d

    @classmethod
    def field_names(cls) -> list:
        return [
            "record_id", "longitude", "latitude", "location_name",
            "observation_time", "source",
            "temperature", "temp_min", "temp_max", "feels_like",
            "precipitation", "precipitation_prob",
            "wind_speed", "wind_direction", "wind_gust",
            "pressure", "humidity",
            "cloud_cover", "weather_code", "weather_desc",
            "visibility", "uv_index",
            "wind_direction_cn", "weather_icon",
        ]
