"""
将已拆分的 sprite 按内容命名后重新输出到最终目录
"""
import shutil
import json
from pathlib import Path

src_dir = Path(r"C:\Users\san\Desktop\素材\output\sprites")
dst_dir = Path(r"C:\Users\san\Desktop\素材\output\named_sprites")
dst_dir.mkdir(parents=True, exist_ok=True)

# 按 sprite 编号 → 描述性名称映射
# 过滤掉噪点: 3(隔板碎片), 6(隔板碎片), 22(噪点), 32(噪点)
NAME_MAP = {
    1:  "desk_cubicle_01",
    2:  "desk_cubicle_02",
    # 3: 过滤 - 隔板窄条
    4:  "desk_cubicle_03",
    5:  "desk_cubicle_04",
    # 6: 过滤 - 隔板窄条
    7:  "desk_cubicle_05",
    8:  "desk_cubicle_06",
    9:  "office_chair_01",
    10: "office_chair_02",
    11: "office_chair_03",
    12: "office_chair_04",
    13: "office_chair_05",
    14: "office_chair_06",
    15: "projection_screen",
    16: "sofa",
    17: "supply_desk",
    18: "bookshelf_large",
    19: "bookshelf_small",
    20: "printer",
    21: "copier",
    # 22: 过滤 - 噪点碎片
    23: "pc_tower",
    24: "whiteboard",
    25: "chart_board",
    26: "bulletin_board",
    27: "water_dispenser",
    28: "desk_lamp",
    29: "cactus_pot",
    30: "vending_machine",
    31: "small_monitor",
    # 32: 过滤 - 噪点碎片
    33: "reception_desk",
    34: "storage_cabinet",
    35: "filing_cabinet",
    36: "supply_crate",
    37: "paper_shredder",
    38: "potted_plant_round",
    39: "potted_fern",
    40: "bush_large",
    41: "bush_small",
}

manifest = []
order = 0

for idx, name in sorted(NAME_MAP.items()):
    order += 1
    src_file = src_dir / f"sprite_{idx:03d}.png"
    dst_file = dst_dir / f"{name}.png"
    
    if not src_file.exists():
        print(f"  [WARN] {src_file} not found, skipping")
        continue
    
    shutil.copy2(str(src_file), str(dst_file))
    
    manifest.append({
        "order": order,
        "original_index": idx,
        "name": name,
        "filename": f"{name}.png",
    })
    print(f"  [{order:02d}] sprite_{idx:03d}.png -> {name}.png")

# 保存 manifest
manifest_path = dst_dir / "sprites_manifest.json"
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print(f"\n完成！共输出 {len(manifest)} 个命名素材")
print(f"输出目录: {dst_dir}")
print(f"Manifest: {manifest_path}")
