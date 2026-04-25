$logFile = "memory/logs/activity_log_" + (Get-Date -Format "yyyy-MM-dd") + ".md"
$date = Get-Date -Format "yyyy-MM-dd HH:mm"
$entry = @"
## [$date]

**Request:** Ceva Logistics testi - ASCII eslesme, None guard, OLUR blacklist

**Files:**
- src/utils/city_district_validator.py
- text_gen_parser.py

**Change:** _ascii_key() ve ascii_district_index eklendi (INEGOL->INEGOL calisir oldu). OLUR/OLUR/PARCA blackliste alindi. AI null gondermesi icin None guard eklendi.

**Test Result:** passed - Ceva Logistics 8/8 rota basariyla ayrıstirildi. BURSA/INEGOL ASCII fix isledi.

---

"@

if (Test-Path $logFile) {
    $existing = Get-Content $logFile -Raw -Encoding UTF8
    [System.IO.File]::WriteAllText((Resolve-Path $logFile).Path, $entry + $existing, [System.Text.Encoding]::UTF8)
} else {
    [System.IO.File]::WriteAllText($logFile, $entry, [System.Text.Encoding]::UTF8)
}
Write-Host "Log yazildi: $logFile"
