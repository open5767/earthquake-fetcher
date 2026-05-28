"""区域划分数据模型 — 行政区划 + 抗震设防等级

数据来源:
  - GADM (gadm.org): 全球行政区划边界 GeoJSON
  - 国家地震科学数据中心 (data.earthquake.cn): 抗震设防烈度区划图
  - GB 18306-2015: 中国地震动参数区划图
"""

from dataclasses import dataclass, field, asdict
from typing import Optional

# GB 18306-2015 地震动峰值加速度 → 抗震设防烈度对照
PGA_TO_INTENSITY = {
    0.05: "Ⅵ度(0.05g)",
    0.10: "Ⅶ度(0.10g)",
    0.15: "Ⅶ度(0.15g)",
    0.20: "Ⅷ度(0.20g)",
    0.30: "Ⅷ度(0.30g)",
    0.40: "Ⅸ度(0.40g)",
}

# 中国各省/主要地区抗震设防基本地震动峰值加速度参考值
# 来源: GB 18306-2015 附录A 中国地震动峰值加速度区划图
PROVINCE_SEISMIC = {
    "Beijing":      {"pga": 0.20, "intensity": "Ⅷ度(0.20g)", "desc": "京津冀地震带"},
    "Tianjin":      {"pga": 0.20, "intensity": "Ⅷ度(0.20g)", "desc": "华北平原地震带"},
    "Hebei":        {"pga": 0.20, "intensity": "Ⅷ度(0.20g)", "desc": "华北平原地震带"},
    "Shanxi":       {"pga": 0.20, "intensity": "Ⅷ度(0.20g)", "desc": "山西地震带"},
    "NeiMongol":    {"pga": 0.15, "intensity": "Ⅶ度(0.15g)", "desc": "阴山-燕山地震带"},
    "Liaoning":     {"pga": 0.15, "intensity": "Ⅶ度(0.15g)", "desc": "郯庐地震带北段"},
    "Jilin":        {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "东北地震区"},
    "Heilongjiang": {"pga": 0.05, "intensity": "Ⅵ度(0.05g)", "desc": "东北地震区"},
    "Shanghai":     {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "长江三角洲"},
    "Jiangsu":      {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "长江中下游地震带"},
    "Zhejiang":     {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "东南沿海地震带"},
    "Anhui":        {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "郯庐地震带南段"},
    "Fujian":       {"pga": 0.15, "intensity": "Ⅶ度(0.15g)", "desc": "东南沿海地震带"},
    "Jiangxi":      {"pga": 0.05, "intensity": "Ⅵ度(0.05g)", "desc": "华南地震区"},
    "Shandong":     {"pga": 0.15, "intensity": "Ⅶ度(0.15g)", "desc": "郯庐地震带+渤海"},
    "Henan":        {"pga": 0.15, "intensity": "Ⅶ度(0.15g)", "desc": "华北平原地震带南段"},
    "Hubei":        {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "长江中下游地震带"},
    "Hunan":        {"pga": 0.05, "intensity": "Ⅵ度(0.05g)", "desc": "华南地震区"},
    "Guangdong":    {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "东南沿海地震带"},
    "Guangxi":      {"pga": 0.05, "intensity": "Ⅵ度(0.05g)", "desc": "华南地震区"},
    "Hainan":       {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "南海地震区"},
    "Chongqing":    {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "长江中上游"},
    "Sichuan":      {"pga": 0.30, "intensity": "Ⅷ度(0.30g)", "desc": "南北地震带中段"},
    "Guizhou":      {"pga": 0.05, "intensity": "Ⅵ度(0.05g)", "desc": "华南地震区"},
    "Yunnan":       {"pga": 0.30, "intensity": "Ⅷ度(0.30g)", "desc": "南北地震带南段"},
    "Xizang":       {"pga": 0.30, "intensity": "Ⅷ度(0.30g)", "desc": "喜马拉雅地震带"},
    "Shaanxi":      {"pga": 0.20, "intensity": "Ⅷ度(0.20g)", "desc": "关中-汾渭地震带"},
    "Gansu":        {"pga": 0.30, "intensity": "Ⅷ度(0.30g)", "desc": "南北地震带北段"},
    "Qinghai":      {"pga": 0.20, "intensity": "Ⅷ度(0.20g)", "desc": "青藏高原地震带"},
    "NingxiaHui":   {"pga": 0.30, "intensity": "Ⅷ度(0.30g)", "desc": "南北地震带北段"},
    "XinjiangUygur":{"pga": 0.30, "intensity": "Ⅷ度(0.30g)", "desc": "天山地震带"},
    "Taiwan":       {"pga": 0.40, "intensity": "Ⅸ度(0.40g)", "desc": "台湾地震带"},
    "HongKong":     {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "东南沿海地震带"},
    "Macau":        {"pga": 0.10, "intensity": "Ⅶ度(0.10g)", "desc": "东南沿海地震带"},
}


@dataclass
class ZoneRecord:
    zone_id: str                          # 区域唯一标识 (GID)
    name: str = ""                        # 区域名称 (中文)
    name_en: str = ""                     # 英文名
    level: str = ""                       # 行政级别: province / city / county
    parent_id: str = ""                   # 上级区域 GID

    # 几何
    longitude: float = 0.0                # 中心经度
    latitude: float = 0.0                 # 中心纬度
    coordinates_json: str = ""            # GeoJSON geometry coordinates (简化)

    # 抗震设防
    seismic_pga: Optional[float] = None   # 基本地震动峰值加速度 (g)
    seismic_intensity: str = ""           # 抗震设防烈度
    seismic_desc: str = ""                # 地震带描述

    # 元数据
    source: str = "gadm"                  # 数据来源
    area_km2: Optional[float] = None      # 面积 (km², 近似)

    raw_data: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw_data", None)
        return d

    @classmethod
    def field_names(cls) -> list:
        return [
            "zone_id", "name", "name_en", "level", "parent_id",
            "longitude", "latitude", "coordinates_json",
            "seismic_pga", "seismic_intensity", "seismic_desc",
            "source", "area_km2",
        ]
