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
