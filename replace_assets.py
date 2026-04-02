"""
将新像素素材缩放到与旧素材完全匹配的尺寸，替换到 frontend/public/objs/
使用 NEAREST 插值保持像素风格，在目标尺寸内保持宽高比并居中。
"""
from PIL import Image
from pathlib import Path
import shutil

SRC_DIR = Path(r"C:\Users\san\Desktop\素材\output\named_sprites")
DST_DIR = Path(r"D:\project\hotclaw\frontend\public\objs")
BACKUP_DIR = Path(r"D:\project\hotclaw\frontend\public\objs_backup")

# 替换映射: 旧文件名 → (新素材名, 旧尺寸 WxH)
REPLACE_MAP = {
    "obj_desk.png":      ("desk_cubicle_01.png",    (48, 48)),
    "obj_chair.png":     ("office_chair_01.png",    (32, 32)),
    "obj_bookshelf.png": ("bookshelf_small.png",    (32, 48)),
    "obj_plant.png":     ("potted_plant_round.png", (24, 32)),
    "obj_vending.png":   ("vending_machine.png",    (32, 48)),
    "obj_couch.png":     ("sofa.png",               (64, 32)),
    "obj_lamp.png":      ("desk_lamp.png",          (16, 24)),
    "obj_window.png":    ("projection_screen.png",  (48, 32)),
    # obj_rug.png 保持不变（无对应新素材）
}


def resize_fit_center(src_img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    将 src_img 缩放到 target_w x target_h 内（保持宽高比），
    然后居中放置在透明背景上。使用 NEAREST 插值。
    """
    # 计算缩放比例
    src_w, src_h = src_img.size
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))

    # NEAREST 缩放
    resized = src_img.resize((new_w, new_h), Image.NEAREST)

    # 创建透明画布并居中
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))

    return canvas


def main():
    # 备份旧素材
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for f in DST_DIR.glob("*.png"):
        backup_path = BACKUP_DIR / f.name
        if not backup_path.exists():
            shutil.copy2(str(f), str(backup_path))
            print(f"  备份: {f.name}")

    print()
    print("=== 开始替换素材 ===")

    for old_name, (new_name, (tw, th)) in REPLACE_MAP.items():
        src_path = SRC_DIR / new_name
        dst_path = DST_DIR / old_name

        if not src_path.exists():
            print(f"  [WARN] 新素材不存在: {new_name}")
            continue

        src_img = Image.open(src_path).convert("RGBA")
        result = resize_fit_center(src_img, tw, th)
        result.save(str(dst_path))
        print(f"  {old_name}: {new_name} ({src_img.size[0]}x{src_img.size[1]}) -> {tw}x{th}")

    # 验证
    print()
    print("=== 替换后素材验证 ===")
    for f in sorted(DST_DIR.glob("*.png")):
        img = Image.open(f)
        print(f"  {f.name}: {img.size[0]}x{img.size[1]}")

    print()
    print("完成！旧素材已备份到:", BACKUP_DIR)


if __name__ == "__main__":
    main()
