# 仿真数据自动获取 - 地震事件模块

基于 USGS Earthquake Catalog API 的地震数据自动获取原型，支持 CLI 拉取、Web 管理后台、离线地图。

USGS API 免费、无需注册、全球覆盖。

## 快速开始

```bash
pip install -r requirements.txt

# CLI 拉取
python main.py fetch --days 7 --min-mag 4.5 --region china

# 启动 Web 管理后台
python web_app.py
# 浏览器打开 http://127.0.0.1:5000
```

## Web 管理后台

| 页面 | 功能 |
|------|------|
| `/` 数据看板 | 统计卡片、震中地图、震级分布、最近事件 |
| `/events` 事件列表 | 分页、多维过滤（震级/时间/地点）、排序、删除 |
| `/events/<id>` 详情 | 完整字段、震中地图标注 |

右上角按钮可手动触发 USGS 数据拉取入库。

## CLI 用法

```bash
python main.py fetch --days 7 --min-mag 4.5 --region china
python main.py fetch --start 2025-01-01 --end 2025-01-31 --min-lat 30 --max-lat 40
python main.py schedule --interval 3600 --region china   # 每小时定时同步
```

## 离线地图（内网部署）

```bash
python download_tiles.py                       # 全球 z3~z6, ~80MB
python download_tiles.py --region china --max-zoom 8  # 中国区域更精细
python download_tiles.py --dry-run             # 预估瓦片数不下载
```

前端自动检测本地瓦片，存在则离线渲染，不存在则回退在线 OSM。内网服务器部署时配合代理使用：

```bash
set HTTP_PROXY=http://proxy:8080
python web_app.py   # USGS 拉取功能通过代理访问
```

## 项目结构

```
earthquake-fetcher/
├── main.py              # CLI 入口 (fetch / schedule)
├── web_app.py           # Flask Web 管理后台
├── db.py                # SQLite 持久化层
├── download_tiles.py    # 离线地图瓦片下载工具
├── config.py            # 配置
├── adapters/
│   ├── base.py          # 数据源适配器抽象基类
│   └── usgs.py          # USGS 适配器实现
├── models/
│   └── earthquake.py    # 地震事件数据模型（17 字段）
├── storage/
│   ├── csv_storage.py   # CSV 输出
│   └── json_storage.py  # JSON 输出
├── templates/           # Jinja2 页面模板
├── static/              # CSS / 本地瓦片缓存
└── output/              # CLI 拉取输出目录
```

## 数据模型

地震三要素：时间、震中位置（经纬度 + 深度）、震级。

标准 17 字段含震级类型、有感报告、社区烈度、仪器烈度、海啸预警、显著性等。

## 扩展

新增数据源只需实现 `adapters/base.py` 中的 `EarthquakeAdapter` 接口：

```python
class MyAdapter(EarthquakeAdapter):
    def fetch(self, start_time, end_time, **filters):
        ...  # 从数据源拉取，yield EarthquakeEvent
```

天气数据、OSM 路网等模块同理可复用此模式。
