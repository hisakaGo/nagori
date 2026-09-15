import math
from kandinsky import fill_rect

# --- 画面・幾何学定数 (240x240px 向け設定) ---
CANVAS_SIZE = 240.0
CENTER = 120.0  # 画面中心 (120, 120)
MAX_RADIUS = 110.0  # 外縁半径 (余白5px確保)

# 色定義 (RGB565相当のタプル)
COLOR_BG = (11, 15, 25)  # 深い背景色 (#0B0F19)
COLOR_SNOW = (224, 247, 250)  # 結晶の白 (#E0F7FA)


def generate_mask(layer, k):
    """結晶生成マスク"""
    max_k = 2 * layer - 2
    ratio = k / max_k if max_k > 0 else 0.0

    is_stem = ratio < 0.25
    is_side_branch = (layer % 10 in (0, 1)) and (ratio < 0.65)
    is_pattern_accent = (k % 4) <= 1

    return 1 if (is_stem or is_side_branch or is_pattern_accent) else 0


def get_triangle_vertices(layer, k):
    """1/12ドメイン内の直角三角形頂点座標算出"""
    delta_r = MAX_RADIUS / 50.0
    r_inner = (layer - 1) * delta_r
    r_outer = layer * delta_r

    angle_step = (math.pi / 6.0) / (2 * layer - 1)
    th_start = k * angle_step
    th_mid = (k + 1) * angle_step
    th_end = (k + 2) * angle_step

    if k % 2 == 0:  # ▲
        pts = [(r_inner, th_mid), (r_outer, th_start), (r_outer, th_end)]
    else:  # ▼
        pts = [(r_inner, th_start), (r_inner, th_end), (r_outer, th_mid)]

    return [(r * math.cos(th), r * math.sin(th)) for r, th in pts]


def draw_filled_triangle(p0, p1, p2, color):
    """
    kandinsky 向けバウンディングボックス（BBox）方式による簡易三角形塗りつぶし
    NumWorks等の低リソース環境でも動作する軽量ラスタライザ
    """
    # 画面座標（中心移動）へ変換
    x0, y0 = int(p0[0] + CENTER), int(p0[1] + CENTER)
    x1, y1 = int(p1[0] + CENTER), int(p1[1] + CENTER)
    x2, y2 = int(p2[0] + CENTER), int(p2[1] + CENTER)

    # 包含矩形（Bounding Box）の算出
    min_x = max(0, min(x0, x1, x2))
    max_x = min(int(CANVAS_SIZE) - 1, max(x0, x1, x2))
    min_y = max(0, min(y0, y1, y2))
    max_y = min(int(CANVAS_SIZE) - 1, max(y0, y1, y2))

    # セルが極小（1px以下）の場合は点描画で高速化
    if min_x == max_x and min_y == max_y:
        fill_rect(min_x, min_y, 1, 1, color)
        return

    # 外積を用いた三角形の内外判定（Barycentric-like test）
    def edge_func(ax, ay, bx, by, cx, cy):
        return (cx - ax) * (by - ay) - (cy - ay) * (bx - ax)

    det = edge_func(x0, y0, x1, y1, x2, y2)
    if det == 0:
        return

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            w0 = edge_func(x1, y1, x2, y2, x, y)
            w1 = edge_func(x2, y2, x0, y0, x, y)
            w2 = edge_func(x0, y0, x1, y1, x, y)

            # すべての重みが同符号なら三角形の内部
            if (det > 0 and w0 >= 0 and w1 >= 0 and w2 >= 0) or (
                det < 0 and w0 <= 0 and w1 <= 0 and w2 <= 0
            ):
                fill_rect(x, y, 1, 1, color)


def render_scc_to_screen(data_bits):
    """240x240画面へ全周結晶コードを直接リアルタイム描画"""
    if len(data_bits) != 2400:
        return

    # 画面全体の背景クリア
    fill_rect(0, 0, int(CANVAS_SIZE), int(CANVAS_SIZE), COLOR_BG)

    # 1. 2,500セルの描画ビット判定
    domain_grid = [0] * 2500
    bit_ptr = 0
    grid_idx = 0

    for layer in range(50, 0, -1):
        num_cells = 2 * layer - 1
        for k in range(num_cells):
            if layer <= 9:
                val = 0
            elif layer == 10:
                val = 1
            else:
                raw_bit = data_bits[bit_ptr]
                mask = generate_mask(layer, k)
                val = raw_bit ^ mask
                bit_ptr += 1

            domain_grid[grid_idx] = val
            grid_idx += 1

    # 2. 万華鏡展開（画面直接ラスタライズ）
    for sector in range(6):
        rad = math.radians(sector * 60.0)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        for mirror in (False, True):
            grid_idx = 0
            for layer in range(50, 0, -1):
                num_cells = 2 * layer - 1
                for k in range(num_cells):
                    if domain_grid[grid_idx] == 1:
                        pts = get_triangle_vertices(layer, k)

                        if mirror:
                            pts = [(x, -y) for x, y in pts]

                        p0 = (
                            pts[0][0] * cos_a - pts[0][1] * sin_a,
                            pts[0][0] * sin_a + pts[0][1] * cos_a,
                        )
                        p1 = (
                            pts[1][0] * cos_a - pts[1][1] * sin_a,
                            pts[1][0] * sin_a + pts[1][1] * cos_a,
                        )
                        p2 = (
                            pts[2][0] * cos_a - pts[2][1] * sin_a,
                            pts[2][0] * sin_a + pts[2][1] * cos_a,
                        )

                        # 画面へ塗りつぶし描画
                        draw_filled_triangle(p0, p1, p2, COLOR_SNOW)

                    grid_idx += 1


# --- デモ実行 ---
demo_bits = [i % 2 for i in range(2400)]  # テストデータ
render_scc_to_screen(demo_bits)
