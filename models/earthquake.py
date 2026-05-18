"""地震事件数据模型 — 地震三要素: 时间、地点(震中位置)、震级"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class EarthquakeEvent:
    """标准化的地震事件数据结构，与数据源无关"""

    event_id: str                         # 事件唯一标识 (如 usgs:us7000xxxx)
    time: datetime                        # 发震时刻 (UTC)
    longitude: float                      # 经度 (WGS84)
    latitude: float                       # 纬度 (WGS84)
    depth_km: float                       # 震源深度 (km)
    magnitude: float                      # 震级
    mag_type: str = ""                    # 震级类型 (mb, mww, ml, ms...)
    place: str = ""                       # 地点描述 (如 "25km SW of Tokyo, Japan")
    source: str = "usgs"                  # 数据来源标识
    url: str = ""                         # 详情页 URL
    felt: Optional[int] = None            # 有感报告人数
    cdi: Optional[float] = None           # 社区烈度 (Community Determined Intensity)
    mmi: Optional[float] = None           # 仪器烈度 (Modified Mercalli Intensity)
    alert: Optional[str] = None           # 警报级别 (green/yellow/orange/red)
    tsunami: int = 0                      # 海啸预警 (0/1)
    significance: int = 0                 # 事件显著性
    raw_data: dict = field(default_factory=dict, repr=False)  # 原始数据

    @property
    def magnitude_category(self) -> str:
        """震级分类"""
        if self.magnitude >= 8.0:
            return "巨大地震"
        elif self.magnitude >= 7.0:
            return "大地震"
        elif self.magnitude >= 6.0:
            return "强震"
        elif self.magnitude >= 5.0:
            return "中强震"
        elif self.magnitude >= 4.0:
            return "有感地震"
        elif self.magnitude >= 3.0:
            return "弱震"
        else:
            return "微震"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["time"] = self.time.isoformat()
        d["magnitude_category"] = self.magnitude_category
        d.pop("raw_data", None)
        return d

    @classmethod
    def field_names(cls) -> list:
        return [
            "event_id", "time", "longitude", "latitude", "depth_km",
            "magnitude", "mag_type", "place", "source", "url",
            "felt", "cdi", "mmi", "alert", "tsunami", "significance",
            "magnitude_category",
        ]
