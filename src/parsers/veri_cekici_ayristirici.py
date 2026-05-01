# -*- coding: utf-8 -*-
"""
veri_cekici_ayristirici.py

Ana Orkestrasyon Scripti - "Sürekli Döngü ve Paralel İşleme Modu"

Görevi:
1. WhatsApp'tan (veya yerel kaynaktan) sürekli yeni mesajları kontrol eder.
2. Yeni mesajları kuyruğa alır.
3. Kuyruktaki işlenmemiş mesajları 'parse_all_messages.py' mantığıyla (Parallel + Gemini) işler.
4. Sonuçları kaydeder ve döngüye devam eder.
"""

import os
import sys

# Define PROJECT_ROOT early to Ensure imports work
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    # src/parsers/veri_cekici_ayristirici.py -> .../maviLojistik
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Windows'ta Emoji karakterlerinin yazdırılması için gerekli
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python sürümü eskiyse (3.6 ve altı)
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

import json
import time
import logging
import threading
import queue
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import cycle
from typing import List, Dict, Any
import re
from src.utils.config import (
    FETCH_HOURS_BACK, 
    WHATSAPP_POLL_INTERVAL, 
    BATCH_SLEEP_TIME, 
    LOOP_WAIT_TIME,
    AUTO_SUBMIT
)



# Importlar
# Production Parser - Text Generation with Per-Route Type Matching
sys.path.insert(0, PROJECT_ROOT)
from production_parser import ProductionParser
from src.utils.phone_utils import is_phone_in_list

from src.utils.file_operations import save_json_safe, load_json_safe
from src.services.persistence_manager import persistence_manager
from src.utils.api_key_manager import get_default_manager

# Import DataService
from src.services.data_service import DataService
from src.services.mongo_service import MongoDataService
from src.utils.location_validator import LocationValidator
from src.utils.reporter import Reporter

# Whapi Fetcher (Opsiyonel)
try:
    from src.fetchers.whapi_fetcher import fetch_all_messages, sync_to_queue, check_health, get_channel_risk, calculate_channel_risk
    WHAPI_AVAILABLE = True
except ImportError:
    WHAPI_AVAILABLE = False

# YukBurada Submitter Entegrasyonu
try:
    from tools.submit_approved_loads import YukBuradaSubmitter
    SUBMITTER_AVAILABLE = True
except ImportError:
    SUBMITTER_AVAILABLE = False

# Logging Yapılandırması
LOG_FILE = os.path.join(PROJECT_ROOT, 'tools', 'orchestrator.log')
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Orchestrator')

# Yapılandırma
POLL_INTERVAL = WHATSAPP_POLL_INTERVAL
MAX_WORKERS_DEFAULT = 50 # Increased for high-parallel real-time processing
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

QUEUE_FILE = os.path.join(DATA_DIR, 'islenmemis_mesajlar.json')
MESSAGES_FILE = os.path.join(DATA_DIR, 'mesajlar.json')
PROCESSED_FILE = os.path.join(DATA_DIR, 'onaylanmamis_ayristirilmis.json')
LIVE_LOG_FILE = os.path.join(DATA_DIR, 'live_messages.json')

class OrchestratorSDK:
    def __init__(self):
        self.api_key_manager = get_default_manager(PROJECT_ROOT)
        self.api_key_manager.load_keys()
        self.api_keys = self.api_key_manager.get_all_keys()
        
        if not self.api_keys:
            logger.error("API Key bulunamadı! Lütfen .env veya config dosyasını kontrol edin.")
            # Fallback environment check
            env_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
            if env_key:
                self.api_keys = [env_key]
                logger.info("Environment variable'dan API Key yüklendi.")
        self.api_manager = self.api_key_manager # Aliasing for self.api_keys access if needed
        self.api_key_cycle = cycle(self.api_keys)
        
        # Reporting
        self.reporter = Reporter()
        
        # Performance Caches
        self.processed_ids_cache = set()
        self._processed_cache_mtime = 0
        self.blacklist_cache = set()
        self._blacklist_cache_mtime = 0
        
        # Initialize DataService (Local-Only by default for performance)
        try:
            self.data_service = DataService(PROJECT_ROOT)
            logger.info("Local DataService specialized for OrchestratorSDK")
        except Exception as e:
            logger.error(f"Local DataService initialization failed: {e}")
            # Absolute fallback
            self.data_service = DataService(os.getcwd())
        
        # SADECE Production Parser (Text Generation with Per-Route Type Matching)
        self.base_parser = ProductionParser()
        self.location_validator = LocationValidator()
        logger.info(f"[START] Orchestrator başlatıldı - Production Parser AKTIF")
        logger.info(f"[STATS] {len(self.api_keys)} API anahtarı yüklendi")
        
        # AUTO-SUBMIT Initialization
        self.auto_submit_active = AUTO_SUBMIT
        self.submitter = None
        if self.auto_submit_active:
            if SUBMITTER_AVAILABLE:
                try:
                    self.submitter = YukBuradaSubmitter()
                    logger.info("[BOT] OTOMATİK ONAY AKTİF: YukBurada Submitter hazır.")
                except Exception as e:
                    logger.error(f"YukBurada Submitter başlatılamadı: {e}")
                    self.auto_submit_active = False
            else:
                logger.warning("[!] AUTO_SUBMIT aktif ancak 'tools/submit_approved_loads.py' bulunamadı.")
                self.auto_submit_active = False

        # REFACTORED: Persistent ThreadPool for continuous processing
        self.max_parallel_workers = MAX_WORKERS_DEFAULT
        self.executor = ThreadPoolExecutor(max_workers=self.max_parallel_workers)
        self.processing_queue = queue.Queue()
        self.active_ids = set() # Track messages currently in queue or processing
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.save_lock = threading.Lock() # Dosya yazma kilidi
        self.last_cleanup_time = 0 # Track storage cleanup
        self.last_yukburada_cleanup = 0 # Track YükBurada deduplication cleanup
        self.last_webhook_fetch = {} # Track last fetch time per chat_id to debounce
        
        # Risk Meter Tracking
        self.risk_score = 3 # Default: Good
        self.last_risk_check = 0
        self.risk_data = {}
        
        self._start_background_worker()

    def _start_background_worker(self):
        """Arka planda mesajları işleyen worker thread'i başlatır."""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.worker_thread = threading.Thread(target=self._background_worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("[WORKER] Arka plan ayrıştırma worker'ı başlatıldı.")

    def _background_worker_loop(self):
        """Kuyruktaki mesajları ana döngüden bağımsız olarak sürekli işler."""
        logger.info(f"[CPU] Worker döngüsü aktif (Max Workers: {self.max_parallel_workers}). Kuyruk izleniyor...")
        
        while not self.stop_event.is_set():
            try:
                # Bloklayarak bir sonraki mesajı bekle
                msg = self.processing_queue.get(timeout=2)
                
                # Her mesaj için bir task oluştur ve hemen executor'a fırlat (beklemeden!)
                api_key = next(self.api_key_cycle)
                try:
                    self.executor.submit(self._task_wrapper, msg, api_key)
                except RuntimeError:
                    # Interpreter kapanırken executor yeni iş kabul etmez — sessizce çık
                    logger.debug("[WORKER] Executor kapandı, worker döngüsü durduruluyor.")
                    return
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker döngü hatası: {e}")
                time.sleep(1)

    def _task_wrapper(self, msg, api_key):
        """Worker task wrapper to handle results and queue management."""
        msg_id = msg.get('id')
        logger.info(f"[JOB] [ISTEM BASLIYOR] ID: {msg_id}")
        try:
            result = self.process_message_task((msg, api_key))
            if result:
                self.save_results([result])
                logger.info(f"[OK] [İŞLEM TAMAMLANDI] ID: {msg_id}")
        except Exception as e:
            logger.error(f"[ERR] [TASK HATASI] ({msg_id}): {e}")
        finally:
            if msg_id in self.active_ids:
                self.active_ids.remove(msg_id)
            self.processing_queue.task_done()

    def check_blocking_risk(self, force=False):
        """
        Whapi Risk Ölçer'i kontrol eder. Günde bir kez çalışır.
        """
        now = time.time()
        # 24 saatte bir veya zorunluysa kontrol et
        if force or (now - self.last_risk_check > 86400):
            logger.info("[SEC] WhatsApp ban riski kontrol ediliyor...")
            try:
                # Önce mevcut durumu al
                risk_info = get_channel_risk()
                
                # Eğer bugün hiç güncellenmemişse hesaplattır
                if not risk_info or force:
                    risk_info = calculate_channel_risk()
                
                if risk_info:
                    self.risk_data = risk_info
                    self.risk_score = risk_info.get('riskFactor', 3)
                    self.last_risk_check = now
                    logger.info(f"[SEC] Güvenlik Ölçer: Skor={self.risk_score} (3:İyi, 2:Dikkat, 1:Tehlike)")
                    
                    # Reporter'ı güncelle
                    if self.reporter:
                        self.reporter.current_risk = self.risk_score
                    
                    # Eğer risk yüksekse kullanıcıyı uyar
                    if self.risk_score <= 2 and self.reporter:
                        risk_msg = "[ALERT] *WHATSAPP BAN RİSKİ UYARISI* [ALERT]\n"
                        risk_msg += f"*Durum:* {'DİKKAT (2)' if self.risk_score == 2 else 'TEHLİKE (1)'}\n"
                        risk_msg += "Sistem otomatik olarak koruma moduna (yavaşlatılmış işlem) geçmiştir."
                        self.reporter.send_whatsapp_message(risk_msg)
                
            except Exception as e:
                logger.error(f"Risk kontrol hatası: {e}")

    def check_periodic_cleanup(self):
        """Her 1 saatte bir gereksiz dosyaları ve logları temizler (User Request)."""
        import time
        now = time.time()
        # 1 saat = 3600 saniye
        if now - self.last_cleanup_time > 3600:
            logger.info("[CLEAN] Periyodik depolama ve log temizliği başlatılıyor...")
            try:
                self.data_service.cleanup_storage()
                self.data_service.purge_old_logs(hours_back=1.0)
            except Exception as e:
                logger.error(f"Periyodik temizlik hatası: {e}")
            self.last_cleanup_time = now

        # --- YÜKBURADA MÜKERRER TEMİZLİĞİ (10 DK'DA BİR) ---
        if now - self.last_yukburada_cleanup > 600:
            logger.info("[CLEAN] Periyodik YükBurada mükerrer temizliği kontrol ediliyor...")
            try:
                from tools.submit_approved_loads import YukBuradaSubmitter
                submitter = YukBuradaSubmitter()
                submitter.periodic_remote_cleanup()
            except Exception as e:
                logger.error(f"YükBurada periyodik temizlik hatası: {e}")
            self.last_yukburada_cleanup = now

    def _update_processed_ids_cache(self):
        """Update processed IDs cache if file changed."""
        try:
            if not os.path.exists(PROCESSED_FILE):
                return
            mtime = os.path.getmtime(PROCESSED_FILE)
            if mtime > self._processed_cache_mtime:
                data = load_json_safe(PROCESSED_FILE, default=[])
                if isinstance(data, list):
                    self.processed_ids_cache = {m.get('message_id') for m in data if m.get('message_id')}
                self._processed_cache_mtime = mtime
        except Exception as e:
            logger.error(f"Processed cache update error: {e}")

    def handle_webhook_event(self, event_data: Dict):
        """
        Receives raw webhook data from Whapi.
        Extracts the chat_id and triggers a targeted fetch for the last 10 messages of that group.
        This prevents WhatsApp bans by avoiding aggressive polling of all groups.
        """
        if not event_data:
            return
            
        messages = event_data.get('messages', [])
        if not messages and 'data' in event_data:
            data = event_data['data']
            if isinstance(data, list):
                messages = data
            elif isinstance(data, dict):
                messages = [data]
        
        if not messages and (event_data.get('body') or event_data.get('text')):
            messages = [event_data]
            
        if not messages:
            return

        logger.info(f"[FLASH] Webhook Tetikleyici: {len(messages)} yeni olay alındı.")
        
        # Hedef group ID'lerini topla
        target_chat_ids = set()
        for msg in messages:
            chat_id = msg.get('chat_id')
            if not chat_id:
                # Bazen 'chat' objesi içinde gelir
                chat_obj = msg.get('chat', {})
                if isinstance(chat_obj, dict):
                    chat_id = chat_obj.get('id')
                elif isinstance(chat_obj, str):
                    chat_id = chat_obj
            
            if chat_id:
                target_chat_ids.add(chat_id)
                
        # Debounce: Don't fetch the same group more than once every 30 seconds
        import time
        now = time.time()
        for cid in list(target_chat_ids):
            last_time = self.last_webhook_fetch.get(cid, 0)
            if now - last_time < 30:
                logger.debug(f"[SKIP] Webhook: {cid} iYin cooldown aktif (Atland).")
                target_chat_ids.remove(cid)
            else:
                self.last_webhook_fetch[cid] = now
        
        if not target_chat_ids:
            return

        logger.info(f"[TARGET] Webhook: Hedef gruplardan {list(target_chat_ids)} son mesajlar çekiliyor (TimeBuffer: 5m)...")
        
        try:
            from src.fetchers.whapi_fetcher import fetch_all_messages
            # Webhook geldiğinde sadece mesaj adedine değil, "son 5 dakika" bazlı garantili çekim yapıyoruz.
            # Bu sayede bildirimler arasındaki milisaniyelik boşluklarda hiçbir mesaj kaçmaz.
            import time
            from datetime import datetime, timedelta
            
            # 5 dakikalık buffer (Current Time - 300s)
            time_from = int(time.time()) - 300
            
            fetch_all_messages(
                hours_back=1.0, 
                max_messages_per_group=50, 
                only_saved_groups=False,
                target_group_ids=list(target_chat_ids),
                orchestrator=self,
                poll_params={'time_from': time_from} # Whapi için zaman filtresi
            )
        except Exception as e:
            logger.error(f"[ERR] Webhook odaklı fetch_all_messages hatası: {e}")

    def add_to_processing_queue(self, messages: List[Dict]):
        """
        Yeni çekilen mesajları filtrelerden geçirip ayrıştırma kuyruğuna ekler.
        
        İşlev: Gelen ham mesaj paketlerini ID, kopya ve kara liste kontrollerinden geçirerek işleme kuyruğuna alır.
        Bağlantılar: self.data_service (blacklist & body duplicate), self.processing_queue.
        Gereklilik: Gereksiz veya engellenmiş mesajların Gemini API'ye gönderilerek maliyet ve zaman kaybı yaratmasını önler.
        Kritik Kurallar: Kara listedeki numaralar asla kuyruğa eklenmemelidir.
        """
        if not messages:
            return
            
        # 1. Update caches once per batch
        self._update_processed_ids_cache()
        blacklist = self.data_service.load_blacklist()
        
        added_count = 0
        new_logs = []
        
        for msg in messages:
            mid = msg.get('id')
            
            # ROBUST BODY EXTRACTION: Always normalize to a clean string
            # 1) Prefer 'text' field (Whapi webhook) if available
            body = ""
            if 'text' in msg:
                text_field = msg['text']
                if isinstance(text_field, dict):
                    body = text_field.get('body', '') or ''
                else:
                    body = str(text_field or "")
            else:
                # 2) Fallback to top-level 'body'
                raw_body = msg.get('body', '')
                if raw_body is None:
                    raw_body = ''
                body = str(raw_body)
            
            body = body.strip()
            # Ensure downstream code (parser, logs, GUI) always sees a string body
            msg['body'] = body
            
            # Normalize sender name from Webhook payload (from_name -> sender_name)
            if 'sender_name' not in msg and 'from_name' in msg:
                msg['sender_name'] = msg['from_name']

            
            # A. Temel ve ID Kontrolü (Kalıcı ve Hafıza Kontrolü)
            if not mid or not body or self.data_service.is_id_handled(mid):
                if not mid: logger.debug("[SKIP] Mesaj ID yok (Atlandı)")
                elif not body: logger.debug(f"[SKIP] Mesaj içeriği boş (Atlandı): {mid}")
                continue
            
            # B. Benzerlik (Body Duplicate) Kontrolü
            if self.data_service.is_body_known(body):
                logger.info(f"[SKIP] Mesaj kopyası/zaten işlenmiş (Atlandı): {mid}")
                self.data_service.mark_id_handled(mid) # Kalıcı olarak işaretle
                continue
            
            sender_raw = msg.get('from', '')
            if sender_raw:
                if is_phone_in_list(sender_raw, blacklist):
                    logger.info(f"[BLOCK] Orchestrator Blacklist: skipping message {mid} from {sender_raw}")
                    self.data_service.mark_id_handled(mid) # Kalıcı mark
                    continue
            
            # D. Check if already in memory queue (active_ids)
            if mid in self.active_ids:
                continue

            # Tüm kontrollerden geçtiyse kuyruğa at
            self.active_ids.add(mid)
            self.data_service.mark_id_handled(mid) # USER REQUEST: Mark ID immediately upon fetch/queue
            self.processing_queue.put(msg)
            added_count += 1
            
            # --- CANLI LOG SİSTEMİ VERİSİNİ HAZIRLA ---
            try:
                orig_ts = msg.get('timestamp')
                try:
                    if orig_ts:
                        msg_time = datetime.fromtimestamp(float(orig_ts)).strftime("%H:%M:%S")
                    else:
                        msg_time = datetime.now().strftime("%H:%M:%S")
                except Exception:
                    msg_time = datetime.now().strftime("%H:%M:%S")

                log_entry = {
                    'time': msg_time,
                    'sender': msg.get('sender_name') or msg.get('from', 'Bilinmiyor'),
                    'group': msg.get('chat_name') or 'Özel Mesaj',
                    'body': body,
                    'timestamp': float(orig_ts) if orig_ts else time.time()
                }
                new_logs.append(log_entry)
            except Exception as le:
                logger.error(f"Canlı log verisi hazırlama hatası: {le}")
            
        # CANLI LOG DOSYASINI GÜNCELLE (TOPLU)
        if new_logs:
            try:
                live_data = []
                if os.path.exists(LIVE_LOG_FILE):
                    live_data = load_json_safe(LIVE_LOG_FILE, default=[])

                if not isinstance(live_data, list):
                    live_data = []
                
                # Yeni logları en başa ekle
                for entry in reversed(new_logs):
                    live_data.insert(0, entry)
                
                live_data = live_data[:50] # Son 50 mesajı tut
                persistence_manager.queue_write(LIVE_LOG_FILE, live_data) # Non-blocking background save
                logger.info(f"[CLEAN] Canlı log dosyasına {len(new_logs)} mesaj eklendi.")
            except Exception as e:
                logger.error(f"Toplu canlı log yazma hatası: {e}")

        if added_count > 0:
            logger.info(f"[IN] {added_count} yeni mesaj ayrıştırma kuyruğuna eklendi.")
        else:
            logger.debug("[SKIP] Yeni eklenecek mesaj bulunamadı (Tümü filtrelendi).")
            
        return added_count

    def fetch_new_messages(self):
        """WhatsApp'tan tüm grupların yeni mesajlarını çeker."""
        return self.fetch_new_messages_batch(None)

    def fetch_new_messages_batch(self, target_group_ids: List[str] = None):
        """WhatsApp'tan belirli bir grup paketinin mesajlarını çeker ve anında kuyruğa iletir."""
        # Periyodik risk kontrolü
        self.check_blocking_risk()

        if not WHAPI_AVAILABLE:
            return 0
        
        try:
            # STREAMING: Mesaj çekilir çekilmez callback ile kuyruğa at
            def stream_callback(msg):
                self.add_to_processing_queue([msg])
            
            # Yeni mesajları çek
            logger.info("[POLL] Yeni mesajlar kontrol ediliyor...")
            count = fetch_all_messages(
                hours_back=FETCH_HOURS_BACK, 
                only_saved_groups=True, 
                target_group_ids=target_group_ids,
                on_message_received=stream_callback,
                risk_score=self.risk_score
            )
            
            if count > 0:
                logger.info(f"[OK] {count} yeni mesaj bulundu ve işleniyor.")
            else:
                logger.info("[SLEEP] Yeni mesaj yok. Beklemede...")
            
            # NOT: Streaming zaten kuyruğa attığı için get_unprocessed_messages 
            # sadece garanti olsun diye sonda bir kez çağrılabilir veya kaldırılabilir.
            # Şimdilik "miss" olmaması için sonda küçük bir sync yapıyoruz ama esas hız callback'ten geliyor.
            if count > 0:
                pass 
                
            return count
        except Exception as e:
            logger.error(f"WhatsApp fetch hatası: {e}")
            return 0

    def process_queue_parallel(self):
        """Eski mantıkla uyumluluk için (Artık arka plan worker kullanılıyor)."""
        # Sadece kuyruğun erimesini beklemek gerekebilir veya boş kalabilir.
        logger.debug("process_queue_parallel çağrıldı (Arka plan worker zaten aktif).")
        return 0

    def get_unprocessed_messages(self) -> List[Dict]:
        """
        Henüz işlenmemiş mesajları tespit eder ve listeler.
        
        İşlev: Kayıtlı mesaj dosyalarını tarar, zaman aşımı, ID ve kara liste filtrelerini uygular.
        Bağlantılar: MESSAGES_FILE, self.data_service.
        Gereklilik: Sistemin kaldığı yerden devam etmesini ve eksik mesajların işlenmesini sağlar.
        Kritik Kurallar: Kara listedeki numaralar asla sonuç listesinde yer almamalıdır.
        """
        try:
            # 1. Tüm mesajları yerel kuyruktan yükle (Yeni gelen mesajlar geçici olarak MESSAGES_FILE'da tutulur)
            all_messages = []
            if os.path.exists(MESSAGES_FILE):
                data = load_json_safe(MESSAGES_FILE, default=[])
                if isinstance(data, dict):
                    all_messages = data.get('messages', [])
                elif isinstance(data, list):
                    all_messages = data
            
            # 2. Zaten işlenmişleri MongoDB'den yükle (Centralized check)
            # load_unprocessed_messages(False) because we need full history for duplicate checking within 24h
            processed_data = self.data_service.load_unprocessed_messages(filter_today=False)
            processed_ids = set(processed_data.keys())
            
            # Zaman eşiği (Şu an - 2 saat) - USER REQUEST: Strict 2 hours
            import time
            cutoff_time = time.time() - (2 * 3600)

            # 3. Filtrele
            unprocessed = []
            skipped_count = 0
            expired_count = 0
            duplicate_count = 0
            
            for msg in all_messages:
                mid = msg.get('id')
                body = msg.get('body', '').strip()
                timestamp = msg.get('timestamp')
                
                # A. Temel Kontrol
                if not mid or not body:
                    continue
                
                # B. ID Kontrolü (Zaten işlenmiş veya elenmiş mi?)
                if self.data_service.is_id_handled(mid) or mid in processed_ids:
                    skipped_count += 1
                    continue
                
                # C. Zaman Kontrolü (2 saatten eski mi?)
                # Timestamp genellikle Unix epoch (int/float)
                is_expired = False
                if timestamp:
                    try:
                        ts_val = float(timestamp)
                        if ts_val < cutoff_time:
                            is_expired = True
                    except (ValueError, TypeError):
                        pass # Timestamp parse edilemezse, yine de işleyelim veya ignore edelim? Şimdilik işleyelim.
                
                if is_expired:
                    expired_count += 1
                    continue

                # E. Blacklist Kontrolü
                sender_raw = msg.get('from', '')
                if sender_raw:
                    blacklist = self.data_service.load_blacklist()
                    if is_phone_in_list(sender_raw, blacklist):
                        logger.info(f"[BLOCK] Kara listedeki numaradan gelen mesaj atlandı: {sender_raw}")
                        continue
                
                # Yurt dışı kontrolü artık burada (ham mesaj üzerinden) yapılmıyor.
                # Sadece ayrıştırma sonrası 'YURT DIŞI' alanı kontrol edilecek.
                
                # Tüm filtreleri geçti
                unprocessed.append(msg)
            
            if unprocessed or skipped_count > 0 or expired_count > 0:
                logger.info(f"[CHECK] Tarama: {len(all_messages)} mesajdan {len(unprocessed)} tanesi yeni/işlenebilir. ({skipped_count} işlenmiş, {expired_count} eski)")
            
            # Tarihe göre sırala (yeniden eskiye - anlık saate en yakın olandan başlasın)
            unprocessed.sort(key=lambda x: str(x.get('timestamp', '0')), reverse=True)
            
            return unprocessed
        except Exception as e:
            logger.error(f"İşlenmemiş mesaj tespiti hatası: {e}")
            return []

    def process_message_task(self, args):
        """
        Tek bir mesajı Gemini API (veya base parser) kullanarak detaylı sevkiyat verilerine ayrıştırır.
        
        İşlev: Mesaj içeriğini analiz eder, şehir/ilçe/yük bilgilerini ayıklar ve konum doğrulaması yapar.
        Bağlantılar: self.base_parser, self.location_validator, self.save_results.
        Gereklilik: Ham metnin yapısal veriye dönüştürülmesi ve geçersiz konumların işaretlenmesi için kritiktir.
        Kritik Kurallar: Türkiye sınırları dışında kalan veya bulunamayan şehirler 'invalid_location' olarak işaretlenmelidir.
        """
        msg, api_key = args
        msg_id = msg.get('id')
        logger.info(f"[JOB] Islem BASLADI: {msg_id} (Gönderen: {msg.get('sender_name')})")
        try:
            # OPTIMIZATION: Use shared parser to avoid reloading JSON files
            parser = self.base_parser
            corrected_body = msg.get('body', '')
            
            # Parsing (Ayrıştırma)
            shipments = parser.parse_message(corrected_body, msg.get('chat_name', ''))
            
            # 3. Metadata Ekleme and Initial Filtering
            import re
            from src.utils.phone_utils import normalize_phone
            sender_raw = msg.get('from', '')
            sender_number = normalize_phone(sender_raw) if sender_raw else ''

            valid_shipments = []
            has_invalid_location = False
            for shipment in shipments:
                # A. Basic Info
                shipment['original_message'] = msg.get('body')
                shipment['message_id'] = msg_id
                shipment['aciklama'] = msg.get('body')
                
                if not shipment.get('telefon') and sender_number:
                     shipment['telefon'] = sender_number

                # B. FILTER: Empty Route Check (Must have at least one city field for both origin and destination)
                nereden_il = str(shipment.get('nereden_il', '')).strip()
                nereden_ilce = str(shipment.get('nereden_ilce', '')).strip()
                nereye_il = str(shipment.get('nereye_il', '')).strip()
                nereye_ilce = str(shipment.get('nereye_ilce', '')).strip()

                if not (nereden_il or nereden_ilce):
                    logger.info(f"[FILTER] Shipment removed: Missing 'nereden' (Origin). ID: {msg_id}")
                    continue
                
                if not (nereye_il or nereye_ilce):
                    logger.info(f"[CLEAN] Shipment removed: Missing 'nereye' (Destination). ID: {msg_id}")
                    continue

                # C. FILTER: Location Validation (Turkey Check)
                is_valid = self.location_validator.is_valid_city(nereden_il) and \
                           self.location_validator.is_valid_city(nereye_il)
                
                if not is_valid:
                    logger.info(f"[MAP] Location Flagged: International or Unknown detected. ID: {msg_id} ({nereden_il} -> {nereye_il})")
                    shipment['invalid_location'] = True
                    has_invalid_location = True # Flag entire message
                else:
                    shipment['invalid_location'] = False

                valid_shipments.append(shipment)

            if not valid_shipments:
                logger.info(f"[WARN] No valid shipments left after filtering: {msg_id}")
                return {'status': 'error', 'msg_id': msg_id, 'error': 'All shipments filtered (International or Empty)', 'original_msg': msg}

            logger.info(f"[OK] Islem BITTI: {msg_id} -> {len(valid_shipments)} geçerli ilan")
            return {
                'status': 'success',
                'msg_id': msg_id,
                'original_msg': msg,
                'shipments': valid_shipments,
                'invalid_location': has_invalid_location, # NEW: Message-level flag
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Mesaj işleme hatası ({msg_id}): {e}")
            return {
                'status': 'error',
                'msg_id': msg_id,
                'error': str(e),
                'original_msg': msg
            }

    def save_results(self, results):
        """Sonuçları onaylanmamış_ayrıştırılmış.json dosyasına ekler."""
        if not results:
            return

        with self.save_lock:
            try:
                # Mevcut veriyi yükle
                current_data = []
                if os.path.exists(PROCESSED_FILE):
                    loaded = load_json_safe(PROCESSED_FILE, default=[])
                    if isinstance(loaded, list):
                        current_data = loaded
                
                new_entries = []
                for res in results:
                    if res['status'] == 'success':
                        # Ensure message_timestamp is a clean float (seconds)
                        orig_ts = res['original_msg'].get('timestamp')
                        try:
                            ts_val = float(orig_ts) if orig_ts else time.time()
                            # If it looks like milliseconds, convert to seconds
                            if ts_val > 10**12:
                                ts_val = ts_val / 1000
                        except:
                            ts_val = time.time()

                        # --- SHIPMENT DEDUPLICATION ---
                        unique_shipments = []
                        for s in res['shipments']:
                            if not self.data_service.is_shipment_duplicate(s):
                                unique_shipments.append(s)
                            else:
                                logger.info(f"[UPDATE] Mükerrer ilan tespit edildi (Rota/Tel): {s.get('nereden_il')}->{s.get('nereye_il')} ({s.get('telefon')})")
                                # AGGRESSIVE: Remove existing copies too
                                removed_count = self.data_service.remove_shipment_duplicates(s)
                                if removed_count > 0:
                                    logger.info(f"[CLEAN] Aggressive: {removed_count} adet eski kopya silindi.")
                                
                                # FIX: Add the new shipment anyway so it replaces the old one!
                                unique_shipments.append(s)
                                logger.info("[UPDATE] Eski ilan silinerek yenisi ile güncellendi.")
                        
                        if not unique_shipments:
                            logger.info(f"[SKIP] Mesaj içindeki tüm ilanlar mükerrer, mesaj yine de 'islenmis' işaretleniyor: {res['msg_id']}")
                            # Mark as processed with empty shipments to stop re-processing loop
                            entry = {
                                'message_id': res['msg_id'],
                                'message_timestamp': ts_val,
                                'createdAt': ts_val,
                                'message_date': datetime.fromtimestamp(ts_val).isoformat(),
                                'message_info': {
                                    'body': res['original_msg'].get('body'),
                                    'sender': res['original_msg'].get('sender_name'),
                                    'sender_number': res['original_msg'].get('from'),
                                    'timestamp': orig_ts,
                                    'chat_id': res['original_msg'].get('chat_id'),
                                    'chat_name': res['original_msg'].get('chat_name')
                                },
                                'parse_timestamp': res['timestamp'],
                                'total_shipments': 0,
                                'shipments': [],
                                'status': 'duplicate'
                            }
                            new_entries.append(entry)
                            continue
                            
                        # Update with unique shipments only
                        res['shipments'] = unique_shipments

                        entry = {
                            'message_id': res['msg_id'],
                            'message_timestamp': ts_val, # Standardized Float
                            'createdAt': ts_val,        # Critical for DataService retention check
                            'message_date': datetime.fromtimestamp(ts_val).isoformat(),
                            'invalid_location': res.get('invalid_location', False), # Propagate flag
                            'message_info': {
                                'body': res['original_msg'].get('body'),
                                'sender': res['original_msg'].get('sender_name'),
                                'sender_number': res['original_msg'].get('from'), 
                                'timestamp': orig_ts,
                                'chat_id': res['original_msg'].get('chat_id'),
                                'chat_name': res['original_msg'].get('chat_name')
                            },
                            'parse_timestamp': res['timestamp'],
                            'total_shipments': len(res['shipments']),
                            'shipments': res['shipments']
                        }
                        new_entries.append(entry)
                        
                        # Mark as processed in duplicate tracker (1-hour window)
                        self.data_service.mark_content_as_processed(res['original_msg'].get('body'))
                    else:
                        # Hatalı olanları da kaydet ki tekrar tekrar denemesin (veya farklı bir log dosyasına)
                        # Şimdilik "hatalı" olarak işaretleyip geçiyoruz
                        entry = {
                            'message_id': res['msg_id'],
                            'error': res['error'],
                            'parse_timestamp': datetime.now().isoformat(),
                            'total_shipments': 0,
                            'shipments': []
                        }
                        new_entries.append(entry)
                
                # --- PREPARE FOR SAVE ---
                # We turn the list of new entries into a dict for the DataService
                save_payload = {}
                for entry in new_entries:
                    # FILTER: Only save to storage if there is at least one recognized city, it's an error, or it's a duplicate
                    has_valid_shipment = False
                    if 'error' in entry or entry.get('status') == 'duplicate':
                        has_valid_shipment = True
                    else:
                        for s in entry.get('shipments', []):
                            if s.get('nereden_il') or s.get('nereye_il'):
                                has_valid_shipment = True
                                break
                    
                    if has_valid_shipment:
                        save_payload[entry['message_id']] = entry
                
                # --- ACTUAL SAVE CALL ---
                if save_payload:
                    success = self.data_service.save_unprocessed_messages(save_payload, merge=True)
                    if success:
                        logger.info(f"{len(save_payload)} yeni geçerli sonuç yerel veri servisine aktarıldı.")
                        # --- CRITICAL: SADECE BAŞARIYLA KAYDEDİLENLERİ "İŞLENDİ" OLARAK İŞARETLE ---
                        for message_id in save_payload.keys():
                            self.data_service.mark_id_handled(message_id)
                            # Hafızadaki aktif listeden de çıkar
                            if message_id in self.active_ids:
                                self.active_ids.remove(message_id)
                        
                        # --- AUTO SUBMIT LOGIC ---
                        if self.auto_submit_active and self.submitter:
                            triggered_count = 0
                            for m_id, entry in save_payload.items():
                                # Sadece hata içermeyen ve lokasyonu geçerli olan yeni ilanları gönder
                                if 'error' not in entry and entry.get('status') != 'duplicate' and not entry.get('invalid_location'):
                                    shipments = entry.get('shipments', [])
                                    if shipments:
                                        logger.info(f"[OUT] [OTO-ONAY] {m_id} için {len(shipments)} ilan gönderiliyor...")
                                        for shipment in shipments:
                                            try:
                                                payload = self.submitter.transform_record_to_payload(shipment)
                                                submit_res = self.submitter.submit_single_load(payload)
                                                if submit_res and submit_res.get('success'):
                                                    triggered_count += 1
                                                    # Başarılı gönderilenleri ayrıca approved listesine ekle
                                                    self.data_service.save_approved_records([shipment])
                                            except Exception as se:
                                                logger.error(f"Oto-gönderim hatası ({m_id}): {se}")
                            
                            if triggered_count > 0:
                                logger.info(f"[DONE] [OTO-ONAY] Toplam {triggered_count} ilan başarıyla sisteme yüklendi.")
                else:
                    logger.debug("Kaydedilecek geçerli/yeni ilan bulunamadı.")
                
                # PHASE 5: Save to historical log file via DataService (Optional)
                try:
                    self.data_service.append_unprocessed_log(new_entries)
                except: pass

            except Exception as e:
                logger.error(f"Sonuç kaydetme hatası: {e}", exc_info=True)

    def run_once(self, keep_only_today: bool = True):
        """Tek seferlik işleme - GUI entegrasyonu için."""
        self.check_periodic_cleanup()
        logger.info("[SYNC] Orchestrator run_once başlatıldı")
        try:
            # OPTIMIZATION: Don't fetch from API again! The GUI loop already did it.
            # Just pick up what was recently written to the files.
            unprocessed = self.get_unprocessed_messages()

            # --- KEEP ONLY TODAY FILTER ---
            if keep_only_today and unprocessed:
                from datetime import datetime
                today_str = datetime.now().strftime('%Y-%m-%d')
                filtered = []
                for msg in unprocessed:
                    # Check timestamp_readable first
                    ts_str = msg.get('timestamp_readable', '')
                    if ts_str and ts_str.startswith(today_str):
                        filtered.append(msg)
                        continue
                    
                    # Fallback to timestamp
                    try:
                        ts = float(msg.get('timestamp', 0))
                        msg_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                        if msg_date == today_str:
                            filtered.append(msg)
                    except:
                        pass
                
                if len(filtered) < len(unprocessed):
                    logger.info(f"[DATE] GÜN FİLTRESİ: {len(unprocessed)} mesajdan {len(filtered)} tanesi bugüne ait.")
                    unprocessed = filtered

            if unprocessed:
                count = len(unprocessed)
                logger.info(f"[CHECK] {count} işlenmemiş mesaj filtrelerden geçiriliyor...")
                actual_added = self.add_to_processing_queue(unprocessed)
                
                if actual_added > 0:
                    # Wait for the queue to drain (Synchronous mode for run_once)
                    logger.info(f"[WAIT] {actual_added} yeni mesajın tamamlanması bekleniyor...")
                    self.processing_queue.join()
                    logger.info("[OK] Tüm yeni mesajlar başarıyla işlendi.")
                else:
                    logger.info("[INFO] Kontrol edilen mesajların tamamı zaten işlenmiş veya filtrelendi.")
            else:
                logger.info("[INFO] İşlenecek yeni mesaj bulunamadı.")
            
            logger.info("[OK] run_once tamamlandı.")
        except Exception as e:
            logger.error(f"run_once hatası: {e}")

    def run_loop(self):
        """Ana sonsuz döngü - BATCH + PARALEL MOD."""
        from src.fetchers.whapi_fetcher import get_saved_chat_ids
        
        logger.info(f"[START] BATCH Orkestratör Başlatıldı")
        
        while not self.stop_event.is_set():
            try:
                # 0. Periyodik temizliği kontrol et
                self.check_periodic_cleanup()
                
                # --- BAN PREVENTION: HEALTH CHECK ---
                if WHAPI_AVAILABLE:
                    health = check_health()
                    status_data = health.get('status', {})
                    status = status_data.get('text', 'unknown').lower() if isinstance(status_data, dict) else str(status_data).lower()
                    
                    if status not in ['connected', 'active', 'auth']:
                        logger.warning(f"[WARN] Whapi bağlantısı sağlıksız ({status}). 15 sn sonra tekrar denenecek...")
                        if status in ['disconnected', 'auth_required', 'blocked']:
                            logger.error(f"[ERROR] KRİTİK DURUM: {status}. 1 dk bekleniyor...")
                            time.sleep(60)
                        else:
                            time.sleep(15)
                        continue
                
                # 1. Kayıtlı grupları yükle
                chat_ids = list(get_saved_chat_ids())
                if not chat_ids:
                    logger.warning("[WARN] Kayıtlı grup bulunamadı! 1 dk bekleniyor...")
                    time.sleep(60)
                    continue
                
                logger.info(f"[LIST] Toplam {len(chat_ids)} grup üzerinden işlem başlatılıyor.")
                
                # 2. Grupları 20'li paketlere böl
                batch_size = 20
                batches = [chat_ids[i:i + batch_size] for i in range(0, len(chat_ids), batch_size)]
                
                for i, batch_ids in enumerate(batches):
                    batch_start = time.time()
                    logger.info(f"\n[BATCH] [PAKET {i+1}/{len(batches)}] {len(batch_ids)} grup taranıyor...")
                    
                    # HUMAN-LIKE DELAY: Random delay before starting batch
                    time.sleep(random.uniform(2.0, 5.0))
                    
                    # A. Mesajları çek (WhatsApp API) - Streaming aktif
                    self.fetch_new_messages_batch(batch_ids)
                    
                    # HUMAN-LIKE DELAY: Random delay after batch completion
                    jitter = random.uniform(3.0, 10.0) 
                    sleep_time = max(1.0, BATCH_SLEEP_TIME - (time.time() - batch_start) + jitter)
                    logger.info(f"⏳ Paket bitti. {sleep_time:.1f}sn insani bekleme veriliyor...")
                    time.sleep(sleep_time)
                
                # 3. Tüm gruplar bittiğinde ana mola (Konfigürasyondan okunur)
                # Webhook bağlantısı olsa bile, periyodik tarama WHATSAPP_POLL_INTERVAL kadar bekler.
                wait_time = WHATSAPP_POLL_INTERVAL
                logger.info(f"\n[OK] Periyodik tarama tamamlandı. {wait_time} saniye sonra tekrar başlayacak...")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                logger.info("Kullanıcı tarafından durduruldu.")
                break
            except Exception as e:
                logger.error(f"Döngü hatası: {e}")
                try:
                    self.reporter.add_error(f"[WARN] *Orkestratör Döngü Hatası*\n\nDetay: {str(e)}", level="WARNING")
                except: pass
                time.sleep(30) # Hata durumunda kısa bekleme

# Module-level orchestrator instance (singleton pattern)
_orchestrator_instance = None

def process_unprocessed_messages(keep_only_today: bool = True, run_once: bool = True):
    """
    GUI entegrasyonu için işlenmemiş mesajları işler.
    """
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        _orchestrator_instance = OrchestratorSDK()
    
    if run_once:
        _orchestrator_instance.run_once(keep_only_today=keep_only_today)
    else:
        _orchestrator_instance.run_loop()

if __name__ == "__main__":
    orchestrator = OrchestratorSDK()
    orchestrator.run_loop()