"""JSON 文件存储 — 保留完整结构，适合程序间交换"""

import json
import os
from typing import List

from models.earthquake import EarthquakeEvent


def save_to_json(events: List[EarthquakeEvent], filepath: str,
                 indent: int = 2, merge: bool = True) -> int:
    """
    保存地震事件到 JSON 文件。

    Args:
        events:   地震事件列表
        filepath: 输出路径
        indent:   JSON 缩进
        merge:    True=合并到已有文件(去重), False=覆盖

    Returns:
        int: 文件中事件总数
    """
    existing = []
    if merge and os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            existing = []

    existing_ids = {e["event_id"] for e in existing if e.get("event_id")}

    new_events = []
    for event in events:
        d = event.to_dict()
        if d["event_id"] not in existing_ids:
            new_events.append(d)
            existing_ids.add(d["event_id"])

    all_events = existing + new_events

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=indent)

    return len(all_events)
