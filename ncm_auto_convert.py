#!/usr/bin/env python3
"""
NCM Auto Converter — 网易云音乐 NCM 自动转换守护
=================================================
监控指定目录，自动将 .ncm 文件转换为 .mp3 并删除原文件。

安全机制：
  - 文件大小稳定检测：确认下载完成后才转换，不会破坏半成品
  - 独占文件锁检测：仍在写入的文件会被跳过
  - 转换后验证：mp3 存在且大小 > 0 才删除 ncm

依赖：仅 Python 标准库 + ncmdump.exe
"""

import os
import sys
import time
import glob
import subprocess
import logging
import argparse
import json
from pathlib import Path

__version__ = "1.0.0"

# ========== 默认配置 ==========
DEFAULT_POLL_INTERVAL   = 5      # 扫描间隔（秒）
DEFAULT_STABLE_CHECKS   = 3      # 连续稳定次数
DEFAULT_STABLE_INTERVAL = 5      # 每次稳定检查间隔（秒）
DEFAULT_CONVERT_TIMEOUT = 120    # 单文件转换超时（秒）
# ==============================


def setup_logging(log_file: Path, verbose: bool = False):
    """配置日志：同时输出到文件和控制台"""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s  %(message)s"
    datefmt = "%H:%M:%S"

    handlers = [
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)
    return logging.getLogger("ncm_watcher")


def is_file_locked(filepath: Path) -> bool:
    """尝试独占打开文件，打不开说明还在被写入"""
    try:
        with open(filepath, "rb"):
            pass
        return False
    except (PermissionError, OSError):
        return True


def wait_until_stable(filepath: Path, stable_checks: int, stable_interval: float, log) -> bool:
    """
    等待文件大小稳定（下载完成）。
    连续 stable_checks 次采样大小不变且文件未被锁定，才认定完成。
    """
    prev_size = -1
    stable_count = 0

    for i in range(stable_checks + 1):
        time.sleep(stable_interval)
        if not filepath.exists():
            log.warning(f"  文件消失了: {filepath.name}")
            return False

        size = filepath.stat().st_size

        if size == prev_size and size > 0 and not is_file_locked(filepath):
            stable_count += 1
            log.info(f"  稳定检测 {stable_count}/{stable_checks}: {size:,} bytes ✓")
            if stable_count >= stable_checks:
                return True
        else:
            stable_count = 0
            if i == 0:
                log.info(f"  等待下载完成... 当前 {size:,} bytes")

        prev_size = size

    return stable_count >= stable_checks


def convert_ncm(ncm_path: Path, ncmdump: Path, timeout: int,
                stable_checks: int, stable_interval: float, log) -> bool:
    """
    转换单个 ncm 文件。
    返回 True = 成功（ncm 已删除）；False = 失败（ncm 保留）
    """
    mp3_path = ncm_path.with_suffix(".mp3")
    ncm_name = ncm_path.name

    # 已有有效 mp3 → 直接删 ncm
    if mp3_path.exists() and mp3_path.stat().st_size > 0:
        log.info(f"  已有 mp3，跳过转换: {mp3_path.name}")
        ncm_path.unlink()
        log.info(f"  已删除 ncm: {ncm_name}")
        return True

    # 等待下载稳定
    log.info(f"  等待文件稳定...")
    if not wait_until_stable(ncm_path, stable_checks, stable_interval, log):
        return False

    # 执行转换
    log.info(f"  开始转换: {ncm_name}")
    try:
        result = subprocess.run(
            [str(ncmdump), str(ncm_path)],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            log.error(f"  转换失败! ncmdump 返回码 {result.returncode}")
            if result.stderr:
                log.error(f"  {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        log.error(f"  转换超时（{timeout} 秒）")
        return False
    except FileNotFoundError:
        log.error(f"  找不到 ncmdump: {ncmdump}")
        return False

    # 验证 mp3
    if not mp3_path.exists():
        log.error(f"  转换后 mp3 不存在: {mp3_path.name}")
        return False
    if mp3_path.stat().st_size == 0:
        log.error(f"  mp3 文件为空: {mp3_path.name}")
        mp3_path.unlink()
        return False

    mp3_mb = mp3_path.stat().st_size / 1024 / 1024
    log.info(f"  转换成功: {mp3_path.name} ({mp3_mb:.1f} MB)")

    # 删除 ncm
    ncm_path.unlink()
    log.info(f"  已删除 ncm: {ncm_name}")
    return True


def scan_and_convert(music_dir: Path, ncmdump: Path, timeout: int,
                     stable_checks: int, stable_interval: float, log):
    """扫描目录，转换所有未处理的 ncm 文件"""
    ncm_files = sorted(music_dir.glob("*.ncm"))
    if not ncm_files:
        return

    for ncm in ncm_files:
        mp3 = ncm.with_suffix(".mp3")
        if mp3.exists() and mp3.stat().st_size > 0:
            log.info(f"清理残留 ncm（已有 mp3）: {ncm.name}")
            ncm.unlink()
            continue
        log.info(f"发现待转换: {ncm.name}")
        convert_ncm(ncm, ncmdump, timeout, stable_checks, stable_interval, log)


def main():
    parser = argparse.ArgumentParser(
        description="NCM Auto Converter — 网易云 NCM 自动转换守护",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python ncm_auto_convert.py                          # 监控脚本所在目录
  python ncm_auto_convert.py -d D:\\Music\\Download     # 监控指定目录
  python ncm_auto_convert.py --once                   # 只处理现有文件，不持续监控
  python ncm_auto_convert.py --poll 10 --stable 5     # 自定义检测参数
        """,
    )
    parser.add_argument("-d", "--dir", type=str, default=None,
                        help="监控目录（默认：脚本所在目录）")
    parser.add_argument("--ncmdump", type=str, default=None,
                        help="ncmdump 路径（默认：监控目录下的 ncmdump.exe）")
    parser.add_argument("--once", action="store_true",
                        help="只处理现有文件，不持续监控")
    parser.add_argument("--poll", type=int, default=DEFAULT_POLL_INTERVAL,
                        help=f"扫描间隔秒数（默认 {DEFAULT_POLL_INTERVAL}）")
    parser.add_argument("--stable", type=int, default=DEFAULT_STABLE_CHECKS,
                        help=f"连续稳定次数（默认 {DEFAULT_STABLE_CHECKS}）")
    parser.add_argument("--stable-interval", type=float, default=DEFAULT_STABLE_INTERVAL,
                        help=f"稳定检测间隔秒数（默认 {DEFAULT_STABLE_INTERVAL}）")
    parser.add_argument("--timeout", type=int, default=DEFAULT_CONVERT_TIMEOUT,
                        help=f"单文件转换超时秒数（默认 {DEFAULT_CONVERT_TIMEOUT}）")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="详细日志")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    # 确定目录
    music_dir = Path(args.dir) if args.dir else Path(__file__).parent.resolve()
    ncmdump   = Path(args.ncmdump) if args.ncmdump else music_dir / "ncmdump.exe"
    log_file  = music_dir / "ncm_watcher.log"

    log = setup_logging(log_file, args.verbose)

    log.info("=" * 50)
    log.info(f"NCM Auto Converter v{__version__}")
    log.info(f"  监控目录:   {music_dir}")
    log.info(f"  ncmdump:    {ncmdump}")
    log.info(f"  轮询间隔:   {args.poll}s | 稳定检测: {args.stable}×{args.stable_interval}s")
    log.info(f"  转换超时:   {args.timeout}s | 模式: {'单次' if args.once else '持续监控'}")
    log.info(f"  日志文件:   {log_file}")
    log.info("=" * 50)

    if not ncmdump.exists():
        log.error(f"ncmdump 不存在: {ncmdump}")
        log.error("请将 ncmdump.exe 放在监控目录下，或用 --ncmdump 指定路径")
        sys.exit(1)

    # 启动清理：已有 mp3 的 ncm 直接删
    for ncm in sorted(music_dir.glob("*.ncm")):
        mp3 = ncm.with_suffix(".mp3")
        if mp3.exists() and mp3.stat().st_size > 0:
            log.info(f"启动清理（已有 mp3）: {ncm.name}")
            ncm.unlink()

    # 处理现有未转换文件
    scan_and_convert(music_dir, ncmdump, args.timeout, args.stable, args.stable_interval, log)

    if args.once:
        log.info("单次模式，处理完毕退出")
        return

    # 持续监控模式
    log.info("进入监控模式，等待新文件...")
    seen = set()

    while True:
        time.sleep(args.poll)
        for ncm in music_dir.glob("*.ncm"):
            if ncm.name in seen:
                continue
            mp3 = ncm.with_suffix(".mp3")
            if mp3.exists() and mp3.stat().st_size > 0:
                log.info(f"清理（已有 mp3）: {ncm.name}")
                ncm.unlink()
                seen.add(ncm.name)
                continue
            log.info(f"检测到新文件: {ncm.name}")
            seen.add(ncm.name)
            convert_ncm(ncm, ncmdump, args.timeout, args.stable, args.stable_interval, log)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断，退出")
    except Exception as e:
        logging.exception(f"未预期错误: {e}")
