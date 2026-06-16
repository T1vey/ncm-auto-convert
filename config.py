"""配置管理 — 支持多目录监控"""

import json
from pathlib import Path

APP_NAME = "NCM-AutoConvert"
CONFIG_DIR = Path.home() / "AppData" / "Local" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "watch_dirs": [],
    "ncmdump_path": "",
    "poll_interval": 5,
    "stable_checks": 3,
    "stable_interval": 5,
    "convert_timeout": 120,
    "max_workers": 10,          # 每个目录的最大并行转换数
    "delete_lrc": False,
    "import_enabled": False,
    "import_dir": "",
    "auto_start": False,
    "minimize_to_tray": True,
}


def load() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg = {**DEFAULTS, **saved}
            # 兼容旧版单目录配置
            if "watch_dir" in cfg and not cfg.get("watch_dirs"):
                cfg["watch_dirs"] = [cfg.pop("watch_dir")]
            elif "watch_dir" in cfg:
                cfg.pop("watch_dir")
            # 确保 watch_dirs 是列表
            if not isinstance(cfg.get("watch_dirs"), list):
                cfg["watch_dirs"] = []
            return cfg
        except (json.JSONDecodeError, IOError):
            pass
    return dict(DEFAULTS)


def save(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # 不保存旧字段
    cfg.pop("watch_dir", None)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_log_path(cfg: dict) -> Path:
    """日志文件路径（第一个监控目录下，或 APPDATA）"""
    for d in cfg.get("watch_dirs", []):
        p = Path(d)
        if p.exists():
            return p / "ncm_watcher.log"
    return CONFIG_DIR / "ncm_watcher.log"
