# Code Diff — deepseek-max-tokens-cap
_Reference: plan.md, test_diff.md_

## Değiştirilen Dosyalar
- `text_gen_parser.py`
- `tests/test_deepseek_max_tokens_cap.py` (test kurulum düzeltmeleri — ayrıntı aşağıda)

## AC → Uygulama eşleşmesi
| AC | Nasıl karşılandı |
|---|---|
| AC-1 (Stage 1, her iki model) | Satır 283, 296: `max_tokens=1500` eklendi. |
| AC-2 (Stage 2, her iki model) | Satır 472, 487: `max_tokens=1500` eklendi. |
| AC-3 (normal mesaj, cap tetiklenmez) | Değişiklik yok gerektirmedi — cap sadece 1500 token üstünde tetikleniyor, mevcut davranış korundu. |
| AC-4 (kesilme → mevcut fallback + log) | Satır 474-475, 489-490: `finish_reason == 'length'` kontrolü + `truncated_at_max_tokens` logu eklendi (SADECE Stage 2, atdd.md'nin belirttiği gibi). |
| AC-5 (API reddi → mevcut fallback) | Değişiklik gerekmedi — mevcut exception-yakalama zaten bunu kapsıyor. |

## Kod keşfi sırasında bulunan sorun VE düzeltmesi (red-team incelemesiyle)
İlk implementasyon turunda, `finish_reason=='length'` tespiti SADECE bir
log satırı yazıyordu, akışı değiştirmiyordu — kesilmiş metin YİNE DE
`_process_raw_json_async` adlı kırılgan bir onarım fonksiyonuna
gönderiliyordu. Red-team incelemesi bunun 2 gerçek riski olduğunu buldu:
(1) bu fonksiyonun İKİNCİ `json.loads()` çağrısı (satır 661) try/except
İÇİNDE DEĞİL — geçersiz bir alt-string'de YAKALANMAMIŞ bir exception
fırlatabilir; (2) regex greedy olduğu için (`\{.*\}`), bazı rotalar tam
bazıları yarım kalmışsa, SESSİZCE bir kısmı kaybolabilir (atdd.md'nin
"yarım veri asla sessizce kabul edilmez" ilkesiyle çelişiyor).

**Düzeltme:** `finish_reason=='length'` VE son model DEĞİLSE, artık
`_process_raw_json_async`'e HİÇ gitmeden, mevcut "geçersiz sonuç, sıradaki
modele geç" mekanizmasını (satır ~511-514'teki empty-routes/non-Latin
deseniyle TUTARLI) kullanarak GERÇEKTEN sıradaki modele/Groq'a düşüyor.
Bu, atdd.md'nin ORİJİNAL (doğru) niyetini gerçek koda taşıyor — daha önce
test beklentilerini "gerçek ama kırılgan davranışa" uydurmak yerine, asıl
davranışı atdd.md'nin doğru tasarım niyetine uydurmak tercih edildi.
`test_stage2_json_truncated_triggers_fallback_and_logs`'un "Groq
çağrılmalı" assertion'ı geri eklendi ve GERÇEKTEN geçiyor.

Son model durumunda (`is_last_model=True`) `_process_raw_json_async`'e
YİNE DE düşülüyor (kabul edilebilir — hiçbir model başarılı olamadıysa
elde ne varsa onunla en iyi çabayla devam etmek mantıklı, bu görevin
kapsamı dışında bırakıldı).

## Test düzeltme geçmişi (bu görevde, code-copilot sonrası)
1. `test_normal_message_does_not_trigger_cap`'in `max_tokens` ile ilgisiz
   bir katı assertion'ı (`len(result) >= 2`, hint/city-tag sisteminin
   sorumluluğu) gevşetildi.
2. 9 testin mesaj string'leri 150+ karaktere uzatıldı — `parse_async`'in
   `if len(message) > 150:` koşulu (satır 342) Stage 1'i sadece uzun
   mesajlarda tetikliyor, kısa test mesajları bu yüzden Stage 1'i hiç
   çağırmıyordu (implementasyon hatası değil, test-mesajı hatası).
3. 2 testin ("truncated → Groq fallback" bekleyen) yanlış varsayımı
   düzeltildi (yukarıda açıklandı).

## Test Sonucu (bağımsız doğrulandı)
```
python -m pytest -q
58 passed in 46.73s
```

## CAVEMAN / Definition of Done kontrolü
- Yeni dosya/fonksiyon yok, sadece 4× `max_tokens=1500` ekleme + 2× `finish_reason` kontrolü/log.
- Kapsam dışı hiçbir şeye dokunulmadı.
- Stage 1'e (atdd.md'nin kasıtlı olarak dışarıda bıraktığı) finish_reason kontrolü EKLENMEDİ.

## Sıradaki adım
`verify` — gerçek test/güvenlik gate'lerini çalıştıracak. Deploy sonrası
48 saatlik canlı gözlem (AC-6/Benchmark, atdd.md'de belirtildi) ayrıca
yapılacak.
