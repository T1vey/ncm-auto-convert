import os
import sys

# 最早隐藏控制台窗口
if sys.platform == "win32":
    try:
        import ctypes
        _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if _hwnd:
            ctypes.windll.user32.ShowWindow(_hwnd, 0)
    except Exception:
        pass

import os
import time
import threading
import logging
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pystray
from PIL import Image

import config
from icon import create_tray_icon
from ncm_auto_convert import is_file_locked, wait_until_stable

# 单实例锁文件 + 信号文件
APPDATA_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "NCM-AutoConvert"
LOCK_FILE = APPDATA_DIR / ".lock"
SIGNAL_FILE = APPDATA_DIR / ".show_settings"

# ──────────────────────────────────────────────
#  核心转换逻辑（并行版）
# ──────────────────────────────────────────────

class NCMConverter:
    """后台转换引擎，支持多文件并行处理"""

    def __init__(self, cfg: dict, log: logging.Logger, on_status=None):
        self.cfg = cfg
        self.log = log
        self.on_status = on_status or (lambda s: None)
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._active = {}  # {filename: "等待稳定" | "转换中"}

    @property
    def running(self):
        return self._running

    def start(self):
        with self._lock:
            if self._running:
                return
            self._stop_event.clear()
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self.on_status("监控中")

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
            self._running = False
            self.on_status("已停止")

    def _update_active(self, name: str, status: str):
        """更新活跃任务状态"""
        if status:
            self._active[name] = status
        else:
            self._active.pop(name, None)
        # 更新托盘提示
        if self._active:
            tasks = ", ".join(f"{n}" for n in self._active)
            self.on_status(f"处理中({len(self._active)}): {tasks[:60]}")
        else:
            self.on_status("监控中")

    def _run(self):
        cfg = self.cfg
        watch_dir = Path(cfg["watch_dir"])
        ncmdump = Path(cfg["ncmdump_path"]) if cfg["ncmdump_path"] else watch_dir / "ncmdump.exe"

        if not watch_dir.exists():
            self.log.error(f"监控目录不存在: {watch_dir}")
            self.on_status("目录不存在")
            self._running = False
            return
        if not ncmdump.exists():
            self.log.error(f"ncmdump 不存在: {ncmdump}")
            self.on_status("缺少 ncmdump")
            self._running = False
            return

        # 启动清理
        self._cleanup_existing(watch_dir)

        self.log.info(f"开始监控: {watch_dir}")
        seen = set()
        # 并行线程池（最多同时处理 3 个文件）
        executor = ThreadPoolExecutor(max_workers=3)
        futures = {}

        try:
            while not self._stop_event.is_set():
                try:
                    for ncm in watch_dir.glob("*.ncm"):
                        if self._stop_event.is_set():
                            break
                        if ncm.name in seen:
                            continue

                        mp3 = ncm.with_suffix(".mp3")
                        if mp3.exists() and mp3.stat().st_size > 0:
                            self.log.info(f"清理（已有 mp3）: {ncm.name}")
                            ncm.unlink()
                            seen.add(ncm.name)
                            continue

                        self.log.info(f"检测到新文件: {ncm.name}")
                        seen.add(ncm.name)
                        # 提交到线程池并行处理
                        future = executor.submit(self._convert, ncm, ncmdump)
                        futures[future] = ncm.name

                    # 清理已完成的任务
                    done = [f for f in futures if f.done()]
                    for f in done:
                        name = futures.pop(f)
                        try:
                            f.result()
                        except Exception as e:
                            self.log.exception(f"转换任务异常 [{name}]: {e}")

                except Exception as e:
                    self.log.exception(f"扫描出错: {e}")

                # 分段等待
                for _ in range(int(cfg["poll_interval"] * 10)):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)
        finally:
            executor.shutdown(wait=False)

    def _cleanup_existing(self, watch_dir: Path):
        """启动时清理已有 mp3 的残留 ncm"""
        for ncm in sorted(watch_dir.glob("*.ncm")):
            mp3 = ncm.with_suffix(".mp3")
            if mp3.exists() and mp3.stat().st_size > 0:
                self.log.info(f"启动清理: {ncm.name}")
                ncm.unlink()

    def _convert(self, ncm_path: Path, ncmdump: Path):
        """转换单个文件（在线程池中运行）"""
        cfg = self.cfg
        mp3_path = ncm_path.with_suffix(".mp3")
        name = ncm_path.stem
        self._update_active(name, "等待稳定")
        self.log.info(f"[{name}] 开始等待稳定...")

        # 等待稳定
        if not wait_until_stable(
            ncm_path, cfg["stable_checks"], cfg["stable_interval"], self.log
        ):
            self._update_active(name, None)
            return

        if self._stop_event.is_set():
            self._update_active(name, None)
            return

        self._update_active(name, "转换中")
        self.log.info(f"[{name}] 开始转换")

        try:
            result = subprocess.run(
                [str(ncmdump), str(ncm_path)],
                capture_output=True, text=True, timeout=cfg["convert_timeout"],
            )
            if result.returncode != 0:
                self.log.error(f"[{name}] 转换失败: {result.stderr.strip()}")
                self._update_active(name, None)
                return
        except subprocess.TimeoutExpired:
            self.log.error(f"[{name}] 转换超时")
            self._update_active(name, None)
            return
        except FileNotFoundError:
            self.log.error(f"[{name}] ncmdump 未找到")
            self._update_active(name, None)
            return

        # 验证
        if not mp3_path.exists() or mp3_path.stat().st_size == 0:
            self.log.error(f"[{name}] mp3 无效")
            self._update_active(name, None)
            return

        mb = mp3_path.stat().st_size / 1024 / 1024
        ncm_path.unlink()
        self.log.info(f"[{name}] 完成 ({mb:.1f} MB)")
        self._update_active(name, None)


# ──────────────────────────────────────────────
#  设置窗口
# ──────────────────────────────────────────────

class SettingsDialog:
    """设置对话框 — 选择监控目录、调整参数"""

    def __init__(self, cfg: dict, on_save=None):
        self.cfg = cfg
        self.on_save = on_save
        self.result = None
        self._build()

    def _build(self):
        self.win = tk.Tk()
        self.win.title("NCM Auto Converter — 设置")
        self.win.geometry("520x420")
        self.win.resizable(False, False)
        self.win.configure(bg="#1a1a2e")

        # 设置窗口图标
        ico_path = Path(__file__).parent / "app.ico"
        if ico_path.exists():
            self.win.iconbitmap(str(ico_path))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#1a1a2e", foreground="#e0e0e0", fieldbackground="#16213e")
        style.configure("TLabel", background="#1a1a2e", foreground="#e0e0e0", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TEntry", fieldbackground="#16213e", foreground="#e0e0e0")
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#00d2ff")
        style.configure("Status.TLabel", font=("Segoe UI", 9), foreground="#888")

        pad = {"padx": 16, "pady": 6}

        # 标题
        ttk.Label(self.win, text="♪ NCM Auto Converter", style="Header.TLabel").pack(pady=(20, 10))

        # 目录选择
        frm_dir = ttk.Frame(self.win)
        frm_dir.pack(fill="x", **pad)
        ttk.Label(frm_dir, text="监控目录：").pack(side="left")
        self.var_dir = tk.StringVar(value=self.cfg["watch_dir"])
        ttk.Entry(frm_dir, textvariable=self.var_dir, width=40).pack(side="left", padx=6)
        ttk.Button(frm_dir, text="浏览…", command=self._browse).pack(side="left")

        # ncmdump 路径
        frm_nmp = ttk.Frame(self.win)
        frm_nmp.pack(fill="x", **pad)
        ttk.Label(frm_nmp, text="ncmdump：").pack(side="left")
        self.var_nmp = tk.StringVar(value=self.cfg.get("ncmdump_path", ""))
        ttk.Entry(frm_nmp, textvariable=self.var_nmp, width=40).pack(side="left", padx=6)
        ttk.Button(frm_nmp, text="浏览…", command=self._browse_nmp).pack(side="left")

        # 参数
        frm_params = ttk.LabelFrame(self.win, text="参数", padding=10)
        frm_params.pack(fill="x", **pad)

        row1 = ttk.Frame(frm_params)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="扫描间隔（秒）：").pack(side="left")
        self.var_poll = tk.IntVar(value=self.cfg["poll_interval"])
        ttk.Entry(row1, textvariable=self.var_poll, width=6).pack(side="left", padx=4)
        ttk.Label(row1, text="    稳定检测次数：").pack(side="left")
        self.var_stable = tk.IntVar(value=self.cfg["stable_checks"])
        ttk.Entry(row1, textvariable=self.var_stable, width=6).pack(side="left", padx=4)

        row2 = ttk.Frame(frm_params)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="检测间隔（秒）：").pack(side="left")
        self.var_sinterval = tk.DoubleVar(value=self.cfg["stable_interval"])
        ttk.Entry(row2, textvariable=self.var_sinterval, width=6).pack(side="left", padx=4)
        ttk.Label(row2, text="    转换超时（秒）：").pack(side="left")
        self.var_timeout = tk.IntVar(value=self.cfg["convert_timeout"])
        ttk.Entry(row2, textvariable=self.var_timeout, width=6).pack(side="left", padx=4)

        # 提示
        ttk.Label(self.win, text="稳定检测 = 连续 N 次文件大小不变才开始转换",
                  style="Status.TLabel").pack(pady=(4, 0))

        # 按钮
        frm_btn = ttk.Frame(self.win)
        frm_btn.pack(pady=(16, 20))
        ttk.Button(frm_btn, text="保存并开始监控", command=self._save).pack(side="left", padx=8)
        ttk.Button(frm_btn, text="取消", command=self.win.destroy).pack(side="left", padx=8)

        # 居中
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        x = (self.win.winfo_screenwidth() - w) // 2
        y = (self.win.winfo_screenheight() - h) // 2
        self.win.geometry(f"+{x}+{y}")

    def _browse(self):
        d = filedialog.askdirectory(title="选择网易云音乐下载目录")
        if d:
            self.var_dir.set(d)
            nmp = Path(d) / "ncmdump.exe"
            if nmp.exists() and not self.var_nmp.get():
                self.var_nmp.set(str(nmp))

    def _browse_nmp(self):
        f = filedialog.askopenfilename(
            title="选择 ncmdump.exe",
            filetypes=[("ncmdump", "ncmdump.exe"), ("所有文件", "*.*")],
        )
        if f:
            self.var_nmp.set(f)

    def _save(self):
        d = self.var_dir.get().strip()
        if not d:
            messagebox.showwarning("提示", "请选择监控目录")
            return
        if not Path(d).exists():
            messagebox.showerror("错误", f"目录不存在：{d}")
            return

        self.cfg["watch_dir"] = d
        self.cfg["ncmdump_path"] = self.var_nmp.get().strip()
        self.cfg["poll_interval"] = max(1, self.var_poll.get())
        self.cfg["stable_checks"] = max(1, self.var_stable.get())
        self.cfg["stable_interval"] = max(1.0, self.var_sinterval.get())
        self.cfg["convert_timeout"] = max(10, self.var_timeout.get())

        config.save(self.cfg)
        if self.on_save:
            self.on_save(self.cfg)
        self.result = self.cfg
        self.win.destroy()

    def show(self):
        self.win.mainloop()
        return self.result


# ──────────────────────────────────────────────
#  系统托盘应用
# ──────────────────────────────────────────────

class TrayApp:
    """主应用 — 系统托盘 + 后台转换线程"""

    def __init__(self):
        self.cfg = config.load()
        self.log = self._setup_logging()
        self.converter = None
        self.icon = None
        self._status = "就绪"

    def _setup_logging(self) -> logging.Logger:
        log = logging.getLogger("ncm_tray")
        log.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")

        log_path = config.get_log_path(self.cfg)
        try:
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setFormatter(fmt)
            log.addHandler(fh)
        except Exception:
            pass

        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        log.addHandler(ch)

        return log

    def _update_status(self, status: str):
        self._status = status
        if self.icon:
            self.icon.title = f"NCM Converter — {status}"

    def _create_tray_icon(self):
        """创建系统托盘图标"""
        active = self.converter and self.converter.running
        img = create_tray_icon(64, active=active)

        menu = pystray.Menu(
            pystray.MenuItem(f"状态: {self._status}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("打开设置", self._on_settings),
            pystray.MenuItem("打开日志", self._on_open_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._on_exit),
        )

        self.icon = pystray.Icon(
            name="ncm-auto-convert",
            icon=img,
            title=f"NCM Converter — {self._status}",
            menu=menu,
        )

    def _on_settings(self, icon=None, item=None):
        threading.Thread(target=self._show_settings, daemon=True).start()

    def _show_settings(self):
        if self.converter and self.converter.running:
            self.converter.stop()

        dlg = SettingsDialog(self.cfg, on_save=self._on_config_saved)
        dlg.show()

    def _on_config_saved(self, new_cfg: dict):
        self.cfg = new_cfg
        self.log = self._setup_logging()
        self._start_converter()

    def _on_open_log(self, icon=None, item=None):
        log_path = config.get_log_path(self.cfg)
        if log_path.exists():
            os.startfile(str(log_path))
        else:
            self.log.info("日志文件暂不存在")

    def _on_exit(self, icon=None, item=None):
        if self.converter:
            self.converter.stop()
        if self.icon:
            self.icon.stop()

    def _start_converter(self):
        self.converter = NCMConverter(
            self.cfg, self.log, on_status=self._update_status
        )
        self.converter.start()

    def _watch_signal(self):
        """监听信号文件"""
        while True:
            time.sleep(1)
            if SIGNAL_FILE.exists():
                try:
                    SIGNAL_FILE.unlink()
                except OSError:
                    pass
                self.log.info("收到信号：打开设置")
                self._on_settings()

    def run(self):
        """主入口"""
        if self.cfg["watch_dir"]:
            nmp = Path(self.cfg["ncmdump_path"]) if self.cfg["ncmdump_path"] else Path(self.cfg["watch_dir"]) / "ncmdump.exe"
            if not nmp.exists():
                self.log.warning(f"ncmdump 未找到: {nmp}")

        if not self.cfg["watch_dir"]:
            self.log.info("首次运行，打开设置向导")
            dlg = SettingsDialog(self.cfg, on_save=self._on_config_saved)
            dlg.show()
            if not self.cfg["watch_dir"]:
                sys.exit(0)
        else:
            self._start_converter()

        threading.Thread(target=self._watch_signal, daemon=True).start()

        self._create_tray_icon()
        self.icon.run()


# ──────────────────────────────────────────────
#  入口
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # 单实例检测
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            os.kill(old_pid, 0)
            SIGNAL_FILE.write_text("show_settings")
            sys.exit(0)
        except (ValueError, OSError, ProcessLookupError):
            LOCK_FILE.unlink(missing_ok=True)

    LOCK_FILE.write_text(str(os.getpid()))

    import atexit
    atexit.register(lambda: LOCK_FILE.unlink(missing_ok=True))

    try:
        app = TrayApp()
        app.run()
    except Exception as e:
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("NCM Auto Converter", f"启动失败:\n\n{e}")
            root.destroy()
        except Exception:
            pass
        logging.exception(f"Fatal: {e}")
        sys.exit(1)
