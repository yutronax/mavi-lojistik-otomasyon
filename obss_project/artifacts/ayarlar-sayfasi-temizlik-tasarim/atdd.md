---
task_slug: ayarlar-sayfasi-temizlik-tasarim
jira_id: null
saga_task_id: null
threat_model: not-applicable
priority: medium
coverage_target: 75
performance_target: null
memory_target: null
test_strategy:
  unit: 70
  integration: 25
  e2e: 5
affected_modules:
  - src/gui/pages/settings_page.py
  - src/gui/styles.py (referans, değiştirilmeyecek)
  - src/services/data_service.py (sadece incelenecek)
---

# ATDD — ayarlar-sayfasi-temizlik-tasarim

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev.

## Persona
Tek kullanıcı/admin — maviLojistik masaüstü uygulamasının sahibi. Çoklu kullanıcı/rol ayrımı yok.

## Hedef (Neden)
Ayarlar sayfasındaki kod-gerçeklik tutarsızlığını gidermek: sayfa şu an backend'de hiç okunmayan (`whapi_token`, `whapi_url`, `refresh_interval`) alanlar gösteriyor, bu kullanıcıyı yanıltıyor ("bunu değiştirirsem bir şey mi olacak?"). Sadece gerçekten işlevsel olan LLM ayarlarını bırakmak ve sayfanın görsel tasarımını gözden geçirmek.

## User Story
As a uygulama sahibi (admin)
I want Ayarlar sayfasında sadece gerçekten kullanılan ayarları görmek
So that hangi ayarın işe yaradığını anlayabilir ve kafası karışmaz

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given Ayarlar sayfası açık, When kullanıcı sayfayı görüntüler, Then sadece "LLM Yapılandırması" bölümü (llm_url, llm_model, llm_keys) gösterilir; "WhatsApp API Yapılandırması" (whapi_token, whapi_url) ve "refresh_interval" alanları/bölümleri UI'dan tamamen kaldırılmıştır.
2. [Critical] Given kullanıcı LLM alanlarından birini değiştirip Kaydet'e basar, When kaydetme işlemi çalışır, Then değer `data_service.save_config` ile `app_settings` altında diske yazılır ve `os.environ` güncellenir (mevcut davranış korunur).
3. [High] Given eski config dosyasında `whapi_token`/`whapi_url`/`refresh_interval` anahtarları hâlâ varsa, When sayfa açılır veya kaydedilir, Then bu anahtarlara dokunulmaz/silinmez, uygulama hatasız çalışır (geriye dönük zararsızlık).
4. [High] Given LLM alanlarından biri boş bırakılıp kaydedilir, When Kaydet'e basılır, Then boş string olarak kaydedilir, mevcut validasyonsuz davranış korunur (hata fırlatılmaz).
5. [Medium] Given config dosyasına yazma sırasında disk/izin hatası oluşur, When Kaydet çalıştırılır, Then kullanıcıya Flet SnackBar/dialog ile hata mesajı gösterilir, uygulama çökmez.
6. [Medium] Given sayfanın genel tasarımı gözden geçiriliyor, When sayfa render edilir, Then mevcut sade kart deseni yerine daha modern bir görsel dil uygulanır (bkz. "Tasarım Yönü" bölümü) — bölüm başlıkları ikon+etiket ile vurgulanır, alanlar arası boşluk/hiyerarşi net, kart gölgesi/köşe yumuşaklığı ve renk kullanımı `AppColors`/`AppStyles` paletinden türetilerek zenginleştirilir; diğer sayfalarla (management_center.py, server_control.py) temel renk/tema tutarlılığı bozulmaz ama Ayarlar sayfası özelinde daha modern bir versiyon hedeflenir.

## Threat Model
Tetikleyici yok — değerlendirilen tetikleyiciler: kimlik doğrulama/yetkilendirme, kullanıcı girdisi, dosya yükleme/indirme, ödeme, kişisel veri (KVKK), çok kiracılı sınır, dış API çağrısı, arka plan işi, yeni HTTP ucu. Hiçbiri uymuyor çünkü bu görev sadece mevcut bir masaüstü GUI ayarlar sayfasından zaten kullanılmayan alanları kaldırıp görsel düzenleme yapıyor; tek kullanıcılı yerel uygulama, ağ ucu/kimlik doğrulama katmanı yok, `llm_keys` zaten var olan bir alan ve bu görevde davranışı değişmiyor.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (LLM alanı değiştir + kaydet) | Fonksiyon başarıyla döner | config dosyasına yazılır, os.environ güncellenir | Başarı bildirimi (SnackBar) | AC-2 |
| 2 | Girdi geçersiz/eksik (boş alan) | Başarıyla döner (validasyon yok) | boş string kaydedilir | Değişiklik olmadan kaydedildiği görünür | AC-4 |
| 3 | Kaynak yok (config dosyası hiç yoksa) | data_service varsayılan boş config döner | dosya ilk kayıtta oluşturulur | Boş alanlarla açılır sayfa | (mevcut davranış, kapsam dışı) |
| 4 | Yetkisiz erişim | Yok | Yok | Yok | Uygulanmıyor — tek kullanıcı masaüstü uygulaması, kimlik doğrulama/rol katmanı yok |
| 5 | Dış bağımlılık hatası (disk yazma hatası) | İstisna yakalanır, hata mesajı döner | Yok (yazma başarısız) | Hata dialog/SnackBar'ı | AC-5 |
| 6 | Zaman aşımı | Yok | Yok | Yok | Uygulanmıyor — yerel dosya I/O, ağ çağrısı yok |
| 7 | Kısmi başarı | Yok | Yok | Yok | Uygulanmıyor — tek JSON yazma işlemi atomik kabul edilir, kısmi kayıt senaryosu yok |
| 8 | Hiçbir şey yapılamadı ama hata yok (değişiklik yapmadan kaydet) | Başarıyla döner | Aynı değerler tekrar yazılır | Başarı bildirimi | AC-2 (kapsamına dahil, sorun değil) |

Kısmi başarı: Uygulanmıyor (bkz. tablo satır 7).
Hiçbir şey yapılamadı ama hata da yok: Kullanıcı hiçbir alanı değiştirmeden Kaydet'e basarsa mevcut değerler aynen tekrar yazılır ve başarı bildirimi gösterilir — sessiz başarısızlık yok, gerçek bir yazma işlemi gerçekleşir.
Boş sonuç ↔ hata ayrımı: Config dosyası yoksa (boş sonuç) varsayılan boş değerlerle sayfa açılır; disk yazma hatası (gerçek hata) ayrı bir SnackBar/dialog ile kullanıcıya gösterilir — ikisi karıştırılmaz.

## Test Strategy
Unit: 70% — settings_page.py'nin state/kaydetme mantığı (ölü alanların artık üretilmediği, LLM alanlarının doğru okunup save_config'e iletildiği), data_service.py'nin app_settings okuma/yazma davranışı.
Integration: 25% — settings_page + data_service birlikte: kaydet → dosyaya yaz → tekrar oku → aynı değerler dönüyor mu; eski config'te whapi/refresh_interval anahtarları varken sayfa açılış davranışı.
E2E: 5% — Flet native GUI için gerçek e2e altyapısı yok (Playwright tabanlı webapp-testing bu pencereyi test edemez); bu oran manuel/görsel doğrulamayla (kullanıcı ekran görüntüsü onayı) karşılanacak.

## Benchmark / Başarı Ölçütü
Coverage Target: 75%
Performance Target: Yok (UI/temizlik görevi, performans hedefi anlamsız)
Memory: Yok
Görsel/UI kriteri: Ayarlar sayfası sadece LLM Yapılandırması bölümünü gösterir; whapi/refresh_interval'a ait UI kodu (TextField, state, import) tamamen kaldırılmıştır; tasarım "Tasarım Yönü" bölümündeki modernizasyon kriterlerini (ikon+etiket başlıklar, net hiyerarşi/boşluk, zenginleştirilmiş kart/gölge/renk) karşılar ve projenin temel renk temasıyla (AppColors) uyumlu kalır — bu kriter `verify` adımında görsel olarak (ekran görüntüsü, `vision-test` skill'i) doğrulanmalı.
Diğer ölçülebilir kriterler: Ayarlar sayfasında gösterilen her alanın karşılık geldiği config anahtarı backend'de en az bir yerde `os.environ` veya doğrudan okunuyor olmalı (grep ile doğrulanabilir).

## Tasarım Yönü (kullanıcı düzeltmesi: "daha modern olsun")
Kullanıcı, sayfanın sadece mevcut desenle tutarlı kalmasını değil, **görsel olarak modernize edilmesini** istedi. Somut hedef:
- Bölüm başlıkları ikon + etiket ile (ör. LLM için bir "beyin/çip" ikonu) vurgulanır, düz `Divider` yerine daha belirgin bir bölüm ayrımı kullanılır.
- Kart tasarımı zenginleştirilir: yumuşak gölge, biraz daha büyük `border_radius`, alanlar arasında net dikey ritim/boşluk (mevcut `padding=30` korunabilir veya artırılabilir).
- Form alanları (`TextField`) modern giriş bileşeni görünümüne yaklaştırılır (ör. dolgulu/rounded border, odaklanınca vurgu rengi) — Flet'in desteklediği ölçüde.
- Renk paleti `AppColors`/`AppStyles`'tan türetilir, projenin genel temasını kırmaz ama Ayarlar sayfası bu paletle en "temiz/modern" görünen sayfa olmayı hedefler.
- Bu değişiklikler sadece `settings_page.py` içinde kalır; `management_center.py`/`server_control.py` bu görevde değiştirilmez (kapsam dışı, bkz. aşağı).

## Kapsam Dışı
- Yeni bir ayar sistemi/framework kurmak
- Config JSON dosya formatını veya şemasını değiştirmek
- data_service.py'nin genel load/save mimarisini değiştirmek
- Diğer sayfaların (management_center.py, server_control.py) tasarımını değiştirmek
- Yeni ayar kalemi eklemek (kullanıcı "asıl gerekli ayarlar" için somut bir liste vermedi; mevcut LLM ayarları zaten "gerekli" olan tek grup)
- Validasyon veya migration mantığı eklemek
- Eski config dosyasındaki whapi/refresh_interval anahtarlarını diskten silmek (zararsız, dokunulmuyor)

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/gui/pages/settings_page.py` — ana değişiklik: ölü alanların UI/state kodu kaldırılacak, tasarım gözden geçirilecek
- `src/gui/styles.py` — referans alınacak (AppColors/AppStyles), değiştirilmeyecek
- `src/services/data_service.py` — sadece incelenecek, şema değiştirilmeyecek

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu makinede git reposunun kökünün proje klasörüyle aynı olup olmadığı teyit edilmedi. Sonraki adımlarda (plan, code-copilot, test-copilot, red-team) arama `src/`, `data/`, `obss_project/` gibi proje-içi dizinlerle sınırlı tutulmalı; kök dizinden sınırsız `grep -r` veya `git log -p --all` kullanılmamalı.

## Rollback Beklentisi
Otomatik yedek beklentisi yok — bu sadece UI'dan alan kaldırma işlemi, config dosyası formatı/şeması değişmediği için veri bozulma riski yok. Kod seviyesinde hata olursa git ile geri dönülür.

## Risks
- Tasarım geçişinde (kart/header stil düzenlemesi) `management_center.py`/`server_control.py` ile tutarlılığın bozulma riski — mevcut desen referans alınmalı.

## Assumptions
- `whapi_token`, `whapi_url`, `refresh_interval` alanlarının hiçbir yerde okunmadığı, önceki Explore taramasıyla (grep) doğrulandı kabul edildi.
- Kullanıcının "asıl gerekli ayarları ekleyelim" ifadesi, somut yeni bir ayar listesi vermediği için "sadece mevcut LLM ayarlarını koru, yeni ayar ekleme" olarak yorumlandı (varsayım — kullanıcı onayı gerekebilir).

## Unknowns
- Çözüldü: kullanıcı "daha modern olsun" dedi — bkz. "Tasarım Yönü" bölümü. Kesin görsel detaylar (hangi ikon, tam renk tonu) `code-copilot` adımında somutlaştırılacak, "Tasarım Yönü"ndeki kriterlere sadık kalınacak.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü/persona → Tek kullanıcı/admin (Sonnet 5 low alt-ajanı tarafından yanıtlandı: masaüstü uygulaması tek kişilik kullanım için tasarlanmış)
2. Ana hedef/neden → Kod-gerçeklik tutarsızlığını gidermek, yeni ayar eklemeyi kapsam dışı say (Sonnet 5 low alt-ajanı tarafından yanıtlandı: kullanıcı somut yeni ayar listesi vermedi)
3. Happy path → Sayfa açılır, sadece LLM alanları görünür, değiştirilir, kaydedilir (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
4. Edge case 1 (eski config anahtarları) → Dokunulmaz, zararsız (Sonnet 5 low alt-ajanı tarafından yanıtlandı: UI artık okumadığı için zararsız)
5. Edge case 2 (boş alan kaydet) → Boş string olarak kaydedilir, mevcut davranış korunur (Sonnet 5 low alt-ajanı tarafından yanıtlandı: validasyon kapsam dışı)
6. Davranış sözleşmesi tablosu → Yukarıdaki tablo (Sonnet 5 low alt-ajanı tarafından yanıtlandı, masaüstü GUI bağlamına uyarlandı)
7. Başarı ölçütü → Sadece kullanılan config anahtarları gösterilir, ölü UI kodu kaldırılır (Sonnet 5 low alt-ajanı tarafından yanıtlandı: performans hedefi bu görev için anlamsız)
8. Kapsam dışı → Yeni ayar sistemi, format değişikliği, diğer sayfa tasarımları, yeni ayar ekleme (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
9. Bağımlılıklar → settings_page.py, styles.py (referans), data_service.py (inceleme) (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
10. Güvenlik kısıtı → llm_keys maskeleme davranışı korunmalı, whapi_token kaldırıldığı için ek not gerekmez (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
11. Rollback → Otomatik yedek gerekmez, git ile kod seviyesinde geri dönüş yeterli (Sonnet 5 low alt-ajanı tarafından yanıtlandı: şema değişmiyor)
12. Kabul kriteri sahibi → Kullanıcı (görsel onay gerekir, UI görevi) (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
13. Test stratejisi → Unit 70/Integration 25/E2E 5 (Sonnet 5 low alt-ajanı tarafından yanıtlandı: Flet native GUI için e2e altyapısı yok)
14. Bilinen riskler → whapi/refresh_interval'ın kullanılmadığı zaten grep ile doğrulanmış, tasarım tutarlılığı riski var (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
