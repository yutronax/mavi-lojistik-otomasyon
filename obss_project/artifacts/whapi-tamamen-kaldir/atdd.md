---
task_slug: whapi-tamamen-kaldir
jira_id: null
saga_task_id: 357
priority: high
coverage_target: 85
performance_target: null
memory_target: null
test_strategy:
  unit: 70
  integration: 25
  e2e: 5
affected_modules:
  - src/api/admin_panel.py
  - src/fetchers/whapi_fetcher.py
  - src/parsers/veri_cekici_ayristirici.py
  - src/api/webhook_server.py (kısmi — sadece kesin VPS-only kısımlar, plan.md'de netleşecek)
---

# ATDD — whapi-tamamen-kaldir

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev (Saga task #357, epic #46 altında)

## Persona
Sistemin tek operatörü/sahibi (kullanıcının kendisi).

## Hedef (Neden)
Baileys migration'ı (Saga epic #46) tamamlandı, mesaj alma tamamen Baileys üzerinden çalışıyor (`WHAPI_POLLING_ENABLED=0`). Ama VPS/üretim kod tabanında Whapi'ye giden aktif API çağrıları hâlâ var (grup listeleme, health check). Kullanıcı VPS/üretim tarafında Whapi'ye giden HİÇBİR bağlantı kalmaması istiyor — ücretli Whapi hizmetine artık tamamen bağımsız olmak.

## User Story
As a sistem operatörü
I want VPS/üretim kod tabanında Whapi'ye giden tüm aktif API çağrılarının kaldırılmasını
So that Whapi hizmetine (ve maliyetine) tamamen bağımsız hale gelebileyim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `src/api/admin_panel.py`'de `/api/groups/available` route'u (Whapi'den grup listesi çeken, `gate.whapi.cloud/groups` çağıran), When bu görev tamamlanır, Then bu route ve panelin "kayıtsız grupları tara/ekle" bölümü (frontend) tamamen kaldırılmış olur — Whapi'ye hiçbir istek gitmez.
2. [Critical] Given `/api/whatsapp-health` route'u (`gate.whapi.cloud/health` çağıran), When bu görev tamamlanır, Then bu route tamamen kaldırılmış olur (panel zaten `/api/whatsapp/qr` ile Baileys durumunu gösteriyor, bu route artık redundant).
3. [Critical] [DÜZELTİLDİ — plan adımında bulundu] Given `src/fetchers/whapi_fetcher.py` (Whapi'ye özel REST client) GUI tarafından (`masaustu_uygulama.py`, `management_center.py`, `yonetim_merkezi.py`, `managers.py`) aktif kullanılıyor, When bu görev tamamlanır, Then dosyanın KENDİSİ SİLİNMEZ (GUI kapsam dışı, silmek GUI'yi kırar) — bunun yerine VPS çalışma zamanının (`vps_main.py` → `run_vps_service` → `orchestrator.run_loop`) `WHAPI_POLLING_ENABLED=0` iken `whapi_fetcher`'daki HİÇBİR fonksiyonu (lazy import olsalar bile) ÇAĞIRMADIĞI doğrulanır.
4. [High] Given `src/parsers/veri_cekici_ayristirici.py`'deki `WHAPI_AVAILABLE`/Whapi'ye bağımlı yardımcı fonksiyonlar (mesaj polling DIŞINDA, `WHAPI_POLLING_ENABLED` zaten mevcut ve mesaj polling'i kapatıyor), When kod incelenir, Then Whapi'ye özel import/fonksiyon çağrıları (`whapi_fetcher` importu dahil) kaldırılır; `WHAPI_POLLING_ENABLED` flag'inin kendisi (mesaj akışını yöneten ana mekanizma) korunur — flag'i silmek kapsam dışı, sadece Whapi'ye giden GERÇEK ağ çağrıları kaldırılıyor.
5. [High] Given data/chat_groups.json'a dayanan MEVCUT `/api/groups` route'u (kayıtlı grupları listeleme/silme, Whapi'ye HİÇ bağımlı değil, sadece yerel JSON okuyor), When bu görev tamamlanır, Then bu route ve ilgili frontend ("Kayıtlı Gruplar" bölümü) DEĞİŞMEDEN çalışmaya devam eder.
6. [Medium] Given `.env`'deki `WHATSAPP_TOKEN` değişkeni, When kod tabanı taranır, Then bu değişkeni okuyan HİÇBİR kod satırı kalmaz (route'lar silindiği için otomatik olarak sağlanır) — `.env` dosyasının kendisi (VPS'te canlı, kullanıcı elle yönetiyor) bu görev kapsamında DEĞİŞTİRİLMEZ.
7. [Medium] [DÜZELTİLDİ — plan adımında bulundu] Given `src/api/webhook_server.py` GUI tarafından da import ediliyor (`masaustu_uygulama.py`'nin `run_server`/`stop_server` fonksiyonları bu dosyadan geliyor — PAYLAŞILAN dosya), When bu görev tamamlanır, Then bu dosyaya HİÇ DOKUNULMAZ (GUI'nin `run_server()`/`setup_webhook()` akışını bozma riski, kullanıcının GUI'yi kapsam dışı bırakma kararıyla çelişir) — VPS akışı zaten sadece `make_webhook_handler_class`'ı import ediyor, `run_server()`/`setup_webhook()`'u hiç çağırmıyor, bu yeterli izolasyon sayılır.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | `/api/groups/available` çağrılırsa (kaldırıldıktan sonra) | `404 Not Found` (Flask varsayılan, route artık yok) | yok | Panel bu route'u artık çağırmıyor (frontend butonu da silindi), doğrudan URL'e gidilirse 404 | AC-1 |
| 2 | `/api/whatsapp-health` çağrılırsa (kaldırıldıktan sonra) | `404 Not Found` | yok | Panel bu route'u artık çağırmıyor, doğrudan URL'e gidilirse 404 | AC-2 |
| 3 | `/api/groups` (kayıtlı gruplar, Whapi'siz) çağrılır | DEĞİŞMEDİ — mevcut davranış korunur | yok | "Kayıtlı Gruplar" bölümü eskisi gibi çalışır | AC-5 |
| 4 | Kod tabanında `import whapi_fetcher` veya `gate.whapi.cloud` araması yapılırsa | Sıfır sonuç (grep ile doğrulanabilir) | yok | — | AC-3, AC-6 |
| 5 | **Kısmi başarı**: bazı Whapi çağrıları kaldırıldı ama `whapi_fetcher.py` hâlâ bir yerden import ediliyorsa | Import hatası (ImportError) veya ölü kod — TAM sayılmaz | yok | Test suite'i (grep-tabanlı regresyon testi, aşağıya bkz.) FAIL verir | AC-3 |
| 6 | Mesaj alma akışı (Baileys → webhook → orchestrator) | DEĞİŞMEDİ — bu görev mesaj akışına dokunmuyor | yok | Mesajlar eskisi gibi işlenmeye devam eder | (regresyon, AC yok) |

Kısmi başarı: Whapi'ye giden bazı çağrılar kaldırılıp bazıları unutulursa, bu görev TAMAMLANMIŞ sayılmaz — "grep whapi = sıfır sonuç (gerçek kod satırlarında, yorum/docstring hariç)" kriteri kesin bir tamamlanma testi olarak kullanılacak.
Hiçbir şey yapılamadı ama hata da yok: Uygulanamaz — bu bir kod kaldırma görevi, ya dosyalar/route'lar gerçekten silinir (grep ile doğrulanabilir) ya da görev eksik kalır.
Boş sonuç ↔ hata ayrımı: Uygulanamaz (bu görev bir API endpoint'i değil, bir kod temizliği).

## Test Strategy
Unit: 70% — Whapi importlarının hiçbir dosyada kalmadığını doğrulayan grep-tabanlı bir regresyon testi (`test_whapi_removed.py` gibi, `subprocess`/`os.walk` ile kod tabanını tarayıp `whapi`/`WHAPI_TOKEN`/`gate.whapi.cloud` string'lerinin (yorum/docstring hariç, sadece aktif kod satırlarında) sıfır olduğunu assert eder), silinen route'ların gerçekten 404 döndüğünü doğrulayan testler.
Integration: 25% — `/api/groups` (kayıtlı gruplar) route'unun DEĞİŞMEDEN çalıştığını doğrulayan mevcut/yeni testler, Baileys webhook akışının (mevcut testler) hâlâ yeşil olduğunu doğrulama.
E2E: 5% — panelin "Gruplar" sekmesinin, "kayıtsız grup" bölümü olmadan doğru render olduğunu canlı tarayıcıda doğrulama (önceki görevlerde JS-kaçış hataları canlı testte bulunmuştu, aynı titizlik).

## Benchmark / Başarı Ölçütü
Coverage Target: 85%
Performance Target: yok
Memory: yok
Görsel/UI kriteri: panelin "Gruplar" sekmesi, "kayıtsız grup tarama" bölümü kaldırıldıktan sonra bozuk/eksik görünmemeli (layout kırılmamalı) — `verify` adımında canlı tarayıcıyla kontrol edilecek.
Diğer ölçülebilir kriterler: `grep -ri "whapi" --include=*.py <VPS-ilgili dosyalar>` sonucu sıfır aktif kod satırı (yorum/docstring/değişken adı geçmişi hariç tutulabilir, ama gerçek API çağrısı/import KESİNLİKLE sıfır olmalı).

## Kapsam Dışı
- Masaüstü GUI uygulaması (`masaustu_uygulama.py`, `management_center.py`, `settings_page.py` ve bağlı diğer GUI dosyaları) — kullanıcı bunu açıkça kapsam dışı bıraktı, hâlâ Whapi kullanabilir.
- Baileys'e "grup listesi çekme" özelliği EKLEMEK (bridge.js'e yeni bir yetenek eklemek) — bu ayrı, büyük bir görev olmalı, bu görev sadece Whapi çağrılarını KALDIRIYOR, yerine yeni bir şey KOYMUYOR.
- Whapi hesabının/API aboneliğinin iptali — bu bir iş kararı, kullanıcının kendisi yapacak.
- `.env` dosyasının VPS'te elle düzenlenmesi (WHATSAPP_TOKEN silme) — kod tarafında bu değişkeni okuyan satır kalmayacağı için gereksiz, VPS `.env`'ine dokunulmuyor.
- Yeni bir feature-flag mekanizması eklemek (örn. "WHAPI_FALLBACK_ENABLED") — kullanıcı açıkça "kaldır" dedi, ek bir toggle katmanı kullanıcının istemediği bir karmaşıklık olurdu (bkz. Assumptions).
- Veritabanı/geçmiş Whapi verisi temizliği (data/*.json içindeki eski Whapi kaynaklı kayıtlar) — bu görev sadece kod tabanını temizliyor, veriye dokunmuyor.

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py` — `/api/groups/available` route'u, `/api/whatsapp-health` route'u, ilgili frontend (kayıtsız grup tarama bölümü) silinir.
- `src/fetchers/whapi_fetcher.py` — dosyanın tamamı silinir (hiçbir yerden import edilmiyorsa, `plan` adımında doğrulanacak).
- `src/parsers/veri_cekici_ayristirici.py` — `whapi_fetcher` importu ve Whapi'ye özel yardımcı çağrılar kaldırılır, `WHAPI_POLLING_ENABLED` flag'i ve ana akış korunur.
- `src/api/webhook_server.py` — VPS akışının gerçekten kullanmadığı Whapi-özel kod (varsa) kaldırılır; tam kapsam `plan` adımında kod okunarak netleşecek (bu dosya hem GUI hem VPS tarafından paylaşılıyor olabilir, dikkatli incelenmeli).
- `vps_main.py` — sadece yorum satırlarında Whapi geçiyor gibi görünüyor, aktif çağrı yoksa dokunulmayabilir (`plan` adımında doğrulanacak).

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — önceki görevlerde bu makinede git reposu kökünün proje klasörüyle örtüştüğü gözlemlendi. Yine de sonraki adımlar (`plan`, `code-copilot`, `test-copilot`, `red-team`) Grep/Glob çağrılarını gerçek proje klasörüyle (`.claude/worktrees/festive-pare-2fb538`) sınırlamalı. Bu görev için özellikle önemli: kod tabanı genelinde 24 dosyada "whapi" geçiyor (GUI dahil) — arama SADECE `affected_modules` listesindeki VPS-ilgili dosyalarla sınırlı tutulmalı, GUI dosyalarına (masaustu_uygulama.py vb.) YANLIŞLIKLA dokunulmamalı.

## Rollback Beklentisi
Bu bir kod kaldırma görevi olduğu için rollback = `git revert` (bu commit'i geri almak, silinen dosya/route'ları geri getirir). Ayrı bir feature-flag mekanizması EKLENMİYOR (bkz. Kapsam Dışı) — kullanıcı "kaldır" dedi, git geçmişi zaten yeterli bir güvenlik ağı sağlıyor.

## Risks
- `src/api/webhook_server.py`'nin GUI ile VPS arasında paylaşılan bir dosya olma ihtimali — eğer GUI de bu dosyayı import ediyorsa, dosyadaki Whapi-özel kodu (örn. `setup_webhook()`) kaldırmak GUI'yi bozabilir. `plan` adımında bu paylaşım netleştirilmeden bu dosyaya dokunulmamalı.
- Kısmi temizlik riski: 24 dosyada "whapi" geçtiği tespit edildi, bunlardan çoğu GUI'ye ait ve kapsam dışı — ama VPS-ilgili dosyaların TAM listesi `plan` adımında kesinleşmeden code-copilot'a geçilirse, bir dosya atlanabilir (AC-3/AC-6'nın "sıfır sonuç" kriteri bunu yakalayacak, ama yine de dikkat gerekiyor).

## Assumptions
- `WHATSAPP_TOKEN` env değişkeninin `.env` dosyasından silinmesi kapsam dışı bırakıldı — kod tarafında okunmadığı sürece zararsız bir "yetim" değişken olarak kalır, VPS'in canlı `.env`'ine dokunmak (kullanıcı elle yönetiyor) bu görevin riskini gereksiz yere artırır.
- Haiku alt-ajanının önerdiği "feature-flag" (WHAPI_FALLBACK_ENABLED) yaklaşımı REDDEDİLDİ — kullanıcının "kaldır, hiç bağlantı kalmasın" ifadesi net bir "sil" talimatı, ek bir toggle katmanı CAVEMAN ilkesine ve kullanıcının açık isteğine aykırı olurdu. Bunun yerine basit silme + git-revert rollback tercih edildi.
- `src/api/webhook_server.py`'nin tam kapsamı (GUI ile paylaşılıp paylaşılmadığı) bu aşamada NETLEŞMEDİ — `plan` adımında kod okunarak kesinleştirilecek (bkz. Unknowns).

## Unknowns
- `src/api/webhook_server.py`'nin GUI tarafından da import edilip edilmediği — `plan` adımında `Grep` ile netleştirilecek.
- `vps_main.py`'de gerçekten aktif bir Whapi çağrısı olup olmadığı (şu an sadece yorum satırları görünüyor) — `plan` adımında doğrulanacak.

## Sorular ve Cevaplar (ham kayıt)
(Kullanıcı mesajından: kapsam sadece VPS/üretim tarafı, GUI kapsam dışı — AskUserQuestion ile netleştirildi, bu kategori için Haiku'ya sorulmadı.)
(Haiku alt-ajanı tarafından yanıtlandı — general-purpose agent, model: haiku)
1. Grup listesi özelliği → tamamen kaldırılsın (Baileys'in bu yeteneği yok, broken feature bırakılmamalı).
2. `/api/whatsapp-health` → silinsin (redundant, `/api/whatsapp/qr` zaten Baileys durumunu gösteriyor).
3. UI'da "kayıtsız grup tarama" → bölüm tamamen kaldırılsın.
4. `WHATSAPP_TOKEN` → Haiku ".env'de kalsın" önerdi, ama orkestratör "kod tarafında okunmadığı için zararsız, dokunulmasın (VPS canlı .env'i)" kararını verdi (Assumptions'a işlendi).
5. `whapi_fetcher.py` → tamamen silinsin (ölü kod, CAVEMAN).
6. `webhook_server.py`'deki Whapi-özel kod → "Unknown, plan adımında netleşecek" olarak işlendi (Haiku'nun "dokunma" önerisi kısmen kabul edildi, ama tam kapsam plan'a bırakıldı).
7. Gruplar sekmesi UI → "Kayıtlı Gruplar" kalsın, "kayıtsız tarama" silinsin.
8. `/api/groups` (kayıtlı) → kapsam dışı, değişmeyecek.
9. Test oranı → 70/25/5 (Haiku'nun 80/15/5 önerisi, orkestratör tarafından projenin genel deseniyle (60-70/20-25/5-15) tutarlı hale getirilerek hafif ayarlandı).
10. Kapsam dışı → Baileys'e grup listeleme eklemek, GUI, Whapi hesap iptali, .env düzenleme, feature-flag, veri temizliği.
11. Rollback → Haiku'nun "feature-flag" önerisi REDDEDİLDİ, basit `git revert` tercih edildi (Assumptions'a gerekçesiyle işlendi).
12. Risk (kısmi WHATSAPP_TOKEN temizliği) → gerçek bir risk, grep-tabanlı doğrulama testiyle (AC-3/AC-6) ele alınıyor.
