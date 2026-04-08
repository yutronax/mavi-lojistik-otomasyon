#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bağımlılık Analiz Aracı

Bu modül, Python projelerindeki dosya bağımlılıklarını analiz eder.
Import satırlarını AST kullanarak parse eder ve bağımlılık ağacını oluşturur.

Özellikler:
- AST tabanlı güvenli import analizi
- Bağımlılık zinciri takibi
- Kullanılmayan dosya tespiti
- Otomatik arşivleme ve geri yükleme
"""

import os
import ast
import shutil
import json
from pathlib import Path
from typing import Set, Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """
    Python projelerindeki dosya bağımlılıklarını analiz eder.
    
    Attributes:
        project_root: Proje kök dizini
        required_files: Gerekli olan dosyaların seti
        import_graph: Dosya -> İmport edilen dosyalar haritası
    """
    
    def __init__(self, project_root: str):
        """
        Args:
            project_root: Proje kök dizininin yolu
        """
        self.project_root = Path(project_root).resolve()
        self.required_files: Set[Path] = set()
        self.import_graph: Dict[Path, Set[Path]] = {}
        self.archive_dir = self.project_root / "_arsiv"
        
    def _is_local_import(self, import_path: str) -> bool:
        """
        Import'un yerel bir Python dosyası olup olmadığını kontrol eder.
        
        Args:
            import_path: Import yolu (örn: "src.utils.helper")
            
        Returns:
            True ise yerel dosya, False ise harici paket
        """
        # Harici paketleri filtrele
        external_packages = {
            'os', 'sys', 'json', 'ast', 'pathlib', 're', 'logging',
            'typing', 'datetime', 'shutil', 'collections', 'itertools',
            'tkinter', 'requests', 'pydantic', 'dotenv', 'openai',
            'google', 'anthropic', 'numpy', 'pandas', 'matplotlib'
        }
        
        first_part = import_path.split('.')[0]
        return first_part not in external_packages
    
    def _resolve_import_to_file(self, import_path: str, from_file: Path) -> Optional[Path]:
        """
        Import yolunu gerçek dosya yoluna çevirir.
        
        Args:
            import_path: Import yolu (örn: "src.utils.helper")
            from_file: Import'u yapan dosyanın yolu
            
        Returns:
            Çözümlenmiş dosya yolu veya None
        """
        # Mutlak import (proje kökünden)
        parts = import_path.split('.')
        
        # 1. Proje kökünden başlayarak dene
        file_path = self.project_root / '/'.join(parts)
        
        # .py uzantısı ile dene
        if file_path.with_suffix('.py').exists():
            return file_path.with_suffix('.py').resolve()
        
        # __init__.py ile dene (paket import'u)
        init_file = file_path / '__init__.py'
        if init_file.exists():
            return init_file.resolve()
        
        # 2. Proje kökünde direkt dosya olarak dene (örn: text_gen_parser.py)
        if len(parts) == 1:  # Tek kelimelik import
            root_file = self.project_root / f"{parts[0]}.py"
            if root_file.exists():
                return root_file.resolve()
        
        # 3. Göreceli import (from . import veya from .. import)
        if import_path.startswith('.'):
            relative_base = from_file.parent
            level = 0
            while import_path.startswith('.'):
                level += 1
                import_path = import_path[1:]
                if level > 1:
                    relative_base = relative_base.parent
            
            if import_path:
                parts = import_path.split('.')
                file_path = relative_base / '/'.join(parts)
                
                if file_path.with_suffix('.py').exists():
                    return file_path.with_suffix('.py').resolve()
                
                init_file = file_path / '__init__.py'
                if init_file.exists():
                    return init_file.resolve()
        
        return None
    
    def analyze_imports(self, file_path: Path) -> Set[Path]:
        """
        Bir dosyadaki tüm yerel import'ları tespit eder.
        
        Args:
            file_path: Analiz edilecek dosyanın yolu
            
        Returns:
            Import edilen yerel dosyaların seti
        """
        imports = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # AST ile parse et
            tree = ast.parse(content, filename=str(file_path))
            
            # Import ve ImportFrom node'larını bul
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    # import X, Y, Z
                    # import X.Y.Z
                    for alias in node.names:
                        if self._is_local_import(alias.name):
                            resolved = self._resolve_import_to_file(alias.name, file_path)
                            if resolved:
                                imports.add(resolved)
                            
                            # Modül import'u için (import src.utils.helper)
                            # Her seviyeyi de kontrol et
                            parts = alias.name.split('.')
                            for i in range(1, len(parts) + 1):
                                partial_import = '.'.join(parts[:i])
                                if self._is_local_import(partial_import):
                                    resolved = self._resolve_import_to_file(partial_import, file_path)
                                    if resolved:
                                        imports.add(resolved)
                
                elif isinstance(node, ast.ImportFrom):
                    # from X import Y, Z
                    if node.module and self._is_local_import(node.module):
                        # Önce modülün kendisini çöz
                        resolved = self._resolve_import_to_file(node.module, file_path)
                        if resolved:
                            imports.add(resolved)
                        
                        # Sonra import edilen her bir öğeyi de kontrol et
                        # Örnek: from src.utils import helper
                        # Bu durumda src/utils/helper.py'yi de bul
                        for alias in node.names:
                            if alias.name != '*':  # from X import * durumunu atla
                                full_import = f"{node.module}.{alias.name}"
                                if self._is_local_import(full_import):
                                    resolved = self._resolve_import_to_file(full_import, file_path)
                                    if resolved:
                                        imports.add(resolved)
                    
                    # from . import X (göreceli import)
                    elif node.level > 0:
                        # Göreceli import'u çöz
                        relative_path = '.' * node.level
                        if node.module:
                            relative_path += node.module
                        
                        resolved = self._resolve_import_to_file(relative_path, file_path)
                        if resolved:
                            imports.add(resolved)
                        
                        # from . import X, Y durumu için
                        for alias in node.names:
                            if alias.name != '*':
                                if node.module:
                                    full_path = f"{relative_path}.{alias.name}"
                                else:
                                    full_path = f"{relative_path}{alias.name}"
                                
                                resolved = self._resolve_import_to_file(full_path, file_path)
                                if resolved:
                                    imports.add(resolved)
        
        except (SyntaxError, UnicodeDecodeError) as e:
            logger.warning(f"Dosya parse edilemedi: {file_path} - {e}")
        
        return imports
    
    def build_dependency_tree(self, entry_points: List[Path]):
        """
        Entry point'lerden başlayarak tüm bağımlılık ağacını oluşturur.
        
        BFS (Breadth-First Search) algoritması kullanır.
        
        Args:
            entry_points: Başlangıç dosyalarının listesi
        """
        # Entry point'leri gerekli olarak işaretle
        for entry in entry_points:
            if entry.exists():
                self.required_files.add(entry.resolve())
        
        # BFS için kuyruk
        queue = list(self.required_files)
        visited = set(self.required_files)
        
        while queue:
            current_file = queue.pop(0)
            
            # Bu dosyanın import'larını analiz et
            imports = self.analyze_imports(current_file)
            self.import_graph[current_file] = imports
            
            # Yeni bulunan dosyaları işle
            for imported_file in imports:
                if imported_file not in visited:
                    visited.add(imported_file)
                    self.required_files.add(imported_file)
                    queue.append(imported_file)
        
        logger.info(f"Bağımlılık ağacı oluşturuldu: {len(self.required_files)} dosya gerekli")
    
    def find_unused_files(self, exclude_patterns: Optional[List[str]] = None) -> Set[Path]:
        """
        Kullanılmayan Python dosyalarını tespit eder.
        
        Args:
            exclude_patterns: Hariç tutulacak dosya/klasör desenleri
            
        Returns:
            Kullanılmayan dosyaların seti
        """
        if exclude_patterns is None:
            exclude_patterns = [
                '_arsiv',
                '__pycache__',
                '.git',
                'venv',
                'env',
                '.pytest_cache',
                'build',
                'dist',
                '*.pyc',
                'test_*.py',  # Test dosyalarını koru
                'setup.py',
                'conftest.py'
            ]
        
        all_py_files = set()
        
        # Proje klasöründeki tüm .py dosyalarını bul
        for py_file in self.project_root.rglob('*.py'):
            # Hariç tutulacak desenleri kontrol et
            should_exclude = False
            for pattern in exclude_patterns:
                if pattern in str(py_file.relative_to(self.project_root)):
                    should_exclude = True
                    break
            
            if not should_exclude:
                all_py_files.add(py_file.resolve())
        
        # Kullanılmayan dosyalar = Tüm dosyalar - Gerekli dosyalar
        unused = all_py_files - self.required_files
        
        logger.info(f"Toplam {len(all_py_files)} dosya, {len(unused)} kullanılmayan")
        
        return unused
    
    def archive_unused(self, unused_files: Set[Path], dry_run: bool = False) -> Dict:
        """
        Kullanılmayan dosyaları _arsiv/ klasörüne taşır.
        
        Args:
            unused_files: Arşivlenecek dosyaların seti
            dry_run: True ise sadece rapor oluştur, dosyaları taşıma
            
        Returns:
            Arşivleme raporu
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_subdir = self.archive_dir / f"{timestamp}_dependency_cleanup"
        
        report = {
            "timestamp": timestamp,
            "dry_run": dry_run,
            "archived_files": [],
            "required_files_count": len(self.required_files),
            "archived_files_count": len(unused_files)
        }
        
        if not dry_run:
            archive_subdir.mkdir(parents=True, exist_ok=True)
        
        for file_path in unused_files:
            relative_path = file_path.relative_to(self.project_root)
            archive_path = archive_subdir / relative_path
            
            report["archived_files"].append({
                "original_path": str(relative_path),
                "archive_path": str(archive_path.relative_to(self.project_root)),
                "reason": "Not imported by any file"
            })
            
            if not dry_run:
                # Hedef klasörü oluştur
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Dosyayı taşı
                shutil.move(str(file_path), str(archive_path))
                logger.info(f"Arşivlendi: {relative_path}")
        
        # Raporu kaydet
        if not dry_run:
            report_file = archive_subdir / "cleanup_report.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Rapor kaydedildi: {report_file}")
        
        return report
    
    def restore_needed(self, needed_files: Set[Path]) -> int:
        """
        Arşivden geri getirilmesi gereken dosyaları tespit eder ve geri getirir.
        
        Args:
            needed_files: Gerekli olan dosyaların seti
            
        Returns:
            Geri yüklenen dosya sayısı
        """
        restored_count = 0
        
        if not self.archive_dir.exists():
            logger.info("Arşiv klasörü bulunamadı")
            return 0
        
        # Arşiv klasörünü tara
        for archive_subdir in sorted(self.archive_dir.iterdir(), reverse=True):
            if not archive_subdir.is_dir():
                continue
            
            # Raporu oku
            report_file = archive_subdir / "cleanup_report.json"
            if not report_file.exists():
                continue
            
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            # Arşivlenen dosyaları kontrol et
            for entry in report.get("archived_files", []):
                original_path = self.project_root / entry["original_path"]
                archive_path = self.project_root / entry["archive_path"]
                
                # Bu dosya şimdi gerekli mi?
                if original_path.resolve() in needed_files and archive_path.exists():
                    # Hedef klasörü oluştur
                    original_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Dosyayı geri getir
                    shutil.move(str(archive_path), str(original_path))
                    logger.info(f"Geri yüklendi: {entry['original_path']}")
                    restored_count += 1
        
        return restored_count
