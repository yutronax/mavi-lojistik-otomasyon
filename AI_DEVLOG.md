# AI Dev Log — maviLojistik

Bu dosya, ATDD pipeline adımlarının (`atdd`/`plan`/`code-copilot`/`verify`/
`red-team`) kendi artifact dosyalarına zaten yazdığı gerçek zorluk/karar/risk
kayıtlarının **doğrudan aktarıldığı** yerdir — `commit` skill'inin 2b adımı
tarafından, yeniden yazılmadan, kaynağıyla birlikte buraya taşınır (bkz.
`commit/SKILL.md` 2b, 2026-09-12). Üzerine eklenir, geçmiş kayıt silinmez.

---

## Epic #54 — Güvenlik Açığı Düzeltmeleri (Strix Bulguları)
### Task #379 — strix-guvenlik-acigi-duzeltme (2026-09-12, commit `65c9fe6`)

**Bulunan ve düzeltilen gerçek bug (kaynak: `code_diff.md`):**
> İlk implementasyon denemesi AC-7'yi (opsiyonel CSP header) `'unsafe-inline'`
> istisnası olmadan ekledi — bu, gerçek admin panelinin tamamen bozulmasına
> yol açacak bir regresyondu (plan.md'nin tam olarak öngördüğü risk:
> "riskliyse ATLA"). İkinci bir Haiku alt-ajan dispatch'iyle sadece bu satır
> geri alındı, XSS düzeltmeleri (AC-1/6) dokunulmadan kaldı.

**Bulunan ve düzeltilen ikinci bug — test kodu hataları (kaynak:
`verify_report.md`, "Kök Neden Analizi"):**
> Üç test fonksiyonu (`test_valid_secret_missing_messages_field_returns_400`,
> `test_valid_secret_valid_shape_returns_200_and_queues`,
> `test_legitimate_html_chars_are_escaped_not_rejected`) yanlış endpoint'e
> istek atıyordu (`/whapi-webhook` yerine `/baileys-webhook` olmalıydı) ve
> bir regex bozuktu (`r'<\s*->\s*&lt;'` gerçek kodda hiç var olmayan bir "->"
> ok karakteri arıyordu). Bu üçü implementasyon değil, test-copilot'un
> yazdığı test kodundaki hatalardı — bağımsız yeniden çalıştırmayla
> doğrulandı (29 passed, 1 skipped, 0 failed).

**Bilinçli kapsam kararı (kaynak: `atdd.md`, Kapsam Dışı):**
> Baileys sidecar köprüsünün ve Whapi webhook kaydının `X-Webhook-Secret`
> header'ı göndermek üzere güncellenmesi — muhtemelen ayrı bir dil/repo,
> ayrı bir Saga görevi olarak açılmalı.

**Kabul edilen risk (kaynak: `atdd.md`, Rollback Beklentisi):**
> Secret kontrolü zorunlu ve kalıcı olacak (feature-flag yok) ama devreye
> alma sırası kritik: `WEBHOOK_SHARED_SECRET` önce Baileys sidecar'a ve
> Whapi kaydına eklenmeli, ancak ondan sonra `webhook_server.py`'de zorunlu
> hale getirilmeli. Bu görev tek başına deploy edilirse ve sidecar/Whapi
> henüz header göndermiyorsa, gerçek webhook trafiği 403 ile kesintiye
> uğrayabilir.

**Red-team'in bulduğu, kapsam dışı bırakılan bulgu (kaynak: `red_team.json`,
takip görevi olarak `spawn_task` ile açıldı — task_59ca031b):**
> do_POST içinde JSON parse, secret/auth kontrolünden ÖNCE çalışıyor.
> Kimliği doğrulanmamış bir saldırgan bozuk JSON gönderdiğinde 403 yerine
> 500 alıyor; bu da auth kontrolünün var olup olmadığı hakkında bilgi
> sızdırabilir. Düzeltmesi mevcut bir regresyon testini (`test_malformed_
> json_returns_500`) bozacağı için ayrı bir ATDD döngüsü gerektiriyor.

---

## Epic #53 — Güvenlik Otomasyonu Altyapısı (Strix & Agentic-Judge)
### Task #377 — strix-scan OpenRouter düzeltmesi (2026-09-12)

**Kök neden ve mimari karar (kaynak: oturum + `strix-scan/SKILL.md`
güncellemesi):**
> "OpenRouter yavaş/işlevsiz" sorunu aslında `STRIX_LLM=openai/auto/best-free`
> ayarıydı — OmniRoute'un ücretsiz model havuzunda round-robin yapıp
> tool-calling desteklemeyen/ücretli key isteyen sağlayıcılara düşüyordu.
> `~/.strix/cli-config.json`'un KENDİSİ kalıcı değil — Strix her çalıştırmada
> bu dosyayı o anki aktif `STRIX_LLM` Windows ortam değişkenine göre yeniden
> yazıyor; gerçek kaynak Windows User/Machine seviyesi env var (strix kurulum
> betiği tarafından ayarlanmış). `openai/auto/best` diye bir combo yok
> (`Unknown built-in auto combo`, HTTP 400) — doğru combo `openai/auto/
> best-coding` (`GET /v1/models` çıktısında `tool_calling:true` işaretli,
> gerçek taramada 66 istek/14 dk boyunca mimari hata almadan doğrulandı).

**Yan bulgu — aynı hedefe ikinci tarama tuzağı:**
> Strix, hedef yoluna göre deterministik bir run-name üretiyor; aynı hedefe
> ikinci `strix --target` çağrısı "resume?" sorusu sorup `-n` bunu atlamadığı
> için sessizce (exit 0, yeni run dizini yok) çıkabiliyor — hata mesajı
> vermiyor.

---

## Pipeline Süreç Kararları (proje-genelinde, tek göreve özel değil)

### 2026-09-12 — threat-model / frontend-pipeline / refactor / postmortem / strix-scan zorunlu karar noktaları
32 tamamlanmış görev geriye dönük tarandığında şu skillerin kullanım
oranları bulundu: `threat-model` 0/32, `frontend-pipeline` 0/32 (hatta
`vision-test` bile bypass edilmiş), `refactor` 1/32, `postmortem` 0/32,
`strix-scan` manuel çağrı dışında 0. Ortak neden: tetikleme tamamen
orkestratörün "hatırlaması"na bırakılmıştı, hiçbir zorunlu adım sormuyordu.
Düzeltme: her birine "karar zorunlu, çalıştırma koşullu" bir kontrol noktası
eklendi — `atdd` 5b (threat-model), `plan` adım 0 (frontend-pipeline),
`verify` (refactor adayı), `red-team` sonrası (strix-scan, AC-S varsa),
`commit` 11b (postmortem, eşik ≥5). Detay: `pipeline/SKILL.md`.

---

## Epic — Ayarlar Sayfası Temizliği
### Task — ayarlar-sayfasi-temizlik-tasarim (2026-09-12)

**Bulunan ve düzeltilen gerçek bug (kaynak: `code_diff.md`, "Düzeltmeler"):**
> İlk implementasyon denemesi LLM bölüm başlığına `ft.Icons.BRAIN` ikonunu
> ekledi — bu, gerçek Flet kütüphanesinde MEVCUT OLMAYAN bir üye
> (`hasattr(ft.Icons, 'BRAIN')` → False), çalışma zamanında Ayarlar sayfası
> açılır açılmaz `AttributeError` fırlatıp çökertecekti. Gerçek Flet kurulu
> ortamda `python -c "import flet as ft; ..."` ile doğrulanıp `ft.Icons.
> SMART_TOY` ile değiştirildi. Aynı geçişte kullanılmayan `AppStyles`
> import'u da temizlendi.

**Test altyapısı hatası — implementasyon değil (kaynak: `code_diff.md`):**
> test-copilot'un yazdığı test dosyası iki fixture hatası içeriyordu: (1)
> proje `pytest-asyncio` kurulu değilken `@pytest.mark.asyncio` deseni
> kullanılmıştı (projenin gerçek konvansiyonu `asyncio.run(...)` içinde
> senkron test — bkz. `tests/test_stage_merge_call_count.py`); (2) `flet`
> modülü tek bir `MagicMock()` ile stub'landığı için `ft.TextField(...)`'in
> her çağrısı AYNI mock nesnesini döndürüyordu — üç farklı form alanı
> aslında aynı objeydi, `.value` ataması birbirini eziyordu. İkisi de
> ikinci bir Haiku alt-ajan dispatch'iyle düzeltildi, orkestratör tarafından
> bağımsız `pytest` çalıştırmasıyla doğrulandı (18/18 PASS).

**Red-team bulgusu, commit öncesi düzeltildi (kaynak: `red_team.json`):**
> `llm_keys_field` (gerçek API anahtarlarını tutuyor) düz metin
> gösteriliyordu — kaldırılan `whapi_token_field`'da zaten kullanılan
> `password=True, can_reveal_password=True` deseni buna da eklendi.

**Bilinçli kapsam kararı (kaynak: `atdd.md`, Kapsam Dışı):**
> Kullanıcı "asıl gerekli ayarları ekleyelim" dedi ama somut yeni bir ayar
> listesi vermedi — bu, "yeni ayar ekleme kapsam dışı, sadece mevcut LLM
> ayarlarını koru" olarak yorumlandı (Sonnet 5 low alt-ajanı tarafından).

---

## Epic — Ayarlar Sayfası Temizliği
### Task — web-admin-panel-ayarlar-temizlik-tasarim (2026-09-12)

**Kabul edilen risk (kaynak: `atdd.md`, Risks + `red_team.json`, tekrar işaretlendi):**
> GET `/api/settings` API anahtarlarını (DEEPSEEK/GROQ/GEMINI) düz metin
> JSON olarak dönüyor — sadece `@require_auth` korumalı, bu görevden ÖNCE
> de var olan bir tasarım kararı, bu görev kapsamında düzeltilmedi. red-team
> bunu tekrar işaretledi (severity low, "ayrı bir görev gerektirir") — ileride
> maskelenmiş döndürme (son 4 karakter) bir sonraki adım olabilir.

**Threat-model bulgusu, gerçek testle kanıtlandı (kaynak: `atdd.md`, AC-S1):**
> `EDITABLE_ENV_KEYS` allowlist'inden bir anahtar çıkarmanın gerçekten
> sunucu tarafında uygulandığı (stale/eski istemci hâlâ o anahtarı
> gönderse bile `.env`'e yazılmadığı) `test_disallowed_key_not_written_to_env`
> testiyle uçtan uca (Flask `test_client()`) doğrulandı — sadece kod
> okumasıyla değil.

**Discover/Design bulgusu (kaynak: `plan.md`, `frontend-pipeline` adımı):**
> Admin panelinin hiçbir sekmesinde (sadece Ayarlar değil, tüm panelde)
> input focus stili yoktu — klavye kullanıcısı hangi alanda olduğunu
> göremiyordu. Bu görev kapsamında SADECE Ayarlar sekmesine scoped bir
> focus stili (`#set-fields input:focus`) eklendi; global `input:focus`
> eklemek diğer sekmeleri de değiştireceği için bilinçli olarak kapsam
> dışı bırakıldı — aynı iyileştirme diğer sekmelere de ayrı bir görev
> olarak uygulanabilir.

---

## Epic — Güvenlik Açığı Düzeltmeleri (Strix Bulguları)
### Task — baileys-sidecar-webhook-secret-header (2026-09-12, ACİL production kesintisi)

**Bulunan ve düzeltilen gerçek bug (kaynak: `atdd.md`, Hedef):**
> `65c9fe6` commit'i (webhook auth güvenlik düzeltmesi) `webhook_server.py`'de
> `WEBHOOK_SHARED_SECRET` kontrolünü fail-closed yaptı, ama `sidecar/bridge.js`'in
> `postToWebhook()` fonksiyonu bu header'ı hiç göndermiyordu. Sonuç: VPS'te
> GERÇEK gelen tüm WhatsApp mesajları 403 ile reddediliyordu (canlı log kanıtı:
> "secret mismatch (secret=False, header=False)"). Bu risk aslında önceki
> güvenlik görevinde ("webhook-shared-secret-auth") ÖNCEDEN yazılmıştı
> (Rollback Beklentisi: "devreye alma sırası kritik... sidecar/Whapi henüz
> header göndermiyorsa, gerçek webhook trafiği 403 ile kesintiye uğrayabilir")
> ama sıra hiç tamamlanmamıştı.

**Kritik keşif, deploy talimatını değiştirdi (kaynak: `plan.md`):**
> `ecosystem.config.js`'in `mavi-baileys-bridge` env bloğu sadece `NODE_ENV`/
> `WEBHOOK_URL` içeriyor — `bridge.js` `dotenv` KULLANMIYOR (Python tarafının
> aksine). Yani VPS'in `.env` dosyasına `WEBHOOK_SHARED_SECRET` eklemek TEK
> BAŞINA bu process'e ulaşmıyor; `ecosystem.config.js`'in `mavi-baileys-bridge`
> `env` bloğu da (VPS'teki çalışan kopyada, commit edilmeden) güncellenmeli.
> Yeni bir `dotenv` bağımlılığı eklemek CAVEMAN'a aykırı kapsam genişlemesi
> sayılıp bilinçli olarak reddedildi.

**Red-team bulgusu, commit öncesi düzeltildi (kaynak: `red_team.json`):**
> `testPostToWebhookWarnsAboutMissingSecret` testi AC-2'nin "startup'ta bir
> kez uyarı loglanır" kriterini fiilen assert etmiyordu (mock tabanlı yaklaşım,
> modül seviyesi kodun sadece ilk `require`'da çalışması yüzünden hiçbir şey
> kanıtlamıyordu). `child_process.execSync` ile taze bir alt-process açıp
> gerçek stdout/stderr çıktısını yakalayan bir teste çevrildi.

**Kabul edilen risk (kaynak: `atdd.md`, Risks):**
> Bu kod değişikliği VPS'e deploy edilse bile `.env`/`ecosystem.config.js`
> güncellenmeden sorun devam eder — iki taraflı (kod + env config) bir
> düzeltme, kod tek başına yeterli değil.

---

## Epic — AI Maliyet İzleme ve Doğruluğu
### Task — ai-hourly-spend-cap-ayarlar-panelinde (2026-09-12)

**Bulunan ve düzeltilen gerçek güvenlik/doğruluk açığı (kaynak: `red_team.json`):**
> AC-S1'in ilk implementasyonu `AI_HOURLY_SPEND_CAP_TRY` için `float(v)` +
> `value < 0` kontrolü yapıyordu — ama Python'da `float("inf")` ve
> `float("nan")` geçerli float'lardır ve `< 0` kontrolünü GEÇER (ikisi de
> `False` döner). Admin panelden "inf"/"nan" girilirse validasyon bunu kabul
> edip `.env`'e yazardı. `text_gen_parser.py:103`'teki `cost_try > cap`
> karşılaştırması `cap=inf` ise hiçbir zaman aşılmaz, `cap=nan` ise her
> zaman `False` döner — ikisi de tam olarak AC-S1'in önlemeye çalıştığı
> "harcama limiti sessizce devre dışı kalır" senaryosunu, YENİ eklenen
> validasyon katmanının ARKASINDAN yeniden açıyordu. `math.isfinite(value)`
> kontrolü eklenip 2 yeni regresyon testi (`test_post_settings_invalid_inf`,
> `test_post_settings_invalid_nan`) yazılarak kapatıldı.

**Kod-doğrulama süreci hatası, orkestratör tarafından yakalandı (kaynak:
`verify_report.md`, Coverage / Quality Notes):**
> code-copilot'un ilk implementasyon turu, yeni testleri (`test_admin_panel_
> ai_spend_cap.py`) TEK BAŞINA çalıştırıp "13/13 PASS" raporladı — ama
> mevcut `test_admin_panel_settings_cleanup.py`'deki "tam olarak 10 anahtar"
> varsayımını (önceki görevin doğru sonucu, bu görevin kasıtlı 11.
> anahtarıyla artık eskimiş) hiç kombine çalıştırmadığı için kaçırdı.
> Orkestratörün bağımsız, iki dosyayı BİRLİKTE çalıştıran doğrulaması bunu
> yakaladı — code-copilot'un kendi test raporuna asla tek başına
> güvenilmemesi gerektiğinin somut bir örneği.
