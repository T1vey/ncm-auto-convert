"""
NCM Auto Converter — 系统托盘应用（多目录版）
=============================================
支持同时监控多个下载目录，每个目录独立并行处理。
"""

import sys
import os

# 最早隐藏控制台窗口
if sys.platform == "win32":
    try:
        import ctypes
        _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if _hwnd:
            ctypes.windll.user32.ShowWindow(_hwnd, 0)
    except Exception:
        pass

import time
import threading
import logging
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pystray
from PIL import Image

import config
from icon import create_tray_icon
from ncm_auto_convert import wait_until_stable

# 单实例锁 + 信号
APPDATA_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "NCM-AutoConvert"
LOCK_FILE = APPDATA_DIR / ".lock"
SIGNAL_FILE = APPDATA_DIR / ".show_settings"


# ──────────────────────────────────────────────
#  转换引擎（多目录并行）
# ──────────────────────────────────────────────

class NCMConverter:
    """后台转换引擎，每个目录独立监控线程 + 线程池并行转换"""

    def __init__(self, cfg: dict, log: logging.Logger, on_status=None):
        self.cfg = cfg
        self.log = log
        self.on_status = on_status or (lambda s: None)
        self._running = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._threads = []
        self._active = {}  # {("目录名", "文件名"): "状态"}
        self._active_lock = threading.Lock()

    @property
    def running(self):
        return self._running

    def start(self):
        with self._lock:
            if self._running:
                return
            self._stop_event.clear()
            self._running = True
            dirs = self.cfg.get("watch_dirs", [])
            for d in dirs:
                t = threading.Thread(target=self._watch_dir, args=(d,), daemon=True)
                t.start()
                self._threads.append(t)
            self.on_status(f"监控中 ({len(dirs)} 个目录)")

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
            self._running = False
            self._active.clear()
            self.on_status("已停止")

    def _update_active(self, dir_label: str, name: str, status: str):
        with self._active_lock:
            key = (dir_label, name)
            if status:
                self._active[key] = status
            else:
                self._active.pop(key, None)
            count = len(self._active)
            if count:
                self.on_status(f"处理中 ({count} 个任务)")
            else:
                self.on_status(f"监控中 ({len(self.cfg.get('watch_dirs', []))} 个目录)")

    def _watch_dir(self, watch_dir: str):
        """单个目录的监控循环"""
        cfg = self.cfg
        wdir = Path(watch_dir)
        ncmdump = Path(cfg["ncmdump_path"]) if cfg["ncmdump_path"] else wdir / "ncmdump.exe"
        label = wdir.name  # 目录短名

        if not wdir.exists():
            self.log.error(f"[{label}] 目录不存在: {wdir}")
            return
        if not ncmdump.exists():
            self.log.warning(f"[{label}] ncmdump 不存在: {ncmdump}")

        # 启动清理：有 mp3 的 ncm 直接删
        for ncm in sorted(wdir.glob("*.ncm")):
            mp3 = ncm.with_suffix(".mp3")
            if mp3.exists() and mp3.stat().st_size > 0:
                self.log.info(f"[{label}] 启动清理: {ncm.name}")
                ncm.unlink()

        # 清理 lrc
        if cfg.get("delete_lrc"):
            for lrc in wdir.glob("*.lrc"):
                self.log.info(f"[{label}] 删除 lrc: {lrc.name}")
                lrc.unlink()

        # 启动导入：已有的 mp3 移到目标目录
        if cfg.get("import_enabled") and cfg.get("import_dir"):
            import_dir = Path(cfg["import_dir"])
            import_dir.mkdir(parents=True, exist_ok=True)
            for mp3 in sorted(wdir.glob("*.mp3")):
                if mp3.stat().st_size > 0:
                    self._move_to_import(mp3, import_dir, label)

        self.log.info(f"[{label}] 开始监控: {wdir}")
        seen = set()
        max_w = cfg.get("max_workers", 10)
        executor = ThreadPoolExecutor(max_workers=max_w)
        self.log.info(f"[{label}] 并行度: {max_w}")
        futures = {}
        import_dir = None
        if cfg.get("import_enabled") and cfg.get("import_dir"):
            import_dir = Path(cfg["import_dir"])
            import_dir.mkdir(parents=True, exist_ok=True)

        try:
            while not self._stop_event.is_set():
                try:
                    # ── 处理 ncm 文件 ──
                    for ncm in wdir.glob("*.ncm"):
                        if self._stop_event.is_set():
                            break
                        if ncm.name in seen:
                            continue
                        mp3 = ncm.with_suffix(".mp3")
                        if mp3.exists() and mp3.stat().st_size > 0:
                            self.log.info(f"[{label}] 清理: {ncm.name}")
                            ncm.unlink()
                            seen.add(ncm.name)
                            continue
                        self.log.info(f"[{label}] 发现: {ncm.name}")
                        seen.add(ncm.name)
                        # 删除同名 lrc
                        if cfg.get("delete_lrc"):
                            lrc = ncm.with_suffix(".lrc")
                            if lrc.exists():
                                self.log.info(f"[{label}] 删除 lrc: {lrc.name}")
                                lrc.unlink()
                        future = executor.submit(self._convert, label, ncm, ncmdump)
                        futures[future] = ncm.name

                    # ── 处理直接下载的 mp3 文件 ──
                    for mp3 in wdir.glob("*.mp3"):
                        if self._stop_event.is_set():
                            break
                        mp3_key = f"_mp3_{mp3.name}"
                        if mp3_key in seen:
                            continue
                        if mp3.stat().st_size == 0:
                            continue
                        seen.add(mp3_key)
                        # 删除同名 lrc
                        if cfg.get("delete_lrc"):
                            lrc = mp3.with_suffix(".lrc")
                            if lrc.exists():
                                self.log.info(f"[{label}] 删除 lrc: {lrc.name}")
                                lrc.unlink()
                        # 导入到目标目录
                        if import_dir:
                            self._move_to_import(mp3, import_dir, label)

                    # ── 清理残留 lrc（无对应 mp3/ncm 的） ──
                    if cfg.get("delete_lrc"):
                        for lrc in wdir.glob("*.lrc"):
                            lrc_key = f"_lrc_{lrc.name}"
                            if lrc_key not in seen:
                                seen.add(lrc_key)
                                self.log.info(f"[{label}] 删除孤立 lrc: {lrc.name}")
                                lrc.unlink()

                    done = [f for f in futures if f.done()]
                    for f in done:
                        name = futures.pop(f)
                        try:
                            f.result()
                        except Exception as e:
                            self.log.exception(f"[{label}] 任务异常 {name}: {e}")

                except Exception as e:
                    self.log.exception(f"[{label}] 扫描出错: {e}")

                for _ in range(int(cfg["poll_interval"] * 10)):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)
        finally:
            executor.shutdown(wait=False)
            self.log.info(f"[{label}] 监控结束")

    def _convert(self, label: str, ncm_path: Path, ncmdump: Path):
        """转换单个文件"""
        cfg = self.cfg
        mp3_path = ncm_path.with_suffix(".mp3")
        name = ncm_path.stem
        self._update_active(label, name, "等待稳定")
        self.log.info(f"[{label}] 等待稳定: {name}")

        if not wait_until_stable(ncm_path, cfg["stable_checks"], cfg["stable_interval"], self.log):
            self._update_active(label, name, None)
            return
        if self._stop_event.is_set():
            self._update_active(label, name, None)
            return

        self._update_active(label, name, "转换中")
        self.log.info(f"[{label}] 转换: {name}")

        try:
            result = subprocess.run(
                [str(ncmdump), str(ncm_path)],
                capture_output=True, text=True, timeout=cfg["convert_timeout"],
            )
            if result.returncode != 0:
                self.log.error(f"[{label}] 失败: {name} — {result.stderr.strip()}")
                self._update_active(label, name, None)
                return
        except subprocess.TimeoutExpired:
            self.log.error(f"[{label}] 超时: {name}")
            self._update_active(label, name, None)
            return
        except FileNotFoundError:
            self.log.error(f"[{label}] ncmdump 未找到")
            self._update_active(label, name, None)
            return

        if not mp3_path.exists() or mp3_path.stat().st_size == 0:
            self.log.error(f"[{label}] mp3 无效: {name}")
            self._update_active(label, name, None)
            return

        mb = mp3_path.stat().st_size / 1024 / 1024
        ncm_path.unlink()
        self.log.info(f"[{label}] 完成: {name} ({mb:.1f} MB)")

        # 导入到目标目录
        if cfg.get("import_enabled") and cfg.get("import_dir"):
            import_dir = Path(cfg["import_dir"])
            import_dir.mkdir(parents=True, exist_ok=True)
            self._move_to_import(mp3_path, import_dir, label)

        self._update_active(label, name, None)

    def _move_to_import(self, mp3_path: Path, import_dir: Path, label: str):
        """将 mp3 移动到目标目录，重名时自动加编号"""
        dest = import_dir / mp3_path.name
        # 重名处理：文件名(2).mp3, 文件名(3).mp3 ...
        if dest.exists():
            stem = mp3_path.stem
            suffix = mp3_path.suffix
            i = 2
            while dest.exists():
                dest = import_dir / f"{stem}({i}){suffix}"
                i += 1
        try:
            # os.replace: 同盘原子移动，跨盘自动复制+删除，不额外占内存
            os.replace(str(mp3_path), str(dest))
            self.log.info(f"[{label}] 导入: {mp3_path.name} → {dest.name}")
        except Exception as e:
            self.log.error(f"[{label}] 导入失败: {mp3_path.name} — {e}")


# ──────────────────────────────────────────────
#  设置窗口（多目录列表）
# ──────────────────────────────────────────────

class SettingsDialog:
    def __init__(self, cfg: dict, on_save=None):
        self.cfg = cfg
        self.on_save = on_save
        self.result = None
        self._build()

    def _build(self):
        self.win = tk.Tk()
        self.win.title("NCM Auto Converter — 设置")
        self.win.geometry("560x640")
        self.win.resizable(False, False)
        self.win.configure(bg="#1a1a2e")

        ico_path = Path(__file__).parent / "app.ico"
        if ico_path.exists():
            self.win.iconbitmap(str(ico_path))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#1a1a2e", foreground="#e0e0e0", fieldbackground="#16213e")
        style.configure("TLabel", background="#1a1a2e", foreground="#e0e0e0", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#00d2ff")
        style.configure("Status.TLabel", font=("Segoe UI", 9), foreground="#888")

        pad = {"padx": 16, "pady": 6}

        ttk.Label(self.win, text="♪ NCM Auto Converter", style="Header.TLabel").pack(pady=(16, 6))

        # ── 目录列表 ──
        frm_dirs = ttk.LabelFrame(self.win, text="监控目录", padding=8)
        frm_dirs.pack(fill="both", expand=True, **pad)

        # Listbox + 滚动条
        list_frame = ttk.Frame(frm_dirs)
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            list_frame, height=6,
            bg="#16213e", fg="#e0e0e0", selectbackground="#2a5298",
            font=("Segoe UI", 9), yscrollcommand=scrollbar.set
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        # 填充已有目录
        for d in self.cfg.get("watch_dirs", []):
            self.listbox.insert(tk.END, d)

        # 按钮行
        btn_frame = ttk.Frame(frm_dirs)
        btn_frame.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_frame, text="＋ 添加目录", command=self._add_dir).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="－ 移除选中", command=self._remove_dir).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="清空", command=self._clear_dirs).pack(side="left", padx=2)

        # 目录计数
        self.lbl_count = ttk.Label(self.win, text="", style="Status.TLabel")
        self.lbl_count.pack()
        self._update_count()

        # ── ncmdump 路径 ──
        frm_nmp = ttk.Frame(self.win)
        frm_nmp.pack(fill="x", **pad)
        ttk.Label(frm_nmp, text="ncmdump：").pack(side="left")
        self.var_nmp = tk.StringVar(value=self.cfg.get("ncmdump_path", ""))
        ttk.Entry(frm_nmp, textvariable=self.var_nmp, width=38).pack(side="left", padx=6)
        ttk.Button(frm_nmp, text="浏览…", command=self._browse_nmp).pack(side="left")
        ttk.Label(self.win, text="留空 = 使用每个目录下的 ncmdump.exe",
                  style="Status.TLabel").pack()

        # ── 参数 ──
        frm_params = ttk.LabelFrame(self.win, text="参数", padding=8)
        frm_params.pack(fill="x", **pad)

        row1 = ttk.Frame(frm_params)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="扫描间隔：").pack(side="left")
        self.var_poll = tk.IntVar(value=self.cfg["poll_interval"])
        ttk.Entry(row1, textvariable=self.var_poll, width=5).pack(side="left", padx=2)
        ttk.Label(row1, text="秒    稳定检测：").pack(side="left")
        self.var_stable = tk.IntVar(value=self.cfg["stable_checks"])
        ttk.Entry(row1, textvariable=self.var_stable, width=5).pack(side="left", padx=2)
        ttk.Label(row1, text="次").pack(side="left")

        row2 = ttk.Frame(frm_params)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="每目录并行数：").pack(side="left")
        self.var_workers = tk.IntVar(value=self.cfg.get("max_workers", 10))
        ttk.Entry(row2, textvariable=self.var_workers, width=5).pack(side="left", padx=2)
        ttk.Label(row2, text="（同时转换的文件数，越大越快）").pack(side="left")

        # ── 选项 ──
        frm_opts = ttk.Frame(self.win)
        frm_opts.pack(fill="x", **pad)
        self.var_lrc = tk.BooleanVar(value=self.cfg.get("delete_lrc", False))
        ttk.Checkbutton(frm_opts, text="自动删除 .lrc 文件", variable=self.var_lrc).pack(side="left")

        # ── 导入目标目录 ──
        frm_import = ttk.LabelFrame(self.win, text="导入（可选）", padding=8)
        frm_import.pack(fill="x", **pad)

        frm_imp_check = ttk.Frame(frm_import)
        frm_imp_check.pack(fill="x")
        self.var_import = tk.BooleanVar(value=self.cfg.get("import_enabled", False))
        ttk.Checkbutton(frm_imp_check, text="转换后自动将 mp3 移动到目标文件夹（已有 mp3 也会移走）",
                        variable=self.var_import).pack(side="left")

        frm_imp_dir = ttk.Frame(frm_import)
        frm_imp_dir.pack(fill="x", pady=(4, 0))
        ttk.Label(frm_imp_dir, text="目标：").pack(side="left")
        self.var_import_dir = tk.StringVar(value=self.cfg.get("import_dir", ""))
        ttk.Entry(frm_imp_dir, textvariable=self.var_import_dir, width=35).pack(side="left", padx=4)
        ttk.Button(frm_imp_dir, text="浏览…", command=self._browse_import).pack(side="left")

        # ── 底部按钮 ──
        frm_btn = ttk.Frame(self.win)
        frm_btn.pack(pady=(10, 16))
        ttk.Button(frm_btn, text="保存并开始监控", command=self._save).pack(side="left", padx=8)
        ttk.Button(frm_btn, text="取消", command=self.win.destroy).pack(side="left", padx=8)

        # 居中
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        x = (self.win.winfo_screenwidth() - w) // 2
        y = (self.win.winfo_screenheight() - h) // 2
        self.win.geometry(f"+{x}+{y}")

    def _update_count(self):
        count = self.listbox.size()
        self.lbl_count.config(text=f"共 {count} 个目录" + ("（首次使用请添加目录）" if count == 0 else ""))

    def _add_dir(self):
        d = filedialog.askdirectory(title="选择下载目录")
        if not d:
            return
        # 去重
        existing = [self.listbox.get(i) for i in range(self.listbox.size())]
        if d in existing:
            messagebox.showinfo("提示", "该目录已在列表中")
            return
        self.listbox.insert(tk.END, d)
        self._update_count()

    def _remove_dir(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.listbox.delete(sel[0])
        self._update_count()

    def _clear_dirs(self):
        if self.listbox.size() == 0:
            return
        if messagebox.askyesno("确认", "清空所有监控目录？"):
            self.listbox.delete(0, tk.END)
            self._update_count()

    def _browse_nmp(self):
        f = filedialog.askopenfilename(
            title="选择 ncmdump.exe",
            filetypes=[("ncmdump", "ncmdump.exe"), ("所有文件", "*.*")],
        )
        if f:
            self.var_nmp.set(f)

    def _browse_import(self):
        d = filedialog.askdirectory(title="选择 mp3 导入目标文件夹")
        if d:
            self.var_import_dir.set(d)

    def _save(self):
        dirs = [self.listbox.get(i) for i in range(self.listbox.size())]
        if not dirs:
            messagebox.showwarning("提示", "请至少添加一个监控目录")
            return
        # 验证目录存在
        for d in dirs:
            if not Path(d).exists():
                messagebox.showerror("错误", f"目录不存在：{d}")
                return

        self.cfg["watch_dirs"] = dirs
        self.cfg["ncmdump_path"] = self.var_nmp.get().strip()
        self.cfg["poll_interval"] = max(1, self.var_poll.get())
        self.cfg["stable_checks"] = max(1, self.var_stable.get())
        self.cfg["max_workers"] = max(1, min(50, self.var_workers.get()))
        self.cfg["delete_lrc"] = self.var_lrc.get()
        self.cfg["import_enabled"] = self.var_import.get()
        self.cfg["import_dir"] = self.var_import_dir.get().strip()

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
    def __init__(self):
        self.cfg = config.load()
        self.log = self._setup_logging()
        self.converter = None
        self.icon = None
        self._status = "就绪"

    def _setup_logging(self) -> logging.Logger:
        log = logging.getLogger("ncm_tray")
        log.setLevel(logging.INFO)
        # 清除旧 handler
        log.handlers.clear()
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
        # 打开设置窗口不再停止监控；只有保存新配置时才重启监控。
        # 否则用户点“取消”会导致后台转换器被停掉，看起来像“打不开/没运行”。
        dlg = SettingsDialog(self.cfg, on_save=self._on_config_saved)
        dlg.show()

    def _on_config_saved(self, new_cfg: dict):
        if self.converter and self.converter.running:
            self.converter.stop()
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
        self.converter = NCMConverter(self.cfg, self.log, on_status=self._update_status)
        self.converter.start()

    def _watch_signal(self):
        while True:
            time.sleep(1)
            if SIGNAL_FILE.exists():
                try:
                    SIGNAL_FILE.unlink()
                except OSError:
                    pass
                self._on_settings()

    def run(self):
        dirs = self.cfg.get("watch_dirs", [])
        if not dirs:
            self.log.info("首次运行，打开设置向导")
            dlg = SettingsDialog(self.cfg, on_save=self._on_config_saved)
            dlg.show()
            if not self.cfg.get("watch_dirs"):
                sys.exit(0)
        else:
            self._start_converter()
            # 手动双击启动时不要只躲进托盘；主动弹设置窗口，让用户确认程序已打开。
            threading.Thread(target=self._show_settings, daemon=True).start()

        threading.Thread(target=self._watch_signal, daemon=True).start()
        self._create_tray_icon()
        self.icon.run()


# ──────────────────────────────────────────────
#  入口
# ──────────────────────────────────────────────

if __name__ == "__main__":
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
