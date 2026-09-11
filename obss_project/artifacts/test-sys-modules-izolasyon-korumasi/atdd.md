---
task_slug: test-sys-modules-izolasyon-korumasi
jira_id: null
saga_task_id: 376
priority: medium
coverage_target: 70
performance_target: null
memory_target: null
test_strategy:
  unit: 60
  integration: 40
  e2e: 0
affected_modules:
  - tests/conftest.py
---

# ATDD — test-sys-modules-izolasyon-korumasi

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task #376 (epic #52 "Altyapı İzleme
ve Uyarı", proje: maviLojistik).

## Persona
Bu projede test yazan/CI'yi izleyen kişi (kullanıcının kendisi) —
gelecekte benzer bir `sys.modules` hatası yapıldığında hemen net bir hata
mesajıyla uyarılmalı.

## Hedef (Neden)
Bugün canlı olarak `tests/test_webhook_server_threading.py`'de
`sys.modules['src.parsers.veri_cekici_ayristirici'] = MagicMock()`
satırı MODÜL SEVİYESİNDE çalışıp hiç geri alınmıyordu. Pytest tüm test
dosyalarını collection aşamasında import ettiği için, bu satır tüm
sürecin paylaştığı `sys.modules` cache'ini kalıcı kirletti —
`test_junk_message_filter.py` ve `test_hourly_spend_cap.py` (7 test)
aylarca "Got: MagicMock" hatasıyla fail etti, CI hep kırmızıydı. Tek
satırlık `del sys.modules[...]` ile manuel düzeltildi (commit 08e1b5c)
ama bu SADECE o tek dosyayı düzeltti — repo'da benzer ham
`sys.modules[key] = mock` deseni kullanan en az 4 dosya daha var
(`test_junk_message_filter.py`, `test_hourly_spend_cap.py`,
`test_whapi_removed.py`, `test_dedup_active_ids_fix.py`). Bunların
çoğu ZARARSIZ (3.parti kütüphaneleri — `google`, `pymongo`, `dotenv`,
`pyngrok` — mock'luyor, birden fazla dosya AYNI şekilde kurduğu için
çakışma yok). Asıl risk SADECE projenin KENDİ modüllerini (`src.*`,
`vps_main`, `text_gen_parser`) tamamen mock'layıp geri almayan bir
dosyanın gelecekte tekrar yazılması.

`monkeypatch.setitem(sys.modules, ...)` (pytest'in otomatik-geri-alan
fixture'ı) burada KULLANILAMAZ çünkü mevcut desen collection zamanında
(modül seviyesinde, ağır bağımlılıkları geç import edilirse collection'ın
kendisi patlıyor) çalışıyor — `monkeypatch` sadece fonksiyon/fixture içi
kullanılabilir. Bu yüzden çözüm "otomatik restore" değil, "sessizce
kirlenmeyi imkansız hale getirme" (TESPİT): collection bitince
`sys.modules`'taki proje-kendi modüllerinin hâlâ gerçek mi mock mu
olduğunu kontrol edip, mock ise pytest'i AÇIKÇA ve HEMEN durdurmak.

## User Story
As a bu projede test yazan/CI'yi izleyen kişi
I want bir test dosyası projenin kendi bir modülünü mock'layıp geri
almazsa bunu collection bitiminde HEMEN ve AÇIKÇA öğrenmeyi
So that aynı hata sınıfı yeniden olduğunda kök nedeni saniyeler içinde
bulabileyim, "7 alakasız testte aylarca gizli kırmızı CI" bir daha
yaşanmasın

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given hiçbir test dosyası projenin kendi bir modülünü
   (`src.*`, `vps_main`, `text_gen_parser`) kalıcı mock'lamamış, When
   pytest collection'ı biter, Then hiçbir uyarı/hata üretilmez — mevcut
   ~290 test normal şekilde geçmeye devam eder.
2. [Critical] Given bir test dosyası `sys.modules['src.X'] = MagicMock()`
   yapıp bunu geri ALMAMIŞ (bugünkü olayın birebir tekrarı), When
   collection biter, Then `tests/conftest.py`'deki
   `pytest_collection_finish` hook'u bunu tespit edip HANGİ modülün kirli
   olduğunu belirten net bir mesajla pytest sürecini durdurur (`pytest.exit`)
   — testler "sessizce" MagicMock alıp yanlış sonuç üretmez.
3. [Critical] Given bir test dosyası fonksiyon/fixture İÇİNDE
   `monkeypatch.setitem(sys.modules, 'src.X', mock)` kullanıyor (geçici,
   test bitince pytest tarafından otomatik geri alınıyor), When collection
   biter, Then bu YANLIŞLIKLA "kirlilik" olarak işaretlenmez — kontrol
   sadece collection ANINDA/SONRASINDA kalıcı olan durumu görür, çalıştırma
   anındaki geçici monkeypatch'leri hiç görmez (zaman dilimi farkı).
4. [High] Given birden fazla proje-kendi modül aynı anda kirli (ör. hem
   `src.parsers.veri_cekici_ayristirici` hem `src.utils.reporter` mock
   kalmış), When hook çalışır, Then TÜM kirli modüller tek bir hata
   mesajında listelenir — sadece ilkini bulup durmaz.
5. [High] Given `sys.modules`'ta proje-kendi bir modül anahtarı HİÇ YOK
   (henüz hiç import edilmemiş, ör. `text_gen_parser` bu test dosyası
   grubunda hiç kullanılmamış), When hook çalışır, Then bu bir hata
   SAYILMAZ — sadece MEVCUT olup da gerçek modül yerine mock olan durum
   kontrol edilir, "hiç import edilmemiş" ile "mock olarak import edilmiş"
   ayrılır.

## Davranış Sözleşmesi (hangi durumda ne döner)
Bu bir pytest hook'u — dış girdi/HTTP endpoint yok, tek temas noktası
`pytest_collection_finish(session)` hook'unun kendisi.

| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: hiçbir proje modülü kirli değil | N/A (hook sessizce döner) | Yok | Normal test çıktısı, ekstra mesaj yok | AC-1 |
| 2 | Bir proje modülü kirli (MagicMock) | N/A | `pytest.exit()` ile süreç durdurulur | "KİRLENME TESPİT EDİLDİ: <modül_adı> gerçek modül değil, bir MagicMock. Muhtemel neden: bir test dosyasının sys.modules['<modül_adı>'] atamasını geri almaması." mesajı | AC-2 |
| 3 | Geçici monkeypatch (fonksiyon içi, test bitince otomatik geri alınmış) | N/A | Yok — collection-finish anında zaten temiz | Normal test çıktısı | AC-3 |
| 4 | Birden fazla modül kirli | N/A | `pytest.exit()` | Tek mesajda TÜM kirli modüllerin listesi | AC-4 |
| 5 | Proje modülü `sys.modules`'ta hiç yok (hiç import edilmemiş) | N/A | Yok — kontrol dışı, hata değil | Normal test çıktısı | AC-5 |

Kısmi başarı: N/A — bu satır atlanıyor çünkü hook'un tek işi bir
tarama+karar, "kısmen tespit etme" diye bir ara durum yok (ya kirli
modül bulunur ya bulunmaz, atomik bir kontrol).
Hiçbir şey yapılamadı ama hata da yok: `PROJECT_OWN_MODULE_PREFIXES`
listesi boşsa veya hiçbiri `sys.modules`'ta yoksa, hook sessizce
"kontrol edilecek bir şey yok" der ve geçer — bu YANLIŞ bir "her şey
temiz" izlenimi DEĞİL, çünkü zaten kontrol edilecek modül yoksa
kirlenme de yok.
Boş sonuç ↔ hata ayrımı: "hiç import edilmemiş modül" (AC-5, hata değil)
ile "mock olarak import edilmiş modül" (AC-2, hata) `sys.modules`'ta
anahtarın VAR OLUP OLMADIĞI + `isinstance(value, MagicMock)` kontrolüyle
kesin ayrılır.

## Test Strategy
Unit: 60% — hook'un karar mantığı (`_find_polluted_project_modules`
gibi saf bir fonksiyona ayrıştırılıp) sahte `sys.modules` sözlükleriyle
izole test edilir: hiç kirlilik yok, bir modül kirli, birden fazla
modül kirli, modül hiç yok (henüz import edilmemiş)
Integration: 40% — gerçek bir pytest alt-süreci (`subprocess.run(["pytest", ...])`)
KASITLI olarak kirletilmiş sahte bir test dosyasıyla çalıştırılıp
hook'un GERÇEKTEN pytest'i durdurduğu ve doğru mesajı bastığı doğrulanır
E2E: 0% — bu bir test-altyapı aracı, e2e kavramı uygulanamaz

## Benchmark / Başarı Ölçütü
Coverage Target: 70%
Performance Target: yok (collection bitişinde bir kez çalışan basit bir
`sys.modules` döngüsü, ihmal edilebilir maliyet)
Memory: yok
Diğer ölçülebilir kriterler:
- Aynı hata sınıfı tekrar oluşursa, CI logunda kök neden (kirlenen modül
  adı) İLK BAKIŞTA görünmeli — "7 alakasız testte aylarca fark edilmeme"
  senaryosu bir daha YAŞANMAMALI.

## Kapsam Dışı
- Mevcut 4 test dosyasındaki (`test_junk_message_filter.py`,
  `test_hourly_spend_cap.py`, `test_whapi_removed.py`,
  `test_dedup_active_ids_fix.py`) ham `sys.modules` kullanımlarını
  `monkeypatch`'e REFACTOR etmek — bu görev SADECE tespit mekanizmasını
  ekliyor, mevcut dosyalara dokunmuyor (zaten zararsız 3.parti kütüphane
  mock'ları).
- 3.parti kütüphanelerin (`google`, `pymongo`, `dotenv`, `pyngrok`)
  mock'lanmasını yasaklamak/hata saymak — bunlar meşru ve zararsız,
  sadece PROJENİN KENDİ modülleri (`src.*`, `vps_main`,
  `text_gen_parser`) hedef alınacak.
- Gerçek zamanlı (her test fonksiyonundan sonra) kontrol —
  `pytest_collection_finish` SADECE collection bitişinde bir kez çalışır,
  test ÇALIŞTIRMA sırasında ara ara kontrol YAPILMIYOR (performans +
  basitlik tercihi, collection-time kirlenme zaten collection bitişinde
  yakalanabiliyor).

## Etkilenen Dosyalar/Modüller (bilinen)
- `tests/conftest.py` — proje kökünde `tests/` altında şu an bir
  `conftest.py` olup olmadığı DOĞRULANMADI, `plan` adımında kontrol
  edilecek. Yoksa yeni oluşturulacak, varsa `pytest_collection_finish`
  hook'u eklenecek.

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — `plan` adımından önce `git rev-parse --show-toplevel` ile
tekrar doğrulanmalı; arama maviLojistik worktree kökü ile sınırlı
tutulmalı.

## Rollback Beklentisi
Additive bir test-altyapı değişikliği — mevcut hiçbir testi bozmuyor,
sadece yeni bir kontrol ekliyor. Hata durumunda `git revert` yeterli.

## Risks
- **"Proje kendi modülü" tanımı net listelenmezse** (`src.` prefix +
  `vps_main`/`text_gen_parser` gibi üst-seviye dosyalar) hook kendisi
  false-positive/false-negative üretebilir — `plan` adımında gerçek
  proje yapısı (`Glob` ile üst-seviye `.py` dosyaları + `src/` altındaki
  paketler) taranarak bu liste netleştirilmeli.
- Bu liste gelecekte yeni üst-seviye modül eklenirse MANUEL
  güncellenmesi gerekecek — `pm2-process-izleme-ve-uyari` görevindeki
  `EXPECTED_PM2_PROCESSES` ile AYNI bakım deseni/riski.
- Mevcut 4 test dosyasının TAMAMININ `sys.modules` kullanım deseni tam
  taranmadı — `plan` adımında gerçek kod okunarak doğrulanmalı, başka
  kirletilmiş-ama-henüz-fark-edilmemiş bir modül olabilir.

## Assumptions
- pytest'in `pytest_collection_finish(session)` hook'u `conftest.py`'de
  tanımlanabilir ve collection TAMAMLANDIKTAN (tüm dosyalar import
  edildikten) SONRA, herhangi bir test ÇALIŞMADAN ÖNCE tetiklenir.
- Mevcut `tests/` dizininin proje kökünde olduğu ve `pytest.ini`'nin
  `testpaths = tests` dediği (daha önce bu oturumda doğrulanmıştı).

## Unknowns
- `tests/conftest.py`'nin şu an var olup olmadığı — `plan` adımında
  netleşecek.
- Diğer 4 test dosyasının TAM `sys.modules` kullanım deseni (hangi
  satırlar modül-seviyesinde, hangileri fonksiyon-içi) — `plan`
  adımında gerçek kod okunarak çıkarılacak.

## Sorular ve Cevaplar (ham kayıt)
1. Persona → Kullanıcının kendisi, test yazan/CI izleyen kişi (Sonnet 5
   low alt-ajanı tarafından yanıtlandı)
2. Ana hedef/neden → Kirlenmenin anında/açıkça tespit edilmesi, "aylarca
   gizli kırmızı CI" bir daha olmasın (Sonnet 5 low alt-ajanı tarafından
   yanıtlandı)
3. Happy path → Kirlilik yoksa sessiz, 290 test normal geçer (Sonnet 5
   low alt-ajanı tarafından yanıtlandı)
4. Edge case (yeniden kirlenme) → hook tespit edip pytest'i durdurur,
   hangi modül olduğunu söyler (Sonnet 5 low alt-ajanı tarafından
   yanıtlandı)
5. Edge case (meşru geçici monkeypatch) → yanlış pozitif olmaz, zaman
   dilimi farkı nedeniyle (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
6. Davranış sözleşmesi → yukarıdaki tablo (Sonnet 5 low alt-ajanı
   tarafından dolduruldu)
7. Başarı ölçütü → kök neden ilk bakışta görünür olmalı, coverage %70
   (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
8. Kapsam dışı → mevcut dosyalara dokunma, 3.parti mock'ları yasaklama
   (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
9. Bağımlılıklar → tests/conftest.py (Sonnet 5 low alt-ajanı tarafından
   yanıtlandı)
10. Performans/güvenlik kısıtı → yok (Sonnet 5 low alt-ajanı tarafından
    yanıtlandı)
11. Rollback → git revert yeterli, additive (Sonnet 5 low alt-ajanı
    tarafından yanıtlandı)
12. Kabul kriteri sahibi → kullanıcı + otomatik testler (Sonnet 5 low
    alt-ajanı tarafından yanıtlandı)
13. Test stratejisi → 60/40/0 (Sonnet 5 low alt-ajanı tarafından
    yanıtlandı)
14. Riskler/varsayımlar → "proje kendi modülü" tanımının netleşmesi
    gerekiyor, bakım riski EXPECTED_PM2_PROCESSES ile aynı desen (Sonnet
    5 low alt-ajanı tarafından yanıtlandı)
