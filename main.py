#!/usr/bin/env python3
"""
仿真数据自动获取 - 地震事件数据模块 (原型)

用法:
    # 拉取近 7 天全球 M≥4.5 地震
    python main.py fetch

    # 拉取指定时间段、中国周边 M≥3.0 地震
    python main.py fetch --start 2025-01-01 --end 2025-01-31 --min-mag 3.0 --region china

    # 拉取特定区域
    python main.py fetch --min-lat 30 --max-lat 40 --min-lon 100 --max-lon 110

    # 定时同步模式 (每小时拉取一次最近数据)
    python main.py schedule --interval 3600
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from adapters.usgs import UsgsAdapter
from config import (
    USGS_TIMEOUT, DEFAULT_MIN_MAGNITUDE, CHINA_BOUNDS,
    DEFAULT_OUTPUT_DIR,
)
from models.earthquake import EarthquakeEvent
from storage.csv_storage import save_to_csv
from storage.json_storage import save_to_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("eq-fetcher")


def do_fetch(args) -> tuple:
    """执行数据拉取，返回 (events, output_dir)"""
    adapter = UsgsAdapter(timeout=USGS_TIMEOUT)

    # 时间范围
    if args.end:
        end_time = args.end
    else:
        end_time = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if args.start:
        start_time = args.start
    else:
        # 默认拉取近 7 天
        start_dt = datetime.now(timezone.utc) - timedelta(days=args.days)
        start_time = start_dt.strftime("%Y-%m-%d")

    # 空间范围
    if args.region == "china":
        min_lat, max_lat = CHINA_BOUNDS["min_latitude"], CHINA_BOUNDS["max_latitude"]
        min_lon, max_lon = CHINA_BOUNDS["min_longitude"], CHINA_BOUNDS["max_longitude"]
    else:
        min_lat, max_lat = args.min_lat, args.max_lat
        min_lon, max_lon = args.min_lon, args.max_lon

    min_mag = args.min_mag

    logger.info("=" * 50)
    logger.info("地震数据拉取任务开始")
    logger.info("  时间: %s ~ %s", start_time, end_time)
    logger.info("  范围: lon[%.1f~%.1f] lat[%.1f~%.1f]", min_lon, max_lon, min_lat, max_lat)
    logger.info("  最小震级: M%.1f", min_mag)
    logger.info("=" * 50)

    events = list(adapter.fetch(
        start_time=start_time,
        end_time=end_time,
        min_magnitude=min_mag,
        min_latitude=min_lat,
        max_latitude=max_lat,
        min_longitude=min_lon,
        max_longitude=max_lon,
    ))
    adapter.close()

    if not events:
        logger.warning("未拉取到任何地震事件")
        return [], None

    # 输出
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"earthquake_{timestamp}.csv"
    json_path = output_dir / f"earthquake_{timestamp}.json"

    n_csv = save_to_csv(events, str(csv_path))
    n_json = save_to_json(events, str(json_path), merge=False)

    # 统计摘要
    mags = [e.magnitude for e in events]
    logger.info("-" * 50)
    logger.info("拉取完成: 共 %d 条地震事件", len(events))
    logger.info("  震级范围: M%.1f ~ M%.1f", min(mags), max(mags))
    logger.info("  最大地震: M%.1f %s", max(mags),
                max(events, key=lambda e: e.magnitude).place)
    logger.info("  CSV 输出: %s (%d 条)", csv_path, n_csv)
    logger.info("  JSON 输出: %s (%d 条)", json_path, n_json)

    # 打印前 5 条
    print("\n" + "=" * 80)
    print(f"{'时间':<22} {'震级':<8} {'深度(km)':<10} {'地点'}")
    print("-" * 80)
    for e in events[:10]:
        print(f"{e.time.strftime('%Y-%m-%d %H:%M:%S'):<22} "
              f"M{e.magnitude:<7.1f} {e.depth_km:<10.1f} {e.place}")
    if len(events) > 10:
        print(f"... 还有 {len(events) - 10} 条，详见输出文件")
    print("=" * 80)

    return events, output_dir


def do_schedule(args):
    """定时同步模式"""
    interval = args.interval
    logger.info("进入定时同步模式，间隔 %d 秒", interval)

    while True:
        try:
            do_fetch(args)
        except Exception as e:
            logger.exception("拉取异常: %s", e)

        logger.info("等待 %d 秒后下次同步...", interval)
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description="仿真数据自动获取 - 地震事件模块",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # ---- fetch ----
    fetch_parser = sub.add_parser("fetch", help="拉取地震数据")
    fetch_parser.add_argument("--start", help="起始日期 (YYYY-MM-DD)")
    fetch_parser.add_argument("--end", help="结束日期 (YYYY-MM-DD)，默认今天")
    fetch_parser.add_argument("--days", type=int, default=7, help="拉取最近 N 天 (默认 7)")
    fetch_parser.add_argument("--min-mag", type=float, default=DEFAULT_MIN_MAGNITUDE,
                              help=f"最小震级 (默认 {DEFAULT_MIN_MAGNITUDE})")
    fetch_parser.add_argument("--region", choices=["global", "china"],
                              default="global", help="预设区域 (默认 global)")
    fetch_parser.add_argument("--min-lat", type=float, default=-90)
    fetch_parser.add_argument("--max-lat", type=float, default=90)
    fetch_parser.add_argument("--min-lon", type=float, default=-180)
    fetch_parser.add_argument("--max-lon", type=float, default=180)
    fetch_parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="输出目录")
    fetch_parser.set_defaults(func=do_fetch)

    # ---- schedule ----
    sched_parser = sub.add_parser("schedule", help="定时同步模式")
    sched_parser.add_argument("--interval", type=int, default=3600,
                              help="同步间隔(秒)，默认 3600")
    sched_parser.add_argument("--start")
    sched_parser.add_argument("--end")
    sched_parser.add_argument("--days", type=int, default=1)
    sched_parser.add_argument("--min-mag", type=float, default=DEFAULT_MIN_MAGNITUDE)
    sched_parser.add_argument("--region", choices=["global", "china"], default="china")
    sched_parser.add_argument("--min-lat", type=float, default=-90)
    sched_parser.add_argument("--max-lat", type=float, default=90)
    sched_parser.add_argument("--min-lon", type=float, default=-180)
    sched_parser.add_argument("--max-lon", type=float, default=180)
    sched_parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR)
    sched_parser.set_defaults(func=do_schedule)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
