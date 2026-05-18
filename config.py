"""项目配置 — 后续可迁移到 YAML 或 Nacos"""

# USGS 数据源设置
USGS_TIMEOUT = 30          # API 请求超时(秒)
DEFAULT_MIN_MAGNITUDE = 4.5  # 默认最小震级

# 中国周边空间范围 (用于区域过滤)
CHINA_BOUNDS = {
    "min_latitude": 18.0,
    "max_latitude": 54.0,
    "min_longitude": 73.0,
    "max_longitude": 135.0,
}

# 存储输出目录
DEFAULT_OUTPUT_DIR = "output"
