"""
Performanslı ve güvenli dosya işlemleri
"""
import json
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import threading
import logging
import os
import time

logger = logging.getLogger(__name__)


# Thread-safe file operation lock
_file_locks: Dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_file_lock(filepath: str) -> threading.Lock:
    """Dosya için thread-safe lock objesi döndür"""
    with _locks_lock:
        if filepath not in _file_locks:
            _file_locks[filepath] = threading.Lock()
        return _file_locks[filepath]


def load_json_safe(
    filepath: str,
    default: Any = None,
    create_if_missing: bool = False
) -> Any:
    """
    JSON dosyasını güvenli şekilde yükler.
    
    Args:
        filepath: JSON dosyasının yolu
        default: Dosya yoksa veya hata varsa döndürülecek değer
        create_if_missing: True ise dosya yoksa default ile oluştur
        
    Returns:
        Any: JSON içeriği veya default değer
        
    Raises:
        ValueError: JSON parse hatası detayları ile
    """
    path = Path(filepath)
    
    # Dosya yoksa default döndür veya oluştur
    if not path.exists():
        if create_if_missing and default is not None:
            save_json_safe(filepath, default)
        return default if default is not None else {}
    
    lock = _get_file_lock(filepath)
    
    try:
        with lock:
            # Check if file is empty before loading
            if path.stat().st_size == 0:
                logger.warning(f"File {filepath} is empty (0 bytes). Returning default.")
                return default if default is not None else {}
                
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        if default is not None:
            logger.warning(f"JSON parse error in {filepath} (using default): {e.msg}")
            return default
        logger.error(f"JSON parse error in {filepath} at line {e.lineno}, column {e.colno}: {e.msg}")
        raise ValueError(
            f"JSON parse error in {filepath} at line {e.lineno}, "
            f"column {e.colno}: {e.msg}"
        )
    except Exception as e:
        logger.error(f"Error reading {filepath}: {str(e)}")
        if default is not None:
            return default
        raise IOError(f"Error reading {filepath}: {str(e)}")


def save_json_safe(
    filepath: str,
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
    create_backup: bool = True
) -> None:
    """
    JSON dosyasını güvenli şekilde kaydeder (atomic write).

    Args:
        filepath: JSON dosyasının yolu
        data: Kaydedilecek veri
        indent: JSON indentation
        ensure_ascii: ASCII encoding zorla
        create_backup: True ise mevcut dosyanın backup'ını al

    Raises:
        IOError: Dosya yazma hatası
    """
    path = Path(filepath)

    # Dizin yoksa oluştur
    path.parent.mkdir(parents=True, exist_ok=True)

    # Backup oluştur (varsa)
    backup_path = None
    if create_backup and path.exists():
        if path.parent.name == 'data':
            backup_dir = path.parent / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / (path.name + '.backup')
        else:
            backup_path = path.with_suffix(path.suffix + '.backup')
            
        try:
            shutil.copy2(path, backup_path)
            logger.info("event=backup_created file=%s backup=%s", os.path.basename(path), os.path.basename(backup_path))
        except Exception:
            logger.warning("event=backup_failed file=%s", os.path.basename(path))

    lock = _get_file_lock(filepath)

    try:
        with lock:
            # Atomic write: önce temp dosyaya yaz, sonra rename et
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=path.parent,
                delete=False,
                suffix='.tmp'
            ) as tmp_file:
                json.dump(
                    data,
                    tmp_file,
                    ensure_ascii=ensure_ascii,
                    indent=indent
                )
                tmp_path = Path(tmp_file.name)
                logger.debug("event=temp_written temp=%s file=%s", tmp_path.name, os.path.basename(path))

            # Atomic rename with retries for Windows/OneDrive synchronization
            max_retries = 10
            success = False
            for attempt in range(max_retries):
                try:
                    tmp_path.replace(path)
                    success = True
                    break
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        logger.warning("event=replace_locked attempt=%d file=%s", attempt + 1, os.path.basename(path))
                        time.sleep(0.2 * (attempt + 1))  # 0.2s, 0.4s, 0.6s...
                    else:
                        # LAST RESORT: Try direct write if atomic replacement fails persistently
                        # This happens on Windows when OneDrive or an editor locks the file
                        logger.warning("event=atomic_failed_last_resort file=%s", os.path.basename(path))
                        try:
                            # tmp_file is closed here because we exited the 'with' block above (line 120)
                            with open(path, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
                            tmp_path.unlink(missing_ok=True)
                            success = True
                            break
                        except Exception as final_e:
                            raise final_e
            
            if not success:
                 raise IOError(f"Failed to replace {path} after retries and fallback")
            # Log success with file size
            try:
                size = path.stat().st_size
            except Exception:
                size = None
            logger.info("event=write_success file=%s bytes=%s backup=%s", os.path.basename(path), size, os.path.basename(backup_path) if backup_path is not None else '')

    except Exception as e:
        # Cleanup temp file
        if 'tmp_path' in locals():
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
        logger.exception("event=write_failed file=%s reason=%s", os.path.basename(path), e)
        raise IOError(f"Error writing {filepath}: {str(e)}")


def atomic_write(
    filepath: str,
    content: str,
    encoding: str = 'utf-8'
) -> None:
    """
    Metni dosyaya atomic olarak yazar.
    
    Args:
        filepath: Dosya yolu
        content: Yazılacak içerik
        encoding: Karakter encoding
        
    Raises:
        IOError: Dosya yazma hatası
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    lock = _get_file_lock(filepath)
    
    try:
        with lock:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding=encoding,
                dir=path.parent,
                delete=False,
                suffix='.tmp'
            ) as tmp_file:
                tmp_file.write(content)
                tmp_path = Path(tmp_file.name)
            
            # Atomic rename with retries for Windows/OneDrive synchronization
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    tmp_path.replace(path)
                    break
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt+1))
                    else:
                        raise e
            
    except Exception as e:
        if 'tmp_path' in locals():
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
        raise IOError(f"Error writing {filepath}: {str(e)}")


def load_json_with_metadata(filepath: str) -> Dict[str, Any]:
    """
    JSON dosyasını metadata ile birlikte yükler.
    
    Returns:
        Dict: {
            'data': JSON içeriği,
            'metadata': {
                'last_modified': timestamp,
                'file_size': bytes,
                'loaded_at': timestamp
            }
        }
    """
    path = Path(filepath)
    
    if not path.exists():
        return {
            'data': None,
            'metadata': {
                'exists': False,
                'loaded_at': datetime.now().isoformat()
            }
        }
    
    stat = path.stat()
    data = load_json_safe(filepath)
    
    return {
        'data': data,
        'metadata': {
            'exists': True,
            'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'file_size': stat.st_size,
            'loaded_at': datetime.now().isoformat()
        }
    }


class FileCache:
    """
    Dosya içeriklerini cache'leyen sınıf.
    Memory'de tutar, değişiklik varsa yeniden yükler.
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def get(self, filepath: str, force_reload: bool = False) -> Any:
        """
        Dosyayı cache'den al, gerekirse yeniden yükle.
        
        Args:
            filepath: Dosya yolu
            force_reload: True ise cache'i atla, direkt diskten oku
            
        Returns:
            Any: Dosya içeriği
        """
        path = Path(filepath)
        
        if not path.exists():
            return None
        
        with self._lock:
            # Force reload veya cache yoksa
            if force_reload or filepath not in self._cache:
                data = load_json_safe(filepath)
                self._cache[filepath] = {
                    'data': data,
                    'mtime': path.stat().st_mtime
                }
                return data
            
            # Cache'deki veri güncel mi kontrol et
            current_mtime = path.stat().st_mtime
            cached_mtime = self._cache[filepath]['mtime']
            
            if current_mtime > cached_mtime:
                # Dosya değişmiş, yeniden yükle
                data = load_json_safe(filepath)
                self._cache[filepath] = {
                    'data': data,
                    'mtime': current_mtime
                }
                return data
            
            # Cache güncel
            return self._cache[filepath]['data']
    
    def clear(self, filepath: Optional[str] = None) -> None:
        """
        Cache'i temizler.
        
        Args:
            filepath: Belirli bir dosya için cache sil, None ise tümünü sil
        """
        with self._lock:
            if filepath:
                self._cache.pop(filepath, None)
            else:
                self._cache.clear()
    
    def size(self) -> int:
        """Cache'deki dosya sayısı"""
        with self._lock:
            return len(self._cache)


# Global cache instance
_global_cache = FileCache()


def get_cached_json(filepath: str, force_reload: bool = False) -> Any:
    """
    Global cache'den JSON dosyası al.
    
    Args:
        filepath: Dosya yolu
        force_reload: True ise cache'i atla
        
    Returns:
        Any: JSON içeriği
    """
    return _global_cache.get(filepath, force_reload)


def clear_cache(filepath: Optional[str] = None) -> None:
    """
    Global cache'i temizle.
    
    Args:
        filepath: Belirli bir dosya için cache sil, None ise tümünü sil
    """
    _global_cache.clear(filepath)
