"""
像素风办公室家具素材图拆分脚本
- 自动识别背景色
- 连通域分析提取每个独立家具
- 输出透明背景 PNG
- 按从上到下、从左到右排序编号
"""

import sys
import json
import numpy as np
import cv2
from pathlib import Path
from PIL import Image


def sample_background_color(img_array: np.ndarray, corner: str = "tl") -> tuple:
    """从图片角点采样背景色"""
    h, w = img_array.shape[:2]
    # 采样 5x5 区域取众数
    regions = {
        "tl": img_array[0:5, 0:5],
        "tr": img_array[0:5, w-5:w],
        "bl": img_array[h-5:h, 0:5],
        "br": img_array[h-5:h, w-5:w],
    }
    region = regions.get(corner, regions["tl"])
    pixels = region.reshape(-1, region.shape[-1])
    # 取出现最多的颜色
    unique, counts = np.unique(pixels, axis=0, return_counts=True)
    bg_color = tuple(unique[np.argmax(counts)])
    return bg_color


def create_foreground_mask(img_array: np.ndarray, bg_color: tuple, tolerance: int = 30) -> np.ndarray:
    """创建前景 mask（非背景区域为 255）"""
    # 只比较 RGB 通道
    if img_array.shape[2] == 4:
        rgb = img_array[:, :, :3]
    else:
        rgb = img_array

    bg = np.array(bg_color[:3], dtype=np.float32)
    diff = np.sqrt(np.sum((rgb.astype(np.float32) - bg) ** 2, axis=2))
    mask = (diff > tolerance).astype(np.uint8) * 255
    return mask


def extract_components(mask: np.ndarray, min_area: int = 50):
    """连通域分析，返回 bbox 列表"""
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    components = []
    for i in range(1, num_labels):  # 跳过背景 label 0
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            components.append({
                "bbox": [int(x), int(y), int(x + w), int(y + h)],
                "area": int(area),
                "centroid": [float(centroids[i][0]), float(centroids[i][1])],
            })
    return components


def sort_bboxes_row_major(components: list, merge_threshold: int = 20) -> list:
    """按行优先排序：先按 y 分行，同行按 x 排序"""
    if not components:
        return []
    
    # 按 y_min 排序
    sorted_comps = sorted(components, key=lambda c: c["bbox"][1])
    
    rows = []
    current_row = [sorted_comps[0]]
    current_y = sorted_comps[0]["bbox"][1]
    
    for comp in sorted_comps[1:]:
        y = comp["bbox"][1]
        if abs(y - current_y) <= merge_threshold:
            current_row.append(comp)
        else:
            rows.append(current_row)
            current_row = [comp]
            current_y = y
    rows.append(current_row)
    
    # 每行内按 x 排序
    result = []
    for row in rows:
        row_sorted = sorted(row, key=lambda c: c["bbox"][0])
        result.extend(row_sorted)
    
    return result


def crop_sprite_rgba(img_pil: Image.Image, bbox: list, bg_color: tuple, tolerance: int = 30, padding: int = 1) -> Image.Image:
    """裁剪单个 sprite 并将背景设为透明"""
    x_min, y_min, x_max, y_max = bbox
    # 添加 padding
    w, h = img_pil.size
    x_min = max(0, x_min - padding)
    y_min = max(0, y_min - padding)
    x_max = min(w, x_max + padding)
    y_max = min(h, y_max + padding)
    
    crop = img_pil.crop((x_min, y_min, x_max, y_max))
    crop = crop.convert("RGBA")
    
    pixels = np.array(crop)
    rgb = pixels[:, :, :3].astype(np.float32)
    bg = np.array(bg_color[:3], dtype=np.float32)
    diff = np.sqrt(np.sum((rgb - bg) ** 2, axis=2))
    
    # 背景区域设为透明
    bg_mask = diff <= tolerance
    pixels[bg_mask, 3] = 0
    
    return Image.fromarray(pixels)


def main():
    input_path = Path(r"C:\Users\san\Desktop\素材\5c744dea-379f-4658-a269-e4a592d16f67.png")
    output_dir = Path(r"C:\Users\san\Desktop\素材\output")
    sprites_dir = output_dir / "sprites"
    debug_dir = output_dir / "debug"
    
    sprites_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    # 读取图片
    img_pil = Image.open(input_path).convert("RGBA")
    img_array = np.array(img_pil)
    
    print(f"输入图片: {input_path}")
    print(f"图片尺寸: {img_pil.size}")
    
    # 采样背景色
    bg_color = sample_background_color(img_array, corner="tl")
    print(f"背景色 (RGBA): {bg_color}")
    
    # 创建前景 mask
    tolerance = 30
    mask = create_foreground_mask(img_array, bg_color, tolerance=tolerance)
    print(f"前景像素数: {np.sum(mask > 0)}")
    
    # 保存 mask 调试图
    cv2.imwrite(str(debug_dir / "mask.png"), mask)
    
    # 形态学操作：膨胀填补家具内小间隙
    kernel = np.ones((3, 3), np.uint8)
    mask_dilated = cv2.dilate(mask, kernel, iterations=2)
    # 连通域分析在膨胀后的 mask 上做，但裁剪用原 mask
    
    cv2.imwrite(str(debug_dir / "mask_dilated.png"), mask_dilated)
    
    # 提取连通域
    components = extract_components(mask_dilated, min_area=100)
    print(f"检测到连通域: {len(components)} 个")
    
    # 排序
    sorted_components = sort_bboxes_row_major(components, merge_threshold=25)
    
    # 保存调试图 - 标注 bbox
    debug_img = img_array.copy()
    for i, comp in enumerate(sorted_components):
        x_min, y_min, x_max, y_max = comp["bbox"]
        cv2.rectangle(debug_img, (x_min, y_min), (x_max, y_max), (255, 0, 0, 255), 1)
        cv2.putText(debug_img, str(i + 1), (x_min, y_min - 3), 
                     cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 0, 255), 1)
    
    debug_pil = Image.fromarray(debug_img)
    debug_pil.save(str(debug_dir / "labeled_boxes.png"))
    
    # 裁剪并保存每个 sprite
    manifest = []
    for i, comp in enumerate(sorted_components):
        sprite = crop_sprite_rgba(img_pil, comp["bbox"], bg_color, tolerance=tolerance, padding=1)
        filename = f"sprite_{i+1:03d}.png"
        sprite.save(str(sprites_dir / filename))
        
        x_min, y_min, x_max, y_max = comp["bbox"]
        manifest.append({
            "id": i + 1,
            "filename": filename,
            "x": x_min,
            "y": y_min,
            "width": x_max - x_min,
            "height": y_max - y_min,
            "bbox": comp["bbox"],
            "area": comp["area"],
        })
        print(f"  [{i+1:03d}] {filename}  bbox={comp['bbox']}  size={x_max-x_min}x{y_max-y_min}")
    
    # 保存 manifest
    with open(output_dir / "sprites_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成！共拆分 {len(manifest)} 个 sprite")
    print(f"输出目录: {output_dir}")


if __name__ == "__main__":
    main()
