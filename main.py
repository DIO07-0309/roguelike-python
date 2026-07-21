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
    from src.systems.buff_system import load_buff_defs
    init_bgm()
    init_sfx()
    print("[Init] Loading data files...")
    # G5 sync: load all JSON modules
    load_buff_defs("resources/buffs.json")
    from src.systems.relic_system import load_relic_defs
    load_relic_defs("resources/relics.json")
    from src.game.enemy_defs import load_enemy_defs
    load_enemy_defs("resources/enemies.json")
    try:
        from src.game.skill_defs import load_skill_defs
        load_skill_defs("resources/skills.json")
    except: pass
    from src.game.biome import load_biome_defs
    load_biome_defs("resources/biomes.json")
    from src.game.landmark import load_landmark_defs
    load_landmark_defs("resources/landmarks.json")
    from src.game.hazard import load_hazard_defs
    load_hazard_defs("resources/hazards.json")
    from src.game.biome_event import load_biome_event_defs
    load_biome_event_defs("resources/biome_events.json")
    print("[Init] Data loaded.")

    engine = GameEngine(screen, clock)
    from src.scenes.title_scene import TitleScene
    engine.change_scene(TitleScene(engine))
    engine.run()
    pygame.quit()


if __name__ == "__main__":
    main()
