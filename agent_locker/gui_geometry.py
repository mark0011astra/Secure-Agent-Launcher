from __future__ import annotations

def recenter_position_if_offscreen(
    *,
    screen_w: int,
    screen_h: int,
    win_w: int,
    win_h: int,
    pos_x: int,
    pos_y: int,
    desktop_x: int = 0,
    desktop_y: int = 0,
    min_visible_w: int = 120,
    min_visible_h: int = 80,
) -> tuple[int, int] | None:
    if screen_w <= 0 or screen_h <= 0 or win_w <= 0 or win_h <= 0:
        return None
    right = desktop_x + screen_w
    bottom = desktop_y + screen_h
    visible_w = max(0, min(pos_x + win_w, right) - max(pos_x, desktop_x))
    visible_h = max(0, min(pos_y + win_h, bottom) - max(pos_y, desktop_y))
    if visible_w >= min_visible_w and visible_h >= min_visible_h:
        return None
    center_x = desktop_x + max((screen_w - win_w) // 2, 0)
    center_y = desktop_y + max((screen_h - win_h) // 2, 0)
    return (center_x, center_y)


def resolve_min_window_size(
    *,
    base_min_w: int,
    base_min_h: int,
    req_w: int,
    req_h: int,
    screen_w: int,
    screen_h: int,
    padding: int = 0,
    screen_limit_ratio: float = 0.98,
) -> tuple[int, int]:
    need_w = max(base_min_w, req_w + padding)
    need_h = max(base_min_h, req_h + padding)
    if screen_w <= 0 or screen_h <= 0:
        return (need_w, need_h)
    max_w = max(1, int(screen_w * screen_limit_ratio))
    max_h = max(1, int(screen_h * screen_limit_ratio))
    return (min(need_w, max_w), min(need_h, max_h))
