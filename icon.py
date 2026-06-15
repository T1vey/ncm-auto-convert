"""程序图标 — 代码生成，不依赖外部资源文件"""

from PIL import Image, ImageDraw


def create_tray_icon(size: int = 64, active: bool = True) -> Image.Image:
    """
    生成系统托盘图标：深色底 + 音符 + 状态指示点
    
    active=True:  绿色圆点 — 正在监控
    active=False: 灰色圆点 — 已暂停
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    s = size / 64  # 缩放因子

    # 背景圆（深色）
    r = int(28 * s)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(25, 25, 40, 240))

    # 音符 ♪ — 圆形 + 竖线 + 旗
    note_color = (220, 225, 240, 255)

    # 音符圆（左下）
    nr = int(8 * s)
    nx, ny = cx - int(3 * s), cy + int(8 * s)
    draw.ellipse([nx - nr, ny - nr, nx + nr, ny + nr], fill=note_color)

    # 竖线
    lx = nx + nr - int(2 * s)
    draw.rectangle([lx, cy - int(12 * s), lx + int(3 * s), ny], fill=note_color)

    # 旗（两个横条）
    tx = lx + int(3 * s)
    draw.rectangle([tx, cy - int(12 * s), tx + int(10 * s), cy - int(9 * s)], fill=note_color)
    draw.rectangle([tx, cy - int(6 * s), tx + int(10 * s), cy - int(3 * s)], fill=note_color)

    # 状态指示点（右下角）
    dot_r = int(5 * s)
    dot_x, dot_y = cx + int(16 * s), cy + int(16 * s)
    dot_color = (80, 220, 100, 255) if active else (120, 120, 130, 255)
    draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=dot_color)

    return img


def create_app_icon(size: int = 256) -> Image.Image:
    """
    生成应用图标（桌面快捷方式 / 窗口标题栏用）
    比托盘图标更精致：带渐变背景 + 发光效果 + MP3 标记
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    s = size / 128

    # 深色渐变背景
    pad = int(6 * s)
    r = int(20 * s)
    for y in range(size):
        t = y / size
        c = int(20 + t * 15), int(22 + t * 8), int(45 + t * 20)
        draw.rectangle([0, y, size, y + 1], fill=(*c, 255))

    # 圆角遮罩
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [pad, pad, size - pad, size - pad], radius=r, fill=255
    )
    img.putalpha(mask)
    draw = ImageDraw.Draw(img)

    # 发光效果
    glow_r = int(28 * s)
    for i in range(glow_r, 0, -1):
        alpha = int(30 * (1 - i / glow_r))
        draw.ellipse(
            [cx - int(10 * s) - i, cy - i, cx - int(10 * s) + i, cy + i],
            fill=(100, 200, 255, alpha),
        )

    # 音符
    note_color = (230, 235, 245, 255)
    nr = int(12 * s)
    nx, ny = cx - int(2 * s), cy + int(10 * s)
    draw.ellipse([nx - nr, ny - nr, nx + nr, ny + int(2 * s)], fill=note_color)
    lx = nx + nr - int(3 * s)
    draw.rectangle([lx, cy - int(18 * s), lx + int(4 * s), ny - int(2 * s)], fill=note_color)
    tx = lx + int(4 * s)
    for yoff, h in [(-18, -12), (-10, -4)]:
        y1, y2 = int(cy + yoff * s), int(cy + h * s)
        draw.rectangle([tx, y1, tx + int(14 * s), y2], fill=note_color)
        draw.ellipse([tx + int(10 * s), y1 - int(1 * s), tx + int(16 * s), y2 + int(1 * s)], fill=note_color)

    # 转换箭头
    arr_color = (80, 220, 140, 255)
    y = cy + int(2 * s)
    x1, x2 = cx + int(6 * s), cx + int(20 * s)
    draw.rectangle([x1, y - int(2 * s), x2, y + int(2 * s)], fill=arr_color)
    draw.polygon([
        (x2 + int(1 * s), y - int(7 * s)),
        (x2 + int(9 * s), y),
        (x2 + int(1 * s), y + int(7 * s)),
    ], fill=arr_color)

    # MP3 标记（右下角绿圆）
    bx, by = cx + int(14 * s), cy + int(14 * s)
    br = int(10 * s)
    draw.ellipse([bx - br, by - br, bx + br, by + br], fill=(40, 160, 80, 240))
    for dx in [-5, 0, 5]:
        xx = bx + int(dx * s) - int(1.5 * s)
        draw.rectangle([xx, by - int(5 * s), xx + int(3 * s), by + int(5 * s)], fill=(255, 255, 255, 255))

    return img


def save_app_ico(path: str = "app.ico"):
    """生成并保存多尺寸 .ico 文件"""
    sizes = [16, 32, 48, 64, 128, 256]
    icons = [create_app_icon(s) for s in sizes]
    icons[0].save(
        path, format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=icons[1:],
    )
    return path
