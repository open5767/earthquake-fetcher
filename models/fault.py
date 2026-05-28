"""断层数据模型 — 活动断层几何与运动学参数

数据来源: 中国活动断层数据库 (CAFD) / CN-faults / GEM Global Active Faults
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class FaultRecord:
    """单条活动断层记录"""

    fault_id: str                         # 断层唯一标识
    name: str = ""                        # 断层名称 (中文)
    name_en: str = ""                     # 断层英文名
    location_desc: str = ""               # 地理位置描述

    # 几何参数
    longitude: float = 0.0
    latitude: float = 0.0                 # 参考点坐标 (通常取中点)
    strike: Optional[float] = None        # 走向 (度, 0-360)
    dip: Optional[float] = None           # 倾向 (度, 0-90)
    dip_direction: Optional[float] = None # 倾角方向 (度)
    length_km: Optional[float] = None     # 断层长度 (km)
    width_km: Optional[float] = None      # 断层宽度 (km)

    # 运动参数
    slip_rate: Optional[float] = None     # 滑动速率 (mm/yr)
    slip_type: str = ""                   # 滑动类型: 正断/逆断/走滑/正走滑/逆走滑
    rake: Optional[float] = None          # 滑动角 (度)

    # 活动性
    activity_age: str = ""                # 活动时代 (如 Q4/晚更新世/全新世)
    activity_level: str = ""              # 活动性等级
    last_event: str = ""                  # 最近一次地表破裂事件年代
    recurrence_interval: Optional[int] = None  # 复发间隔 (年)

    # 震源参数
    max_magnitude: Optional[float] = None # 最大潜在地震震级
    segmentation: str = ""                # 分段信息

    # 位置坐标串
    coordinates_wkt: str = ""             # 断层迹线 WKT 格式 (LINESTRING)
    coordinates_json: str = ""            # 断层迹线 GeoJSON 格式

    source: str = "cafd"                  # 数据来源
    source_url: str = ""                  # 来源链接
    reference: str = ""                   # 参考文献

    raw_data: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw_data", None)
        return d

    @classmethod
    def field_names(cls) -> list:
        return [
            "fault_id", "name", "name_en", "location_desc",
            "longitude", "latitude",
            "strike", "dip", "dip_direction",
            "length_km", "width_km",
            "slip_rate", "slip_type", "rake",
            "activity_age", "activity_level",
            "last_event", "recurrence_interval",
            "max_magnitude", "segmentation",
            "coordinates_wkt", "coordinates_json",
            "source", "source_url", "reference",
        ]


# 中国主要活动断层带预设数据 (基于 CN-faults + CAFD 公开资料)
KNOWN_FAULTS_CHINA = [
    {"name": "郯庐断裂带", "name_en": "Tanlu Fault Zone", "slip_type": "走滑",
     "length_km": 2400, "activity_age": "全新世", "max_magnitude": 8.5,
     "strike": 20, "lat": 35.0, "lon": 118.5, "slip_rate": 2.3},
    {"name": "龙门山断裂带", "name_en": "Longmenshan Fault Zone", "slip_type": "逆断兼走滑",
     "length_km": 500, "activity_age": "全新世", "max_magnitude": 8.0,
     "strike": 45, "lat": 31.0, "lon": 103.5, "slip_rate": 1.5},
    {"name": "鲜水河断裂带", "name_en": "Xianshuihe Fault Zone", "slip_type": "走滑",
     "length_km": 350, "activity_age": "全新世", "max_magnitude": 8.0,
     "strike": 135, "lat": 30.5, "lon": 101.5, "slip_rate": 12.0},
    {"name": "红河断裂带", "name_en": "Red River Fault Zone", "slip_type": "走滑",
     "length_km": 1000, "activity_age": "全新世", "max_magnitude": 7.5,
     "strike": 140, "lat": 23.5, "lon": 103.0, "slip_rate": 3.0},
    {"name": "阿尔金断裂带", "name_en": "Altyn Tagh Fault", "slip_type": "走滑",
     "length_km": 1600, "activity_age": "全新世", "max_magnitude": 8.0,
     "strike": 75, "lat": 38.0, "lon": 90.0, "slip_rate": 9.0},
    {"name": "海原断裂带", "name_en": "Haiyuan Fault", "slip_type": "走滑",
     "length_km": 240, "activity_age": "全新世", "max_magnitude": 8.5,
     "strike": 110, "lat": 36.5, "lon": 105.5, "slip_rate": 5.0},
    {"name": "东昆仑断裂带", "name_en": "East Kunlun Fault", "slip_type": "走滑",
     "length_km": 1500, "activity_age": "全新世", "max_magnitude": 8.0,
     "strike": 100, "lat": 35.5, "lon": 96.0, "slip_rate": 10.0},
    {"name": "安宁河断裂带", "name_en": "Anninghe Fault", "slip_type": "走滑",
     "length_km": 200, "activity_age": "全新世", "max_magnitude": 7.5,
     "strike": 0, "lat": 28.5, "lon": 102.2, "slip_rate": 3.0},
    {"name": "小江断裂带", "name_en": "Xiaojiang Fault", "slip_type": "走滑",
     "length_km": 400, "activity_age": "全新世", "max_magnitude": 8.0,
     "strike": 0, "lat": 26.5, "lon": 103.0, "slip_rate": 8.0},
    {"name": "台湾纵谷断裂带", "name_en": "Longitudinal Valley Fault", "slip_type": "逆断",
     "length_km": 150, "activity_age": "全新世", "max_magnitude": 7.5,
     "strike": 20, "lat": 23.5, "lon": 121.5, "slip_rate": 40.0},
]
