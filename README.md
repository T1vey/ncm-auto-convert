# NCM Auto Converter

网易云音乐 NCM → MP3 自动转换守护。**系统托盘应用**，下载完一首自动转、自动删，全程无需手动操作。

## 核心特性

- **系统托盘常驻** — 通知区小图标，不占任务栏，不弹黑框
- **首次启动弹窗设置** — 选择下载目录即可，参数有默认值
- **安全转换** — 文件大小稳定检测 + 文件锁检测，不会转换"下了一半"的文件
- **自动清理** — 转换成功后自动删除 `.ncm`，已有 `.mp3` 的残留也会清理
- **低占用** — 内存 ~30 MB，CPU 接近 0

## 截图

```
  ┌─────────────────────────────────────┐
  │  ♪ NCM Auto Converter — 设置        │
  │                                     │
  │  监控目录：[D:\Music\Download    ] [浏览…] │
  │  ncmdump： [D:\Music\ncmdump.exe ] [浏览…] │
  │                                     │
  │  ┌─ 参数 ─────────────────────────┐ │
  │  │ 扫描间隔：[5]秒   稳定检测：[3]次  │ │
  │  │ 检测间隔：[5]秒   转换超时：[120]秒│ │
  │  └────────────────────────────────┘ │
  │                                     │
  │      [ 保存并开始监控 ]  [ 取消 ]     │
  └─────────────────────────────────────┘

  系统托盘（右下角）：
    ┌─────────────────────────┐
    │ 状态: 监控中             │
    │ ─────────────────────── │
    │ 打开设置                 │
    │ 打开日志                 │
    │ ─────────────────────── │
    │ 退出                     │
    └─────────────────────────┘
```

## 快速开始

### 1. 安装

```bash
# 克隆仓库
git clone https://github.com/T1vey/ncm-auto-convert.git
cd ncm-auto-convert

# 安装依赖
pip install -r requirements.txt
```

### 2. 准备 ncmdump

从 [ncmdump Releases](https://github.com/anonymous5l/ncmdump/releases) 下载 `ncmdump.exe`，放到你的网易云下载目录下。

### 3. 运行

```bash
python tray_app.py
```

首次启动会弹出设置窗口，选择你的网易云下载目录，点击「保存并开始监控」。

之后应用最小化到系统托盘，自动监控、转换、清理。

### 4. 开机自启（可选）

```bash
# 方式 1：运行安装脚本
install_startup.bat

# 方式 2：手动
# 把 tray_app.py 的快捷方式放到 shell:startup 文件夹
```

## 命令行模式

如果不需要 GUI，也可以直接用命令行版：

```bash
# 持续监控
python ncm_auto_convert.py -d "D:\Music\Download"

# 只处理现有文件
python ncm_auto_convert.py --once

# 自定义参数
python ncm_auto_convert.py --poll 10 --stable 5 -v
```

### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-d, --dir` | 脚本所在目录 | 监控目录路径 |
| `--ncmdump` | 目录下 ncmdump.exe | ncmdump 路径 |
| `--once` | - | 只处理现有文件，不持续监控 |
| `--poll` | 5 | 扫描间隔（秒） |
| `--stable` | 3 | 连续稳定次数 |
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
       ▼
  文件大小稳定？（连续 N 次采样不变 + 未被锁定）
       │                    │
      否                   是
       │                    │
       ▼                    ▼
  等待下一轮          ncmdump 转换
                            │
                            ▼
                    mp3 存在且 > 0？
                        │        │
                       是       否 → 保留 ncm，日志报错
                        │
                        ▼
                    删除 .ncm ✓
```

## 项目结构

```
ncm-auto-convert/
├── tray_app.py           # 系统托盘应用（主入口）
├── ncm_auto_convert.py   # 核心转换逻辑（可独立使用）
├── config.py             # 配置管理
├── icon.py               # 托盘图标生成
├── requirements.txt      # Python 依赖
├── install_startup.bat   # 开机自启安装
├── uninstall_startup.bat # 开机自启卸载
├── LICENSE               # MIT
└── README.md
```

## 配置文件

配置保存在 `%LOCALAPPDATA%/NCM-AutoConvert/config.json`：

```json
{
  "watch_dir": "D:\\Music\\Download",
  "ncmdump_path": "",
  "poll_interval": 5,
  "stable_checks": 3,
  "stable_interval": 5,
  "convert_timeout": 120
}
```

## 常见问题

**Q: 会不会转换到一半下载的文件？**
A: 不会。脚本会连续采样文件大小（默认 3 次 × 5 秒 = 至少 15 秒无变化），还会检测文件是否被其他程序占用。

**Q: ncmdump 在哪下载？**
A: https://github.com/anonymous5l/ncmdump/releases

**Q: 内存 / CPU 占用多少？**
A: 约 30 MB 内存，CPU 接近 0。

**Q: 怎么完全退出？**
A: 右键托盘图标 → 退出。或在任务管理器中结束 python 进程。

**Q: 可以不用 GUI 只用命令行吗？**
A: 可以，直接 `python ncm_auto_convert.py -d 目录`。

## License

MIT
