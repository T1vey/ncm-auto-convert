# NCM Auto Converter

网易云音乐 NCM → MP3 自动转换守护。下载完一首自动转、自动删，全程无需手动操作。

## 核心特性

- **安全转换** — 文件大小稳定检测 + 文件锁检测，不会转换"下了一半"的文件
- **自动清理** — 转换成功后自动删除 `.ncm`，已有 `.mp3` 的残留也会清理
- **零依赖** — 仅需 Python 标准库 + [ncmdump](https://github.com/anonymous5l/ncmdump)
- **低占用** — 内存 ~5-16 MB，CPU 接近 0
- **开机自启** — 一键配置 Windows 开机静默运行

## 快速开始

### 1. 准备

确保目录结构如下：

```
你的网易云下载目录/
├── ncmdump.exe          ← 从 ncmdump 项目下载
├── ncm_auto_convert.py  ← 本脚本
├── 歌曲A.ncm
├── 歌曲B.ncm
└── ...
```

> **ncmdump 下载**：https://github.com/anonymous5l/ncmdump/releases

### 2. 运行

```bash
# 监控脚本所在目录（最简单）
python ncm_auto_convert.py

# 监控指定目录
python ncm_auto_convert.py -d "D:\Music\Download"

# 只处理现有文件，不持续监控
python ncm_auto_convert.py --once

# 后台静默运行（无窗口）
pythonw ncm_auto_convert.py
```

### 3. Windows 开机自启

双击 `install_startup.bat` 即可。会创建一个隐藏窗口的启动项。

卸载：双击 `uninstall_startup.bat`，或删除 `shell:startup` 中的 `ncm_watcher.vbs`。

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-d, --dir` | 脚本所在目录 | 监控目录路径 |
| `--ncmdump` | 目录下 ncmdump.exe | ncmdump 路径 |
| `--once` | - | 只处理现有文件，不持续监控 |
| `--poll` | 5 | 扫描间隔（秒） |
| `--stable` | 3 | 连续稳定次数（确认下载完成） |
| `--stable-interval` | 5 | 每次稳定检查间隔（秒） |
| `--timeout` | 120 | 单文件转换超时（秒） |
| `-v, --verbose` | - | 详细日志 |

## 安全机制

```
新 .ncm 文件出现
       │
       ▼
  已有对应 .mp3？─── 是 ──→ 直接删除 .ncm
       │
      否
       │
       ▼
  文件大小稳定？（连续 N 次采样不变）
       │                    │
      否                   是
       │                    │
       ▼                    ▼
  等待下一轮         文件未被锁定？
       │                    │
       │                   是
       │                    │
       │                    ▼
       │            ncmdump 转换
       │                    │
       │                    ▼
       │            mp3 存在且 > 0？
       │                │        │
       │               是       否 → 保留 ncm，日志报错
       │                │
       │                ▼
       │            删除 .ncm ✓
       │
       └──→ 继续监控
```

## 日志

运行日志保存在监控目录下的 `ncm_watcher.log`：

```
19:26:28  NCM 自动转换守护已启动
19:26:28    监控目录: D:\Music\Download
19:28:31    等待下载完成... 当前 27,325,597 bytes
19:28:36    稳定检测 1/3: 27,325,597 bytes ✓
19:28:41    稳定检测 2/3: 27,325,597 bytes ✓
19:28:46    稳定检测 3/3: 27,325,597 bytes ✓
19:28:46    开始转换: Boxplot - Human Again.ncm
19:28:46    转换成功: Boxplot - Human Again.mp3 (26.1 MB)
19:28:46    已删除 ncm: Boxplot - Human Again.ncm
```

## 常见问题

**Q: 会不会转换到一半下载的文件？**
A: 不会。脚本会连续采样文件大小（默认 3 次 × 5 秒 = 至少 15 秒无变化），还会检测文件是否被其他程序占用，双重确认下载完成后才转换。

**Q: ncmdump 在哪下载？**
A: https://github.com/anonymous5l/ncmdump/releases — 下载对应系统的版本，重命名为 `ncmdump.exe` 放到下载目录即可。

**Q: 支持批量下载吗？**
A: 支持。网易云批量下载时，脚本会逐个等待每个文件下载完成再转换，不会并发处理。

**Q: 内存 / CPU 占用多少？**
A: 空闲时内存约 5-16 MB，CPU 接近 0（每 5 秒一次文件列表扫描）。

## License

MIT
