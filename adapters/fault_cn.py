"""中国断层数据适配器

数据来源:
  1. CN-faults 数据集 (GMT-China 项目提供的公开中国断层数据)
  2. 中国活动断层数据库 (CAFD) — 参考数据
  3. 预置中国 10 条主要活动断裂带参数

说明: 断层数据主要是静态参考数据，不涉及实时 API 拉取。
     完整数据可通过 CAFD WFS 服务获取或从国家地震科学数据中心下载。
"""

import logging
from typing import Iterator

from models.fault import FaultRecord, KNOWN_FAULTS_CHINA

logger = logging.getLogger(__name__)


class CNActiveFaultAdapter:
    """中国活动断层数据适配器 — 使用预置的主要断裂带数据"""

    def __init__(self):
        self._faults = list(KNOWN_FAULTS_CHINA)

    def fetch_all(self) -> list[FaultRecord]:
        """获取所有预置的中国活动断层数据"""
        records = []
        for i, f in enumerate(self._faults):
            fault_id = f"cn-fault-{i+1:03d}"
            records.append(FaultRecord(
                fault_id=fault_id,
                name=f["name"],
                name_en=f.get("name_en", ""),
                longitude=f["lon"],
                latitude=f["lat"],
                strike=f.get("strike"),
                dip=f.get("dip"),
                length_km=f.get("length_km"),
                slip_rate=f.get("slip_rate"),
                slip_type=f.get("slip_type", ""),
                activity_age=f.get("activity_age", ""),
                max_magnitude=f.get("max_magnitude"),
                source="cn-faults",
                source_url="https://docs.gmt-china.org/latest/dataset/CN-faults/",
                reference="中国活动断层数据库 (CAFD); CN-faults GMT-China",
            ))
        logger.info("断层数据: 加载 %d 条中国主要活动断裂带", len(records))
        return records
