# Plan — onaylananlar-jsonl-append
_Reference: atdd.md_

## Kod keşfi — mevcut durum (revert sonrası, önceki denemeden ÖNCEKİ kod)
- `APPROVED_PATH = os.path.join(PROJECT_ROOT, "data", "Onaylananlar.json")` (satır 46).
- `unprocessed_approve` (satır 414-467), tekli onay: satır 456-461'de
  `open()`+`json.load()`+`_atomic_write()` ile tam dosya oku/yaz.
- `_approve_message` (satır 471-519), toplu onay: `_approve_lock` (satır 469)
  ile korunuyor; satır 490-515'te aynı tam dosya oku/yaz deseni.
- `_atomic_write` (satır ~141-146, önceki görevlerden bilinen) — bu görevde
  KULLANILMAYACAK (append, temp+rename atomikliğine ihtiyaç duymuyor;
  append zaten dosyanın sonuna ekliyor, var olan içeriği hiç değiştirmiyor).
- Proje genelinde `Onaylananlar.json`'u OKUYAN başka hiçbir kod yok (önceki
  görevde Grep ile doğrulanmıştı, hâlâ geçerli — `data_service.py`'nin
  `onaylananlar_file`'ı farklı bir dosyaya, `onaylanan_kayitlar.json`'a
  işaret ediyor).
- `scripts/` dizini mevcut (proje kökünde) — yeni migration script'i buraya
  eklenecek, mevcut script isimlendirme kalıbı kontrol edildi, çakışma yok.

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/admin_panel.py | `APPROVED_PATH`'i `Onaylananlar.jsonl`'a çevir; `unprocessed_approve` (satır 456-461) ve `_approve_message` (satır 490-515) içindeki oku+yaz mantığını SAF APPEND ile değiştir (mevcut içerik hiç okunmaz). | medium |

## New Files
| File | Purpose |
|------|---------|
| scripts/migrate_onaylananlar_to_jsonl.py | Bir kerelik, MANUEL çalıştırılan migration: mevcut `data/Onaylananlar.json` (tek JSON dizisi) içeriğini `data/Onaylananlar.jsonl`'a (satır başına bir kayıt) dönüştürür. Orijinal dosyayı SİLMEZ. |

## Dependencies
- `json` (stdlib) — hem `json.loads`/`json.dumps` (satır bazlı) hem migration script'inde `json.load` (bir kerelik, tam dosya).
- Yeni harici bağımlılık YOK (`ijson` gibi streaming kütüphaneler
  DEĞERLENDİRİLDİ ama migration'ın bir kerelik, manuel, PM2 dışı bir
  script olması nedeniyle gerekli görülmedi — CAVEMAN: mevcut stdlib
  yeterli, migration'ın kendisi hedef performans kısıtının parçası değil).
- `_approve_lock` (mevcut, satır 469) — toplu onaydaki append'i sarmaya
  devam edecek. `unprocessed_approve` (tekli onay) için ATDD'nin Risks
  bölümünde bahsedilen interleaving riskine karşı, append işlemini de
  BİR lock altına almak gerekip gerekmediği aşağıda Open Questions'ta.

## Migration Required?
**Evet** — `scripts/migrate_onaylananlar_to_jsonl.py`. Ayrıntı: atdd.md'nin
AC-5'i ve "Risks" bölümü. Bu, bir veritabanı şema göçü değil, dosya FORMATI
göçü (JSON dizisi → JSON Lines). Otomatik/silent DEĞİL — kullanıcı SSH ile
VPS'te manuel çalıştıracak, admin_panel.py'nin başlangıcında OTOMATİK
TETİKLENMEYECEK (atdd.md'nin Assumptions'ında zaten karara bağlandı — bu,
tam da önceki incident'ın nedeni olan "büyük dosyayı sürecin kendi bellek
bütçesinde işleme" hatasını tekrar etmemek için).

## Risks
_(atdd.md'den taşındı + kod keşfinde netleşenler)_
- **Append atomikliği/interleaving riski** (atdd.md'nin Risks bölümünde
  zaten flagged): `unprocessed_approve` şu an HİÇ lock kullanmıyor (sadece
  `_approve_message` `_approve_lock` kullanıyor). İki eşzamanlı tekli onay
  isteği aynı anda dosyaya append yaparsa, Python'un buffered `write()`'ı
  büyük bir string için birden fazla syscall'a bölünebilir, bu da satırların
  iç içe geçmesine (bozuk JSONL satırı) yol açabilir. **Karar gerekiyor**
  (aşağıda Open Questions'ta) — muhtemel çözüm: `unprocessed_approve`'un
  append'ini de `_approve_lock` (veya yeni bir `_approved_write_lock`)
  altına almak, CAVEMAN'a uygun en basit çözüm.
- **Migration'ın bellek maliyeti**: Kabul edilmiş risk (atdd.md'de zaten
  not düşüldü) — bir kerelik, PM2 dışı, kullanıcı gözetiminde.
- **AC-3'ün büyük-dosya testi**: Bu görevin EN KRİTİK doğrulama adımı — test-copilot
  bu testi YAZMAZSA veya küçük bir dosyayla "yeterli" derse, önceki
  incident'ın TAM AYNISI tekrar edebilir. `verify` adımına bu özel olarak
  hatırlatılmalı.

## Open Questions
1. **`unprocessed_approve`'un append'i lock altına alınmalı mı?**
   Öneri: EVET — `_approve_lock`'u (mevcut, zaten `_approve_message` için
   var) HER İKİ fonksiyonun da append çağrısını sarmak için yeniden
   kullan (yeni bir lock icat etmeden, CAVEMAN'a uygun). Bu, önceki
   görevde bulunan "unprocessed_approve kilitsiz" red-team bulgusunun
   JSONL bağlamındaki karşılığını da kapatır.
2. **JSONL dosya adı**: `Onaylananlar.jsonl` mi yoksa mevcut `Onaylananlar.json`
   adını koruyup İÇERİK formatını mı değiştirmeli (dosya uzantısı yanıltıcı
   olur — `.json` uzantılı ama geçerli tek bir JSON değeri olmayan bir
   dosya, ileride birinin yanlışlıkla `json.load()` ile okumaya çalışıp
   `JSONDecodeError` almasına yol açabilir). Öneri: **`Onaylananlar.jsonl`**
   (yeni, doğru uzantı) — yanıltıcı isimlendirmeyi önler, migration
   script'i zaten yeni bir dosya oluşturuyor.

## Kararlar
1. **Mevcut `_approve_lock`'u paylaş** — `unprocessed_approve`'un yeni
   append işlemi de `_approve_lock`'u kullanacak (yeni bir lock icat
   edilmeyecek). (Haiku alt-ajanı tarafından yanıtlandı: iki fonksiyon da
   aynı dosyaya yazdığı için ortak lock basitlik sağlıyor ve race
   condition'ı güvenilir şekilde önlüyor.)
2. **Dosya adı `Onaylananlar.jsonl`** — yeni, doğru uzantı. (Haiku
   alt-ajanı tarafından yanıtlandı: format değişimiyle tutarlı, migration'ı
   netleştiriyor, eski ad korunursa format değişikliği gizli kalır.)
