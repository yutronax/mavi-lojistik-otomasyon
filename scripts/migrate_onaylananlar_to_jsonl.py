#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bir kerelik migration: data/Onaylananlar.json (tek JSON dizisi) içeriğini
data/Onaylananlar.jsonl'a (satır başına bir JSON kaydı) dönüştürür.

Orijinal Onaylananlar.json SİLİNMEZ (yedek olarak kalır).

Kullanım (manuel, VPS'te SSH ile):
    python3 scripts/migrate_onaylananlar_to_jsonl.py

DİKKAT: Bu script mevcut Onaylananlar.json'u TAMAMEN belleğe yükler
(büyük dosyalarda yüksek bellek kullanımı beklenir — bu NORMAL ve KABUL
EDİLMİŞ bir durumdur, çünkü bu BİR KEZ, manuel, PM2'nin bellek limiti
DIŞINDA çalıştırılan bir işlemdir; production sunucu sürecinin (admin_panel.py)
kendisi ASLA bu şekilde tam dosya yüklemesi yapmaz).
"""
import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OLD_PATH = os.path.join(PROJECT_ROOT, "data", "Onaylananlar.json")
NEW_PATH = os.path.join(PROJECT_ROOT, "data", "Onaylananlar.jsonl")


def main():
    if not os.path.exists(OLD_PATH):
        print(f"Kaynak dosya bulunamadı: {OLD_PATH}")
        sys.exit(1)

    if os.path.exists(NEW_PATH):
        print(f"HATA: Hedef dosya zaten var: {NEW_PATH}")
        print("Migration'ı tekrar çalıştırmadan önce mevcut .jsonl dosyasını yedekleyin/silin.")
        sys.exit(1)

    print(f"Okunuyor: {OLD_PATH} ...")
    with open(OLD_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not isinstance(records, list):
        print(f"HATA: Beklenmeyen format — bir JSON dizisi bekleniyordu, {type(records)} bulundu.")
        sys.exit(1)

    print(f"{len(records)} kayıt bulundu. Yazılıyor: {NEW_PATH} ...")
    with open(NEW_PATH, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Tamamlandı: {len(records)} kayıt {NEW_PATH} dosyasına taşındı.")
    print(f"Orijinal dosya SİLİNMEDİ: {OLD_PATH} (yedek olarak kalıyor).")


if __name__ == "__main__":
    main()
