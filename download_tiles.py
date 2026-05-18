#!/usr/bin/env python3
"""
预下载 OpenStreetMap 瓦片到本地，供内网离线使用。

用法:
    python download_tiles.py                          # 默认全球 z0~z6
    python download_tiles.py --region china            # 仅中国周边 (更快)
    python download_tiles.py --max-zoom 7              # 全球到 z7 (~87K tiles, ~350MB)
    python download_tiles.py --region china --max-zoom 8  # 中国到 z8

层级参考:
    z0~z4  全球    ~1,400 tiles    ~5 MB      秒级
    z0~z5  全球    ~5,500 tiles    ~20 MB     秒级
    z0~z6  全球    ~22,000 tiles   ~80 MB     分钟级
    z0~z7  全球    ~87,000 tiles   ~350 MB    十分钟级

代理设置 (内网穿透场景):
    set HTTP_PROXY=http://proxy:8080
    python download_tiles.py
"""

import argparse
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

TILES_DIR = Path(__file__).parent / "static" / "tiles"

REGIONS = {
    "global": {"lon_min": -180, "lon_max": 180, "lat_min": -85, "lat_max": 85},
    "china":  {"lon_min": 70, "lon_max": 140, "lat_min": 15, "lat_max": 55},
}

TILE_URLS = [
    "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
]

USER_AGENT = "EarthquakeFetcher-TileCache/1.0"
MAX_WORKERS = 8
REQUEST_TIMEOUT = 15


def latlon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) +
                          1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def _compute_tile_bounds(region: dict, zoom: int) -> tuple[int, int, int, int]:
    """计算区域覆盖的瓦片坐标范围 → (x_min, x_max, y_min, y_max)"""
    x_nw, y_nw = latlon_to_tile(region["lat_max"], region["lon_min"], zoom)
    x_se, y_se = latlon_to_tile(region["lat_min"], region["lon_max"], zoom)
    n = 2 ** zoom
    return (
        max(0, min(x_nw, x_se)),
        min(n - 1, max(x_nw, x_se)),
        max(0, min(y_nw, y_se)),
        min(n - 1, max(y_nw, y_se)),
    )


def estimate_tiles(region: dict, min_zoom: int, max_zoom: int) -> dict[int, int]:
    estimates = {}
    for zoom in range(min_zoom, max_zoom + 1):
        x_min, x_max, y_min, y_max = _compute_tile_bounds(region, zoom)
        estimates[zoom] = (x_max - x_min + 1) * (y_max - y_min + 1)
    return estimates


def get_tiles_for_zoom(zoom: int, region: dict) -> list[tuple[int, int, int]]:
    x_min, x_max, y_min, y_max = _compute_tile_bounds(region, zoom)
    return [(zoom, x, y) for x in range(x_min, x_max + 1)
            for y in range(y_min, y_max + 1)]


def download_tile(z: int, x: int, y: int) -> tuple[int, bool]:
    out_path = TILES_DIR / str(z) / str(x) / f"{y}.png"
    if out_path.exists():
        return 304, True

    out_path.parent.mkdir(parents=True, exist_ok=True)
    url = TILE_URLS[(x + y) % len(TILE_URLS)].format(z=z, x=x, y=y)

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT},
                            timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            out_path.write_bytes(resp.content)
            return 200, True
        return resp.status_code, False
    except requests.RequestException:
        return 0, False


def main():
    parser = argparse.ArgumentParser(
        description="下载离线地图瓦片 (OSM)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python download_tiles.py                          全球 z3~z6 (推荐)
  python download_tiles.py --region china --max-zoom 8   中国到 z8
  python download_tiles.py --max-zoom 7 --workers 12     全球到 z7, 12线程
        """,
    )
    parser.add_argument("--region", choices=["global", "china"], default="global")
    parser.add_argument("--min-zoom", type=int, default=3)
    parser.add_argument("--max-zoom", type=int, default=6)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--dry-run", action="store_true",
                        help="仅显示预估瓦片数和大小，不实际下载")
    args = parser.parse_args()

    region = REGIONS[args.region]

    # 预估
    estimates = estimate_tiles(region, args.min_zoom, args.max_zoom)
    total_estimate = sum(estimates.values())
    size_estimate_mb = total_estimate * 4 / 1024  # 每个瓦片约 4KB 平均

    print(f"区域: {args.region}  Zoom: {args.min_zoom}~{args.max_zoom}")
    print(f"预估瓦片总数: {total_estimate:,}  预估大小: ~{size_estimate_mb:.0f} MB")
    print(f"存储路径: {TILES_DIR}")
    print()

    for z, count in estimates.items():
        print(f"  Zoom {z}: {count:,} tiles")
    print()

    if args.dry_run:
        print("--dry-run 模式，不执行下载。")
        return

    if total_estimate > 50000:
        print(f"⚠ 瓦片数超过 50,000，下载可能较慢。建议先试 --dry-run 或降低 --max-zoom。")
        try:
            input("按 Enter 继续, Ctrl+C 取消...")
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            return

    start_time = time.time()
    total_downloaded = 0
    total_cached = 0
    total_failed = 0

    for zoom in range(args.min_zoom, args.max_zoom + 1):
        tiles = get_tiles_for_zoom(zoom, region)
        n = len(tiles)
        print(f"Zoom {zoom}: {n} 个瓦片 ", end="", flush=True)

        cached = sum(1 for t in tiles if (TILES_DIR / str(t[0]) / str(t[1]) / f"{t[2]}.png").exists())
        to_download = [t for t in tiles if not (TILES_DIR / str(t[0]) / str(t[1]) / f"{t[2]}.png").exists()]

        if not to_download:
            print(f"[全部已缓存 {cached}]")
            total_cached += cached
            continue

        dl_count = 0
        fail_count = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(download_tile, z, x, y): (z, x, y)
                       for z, x, y in to_download}
            for future in as_completed(futures):
                status, ok = future.result()
                if ok and status == 200:
                    dl_count += 1
                elif ok and status == 304:
                    cached += 1
                else:
                    fail_count += 1

        total_cached += cached
        total_downloaded += dl_count
        total_failed += fail_count
        print(f"[下载 {dl_count}, 缓存 {cached}, 失败 {fail_count}]")

    elapsed = time.time() - start_time
    total_bytes = sum(
        f.stat().st_size for f in TILES_DIR.rglob("*.png") if f.is_file()
    )
    print(f"\n========== 完成 ==========")
    print(f"下载: {total_downloaded}  缓存: {total_cached}  失败: {total_failed}")
    print(f"耗时: {elapsed:.1f} 秒  大小: {total_bytes / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
