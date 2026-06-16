# NCM Auto Converter

网易云音乐 NCM → MP3 自动转换守护。系统托盘常驻，下载完自动转、自动删。

## 特性

- 多目录同时监控，每目录 10 路并行转换
- 文件大小稳定检测，不会损坏下载中的文件
- 转换后自动删除 `.ncm`
- 可选：自动删除 `.lrc` 文件
- 可选：转换后将 mp3 移动到指定文件夹
- 系统托盘常驻，无窗口，内存 ~5 MB

## 安装

```bash
git clone https://github.com/T1vey/ncm-auto-convert.git
cd ncm-auto-convert
pip install -r requirements.txt
```

从 [ncmdump Releases](https://github.com/anonymous5l/ncmdump/releases) 下载 `ncmdump.exe`，放到监控目录下。

## 使用

```bash
python tray_app.py
```

首次启动弹出设置窗口，添加目录，保存即可。之后最小化到托盘自动运行。

双击桌面快捷方式可随时打开设置修改参数。

## 命令行模式

```bash
python ncm_auto_convert.py -d "D:\Music\Download"
python ncm_auto_convert.py --once
```

## License

MIT
