"""CSV 文件存储 — 兼容 Excel 查看，方便非技术人员使用"""

import csv
import os
from typing import List

from models.earthquake import EarthquakeEvent


def save_to_csv(events: List[EarthquakeEvent], filepath: str) -> int:
    """保存地震事件到 CSV，返回写入条数"""
    file_exists = os.path.exists(filepath)
    fieldnames = EarthquakeEvent.field_names()

    with open(filepath, "a" if file_exists else "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for event in events:
            writer.writerow(event.to_dict())

    return len(events)
