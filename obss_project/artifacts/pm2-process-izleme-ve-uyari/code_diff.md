# Code Diff — pm2-process-izleme-ve-uyari

> Codex kotası dolu; bu task'ta test/implementasyon istisnai olarak Claude
> tarafından yazıldı, kullanıcı onaylıdır (bkz. `saga` skill Bölüm C).

## Değiştirilen Dosya
`src/api/admin_panel.py`

## Yeni Semboller
- `EXPECTED_PM2_PROCESSES` — beklenen 3 process adının sabit listesi.
- `_process_health` — global durum: `{process_adı: {"status": "ok"|"down"|"unknown", "down_since": iso|None}}`.
- `_parse_pm2_jlist(ok, out)` — saf I/O-ayrıştırma fonksiyonu, mevcut
  `_refresh_status_cache`'in `out.find("[")` desenini yeniden kullanıyor
  (yeni bir ayrıştırma deseni İCAT EDİLMEDİ).
- `_compute_process_health(pm2_processes, previous_health, now_iso)` — saf
  fonksiyon, dosya/ağ I/O yok. AC-1 ila AC-5'in tamamının mantığı burada.

## Değiştirilen Semboller
- `_refresh_status_cache()` döngüsü: artık AYNI `_pm2(["jlist"])` çağrısının
  çıktısını (`ok`, `out`) hem mevcut `SERVICE_NAME`-özel `service` alanı
  için HEM DE yeni `_process_health` hesaplaması için kullanıyor — **PM2'ye
  ikinci bir `jlist` çağrısı YAPILMIYOR** (gereksiz subprocess maliyeti
  önlendi).
- `/api/status` (`status()`): `process_health` alanı eklendi. `service`,
  `system`, `deepseek_balance`, `deepseek_real_spend` alanları DEĞİŞMEDİ.

## Kasıtlı Olarak Değiştirilmeyenler (plan.md kararı — seçenek B)
- `sidecar/bridge.js`'e YENİ bir mesaj gönderme endpointi EKLENMEDİ —
  bugün kırılganlığını gördüğümüz bu dosyaya dokunmamak bilinçli bir
  risk kararıydı (kullanıcı onayladı).
- `src/utils/notification_service.py`'deki `DiscordNotifier` AKTİFLEŞTİRİLMEDİ
  — VPS'te `DISCORD_WEBHOOK_URL` tanımlı değildi, yeni kanal kurulumu ATDD'nin
  Kapsam Dışı kararına girer.
- Otomatik process yeniden başlatma (auto-heal) EKLENMEDİ — bu görev
  sadece TESPİT yapıyor, müdahale etmiyor.

## CAVEMAN / Definition of Done Kontrolü
- Hesaplama (`_compute_process_health`) ile I/O (`_parse_pm2_jlist`) ayrı
  fonksiyonlarda — test edilebilirlik için (deepseek-balance-diff
  görevindeki aynı desen tekrarlandı, tutarlılık).
- Yeni bağımlılık/kütüphane eklenmedi.
- Magic number yok — `EXPECTED_PM2_PROCESSES` sabit liste, davranış
  tablosundaki her dal ATDD'nin AC'lerinden birine karşılık geliyor.
- Derin nesting yok (en fazla 2 seviye if/for).
