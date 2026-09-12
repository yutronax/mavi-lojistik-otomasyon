# Test Diff — strix-guvenlik-acigi-duzeltme (Red Step)
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar
- `tests/test_webhook_shared_secret_auth.py` (11 test metodu)
- `tests/test_admin_panel_message_id_xss.py` (10 test metodu)

## AC → Test Eşleşmesi
| AC | Test Dosyası | Sınıf/Metod |
|---|---|---|
| AC-1 (XSS: data-mid + escapeHtml) | test_admin_panel_message_id_xss.py | `TestAC1_XSSPayloadEscaping` (5 metod) |
| AC-2 (403 invalid/missing secret) | test_webhook_shared_secret_auth.py | `TestAC2_UnauthorizedAccess` (2 metod) |
| AC-3 (fail-closed, secret tanımsız) | test_webhook_shared_secret_auth.py | `TestAC3_FailClosedBehavior` (1 metod) |
| AC-4 (400 geçersiz JSON şekli) | test_webhook_shared_secret_auth.py | `TestAC4_InvalidJsonShape` (2 metod) |
| AC-5 (200 + kuyruğa ekleme, happy path) | test_webhook_shared_secret_auth.py | `TestAC5_HappyPath` (1 metod) |
| AC-6 (meşru HTML karakteri escape edilir, reddedilmez) | test_admin_panel_message_id_xss.py | `TestAC6_LegitimateCharactersEscaped` (1 metod) |
| AC-7 (opsiyonel CSP header) | test_admin_panel_message_id_xss.py | `TestAC7_CSPHeader` (1 metod, CSP yoksa skip) |
| Kaynak-kod regresyon/yapı kontrolleri | her iki dosya | `TestSourceCodeVerification` / `TestSourceCodeStructure` / `TestMessageIDPatterns` |

## Davranış Sözleşmesi Satırı → Test
| Satır | Durum | Test |
|---|---|---|
| 1 | Happy path (200+kuyruk) | `TestAC5_HappyPath.test_valid_secret_valid_shape_returns_200_and_queues` |
| 2 | Girdi geçersiz (400) | `TestAC4_InvalidJsonShape` (2 metod) |
| 4 | Yetkisiz erişim (403) | `TestAC2_UnauthorizedAccess` + `TestAC3_FailClosedBehavior` |
| "Hiçbir şey yapılamadı ama hata yok" YASAĞI | mevcut "önce 200, sonra işle" davranışının kaldırılması | `TestSourceCodeVerification.test_do_post_response_order_auth_before_200` |

## Düzeltme Notu (2. dispatch)
İlk yazımda `TestAC4_InvalidJsonShape` ve `TestAC5_HappyPath`'teki 3 test, `WEBHOOK_SHARED_SECRET`'ı hiç set etmiyor ve `X-Webhook-Secret` header'ı göndermiyordu — bu haliyle code-copilot doğru implementasyonu yapsa bile bu testler hep 403 alıp asla "geçerli secret" senaryosunu test edemeyecekti. İkinci bir Haiku alt-ajan dispatch'iyle düzeltildi: modül seviyesinde `TEST_WEBHOOK_SECRET` sabiti eklendi, `@patch.dict(os.environ, {'WEBHOOK_SHARED_SECRET': TEST_WEBHOOK_SECRET})` + `X-Webhook-Secret` header'ı her üç teste eklendi. `TestAC2`/`TestAC3` zaten doğruydu, dokunulmadı.

## Doğrulanan Durum (Red)
Testler henüz çalıştırılmadı (bu adımın işi değil — `verify` adımında çalıştırılacak). Şu an implementasyon yok, dosyalar diskte mevcut (`git status --short` ile doğrulandı).

## Varsayımlar
- `secrets.compare_digest` kullanılacağı varsayıldı (plan.md'nin `admin_panel.py:164` tutarlılık kararına uygun), testler hem `compare_digest` hem `hmac` string aramasını kabul ediyor.
- Test secret değeri: `"test-secret-for-atdd-red-step"` — code-copilot'un gerçek `.env` değeriyle bir ilgisi yok, sadece test ortamı için.
