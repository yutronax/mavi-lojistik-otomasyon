# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Proje kök dizini
import os
ROOT_DIR = 'c:/Users/MONSTER/3D Objects/yazprojeler/maviLojistik'

a = Analysis(
    [os.path.join(ROOT_DIR, 'src/gui/masaustu_uygulama.py')],
    pathex=[ROOT_DIR, os.path.join(ROOT_DIR, 'src'), os.path.join(ROOT_DIR, 'src/fetchers')],
    binaries=[],
    datas=[
        (os.path.join(ROOT_DIR, 'data/chat_groups.json'), 'data'),
        (os.path.join(ROOT_DIR, 'data/il_ilçeler.json'), 'data'),
        (os.path.join(ROOT_DIR, 'data/yuk_tipi.json'), 'data'),
        (os.path.join(ROOT_DIR, 'data/arac_yuk_kasa_tipleri.json'), 'data'),
        (os.path.join(ROOT_DIR, 'data/special_locations.json'), 'data'),
        (os.path.join(ROOT_DIR, 'tools/yukburada_config.json'), 'tools'),
    ],
    hiddenimports=[
        'rapidfuzz',
        'rapidfuzz.process',
        'cryptography',
        'requests',
        'src.fetchers.whapi_fetcher',
        'src.fetchers.mavi_whap',
        'tools.submit_approved_loads',
    ],
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
    name='MaviLojistik',
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
    icon=None,
)
