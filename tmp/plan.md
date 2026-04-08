📋 PLAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Görev:**
1. "23 KAYA NAKLIYAT" (905330460585) numarasını kara listeye ekleyerek engellemek.
2. Kara liste sisteminin tüm mesaj çekme süreçlerinde (Whapi Fetcher) aktif çalışmasını sağlamak.
3. `server_worker.py` dosyasını sistemden kaldırmak.

**Bağlam:**
Kullanıcı, kara listenin çalışmadığını ve belirli bir numaranın mesajlarının sürekli yeniden yayınlandığını bildirdi. Ayrıca artık `server_worker.py` dosyasına ihtiyaç olmadığını belirtti. Yapılan incelemede, ana mesaj çekme modülünde (`whapi_fetcher.py`) kara liste filtresinin eksik olduğu ve bildirilen numaranın listede yer almadığı görüldü.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Adımlar:**

1. **Numarayı Kara Listeye Ekleme**
   - Ne: `905330460585` numarasını `data/blacklist.json` dosyasına ekle.
   - Dosya: [blacklist.json](file:///c:/Users/YUSUF%20%C3%87%C4%B0NAR/OneDrive/Belgeler/Masa%C3%BCst%C3%BC/projelerim/maviLojistik/data/blacklist.json)
   - Neden: Numarayı sisteme tanıtmak için.

2. **Whapi Fetcher'a Filtreleme Ekleme**
   - Ne: `convert_whapi_message` veya `fetch_all_messages` aşamasında, mesajı sisteme kabul etmeden önce kara liste kontrolü yap.
   - Dosya: [whapi_fetcher.py](file:///c:/Users/YUSUF%20%C3%87%C4%B0NAR/OneDrive/Belgeler/Masa%C3%BCst%C3%BC/projelerim/maviLojistik/src/fetchers/whapi_fetcher.py)
   - Neden: Mesajların en başında, yani yerel veritabanına dahi girmeden engellenmesi için.

3. **Server Worker'ı Kaldırma**
   - Ne: `server_worker.py` dosyasını sil.
   - Dosya: [server_worker.py](file:///c:/Users/YUSUF%20%C3%87%C4%B0NAR/OneDrive/Belgeler/Masa%C3%BCst%C3%BC/projelerim/maviLojistik/server_worker.py)
   - Neden: Kullanıcı talebi üzerine (artık ihtiyaç duyulmuyor).

4. **Kayıt Güncelleme**
   - Ne: Yapılan işlemleri `memory/project.md` ve `activity_log` dosyalarına işle.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Etkilenen dosyalar:**
- `data/blacklist.json`
- `src/fetchers/whapi_fetcher.py`
- `DELETE server_worker.py`
- `memory/project.md`

⚠️  **Uyarı:** `server_worker.py` dosyasının silinmesi bu modüle dayalı otomatik süreçleri durduracaktır.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Onaylıyor musunuz? (evet / hayır / değiştir)**
