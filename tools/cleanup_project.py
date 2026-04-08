#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Proje Temizleme Aracı

Kullanılmayan Python dosyalarını otomatik olarak tespit edip arşivler.

Kullanım:
    python tools/cleanup_project.py --dry-run    # Sadece rapor göster
    python tools/cleanup_project.py --execute    # Arşivleme yap
    python tools/cleanup_project.py --restore    # Geri yükle
    python tools/cleanup_project.py --stats      # İstatistikleri göster
"""

import sys
import argparse
from pathlib import Path
import logging

# Proje kökünü sys.path'e ekle
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.dependency_analyzer import DependencyAnalyzer

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def print_banner():
    """Hoş geldin banner'ı yazdır"""
    print("=" * 60)
    print("🧹 Proje Temizleme Aracı")
    print("=" * 60)
    print()


def print_report(report: dict, analyzer: DependencyAnalyzer):
    """Analiz raporunu yazdır"""
    print("\n📊 Analiz Raporu")
    print("━" * 60)
    print(f"✅ Gerekli dosyalar:        {report['required_files_count']} dosya")
    print(f"❌ Gereksiz dosyalar:       {report['archived_files_count']} dosya")
    
    if report['dry_run']:
        print(f"\n⚠️  DRY-RUN modu: Hiçbir dosya taşınmadı")
    else:
        print(f"\n✓ Arşivleme tamamlandı")
    
    print("━" * 60)
    
    if report['archived_files']:
        print("\n📦 Arşivlenecek/Arşivlenen Dosyalar:")
        for i, entry in enumerate(report['archived_files'][:10], 1):
            print(f"  {i}. {entry['original_path']}")
        
        if len(report['archived_files']) > 10:
            print(f"  ... ve {len(report['archived_files']) - 10} dosya daha")
    
    print()


def print_stats(analyzer: DependencyAnalyzer):
    """İstatistikleri yazdır"""
    print("\n📊 Proje İstatistikleri")
    print("━" * 60)
    
    # Gerekli dosyaları say
    required_count = len(analyzer.required_files)
    
    # Tüm Python dosyalarını say
    all_py_files = set(analyzer.project_root.rglob('*.py'))
    # Arşiv klasörünü hariç tut
    all_py_files = {f for f in all_py_files if '_arsiv' not in str(f)}
    
    # Gereksiz dosyaları say
    unused = analyzer.find_unused_files()
    
    # Arşivlenmiş dosyaları say
    archived_count = 0
    if analyzer.archive_dir.exists():
        for archive_subdir in analyzer.archive_dir.iterdir():
            if archive_subdir.is_dir():
                archived_count += len(list(archive_subdir.rglob('*.py')))
    
    print(f"✅ Gerekli dosyalar:        {required_count} dosya")
    print(f"❌ Gereksiz dosyalar:       {len(unused)} dosya")
    print(f"📦 Arşivlenmiş dosyalar:    {archived_count} dosya")
    print(f"📁 Toplam Python dosyası:   {len(all_py_files)} dosya")
    print("━" * 60)
    
    # Bağımlılık istatistikleri
    if analyzer.import_graph:
        avg_imports = sum(len(imports) for imports in analyzer.import_graph.values()) / len(analyzer.import_graph)
        print(f"\n📈 Bağımlılık İstatistikleri:")
        print(f"  Ortalama import sayısı:   {avg_imports:.1f}")
        print(f"  En çok import eden:       ", end="")
        
        max_imports_file = max(analyzer.import_graph.items(), key=lambda x: len(x[1]))
        print(f"{max_imports_file[0].name} ({len(max_imports_file[1])} import)")
    
    print()


def cmd_dry_run(args):
    """Dry-run komutu: Sadece rapor göster"""
    print_banner()
    print("🔍 Dry-run modu: Dosyalar taşınmayacak, sadece rapor gösterilecek\n")
    
    analyzer = DependencyAnalyzer(project_root=args.project_root)
    
    # Entry points
    entry_points = [
        Path(args.project_root) / "src" / "parsers" / "veri_cekici_ayristirici.py",
        Path(args.project_root) / "src" / "gui" / "masaustu_uygulama.py"
    ]
    
    # Analiz
    logger.info("Bağımlılık ağacı oluşturuluyor...")
    analyzer.build_dependency_tree(entry_points)
    
    logger.info("Kullanılmayan dosyalar tespit ediliyor...")
    unused = analyzer.find_unused_files()
    
    # Rapor
    report = analyzer.archive_unused(unused, dry_run=True)
    print_report(report, analyzer)


def cmd_execute(args):
    """Execute komutu: Arşivleme yap"""
    print_banner()
    print("⚠️  UYARI: Bu işlem dosyaları _arsiv/ klasörüne taşıyacak!\n")
    
    if not args.force:
        response = input("Devam etmek istiyor musunuz? (evet/hayır): ")
        if response.lower() not in ['evet', 'e', 'yes', 'y']:
            print("İşlem iptal edildi.")
            return
    
    analyzer = DependencyAnalyzer(project_root=args.project_root)
    
    # Entry points
    entry_points = [
        Path(args.project_root) / "src" / "parsers" / "veri_cekici_ayristirici.py",
        Path(args.project_root) / "src" / "gui" / "masaustu_uygulama.py"
    ]
    
    # Analiz
    logger.info("Bağımlılık ağacı oluşturuluyor...")
    analyzer.build_dependency_tree(entry_points)
    
    logger.info("Kullanılmayan dosyalar tespit ediliyor...")
    unused = analyzer.find_unused_files()
    
    # Arşivle
    logger.info("Dosyalar arşivleniyor...")
    report = analyzer.archive_unused(unused, dry_run=False)
    print_report(report, analyzer)
    
    print("✓ Arşivleme tamamlandı!")


def cmd_restore(args):
    """Restore komutu: Geri yükle"""
    print_banner()
    print("🔄 Arşivden dosyalar geri yükleniyor...\n")
    
    analyzer = DependencyAnalyzer(project_root=args.project_root)
    
    # Entry points
    entry_points = [
        Path(args.project_root) / "src" / "parsers" / "veri_cekici_ayristirici.py",
        Path(args.project_root) / "src" / "gui" / "masaustu_uygulama.py"
    ]
    
    # Analiz
    logger.info("Bağımlılık ağacı oluşturuluyor...")
    analyzer.build_dependency_tree(entry_points)
    
    # Geri yükle
    restored_count = analyzer.restore_needed(analyzer.required_files)
    
    print(f"\n✓ {restored_count} dosya geri yüklendi!")


def cmd_stats(args):
    """Stats komutu: İstatistikleri göster"""
    print_banner()
    
    analyzer = DependencyAnalyzer(project_root=args.project_root)
    
    # Entry points
    entry_points = [
        Path(args.project_root) / "src" / "parsers" / "veri_cekici_ayristirici.py",
        Path(args.project_root) / "src" / "gui" / "masaustu_uygulama.py"
    ]
    
    # Analiz
    logger.info("Bağımlılık ağacı oluşturuluyor...")
    analyzer.build_dependency_tree(entry_points)
    
    # İstatistikleri göster
    print_stats(analyzer)


def main():
    parser = argparse.ArgumentParser(
        description="Proje temizleme aracı - Kullanılmayan dosyaları otomatik arşivler"
    )
    
    parser.add_argument(
        '--project-root',
        default='.',
        help='Proje kök dizini (varsayılan: mevcut dizin)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Komutlar')
    
    # Dry-run komutu
    parser_dry_run = subparsers.add_parser(
        'dry-run',
        help='Sadece rapor göster, dosyaları taşıma'
    )
    parser_dry_run.set_defaults(func=cmd_dry_run)
    
    # Execute komutu
    parser_execute = subparsers.add_parser(
        'execute',
        help='Arşivleme işlemini gerçekleştir'
    )
    parser_execute.add_argument(
        '--force',
        action='store_true',
        help='Onay istemeden çalıştır'
    )
    parser_execute.set_defaults(func=cmd_execute)
    
    # Restore komutu
    parser_restore = subparsers.add_parser(
        'restore',
        help='Arşivden dosyaları geri yükle'
    )
    parser_restore.set_defaults(func=cmd_restore)
    
    # Stats komutu
    parser_stats = subparsers.add_parser(
        'stats',
        help='Proje istatistiklerini göster'
    )
    parser_stats.set_defaults(func=cmd_stats)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Komutu çalıştır
    args.func(args)


if __name__ == '__main__':
    main()
