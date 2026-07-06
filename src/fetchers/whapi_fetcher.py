# -*- coding: utf-8 -*-
"""
Whapi.cloud API Mesaj Çekici

WhatsApp gruplarından mesajları çeker ve mesajlar.json dosyasına kaydeder.
"""

import os
import sys
import json
import time
import socket
import requests
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import logging
import threading

# Add project root to sys.path to fix ModuleNotFoundError
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.config import FETCH_HOURS_BACK, WHATSAPP_TOKEN, WHAPI_TOOLS_URL
WHAPI_TOKEN = WHATSAPP_TOKEN
logger = logging.getLogger(__name__)

# Root dizini bul
from src.utils.common import get_root_path, get_user_data_dir
from src.services.data_service import DataService
from src.utils.phone_utils import is_phone_in_list
ROOT_DIR = str(get_root_path())
data_service = DataService(ROOT_DIR)

# Dosya yolları
DATA_DIR = get_user_data_dir()
MESSAGE_FILE = str(DATA_DIR / 'mesajlar.json')
QUEUE_FILE = str(DATA_DIR / 'islenmemis_mesajlar.json')
CHAT_GROUPS_FILE = str(DATA_DIR / 'chat_groups.json')

# Whapi API yapılandırması
WHAPI_BASE_URL = "https://gate.whapi.cloud"
WHAPI_IP = "104.21.10.27"  # DNS sorunu için yedek IP

# DNS patch - Whapi için
_original_getaddrinfo = socket.getaddrinfo
_dns_patched = False
_GROUPS_CACHE = []
_GROUPS_LOCK = threading.Lock()
_GROUPS_CACHE_TIME = 0
_GROUPS_CACHE_TTL = 1800

def patch_dns():
    """DNS çözümleme sorunları için IP patch uygula - Devre dışı bırakıldı (Cloudflare IP değişimi kontrolü için)"""
    # global _dns_patched
    # if _dns_patched:
    #     return
    # 
    # def patched_getaddrinfo(host, *args, **kwargs):
    #     if host == 'gate.whapi.cloud':
    #         return _original_getaddrinfo(WHAPI_IP, *args, **kwargs)
    #     return _original_getaddrinfo(host, *args, **kwargs)
    # 
    # socket.getaddrinfo = patched_getaddrinfo
    # _dns_patched = True
    pass

def get_headers() -> Dict:
    """API için header'ları döndür"""
    return {
        'accept': 'application/json',
        'Authorization': f'Bearer {WHAPI_TOKEN}',
        'Host': 'gate.whapi.cloud'
    }

def check_health() -> Dict:
    """
    Whapi kanal durumunu kontrol eder. 
    Banlanma veya bağlantı kopma durumlarını erkenden tespit etmek için kritiktir.
    """
    patch_dns()
    url = f"{WHAPI_BASE_URL}/health"
    try:
        response = requests.get(url, headers=get_headers(), timeout=45)
        if response.status_code == 200:
            data = response.json()
            # Status: 'connected', 'auth_required', 'disconnected', 'blocked'
            status = data.get('status', 'unknown')
            status_text = status.get('text', 'unknown') if isinstance(status, dict) else str(status)
            logger.info(f"[HEALTH] Whapi Sağlık Durumu: {status_text.upper()}")
            return data
        else:
            logger.error(f"[ERROR] Sağlık kontrolü başarısız: {response.status_code}")
            return {'status': 'error', 'error': response.text}
    except Exception as e:
        logger.error(f"[ERROR] Sağlık kontrolü hatası: {e}")
        return {'status': 'error', 'error': str(e)}

def fetch_groups(max_count: int = 200, retries: int = 3) -> List[Dict]:
    """Tüm WhatsApp gruplarını çek (Exponential Backoff ve Küçük Limit ile Optimize Edildi)"""
    global _GROUPS_CACHE, _GROUPS_CACHE_TIME
    with _GROUPS_LOCK:
        if _GROUPS_CACHE and (time.time() - _GROUPS_CACHE_TIME) < _GROUPS_CACHE_TTL:
            return list(_GROUPS_CACHE)

    patch_dns()
    
    # Session ile bağlantı yönetimi
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    
    base_url = f"{WHAPI_BASE_URL}/groups"
    all_groups = []
    limit = 50  # Limit 100'den 50'ye çekildi (Daha kararlı)
    offset = 0
    
    logger.info(f"[GROUPS] Grup çekimi başladı (Base URL: {base_url}, Limit: {limit})")
    
    while True:
        success = False
        for attempt in range(retries):
            try:
                url = f"{base_url}?count={limit}&offset={offset}"
                response = session.get(url, headers=get_headers(), timeout=60)
                
                if response.status_code == 200:
                    data = response.json()
                    groups = data.get('groups', [])
                    
                    if not groups:
                        logger.info(f"[INFO] Ofset {offset}: Başka grup kalmadı.")
                        with _GROUPS_LOCK:
                            _GROUPS_CACHE = list(all_groups)
                            _GROUPS_CACHE_TIME = time.time()
                        return all_groups
                        
                    all_groups.extend(groups)
                    logger.info(f"[IN] {len(groups)} grup çekildi (Toplam: {len(all_groups)})")
                    
                    if len(groups) < limit:
                        with _GROUPS_LOCK:
                            _GROUPS_CACHE = list(all_groups)
                            _GROUPS_CACHE_TIME = time.time()
                        return all_groups
                        
                    offset += limit
                    success = True
                    time.sleep(0.5)
                    break
                    
                elif response.status_code == 429:
                    wait = (attempt + 1) * 5
                    logger.warning(f"[WAIT] Rate limit (429). {wait} saniye bekleniyor...")
                    time.sleep(wait)
                elif response.status_code == 404:
                    logger.error("❌ KRİTİK HATA: Kanal bulunamadı (404)! Token geçersiz veya kanal silinmiş.")
                    logger.error("👉 Lütfen Whapi panelinden Token'ınızı kontrol edin ve .env dosyasını güncelleyin.")
                    return [] # 404 durumunda denemeye gerek yok
                elif 500 <= response.status_code <= 599:
                    wait = (attempt + 1) * 3
                    logger.warning(f"[WAIT] Sunucu Hatası ({response.status_code}). Deneme {attempt+1}/{retries}. {wait} sn bekleniyor...")
                    time.sleep(wait)
                else:
                    logger.error(f"❌ API Hatası: {response.status_code} - {response.text}")
                    break
                    
            except Exception as e:
                wait = (attempt + 1) * 2
                logger.error(f"❌ İstek hatası (Ofset {offset}, Deneme {attempt+1}): {e}")
                time.sleep(wait)
        
        if not success:
            logger.error(f"[STOP] Ofset {offset} için maksimum deneme sayısına ulaşıldı. Mevcut listeyle devam ediliyor.")
            break
            
    with _GROUPS_LOCK:
        _GROUPS_CACHE = list(all_groups)
        _GROUPS_CACHE_TIME = time.time()
    return all_groups

# Global Session Cache to prevent TCP socket exhaustion during 50+ channel fetch loops
_GLOBAL_FETCH_SESSION = None

def _get_fetch_session():
    global _GLOBAL_FETCH_SESSION
    if _GLOBAL_FETCH_SESSION is None:
        _GLOBAL_FETCH_SESSION = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=100, max_retries=3)
        _GLOBAL_FETCH_SESSION.mount('https://', adapter)
    return _GLOBAL_FETCH_SESSION

def fetch_messages_from_group(group_id: str, count: int = 100, retries: int = 3, poll_params: dict = None) -> List[Dict]:
    """Belirtilen gruptan mesajları çek (Robust with retries)"""
    patch_dns()
    session = _get_fetch_session()
    
    if poll_params:
        # Build URL with dynamic parameters
        query_parts = []
        for k, v in poll_params.items():
            if k == 'use_author_filter': continue
            if isinstance(v, bool):
                query_parts.append(f"{k}={'true' if v else 'false'}")
            else:
                query_parts.append(f"{k}={v}")
        query_string = "&".join(query_parts)
        url = f"{WHAPI_BASE_URL}/messages/list/{group_id}?{query_string}"
    else:
        url = f"{WHAPI_BASE_URL}/messages/list/{group_id}?count={count}"
        
    for attempt in range(retries):
        try:
            logger.info(f"📤 API Request: GET {url}")
            response = session.get(url, headers=get_headers(), timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                messages = data.get('messages', [])
                logger.info(f"[OK] API Response (200): {len(messages)} messages fetched from {group_id}")
                return messages
            elif response.status_code == 404:
                logger.error(f"❌ Kanal bulunamadı (404): {group_id}. Token veya kanal geçersiz.")
                return []
            elif response.status_code == 429:
                wait_time = (attempt + 1) * 2
                logger.warning(f"[WAIT] API Rate Limit (429) for {group_id}. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ API Error ({response.status_code}) for {group_id}: {response.text}")
                if attempt == retries - 1: return []
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.error(f"❌ Connection Error for {group_id}: {e}")
            time.sleep((attempt + 1) * 2)
            if attempt == retries - 1: return []
        except Exception as e:
            logger.error(f"❌ Unexpected Error for {group_id}: {e}")
            return []
    return []

def convert_whapi_message(msg: Dict, group_info: Dict) -> Optional[Dict]:
    """Whapi mesaj formatını standart formata dönüştür"""
    try:
        msg_id = msg.get('id')
        if not msg_id:
            return None
        
        # Mesaj body'sini al
        body = ''
        text_data = msg.get('text')
        if isinstance(text_data, dict):
            body = text_data.get('body', '')
        elif isinstance(text_data, str):
            body = text_data
        else:
            body = msg.get('body', '')
        
        # Boş mesajları atla
        if not body or not body.strip():
            return None
        
        # Timestamp
        timestamp = msg.get('timestamp')
        timestamp_readable = None
        if timestamp:
            try:
                ts_int = int(timestamp)
                timestamp_readable = datetime.fromtimestamp(ts_int).strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        # Gönderen bilgisi
        from_info = msg.get('from', '')
        sender_name = msg.get('from_name', '')
        if not sender_name and '@' in str(from_info):
            sender_name = str(from_info).split('@')[0]
        
        # --- BLACKLIST FILTER ---
        blacklist = data_service.load_blacklist()
        if is_phone_in_list(from_info, blacklist):
            logger.info(f"🚫 Whapi Fetcher Blacklist: Skipping and marking ID handled: {from_info} (ID: {msg_id})")
            data_service.mark_id_handled(msg_id)
            return None
        
        return {
            'id': msg_id,
            'body': body,
            'timestamp': timestamp,
            'timestamp_readable': timestamp_readable,
            'chat_id': group_info.get('id', ''),
            'chat_name': group_info.get('name', group_info.get('subject', '')),
            'sender_name': sender_name,
            'from': from_info,
            'type': msg.get('type', 'text'),
            'is_processed': False
        }
    except Exception as e:
        logger.error(f" Mesaj dönüştürme hatası: {e}")
        return None

def load_existing_messages() -> Dict:
    """Mevcut mesajları yükle"""
    if os.path.exists(MESSAGE_FILE):
        try:
            with open(MESSAGE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return {'messages': data}
            return data
        except:
            pass
    return {'messages': []}

def save_messages(data: Dict):
    """Mesajları dosyaya kaydet"""
    try:
        with open(MESSAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[SAVE] Mesajlar dosyaya kaydedildi: {MESSAGE_FILE} (Toplam: {len(data.get('messages', []))})")
    except Exception as e:
        logger.error(f"❌ Mesaj kaydetme hatası: {e}")

def get_saved_chat_ids() -> Set[str]:
    """Kaydedilmiş grup ID'lerini yükle"""
    try:
        if os.path.exists(CHAT_GROUPS_FILE):
            with open(CHAT_GROUPS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return {str(g.get('id') or g.get('chat_id', '')) for g in data if g.get('id') or g.get('chat_id')}
            elif isinstance(data, dict):
                return set(data.keys())
    except:
        pass
    return set()

def fetch_all_messages(
    hours_back: float = FETCH_HOURS_BACK,
    max_messages_per_group: int = 100,
    only_saved_groups: bool = True,
    target_group_ids: Optional[List[str]] = None,
    orchestrator=None,
    status_callback = None,
    on_message_received = None,
    poll_params: dict = None,
    risk_score: int = 3
) -> int:
    """
    Tüm gruplardan mesajları çek ve kaydet
    
    Args:
        hours_back: Son kaç saatin mesajlarını çek (0.5 = 30 dakika)
        max_messages_per_group: Her gruptan maksimum mesaj sayısı
        only_saved_groups: Sadece kaydedilmiş gruplardan mı çek
        target_group_ids: Eğer belirtilirse sadece bu ID'leri çek (Batching için)
        status_callback: Canlı durum raporu için fonksiyon (dict veri gönderir)
        on_message_received: Yeni bir mesaj geldiğinde hemen çağrılacak callback (streaming)
    """

    logger.info("\n" + "="*60)
    logger.info("📲 WHAPI MESAJ SENKRONIZASYONU")
    logger.info("="*60)
    logger.info(f"⏰ Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    # Dakika veya saat olarak göster
    if hours_back < 1:
        logger.info(f"📅 Son {int(hours_back * 60)} dakikanın mesajları çekilecek")
    else:
        logger.info(f"📅 Son {hours_back} saatin mesajları çekilecek")
    logger.info(f"🔑 Token: {WHAPI_TOKEN[:8]}...{WHAPI_TOKEN[-4:]}")
    logger.info("")

    # EARLY ABORT: Check Health first before hitting all 57 channels
    health_data = check_health()
    status_raw = health_data.get('status', {})
    
    # Extract status text (Handle both dict and string responses)
    if isinstance(status_raw, dict):
        status_text = str(status_raw.get('text', 'unknown')).lower()
    else:
        status_text = str(status_raw).lower()
        
    if status_text in ['auth_required', 'disconnected']:
        logger.warning(f"⚠️ fetch_all_messages aborted: WhatsApp is disconnected ({status_text.upper()}). QR Scan required!")
        if status_callback: status_callback({'status': 'error', 'message': f'WhatsApp disconnected ({status_text.upper()})'})
        return 0
    elif status_text == 'blocked':
        logger.error("🚫 fetch_all_messages aborted: WHAPI account blocked!")
        if status_callback: status_callback({'status': 'error', 'message': 'Account Blocked'})
        return 0
    
    logger.info(f"✅ Whapi Bağlantısı Aktif: {status_text.upper()}")

    # Enforce only-saved-groups policy if requested by environment (default: enforced)
    enforce_only_saved = os.getenv('ONLY_SAVED_GROUPS_ENFORCE', '1') == '1'
    if enforce_only_saved:
        only_saved_groups = True
        logger.debug(" ONLY_SAVED_GROUPS_ENFORCE=1: Sadece `data/chat_groups.json` içindeki gruplardan çekilecek.")
    else:
        logger.debug(f"ℹ️ only_saved_groups={only_saved_groups} (env ONLY_SAVED_GROUPS_ENFORCE=0 ile değiştirebilirsiniz)")
    
    # Mevcut mesajları yükle
    existing_data = load_existing_messages()
    existing_messages = existing_data.get('messages', [])
    existing_ids = {m.get('id') for m in existing_messages if m.get('id')}
    
    logger.info(f"📁 Mevcut mesaj sayısı: {len(existing_messages)}")
    
    # Kaydedilmiş grupları al
    saved_chat_ids = get_saved_chat_ids() if only_saved_groups else set()
    if saved_chat_ids:
        logger.info(f"📋 Kaydedilmiş grup sayısı: {len(saved_chat_ids)}")
        logger.info(f"📋 Grup ID'leri: {list(saved_chat_ids)[:3]}... (ilk 3)")
    
    # Grupları optimize et: İlk çalıştırmada API'den çek, sonra hafızadan kullan (Session Cache)
    global _GROUPS_CACHE
    all_groups = []
    
    with _GROUPS_LOCK:
        # 1. Hafızada (RAM) var mı kontrol et
        if _GROUPS_CACHE:
            all_groups = _GROUPS_CACHE
            logger.info(f"💾 Hafızadan {len(all_groups)} grup kullanılıyor (API çağrısı yok).")
        else:
            # 2. Yoksa API'den çek (İlk açılış veya cache temizlendiğinde)
            logger.info("🌐 İlk çalıştırma/Cache boş: API'den güncel grup listesi çekiliyor...")
            all_groups = fetch_groups()
            if all_groups:
                _GROUPS_CACHE = all_groups  # Hafızaya kaydet
                logger.info(f"✅ API'den {len(all_groups)} grup çekildi ve hafızaya alındı.")
            else:
                if saved_chat_ids:
                    logger.info("ℹ️ API'den grup listesi alınamadı (500) ama Kayıtlı Gruplar mevcut. Bypass Mode aktif.")
                else:
                    logger.warning("⚠️ API'den grup listesi alınamadı ve kayıtlı grup da yok.")
                    return 0
    
    # 3. ROBUSTNESS: Eğer saved_chat_ids varsa ama all_groups içinde eksikse, onları ekle (Bypass API 500/Partial list)
    if saved_chat_ids:
        found_ids = {g.get('id') for g in all_groups if g.get('id')}
        missing_ids = saved_chat_ids - found_ids
        if missing_ids:
            logger.info(f"🛠️ {len(missing_ids)} kayıtlı grup API listesinde eksik. Manuel ekleniyor (Bypass Mode)...")
            for mid in missing_ids:
                all_groups.append({
                    'id': mid,
                    'name': f"Kayıtlı Grup ({mid[:8]}...)",
                    'subject': f"Kayıtlı Grup ({mid[:8]}...)"
                })
    
    # Filtreleme (Prioritize target_group_ids for batching)
    if target_group_ids:
        groups_to_fetch = [g for g in all_groups if g.get('id') in target_group_ids]
        logger.info(f"🎯 Hedeflenen {len(groups_to_fetch)} grup işleniyor (Batch modu)")
    elif only_saved_groups and saved_chat_ids:
        groups_to_fetch = [g for g in all_groups if g.get('id') in saved_chat_ids]
        logger.info(f"🎯 Filtrelenen grup sayısı: {len(groups_to_fetch)}")
        if len(groups_to_fetch) == 0:
            logger.warning(f"⚠️ Hiçbir grup eşleşmedi! API grupları: {[g.get('id')[:10] for g in all_groups[:3]]}")
    else:
        groups_to_fetch = all_groups
        
    # İnsanı davranış modelini hazırla
    from src.utils.human_behavior import HumanBehaviorModel
    behavior_model = HumanBehaviorModel()
    if risk_score:
        behavior_model.adjust_behavior_by_risk(risk_score)
    
    # 33% chance to open an unsaved group (Skip if this is a priority webhook/target fetch)
    if not target_group_ids and behavior_model.should_open_non_target_chat():
        unsaved = [g for g in all_groups if g.get('id') not in saved_chat_ids]
        if unsaved:
            groups_to_fetch.append(random.choice(unsaved))
            logger.info("👻 Human behavior: Adding 1 non-target group to simulate random browsing.")

    if not groups_to_fetch:
        logger.warning("⚠️ İşlenecek grup yok!")
        return 0
    
    # Zaman filtresi
    cutoff_time = datetime.now() - timedelta(hours=hours_back)
    cutoff_timestamp = int(cutoff_time.timestamp())
    
    new_messages = []
    total_fetched = 0
    
    for i, group in enumerate(groups_to_fetch):
        # 21% prob: enter then exit within 3 sec (Skip if this is a priority webhook/target fetch)
        if not target_group_ids and behavior_model.should_enter_then_exit_fast():
            logger.info("👻 Human behavior: Entering then exiting fast (within 3 sec).")
            time.sleep(random.uniform(0.5, 3.0))
            continue
            
        group_id = group.get('id', '')
        group_name = group.get('name', group.get('subject', 'Unknown'))
        
        logger.debug(f"  [{i+1}/{len(groups_to_fetch)}] {group_name[:40]}...")
        
        if status_callback:
            status_callback({
                'type': 'group_start',
                'group_name': group_name,
                'progress': f"{i+1}/{len(groups_to_fetch)}"
            })

        logger.info(f"⏳ [{i+1}/{len(groups_to_fetch)}] İşleniy