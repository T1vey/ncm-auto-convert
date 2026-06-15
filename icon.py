"""程序图标 — 代码生成，不依赖外部资源文件"""

from PIL import Image, ImageDraw


def create_icon(size: int = 64, active: bool = True) -> Image.Image:
    """
    生成托盘图标：深色底 + 音符 + 状态指示
    
    active=True:  绿色箭头 — 正在监控
    active=False: 灰色圆点 — 已暂停
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx, cy = size // 2, size // 2
    s = size / 64  # 缩放因子

    # 背景圆（深色）
    r = int(28 * s)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 30, 40, 230))

    # 音符 ♪ — 圆形 + 竖线 + 横线
    note_color = (220, 220, 230, 255)
    
    # 音符圆（左下）
    nr = int(8 * s)
    nx, ny = cx - int(4 * s), cy + int(8 * s)
    draw.ellipse([nx - nr, ny - nr, nx + nr, ny + nr], fill=note_color)
    
    # 竖线
    lx = nx + nr - int(2 * s)
    draw.rectangle([lx, cy - int(14 * s), lx + int(3 * s), ny], fill=note_color)
    
    # 横线（旗）
    tx = lx + int(3 * s)
    draw.rectangle([tx, cy - int(14 * s), tx + int(10 * s), cy - int(11 * s)], fill=note_color)
    draw.rectangle([tx, cy - int(8 * s), tx + int(10 * s), cy - int(5 * s)], fill=note_color)

    # 状态指示点（右下角）
    dot_r = int(5 * s)
    dot_x, dot_y = cx + int(16 * s), cy + int(16 * s)
    dot_color = (80, 220, 100, 255) if active else (120, 120, 130, 255)
    draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=dot_color)

    return img


def create_icon_bytes(size: int = 64, active: bool = True) -> bytes:
    """返回 ICO 格式的 bytes（用于 Windows 任务栏图标）"""
    import io
    img = create_icon(size, active)
    buf = io.BytesIO()
    img.save(buf, format="ICO")
    return buf.getvalue()
