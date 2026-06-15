"""配置管理 — 存储在 %LOCALAPPDATA%/NCM-AutoConvert/config.json"""

import json
from pathlib import Path

APP_NAME = "NCM-AutoConvert"
CONFIG_DIR = Path.home() / "AppData" / "Local" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "watch_dir": "",           # 监控目录（首次启动需设置）
    "ncmdump_path": "",        # ncmdump 路径（空=自动找 watch_dir 下的）
    "poll_interval": 5,        # 扫描间隔（秒）
    "stable_checks": 3,        # 连续稳定次数
    "stable_interval": 5,      # 稳定检测间隔（秒）
    "convert_timeout": 120,    # 单文件转换超时（秒）
    "auto_start": False,       # 开机自启
    "minimize_to_tray": True,  # 关闭窗口时最小化到托盘
}


def load() -> dict:
    """加载配置，不存在则返回默认值"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # 合并：用默认值填充缺失的键
            cfg = {**DEFAULTS, **saved}
            return cfg
        except (json.JSONDecodeError, IOError):
            pass
    return dict(DEFAULTS)


def save(cfg: dict):
    """保存配置"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_log_path(cfg: dict) -> Path:
    """日志文件路径"""
    watch = Path(cfg["watch_dir"])
    if watch.exists():
        return watch / "ncm_watcher.log"
    return CONFIG_DIR / "ncm_watcher.log"
