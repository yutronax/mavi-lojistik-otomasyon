"""
Ortak kullanılan yardımcı fonksiyonlar
"""
import os
from pathlib import Path
from typing import Optional


def get_root_path() -> Path:
    """
    Proje root dizinini döndürür.
    
    Returns:
        Path: Proje root dizini (mavi_lojisti_yusuf dizininin bir üst dizini)
    """
    current_dir = Path(__file__).resolve().parent
    # utils -> mavi_lojisti_yusuf -> root
    
    # Check if running as PyInstaller EXE
    import sys
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
        
    return current_dir.parent.parent


def get_user_data_dir() -> Path:
    """
    Kullanıcı verilerinin (yazılabilir) saklanacağı dizini döndürür.
    EXE modunda: EXE'nin yanındaki 'data' klasörü
    Geliştirme modu: Proje root'undaki 'data' klasörü
    """
    root = get_root_path()
    data_dir = root / 'data'
    ensure_directory(str(data_dir))
    return data_dir


def get_bundled_data_dir() -> Path:
    """
    Paketlenmiş (read-only) veri dosyalarının bulunduğu dizini döndürür.
    EXE modunda: _internal/data veya sys._MEIPASS/data
    Geliştirme modu: Proje root'undaki 'data' klasörü
    """
    import sys
    if getattr(sys, 'frozen', False):
        # PyInstaller _MEIPASS temp directory for bundled files
        base_path = Path(sys._MEIPASS)
        return base_path / 'data'
    
    return get_root_path() / 'data'


def ensure_directory(path: str) -> Path:
    """
    Verilen path'in dizin olarak var olduğundan emin olur, yoksa oluşturur.
    
    Args:
        path: Dizin yolu
        
    Returns:
        Path: Oluşturulan/mevcut dizin path'i
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_project_file_path(filename: str, root_relative: bool = True) -> Path:
    """
    Proje dosyasının tam path'ini döndürür.
    
    Args:
        filename: Dosya adı
        root_relative: True ise root dizinine göre, False ise current dir'e göre
        
    Returns:
        Path: Dosyanın tam path'i
    """
    if root_relative:
        root = get_root_path()
        return root / filename
    return Path(filename)


def normalize_turkish_text(text: str) -> str:
    """
    Türkçe karakterleri normalize eder (büyük harfe çevirir).
    
    Args:
        text: Normalize edilecek metin
        
    Returns:
        str: Normalize edilmiş metin
    """
    if not text:
        return ''
    
    import unicodedata
    turkish_char_map = str.maketrans({
        'İ': 'I', 'I': 'I', 'ı': 'I',
        'Ş': 'S', 'ş': 'S',
        'Ğ': 'G', 'ğ': 'G',
        'Ü': 'U', 'ü': 'U',
        'Ö': 'O', 'ö': 'O',
        'Ç': 'C', 'ç': 'C'
    })
    
    translated = text.translate(turkish_char_map).upper()
    return unicodedata.normalize('NFC', translated).strip()


def mask_sensitive_data(data: str, show_chars: int = 6) -> str:
    """
    Hassas veriyi maskeler (API key, telefon vb.)
    
    Args:
        data: Maskelenecek veri
        show_chars: Başta ve sonda gösterilecek karakter sayısı
        
    Returns:
        str: Maskelenmiş veri
    """
    if not data:
        return ''
    
    if len(data) <= show_chars * 2:
        return data
    
    return f"{data[:show_chars]}...{data[-4:]}"
