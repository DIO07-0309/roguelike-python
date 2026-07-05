# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

datas = []
binaries = []
hiddenimports = ['saves.save_manager', 'config', 'game']

# 收集 src 子模块
hiddenimports += collect_submodules('src')

# assets 文件（The World 时停音效）
datas += [('assets/jojo_timestop.mp3', 'assets')]

# ============================================================
# 关键：排除 numpy 和 MKL（游戏完全不需要）
# collect_all('pygame') 会递归拖进 numpy + 29个MKL DLL（633MB）
# 依赖 PyInstaller 内置的 hook-pygame.py 即可正确处理 pygame
# ============================================================
excludes = ['numpy', 'mkl', 'scipy', 'pandas', 'matplotlib',
            'pygame.examples', 'pygame.tests', 'pygame.docs',
            'pygame._camera_opencv', 'pygame._camera_vidcapture']


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Roguelike',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # 游戏不需要控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Roguelike',
)
