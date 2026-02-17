"""Passability computation for map tiles."""

from __future__ import annotations

def compute_passability(map_data, flags):
    """计算地图每个格子的通行度 (基于 RPG Maker MV 逻辑)"""
    w = map_data.get("width", 0)
    h = map_data.get("height", 0)
    data = map_data.get("data", [])
    if not w or not h or not data:
        return []
    layer_size = w * h
    # 结果: 0=不可通行, 1=可通行
    result = []
    for y in range(h):
        for x in range(w):
            passable = False
            for bit in [0x01, 0x02, 0x04, 0x08]:
                if _check_passage(data, flags, x, y, w, h, layer_size, bit):
                    passable = True
                    break
            result.append(1 if passable else 0)
    return result


def _check_passage(data, flags, x, y, w, h, layer_size, bit):
    """模拟 RPG Maker MV 的 Game_Map.checkPassage"""
    for z in range(3, -1, -1):
        idx = z * layer_size + y * w + x
        if idx >= len(data):
            continue
        tile_id = data[idx]
        if tile_id == 0:
            continue
        if tile_id >= len(flags):
            continue
        flag = flags[tile_id]
        if (flag & 0x10) != 0:  # star: 通行，继续检查下层
            continue
        if (flag & bit) == 0:   # 该方向可通行
            return True
        if (flag & bit) == bit: # 该方向不可通行
            return False
    return False
