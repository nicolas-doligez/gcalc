# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
	['gaiacalc.py', 'util.py', 'loop.py', 'show.py', 'index.py', 'webserver.py', '__init__.py'],
    pathex=['/Users/ikendo/Library/Python/3.10/lib/python/site-packages'],
    binaries=[],
	datas=[('data', 'data'), ('log', 'log'), ('*.py', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='gaiacalc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='gaiacalc.app',
    icon='../../gaiacalc.icns',
    bundle_identifier=None,
)
