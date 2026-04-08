# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['requests', 'rapidfuzz', 'backports', 'backports.tarfile']
hiddenimports += collect_submodules('jaraco')
hiddenimports += collect_submodules('backports')


block_cipher = None


a = Analysis(
    ['masaustu_uygulama.py'],
    pathex=['..\\..', '..\\fetchers'],
    binaries=[],
    datas=[('..\\..\\data\\chat_groups.json', 'data'), ('..\\..\\data\\il_ilçeler.json', 'data'), ('..\\..\\data\\yuk_tipi.json', 'data'), ('..\\..\\data\\arac_yuk_kasa_tipleri.json', 'data'), ('..\\..\\data\\special_locations.json', 'data'), ('..\\..\\tools\\yukburada_config.json', 'tools')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tensorflow', 'torch', 'pandas', 'numpy', 'matplotlib', 'scipy', 'IPython', 'jupyter', 'notebook'],
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
)
