"""
──────────────────────────────────────────
《Roguelike 肉鸽游戏》— 程序入口
──────────────────────────────────────────
"""
import sys
import os
import traceback
import datetime

# ==========================================
# 全局崩溃日志（写到 EXE 同目录 crash.log）
# ==========================================
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                         "crash.log")

def _log_crash(exc_type, exc_value, exc_tb):
    """未捕获异常 → 写入 crash.log + 弹出报错文件路径。"""
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    msg = "".join(tb_lines)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(f"[{stamp}] CRASH\n{msg}")
    print(f"FATAL ERROR written to {LOG_PATH}", file=sys.stderr)
    input("Press Enter to exit...")

sys.excepthook = _log_crash

# ==========================================
import pygame
from config import (WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
                     FULLSCREEN)
from game import GameEngine


def create_screen(fullscreen: bool = FULLSCREEN) -> pygame.Surface:
    flags = pygame.SCALED
    if fullscreen:
        flags |= pygame.FULLSCREEN
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), flags)
    pygame.display.set_caption(WINDOW_TITLE)
    return screen


def main():
    pygame.init()
    pygame.mixer.init(frequency=22050, size=-16, channels=8, buffer=1024)
    screen = create_screen(FULLSCREEN)
    clock = pygame.time.Clock()

    from src.bgm_engine import init_bgm
    from src.sfx_engine import init_sfx
    init_bgm()
    init_sfx()

    engine = GameEngine(screen, clock)
    engine.run()
    pygame.quit()


if __name__ == "__main__":
    main()
