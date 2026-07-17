# -*- mode: python ; coding: utf-8 -*-

# Trackeep Lit PyInstaller 打包规格（对齐 mecha-quant/build/MechaQuant.spec）。
# PySide6 的 Qt plugins / 二进制由 PyInstaller 内置 hook 自动收集（同机已验证可打包 PySide6）。
# 运行时外部读取（zotero-import.ps1 / .mecha/*.json / 期刊表 / zotero.env）全是绝对路径，不打进 exe。
# 本项目无 app.ico → 用默认图标（icon=[]）。


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Trackeep Lit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Trackeep Lit',
)
