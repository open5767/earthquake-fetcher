# 仿真数据自动获取模块 (Simulation Data Fetcher)

面向灾害仿真平台的**多源仿真数据自动获取与 Web 管理后台**，采用 Python 实现，支持 CLI 拉取 + Flask Web 管理两种模式。

## 已接入数据模块

| 模块 | 数据源 | 范围 | 需 API Key |
|---|---|---|---|
| 地震事件 | USGS Earthquake Catalog + 中国地震台网 (CENC) | 全球 / 中国区域 | 否 |
| 天气数据 | Open-Meteo API | 中国主要城市 + 任意坐标 | 否 |
| 断层数据 | 中国活动断层数据库 (CAFD) | 中国 | 否 |
| 道路数据 | OSM Overpass API | 全球 | 否 |
| 区域划分 | GADM 全球行政区划 | 中国省级 + 抗震设防属性 | 否 |

## 项目结构

```
earthquake-fetcher/
├── adapters/              # 数据源适配器 (Adapter 模式)
│   ├── base.py            #   抽象基类
│   ├── usgs.py            #   USGS 地震目录
│   ├── cenc.py            #   中国地震台网
│   ├── weather_openmeteo.py  # Open-Meteo 天气
│   ├── fault_cn.py        #   中国活动断层
│   ├── road_osm.py        #   OSM Overpass 道路
│   └── zone_gadm.py       #   GADM 行政区划
├── models/                # 数据模型 (dataclass)
│   ├── earthquake.py
│   ├── weather.py
│   ├── fault.py
│   ├── road.py
│   └── zone.py
├── storage/               # 文件存储 (CSV / JSON)
│   ├── csv_storage.py
│   └── json_storage.py
├── db.py                  # 地震数据 SQLite
├── db_weather.py          # 天气数据 SQLite
├── db_fault.py            # 断层数据 SQLite
├── db_road.py             # 道路数据 SQLite
├── db_zone.py             # 区域数据 SQLite
├── templates/             # Jinja2 前端模板
│   ├── base.html          #   公共布局 + 模块导航
│   ├── dashboard.html     #   地震事件看板
│   ├── list.html          #   地震事件列表
│   ├── detail.html        #   事件详情
│   ├── weather.html       #   天气看板 + 地图选点
│   ├── weather_list.html  #   天气列表
│   ├── fault.html         #   断层数据管理
│   ├── road.html          #   道路数据管理
│   └── zone.html          #   区域划分管理
├── static/
│   ├── style.css          # 全局样式
│   └── tiles/             # 离线 OSM 瓦片
├── main.py                # CLI 入口 (拉取 / 定时同步)
├── web_app.py             # Flask Web 管理后台
├── download_tiles.py      # 离线瓦片下载工具
├── config.py              # 配置文件
└── requirements.txt       # 依赖 (Flask + requests)
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# CLI 模式 — 拉取近 7 天全球 M≥4.5 地震
python main.py fetch

# CLI 模式 — 拉取中国区域 M≥3.0
python main.py fetch --region china --min-mag 3.0 --days 30

# 定时同步模式 (每小时)
python main.py schedule --region china --interval 3600

# Web 管理后台
python web_app.py
# 浏览器打开 http://127.0.0.1:5000
```

## Web 管理功能

- **多模块导航** — 地震 / 天气 / 断层 / 道路 / 区域划分，Tab 切换
- **数据拉取面板** — 按数据源、时间范围、空间范围拉取入库
- **列表 + 筛选 + 排序** — 分页浏览，支持震级 / 地名 / 时间筛选
- **地图可视化** — Leaflet 离线瓦片地图，展示事件分布 / 断层线 / 区域面
- **删除管理** — 逐条删除或清空模块数据
- **地图点击选点** — 天气模块支持点击地图，拉取任意坐标天气预报

## API 路由一览

### 地震 /api/eq/*
| 方法 | 路由 | 说明 |
|---|---|---|
| GET | `/api/eq/stats` | 统计摘要 |
| GET | `/api/eq/events` | 分页列表 (支持筛选排序) |
| GET | `/api/eq/map` | 地图 Markers 数据 |
| POST | `/api/eq/fetch` | 触发拉取 (source: usgs/cenc) |
| DELETE | `/api/eq/events/<id>` | 删除单条 |

### 天气 /api/wx/*
| 方法 | 路由 | 说明 |
|---|---|---|
| POST | `/api/wx/fetch` | 拉取中国城市天气 |
| POST | `/api/wx/fetch_point` | 拉取任意坐标天气 |
| GET | `/api/wx/records` | 分页列表 |
| GET | `/api/wx/locations` | 已拉取城市列表 |
| DELETE | `/api/wx/records/<id>` | 删除单条 |

### 断层 /api/fault/*
| 方法 | 路由 | 说明 |
|---|---|---|
| GET | `/api/fault/list` | 分页列表 |
| GET | `/api/fault/map` | 地图 GeoJSON |
| DELETE | `/api/fault/<id>` | 删除单条 |

### 道路 /api/road/*
| 方法 | 路由 | 说明 |
|---|---|---|
| POST | `/api/road/fetch` | 按 BBox 拉取 |
| GET | `/api/road/list` | 分页列表 |
| GET | `/api/road/stats` | 按等级统计 |
| DELETE | `/api/road/<id>` | 删除单条 |

### 区域 /api/zone/*
| 方法 | 路由 | 说明 |
|---|---|---|
| POST | `/api/zone/load` | 从 GADM 加载 |
| GET | `/api/zone/list` | 分页列表 |
| GET | `/api/zone/map` | 地图 GeoJSON |
| GET | `/api/zone/stats` | 统计汇总 |
| DELETE | `/api/zone/<id>` | 删除单条 |

## 扩展新数据源

所有适配器实现统一接口：

```python
class MyAdapter(DataAdapter):
    def fetch(self, **filters):
        ...  # 从数据源拉取，yield 数据对象
```

数据到入库的流水线：`adapter.fetch()` → `model.to_dict()` → `db.upsert_*()`

## 设计决策

- **全部免费数据源** — 不依赖付费 API，所有模块开箱即用
- **Adapter 模式** — 统一数据流水线，新增数据源只需实现一个 adapter
- **SQLite 持久化** — 零配置数据库，适合单机 / 原型阶段
- **离线地图** — 预下载瓦片到 `static/tiles/`，脱离互联网也能展示
