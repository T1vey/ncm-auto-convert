"""程序图标 — 代码生成，不依赖外部资源文件"""

from PIL import Image, ImageDraw


def create_tray_icon(size: int = 64, active: bool = True) -> Image.Image:
    """
    生成系统托盘图标：亮色音符 + 状态指示点
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    s = size / 64

    # 背景圆（深蓝但不至于和系统托盘背景融为一体）
    r = int(28 * s)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(40, 60, 120, 255))
    # 内圈高光
    r2 = int(25 * s)
    draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=(50, 75, 150, 255))

    # 音符 — 纯白色，够亮够清晰
    note_color = (255, 255, 255, 255)

    # 音符圆（左下）
    nr = int(9 * s)
    nx, ny = cx - int(3 * s), cy + int(9 * s)
    draw.ellipse([nx - nr, ny - nr, nx + nr, ny + nr], fill=note_color)

    # 竖线
    lx = nx + nr - int(2 * s)
    draw.rectangle([lx, cy - int(14 * s), lx + int(3.5 * s), ny], fill=note_color)

    # 旗（两个横条）
    tx = lx + int(3.5 * s)
    draw.rectangle([tx, cy - int(14 * s), tx + int(11 * s), cy - int(10 * s)], fill=note_color)
    draw.rectangle([tx, cy - int(7 * s), tx + int(11 * s), cy - int(3 * s)], fill=note_color)

    # 状态指示点（右下角）
    dot_r = int(6 * s)
    dot_x, dot_y = cx + int(17 * s), cy + int(17 * s)
    # 白色边框让绿点更突出
    draw.ellipse([dot_x - dot_r - int(1*s), dot_y - dot_r - int(1*s),
                  dot_x + dot_r + int(1*s), dot_y + dot_r + int(1*s)], fill=(255, 255, 255, 200))
    dot_color = (80, 230, 120, 255) if active else (160, 160, 170, 255)
    draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=dot_color)

    return img


def create_app_icon(size: int = 256) -> Image.Image:
    """
    生成应用图标（桌面快捷方式 / 窗口标题栏用）
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    s = size / 128

    # 背景：深蓝紫渐变
    pad = int(6 * s)
    r = int(20 * s)
    for y in range(size):
        t = y / size
        c = int(35 + t * 20), int(50 + t * 15), int(100 + t * 30)
        draw.rectangle([0, y, size, y + 1], fill=(*c, 255))

    # 圆角遮罩
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [pad, pad, size - pad, size - pad], radius=r, fill=255
    )
    img.putalpha(mask)
    draw = ImageDraw.Draw(img)

    # 发光效果
    glow_r = int(35 * s)
    for i in range(glow_r, 0, -1):
        alpha = int(50 * (1 - i / glow_r))
        draw.ellipse(
            [cx - int(10 * s) - i, cy - i, cx - int(10 * s) + i, cy + i],
            fill=(120, 180, 255, alpha),
        )

    # 音符 — 纯白
    note_color = (255, 255, 255, 255)
    nr = int(14 * s)
    nx, ny = cx - int(2 * s), cy + int(12 * s)
    draw.ellipse([nx - nr, ny - nr, nx + nr, ny + int(2 * s)], fill=note_color)
    lx = nx + nr - int(3 * s)
    draw.rectangle([lx, cy - int(20 * s), lx + int(5 * s), ny - int(2 * s)], fill=note_color)
    tx = lx + int(5 * s)
    for yoff, h in [(-20, -13), (-11, -4)]:
        y1, y2 = int(cy + yoff * s), int(cy + h * s)
        draw.rectangle([tx, y1, tx + int(16 * s), y2], fill=note_color)
        draw.ellipse([tx + int(12 * s), y1 - int(1 * s), tx + int(18 * s), y2 + int(1 * s)], fill=note_color)

    # 转换箭头 — 亮绿
    arr_color = (100, 240, 160, 255)
    y = cy + int(2 * s)
    x1, x2 = cx + int(8 * s), cx + int(24 * s)
    draw.rectangle([x1, y - int(3 * s), x2, y + int(3 * s)], fill=arr_color)
    draw.polygon([
        (x2 + int(2 * s), y - int(9 * s)),
        (x2 + int(11 * s), y),
        (x2 + int(2 * s), y + int(9 * s)),
    ], fill=arr_color)

    # MP3 标记
    bx, by = cx + int(16 * s), cy + int(16 * s)
    br = int(12 * s)
    draw.ellipse([bx - br, by - br, bx + br, by + br], fill=(60, 200, 100, 255))
    for dx in [-6, 0, 6]:
        xx = bx + int(dx * s) - int(2 * s)
        draw.rectangle([xx, by - int(6 * s), xx + int(3.5 * s), by + int(6 * s)], fill=(255, 255, 255, 255))

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
