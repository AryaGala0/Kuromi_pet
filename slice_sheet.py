# -*- coding: utf-8 -*-
"""
精灵图切分工具
将 4 行 × 6 列的角色行为表切成 24 张独立 PNG，并把【外部】白色背景转为透明。

切图特性：
  1. Flood Fill 抠图：只去除和边缘连通的白色像素，
     人物内部封闭区域里的白色（脸、身体）会完整保留。
  2. 【人物大小一致】：直接按原图网格 (cell_w × cell_h) 输出，
     不做 trim、不做二次居中，保持原图中人物的相对大小与位置不变。
     桌宠按 pet_size 等比缩放每帧 → 所有状态/帧的人物视觉大小一致。

用法：
  1. 把参考图放到  assets/sheet.png  （或用 --input 指定其它路径）
  2. python slice_sheet.py
  3. 切出来的帧保存在 assets/frames/<state>/frame_{i}.png
"""

import argparse
import sys
from collections import deque
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("[ERR] 缺少 Pillow，请先：pip install pillow")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
DEFAULT_SHEET = BASE_DIR / "assets" / "sheet.png"
OUT_DIR = BASE_DIR / "assets" / "frames"

# 4 行的状态名（与桌宠中的状态对应）
STATE_NAMES = ["1", "2", "3", "4","5","6"]


def remove_outer_white(img: Image.Image, threshold: int = 235) -> Image.Image:
    """从图像四边做 flood fill，只把【和边缘连通的白色】设为透明。
    人物内部封闭的白色区域会被保留。
    """
    img = img.convert("RGBA")
    w, h = img.size
    data = bytearray(img.tobytes())
    visited = bytearray(w * h)

    def idx(x, y):
        return (y * w + x) * 4

    def vidx(x, y):
        return y * w + x

    q = deque()

    # 四条边上的白色像素入队
    for x in range(w):
        for y in (0, h - 1):
            i = idx(x, y)
            if (data[i] >= threshold and data[i + 1] >= threshold
                    and data[i + 2] >= threshold):
                q.append((x, y))
                visited[vidx(x, y)] = 1
    for y in range(h):
        for x in (0, w - 1):
            i = idx(x, y)
            if (data[i] >= threshold and data[i + 1] >= threshold
                    and data[i + 2] >= threshold):
                if not visited[vidx(x, y)]:
                    q.append((x, y))
                    visited[vidx(x, y)] = 1

    # BFS 向四邻域扩散
    while q:
        x, y = q.popleft()
        data[idx(x, y) + 3] = 0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[vidx(nx, ny)]:
                ni = idx(nx, ny)
                if (data[ni] >= threshold and data[ni + 1] >= threshold
                        and data[ni + 2] >= threshold):
                    visited[vidx(nx, ny)] = 1
                    q.append((nx, ny))

    # 反锯齿：边缘浅色像素做半透明，减轻白边
    soft_threshold = max(180, threshold - 40)
    for y in range(h):
        for x in range(w):
            i = idx(x, y)
            if data[i + 3] == 0:
                continue
            r, g, b = data[i], data[i + 1], data[i + 2]
            m = min(r, g, b)
            if m < soft_threshold:
                continue
            has_transparent_neighbor = False
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    if data[idx(nx, ny) + 3] == 0:
                        has_transparent_neighbor = True
                        break
            if has_transparent_neighbor:
                alpha = int((255 - m) * 255 / max(1, 255 - soft_threshold))
                data[i + 3] = max(0, min(255, alpha))

    return Image.frombytes("RGBA", (w, h), bytes(data))


def slice_sheet(sheet_path: Path, rows: int = 6, cols: int = 6,
                threshold: int = 235, square: bool = True):
    if not sheet_path.exists():
        print(f"[ERR] 找不到精灵图：{sheet_path}")
        print("      请把参考图保存为 assets/sheet.png 后重试。")
        sys.exit(1)

    sheet = Image.open(sheet_path).convert("RGBA")
    W, H = sheet.size
    cell_w = W // cols
    cell_h = H // rows
    print(f"[INFO] 原图 {W}x{H}, 每格 {cell_w}x{cell_h}")
    print(f"[INFO] 白底阈值 = {threshold}")

    # 统一画布尺寸：所有帧输出都用同一个 (out_w, out_h)
    # square=True 时取正方形（取宽高最大值），方便桌宠等比加载
    if square:
        side = max(cell_w, cell_h)
        out_w, out_h = side, side
    else:
        out_w, out_h = cell_w, cell_h
    print(f"[INFO] 输出统一画布 = {out_w}x{out_h}（每帧尺寸完全一致）\n")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for r in range(rows):
        state = STATE_NAMES[r] if r < len(STATE_NAMES) else f"state_{r}"
        state_dir = OUT_DIR / state
        state_dir.mkdir(exist_ok=True)
        print(f"[ROW {r}] 状态 = {state}")

        for c in range(cols):
            # 1. 按原网格切出 cell
            box = (c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h)
            cell = sheet.crop(box)
            # 2. 抠掉外部白底
            cell = remove_outer_white(cell, threshold)
            # 3. 取出人物实际包围盒（非透明像素的最小矩形），保证之后居中的是【人物本身】
            bbox = cell.getbbox()
            if bbox is None:
                person = cell  # 整格透明，兜底
            else:
                person = cell.crop(bbox)
            # 4. 贴到统一尺寸的透明画布上，水平 + 垂直都居中
            canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
            offset = ((out_w - person.width) // 2,
                      (out_h - person.height) // 2)
            canvas.paste(person, offset, person)

            out_path = state_dir / f"frame_{c}.png"
            canvas.save(out_path)
            print(f"  -> {out_path.relative_to(BASE_DIR)}  "
                  f"({out_w}x{out_h}, 人物 {person.width}x{person.height})")

    print(f"\n[OK] 切分完成！共 {rows * cols} 帧，统一尺寸 {out_w}x{out_h}")
    print(f"     保存在 {OUT_DIR}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", "-i", default=str(DEFAULT_SHEET),
                   help="精灵图路径（默认 assets/sheet.png）")
    p.add_argument("--rows", type=int, default=6)
    p.add_argument("--cols", type=int, default=6)
    p.add_argument("--threshold", type=int, default=200,
                   help="白底阈值，越大保留越多浅色（默认 235）")
    p.add_argument("--no-square", action="store_true",
                   help="输出按原始 cell 长宽比（默认输出为正方形）")
    args = p.parse_args()
    slice_sheet(Path(args.input), args.rows, args.cols,
                args.threshold, square=not args.no_square)


if __name__ == "__main__":
    main()
