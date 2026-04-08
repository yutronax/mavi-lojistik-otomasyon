import sys
import os
import certifi

# Ensure project root is in path for module discovery
project_root = os.path.abspath('.')
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyInstaller.utils.hooks import collect_all

datas = [
    ('data', 'data'),
    # ('src', 'src'), # Disabled to prevent source distribution
    # ('tools', 'tools'), # Disabled to prevent source distribution
    ('production_parser.py', '.'),
    ('text_gen_parser.py', '.'),
    # Add certifi CA bundle explicitly
    (certifi.where(), 'certifi'),
]
binaries = []
hiddenimports = [
    # Core veri_cekici_ayristirici module
    'src.parsers.veri_cekici_ayristirici',
    
    # Production parsers
    'production_parser',
    'text_gen_parser',
    
    # Fetchers
    'src.fetchers.whapi_fetcher',
    'src.fetchers.mavi_whap',
    
    # Parsers
    'src.parsers.location_research_agent',
    'src.parsers.production_parser',
    'src.parsers.shipment_models',
    
    # Utils
    'src.utils.api_key_manager',
    'src.utils.file_operations',
    'src.utils.file_ops',
    'src.utils.gemini_adapter',
    'src.utils.gemini_client',
    'src.utils.vehicle_type_matcher',
    'src.utils.city_district_validator',
    'src.utils.phone_utils',


    
    # Tools
    'tools.submit_approved_loads',
    
    # Services
    'src.services.data_service',
    
    # Models
    'src.models.shipment',
    
    # GUI Components
    'src.gui.components.autocomplete',
    'src.gui.components.tag_selector',

    
    # Standard library modules that might be missed
    'concurrent.futures',
    'itertools',
    'threading',
    'datetime',
    'json',
    'logging',
    
    # Third-party packages
    'pydantic',
    'pydantic.main',
    'pydantic.fields',
    'pydantic_core',
    'dotenv',
    'google.genai',
    'google.generativeai',
]



# Namespace paketleri için kapsamlı toplama (collect_all)
packages_to_collect = [
    'backports.tarfile', 
    'jaraco.text', 
    'jaraco.context', 
    'jaraco.functools',
    'jaraco.classes',
    'pydantic',
    'dotenv',
    'requests',
    'certifi',
    'charset_normalizer',
    'idna',
    'urllib3',
    'google.genai',
    'google.generativeai'
]

# Simplified package collection to avoid build issues
# Enable package collection
for pkg in packages_to_collect:
    try:
        tmp_ret = collect_all(pkg)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
    except Exception as e:
        print(f"Warning: Could not collect {pkg}: {e}")

block_cipher = None

a = Analysis(
    ['src/gui/masaustu_uygulama.py'],
    pathex=[os.path.abspath('.')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tensorflow', 'torch', 'keras', 'jax', 'matplotlib', 'scipy', 'IPython', 'notebook', 'jupyter', 'cv2', 'PIL', 'pkg_resources', 'setuptools', 'distutils'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --- Second Executable: Tanımlama Merkezi (Yük + Mahalle) ---
b = Analysis(
    ['src/gui/yonetim_merkezi.py'],
    pathex=[os.path.abspath('.')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ['src.gui.yonetim_merkezi'],
    hookspath=['hooks'],
    runtime_hooks=[],
    excludes=['tensorflow', 'torch', 'keras', 'jax', 'matplotlib', 'scipy', 'distutils'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_a = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
pyz_b = PYZ(b.pure, b.zipped_data, cipher=block_cipher)

exe_a = EXE(
    pyz_a,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MaviLojistik',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

exe_b = EXE(
    pyz_b,
    b.scripts,
    [],
    exclude_binaries=True,
    name='TanimlamaMerkezi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe_a,
    a.binaries,
    a.zipfiles,
    a.datas,
    exe_b,
    b.binaries,
    b.zipfiles,
    b.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MaviLojistik',
)
