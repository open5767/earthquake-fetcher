"""数据源适配器抽象基类 — 策略模式，每种数据源一个实现"""

from abc import ABC, abstractmethod
from typing import Iterator
from models.earthquake import EarthquakeEvent


class EarthquakeAdapter(ABC):
    """地震数据源适配器基类"""

    @abstractmethod
    def fetch(self, start_time: str, end_time: str,
              min_magnitude: float = 0.0,
              min_latitude: float = -90, max_latitude: float = 90,
              min_longitude: float = -180, max_longitude: float = 180) -> Iterator[EarthquakeEvent]:
        """
        从数据源拉取地震数据。

        Args:
            start_time:   起始时间 (UTC, ISO 8601 格式)
            end_time:     结束时间 (UTC, ISO 8601 格式)
            min_magnitude: 最小震级过滤
            min_latitude ~ max_longitude: 空间范围过滤 (WGS84)

        Yields:
            EarthquakeEvent: 标准化的地震事件
        """
        ...
