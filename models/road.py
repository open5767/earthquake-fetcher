"""道路数据模型 — 路网几何与属性数据

数据来源: OSM Overpass API / 国家基础地理信息中心 / 天地图
"""

from dataclasses import dataclass, field, asdict
from typing import Optional

HIGHWAY_LEVEL_MAP = {
    "motorway": "高速公路",
    "trunk": "国道/快速路",
    "primary": "主干道",
    "secondary": "次干道",
    "tertiary": "支路",
    "residential": "居住区道路",
    "service": "服务性道路",
    "pedestrian": "步行街",
    "unclassified": "未分类道路",
}


@dataclass
class RoadRecord:
    road_id: str                          # 道路唯一标识
    name: str = ""                        # 道路名称 (中文)
    highway_level: str = ""               # OSM 公路等级 (motorway/trunk/primary/...)
    highway_level_cn: str = ""            # 公路等级中文描述
    surface: str = ""                     # 路面类型 (asphalt/concrete/unpaved...)
    lanes: Optional[int] = None           # 车道数
    oneway: str = ""                      # 单行道 (yes/no/-1)
    max_speed: Optional[int] = None       # 限速 (km/h)
    length_m: Optional[float] = None      # 长度 (米)

    # 坐标 (取路段中点作为参考点)
    longitude: float = 0.0
    latitude: float = 0.0

    # 几何 (完整线段坐标)
    coordinates_json: str = ""            # GeoJSON LineString coordinates

    source: str = "osm"                   # 数据来源
    bbox: str = ""                        # 查询范围

    raw_tags: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw_tags", None)
        return d

    @classmethod
    def field_names(cls) -> list:
        return [
            "road_id", "name", "highway_level", "highway_level_cn",
            "surface", "lanes", "oneway", "max_speed", "length_m",
            "longitude", "latitude", "coordinates_json",
            "source", "bbox",
        ]
