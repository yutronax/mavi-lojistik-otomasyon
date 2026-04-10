import json
import requests
import re
import os
import base64
import logging
from datetime import datetime, timedelta
from src.utils.phone_utils import get_phone_variants
logger = logging.getLogger(__name__)

class YukBuradaSubmitter:
    def __init__(self, config_path='tools/yukburada_config.json'):
        # Load configuration
        self.config = self.load_config(config_path)

        # Setup logging
        self.setup_logging()

        self.api_base_url = self.config.get('api_base_url', 'https://yukburadabackend.onrender.com')
        self.master_phone = self.config.get('phone_number', '')  # No hardcoded default
        self.api_key = self.config.get('api_key') or os.getenv('YUKBURADA_API_KEY')
        self.session = requests.Session()

        # Database API configuration
        self.db_api_config = self.config.get('database_api', {})
        self.db_api_base_url = self.db_api_config.get('base_url', 'https://yukburadabackend.onrender.com')
        self.db_api_key = self.db_api_config.get('api_key') or os.getenv('DATABASE_API_KEY')
        self.db_session = requests.Session() if self.db_api_config.get('use_api', False) else None

        # Set headers
        headers = self.config.get('headers', {
            'Content-Type': 'application/json',
            'User-Agent': 'MaviLojistik/1.0'
        })
        self.session.headers.update(headers)

        # Try automatic master login if api_key is missing or at startup to ensure it's valid
        if self.master_phone:
            logger.info(f"Attempting smart master login with {self.master_phone}...")
            user_info = self.get_or_create_user_with_merge(self.master_phone)
            
            if user_info:
                self.api_key = user_info.get('access_token')
                self.config['owner_user_id'] = user_info.get('user_id')
                master_name = user_info.get('fullName', 'Unknown')
                logger.info(f"Master login successful. User ID: {self.config['owner_user_id']}, Name: {master_name}")
            else:
                logger.error(f"Failed to initialize master user after all attempts.")

        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}'
            })
        
        # Cache for phone sessions to avoid redundant logins
        self.phone_sessions = {} # {phone: {"token": token, "user_id": user_id, "expires": ...}}
        
        # Persistent User Cache (Phone -> ID)
        self.known_users_file = 'yukburada_users.json'
        self.known_users = self.load_known_users()

    def load_known_users(self):
        try:
            if os.path.exists(self.known_users_file):
                with open(self.known_users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load known users: {e}")
        return {}
        
    def save_known_users(self):
        try:
            with open(self.known_users_file, 'w', encoding='utf-8') as f:
                json.dump(self.known_users, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save known users: {e}")

    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info(f"Config file not found: {config_path}, using defaults")
            return {}
        except json.JSONDecodeError as e:
            logger.info(f"Invalid JSON in config file: {e}, using defaults")
            return {}

    def setup_logging(self):
        """Setup logging configuration"""
        log_file = self.config.get('log_file', 'yukburada_submission.log')

        # Create logger
        self.logger = logging.getLogger('YukBuradaSubmitter')
        self.logger.setLevel(logging.INFO)

        # Remove any existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create formatters
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def fetch_approved_records_from_api(self):
        """Fetch approved records from database API"""
        if not self.db_session:
            self.logger.error("Database API session not initialized")
            return []

        endpoint = self.db_api_config.get('approved_records_endpoint', '/api/approved-loads')
        url = f"{self.db_api_base_url}{endpoint}"

        # Set headers for database API
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'MaviLojistik/1.0'
        }
        if self.db_api_key:
            headers['Authorization'] = f'Bearer {self.db_api_key}'

        self.db_session.headers.update(headers)

        try:
            timeout = self.db_api_config.get('timeout_seconds', 30)
            response = self.db_session.get(url, timeout=timeout)
            response.raise_for_status()

            data = response.json()
            # Handle different response formats: items, records, or direct array
            records = data.get('items', data.get('records', data))

            if isinstance(records, list):
                self.logger.info(f"Fetched {len(records)} approved records from API")
                return records
            else:
                self.logger.error("API response does not contain a records/items array")
                return []

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch approved records from API: {e}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response from API: {e}")
            return []

    def ensure_auth_for_phone(self, phone_number, full_name=None, email=None):
        """
        Ensures the user is registered and logged in for the given phone number.
        Returns a tuple: (access_token, user_id)
        """
        # Cleanup phone number (digits only)
        import re
        clean_phone = re.sub(r'\D', '', str(phone_number))
        
        # Standardize to 0XXXXXXXXXX (11 digits)
        if len(clean_phone) == 10:
            clean_phone = '0' + clean_phone
        elif len(clean_phone) == 12 and clean_phone.startswith('90'):
            clean_phone = '0' + clean_phone[2:]
        
        # NOTE: This ensures consistent formatting (e.g., 0532...) 
        # avoiding "0532..." vs "90532..." duplicate user issues.
            
        # Check cache
        if clean_phone in self.phone_sessions:
            session = self.phone_sessions[clean_phone]
            return session['token'], session['user_id']
            
        self.logger.info(f"Ensuring auth for: {clean_phone}")
        
        # 1. Try Login
        login_res = self.login_user(clean_phone)
        if login_res.get('success'):
            token = login_res.get('access_token')
            user_id = login_res.get('user_id')
            self.phone_sessions[clean_phone] = {"token": token, "user_id": user_id}
            
            # Update known users
            if self.known_users.get(clean_phone) != user_id:
                self.known_users[clean_phone] = user_id
                self.save_known_users()
                
            return token, user_id
            
        # 2. If Login fails with 404, try Register (Strict Check)
        if login_res.get('status') == 404:
            # Check if we knew this user
            if clean_phone in self.known_users:
                self.logger.warning(f"⚠️ User {clean_phone} known locall as {self.known_users[clean_phone]} but 404 on API. Re-registering...")
                
            self.logger.info(f"User not found (404) for {clean_phone}, attempting registration...")
            reg_res = self.register_phone_number(clean_phone, full_name=full_name, email=email)
        else:
            self.logger.error(f"Login failed for {clean_phone} with error: {login_res.get('error')}. NOT registering.")
            return None, None
        
        # 3. Try Login again after registration
        login_res = self.login_user(clean_phone)
        if login_res.get('success'):
            token = login_res.get('access_token')
            user_id = login_res.get('user_id')
            self.phone_sessions[clean_phone] = {"token": token, "user_id": user_id}
            
            # Update known users
            self.known_users[clean_phone] = user_id
            self.save_known_users()
            
            return token, user_id
            
        self.logger.error(f"Could not ensure auth for {clean_phone}")
        return None, None

    def fetch_live_loads(self):
        """Fetch all live loads from the main API"""
        url = f"{self.api_base_url}/api/Loads"
        
        try:
            # Fetch with dynamic headers to avoid permanent session update
            headers = {}
            if self.master_phone:
                token, _ = self.ensure_auth_for_phone(self.master_phone)
                if token:
                    headers['Authorization'] = f'Bearer {token}'
            
            response = self.session.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                self.logger.error(f"Live loads error: {response.status_code} - {response.text}")
            response.raise_for_status()
            
            records = response.json()
            # The API might return { "items": [...] } or { "loads": [...] } or just a list [...]
            if isinstance(records, dict):
                # Try common keys
                records = records.get('loads') or records.get('items') or records.get('data') or []
            
            if isinstance(records, list):
                self.logger.info(f"Fetched {len(records)} live loads from API")
                return records
            
            self.logger.warning(f"Unexpected response format from /api/Loads: {type(records)}")
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to fetch live loads: {e}")
            return []

    def load_approved_records(self, file_path=None):
        """Load approved records from API or JSON file"""
        # Check if API should be used
        if self.db_api_config.get('use_api', False):
            records = self.fetch_approved_records_from_api()
            if records:
                return records
            self.logger.warning("Failed to fetch from API, falling back to local file")

        # Fallback to local file
        file_path = file_path or self.config.get('approved_records_file', 'onaylanan_kayitlar.json')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
            self.logger.info(f"Loaded {len(records)} approved records from file")
            return records
        except FileNotFoundError:
            self.logger.error(f"File not found: {file_path}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
            return []


    def transform_record_to_payload(self, record):
        """Transform a single record to YukBurada API payload format"""
        from datetime import datetime
        
        # Varsayılan değerler
        tel = ""  # Telefon numarası varsayılan boş
        
        # Hangi formatta olduğunu kontrol et
        # 1. API formatı: pickupCity
        # 2. GUI formatı: yuklenme_yeri_ili
        # 3. Parser formatı: nereden_il, nereden_ilce
        # 4. Eski format: nerden (string parse)
        
        if 'pickupCity' in record:
            # API'den gelen format
            pickup_city = record.get("pickupCity", "")
            pickup_ilce = record.get("pickupDistrict", "")
            delivery_city = record.get("deliveryCity", "")
            delivery_ilce = record.get("deliveryDistrict", "")
            load_type = record.get("loadType", "KOMPLE")
            weight = record.get("weight", 1001)
            price = record.get("price", 0)
            description = record.get("orijinal_mesaj", record.get("description", ""))
            vehicle_types = record.get("requiredVehicleTypes", [])
            pricing_mode = record.get("pricingMode", 1)
        elif 'yuklenme_yeri_ili' in record:
            # GUI formatı - doğrudan il/ilçe alanları var
            pickup_city = record.get("yuklenme_yeri_ili", "")
            pickup_ilce = record.get("yuklenme_yeri_ilcesi", "")
            delivery_city = record.get("varış_yeri_ili", "")
            delivery_ilce = record.get("varış_yeri_ilcesi", "")
            
            # Yük tipini al
            yuk_tipi = record.get("yuk_tipi", "KOMPLE")
            load_type = yuk_tipi if isinstance(yuk_tipi, str) else "KOMPLE"
            
            # Tonajı al
            tonaj = record.get("yuk_tonaji")
            weight = int(tonaj * 1000) if tonaj else 1001
            
            # Araç/kasa kombinasyonlarını al
            kombos = record.get("arac_kasa_kombinasyon_listesi", [])
            if kombos:
                # Kombinasyonları boşlukla birleştir: "1360-AÇIK" -> "1360 AÇIK"
                vehicle_types = [k.replace("-", " ") for k in kombos]
            else:
                vehicle_types = record.get("arac_tipi", ["Tir"])
            
            # Telefon bilgisi
            tel_list = record.get("telefon_numarasi", [])
            tel = tel_list[0] if tel_list else ""
            description = record.get("orijinal_mesaj", record.get("aciklama", ""))
            
            price = 0
            pricing_mode = 1  # Pazarlıklı
        elif 'nereden_il' in record:
            # Parser formatı - nereden_il, nereden_ilce, nereye_il, nereye_ilce
            pickup_city = record.get("nereden_il", "")
            pickup_ilce = record.get("nereden_ilce", "")
            delivery_city = record.get("nereye_il", "")
            delivery_ilce = record.get("nereye_ilce", "")
            
            # Yük tipini al
            yuk_tipi = record.get("yuk_tipi", [])
            if isinstance(yuk_tipi, list):
                load_type = yuk_tipi[0] if yuk_tipi else "KOMPLE"
            else:
                load_type = yuk_tipi or "KOMPLE"
            
            # Tonaj - parser'da bu alan yok, varsayılan
            weight = 1001
            
            # Araç/kasa kombinasyonlarını al
            kombos = record.get("arac_kasa_kombinasyon_listesi", [])
            if kombos:
                # Kombinasyonları boşlukla birleştir: "1360-AÇIK" -> "1360 AÇIK"
                vehicle_types = [k.replace("-", " ") for k in kombos]
            else:
                arac_tipi = record.get("arac_tipi", [])
                vehicle_types = arac_tipi if arac_tipi else ["Tir"]
            
            # Telefon bilgisi (parser'da string olarak)
            tel = record.get("telefon", "")
            description = record.get("orijinal_mesaj", record.get("aciklama", ""))
            
            price = 0
            pricing_mode = 1  # Pazarlıklı
        else:
            # Eski dosya formatı - nerden/nereye alanlarından il/ilçe ayır
            nerden = record.get("nerden", "")
            nereye = record.get("nereye", "")
            
            # Format: "İL İlçe" veya sadece "İL"
            nerden_parts = nerden.split() if nerden else []
            nereye_parts = nereye.split() if nereye else []
            
            pickup_city = nerden_parts[0] if nerden_parts else ""
            pickup_ilce = " ".join(nerden_parts[1:]) if len(nerden_parts) > 1 else ""
            
            delivery_city = nereye_parts[0] if nereye_parts else ""
            delivery_ilce = " ".join(nereye_parts[1:]) if len(nereye_parts) > 1 else ""
            
            # Yük tipini al
            yuk_tipi = record.get("yuk_tipi", [])
            if isinstance(yuk_tipi, list):
                load_type = ",".join(yuk_tipi) if yuk_tipi else "KOMPLE"
            else:
                load_type = yuk_tipi or "KOMPLE"
            
            # Araç tiplerini listeye çevir
            arac_tipi = record.get("arac_tipi", [])
            if isinstance(arac_tipi, str):
                vehicle_types = [arac_tipi]
            else:
                vehicle_types = arac_tipi if arac_tipi else []
            
            # Fiyatı sayıya çevir
            fiyat_str = record.get("fiyat", "0")
            try:
                price = int(''.join(filter(str.isdigit, str(fiyat_str)))) if fiyat_str else 0
            except:
                price = 0
            
            weight = 1001
            tel = record.get("telefon", "")  # Telefon numarasını al
            description = record.get("orijinal_mesaj", record.get("aciklama", ""))
            pricing_mode = 0 if price > 0 else 1  # 0=Fixed, 1=Negotiable
        
        # pricingMode: 0=Fixed (fiyat > 0 ise), 1=Negotiable (pazarlıklı)
        # requiredVehicleTypes boş olamaz, varsayılan "Tir"
        final_pricing_mode = 0 if price > 0 else 1
        final_vehicle_types = vehicle_types if vehicle_types else ["Tir"]
        
        # YukBurada API /api/Loads/batch payload formatı (Structure 2 - Flat)
        payload = {
            "pickupCity": pickup_city,
            "pickupIlce": pickup_ilce,
            "pickupDistrict": pickup_ilce,
            "pickupDate": datetime.now().isoformat() + "Z",
            "ownerUserId": self.config.get("owner_user_id", ""),
            "deliveryCity": delivery_city,
            "deliveryIlce": delivery_ilce,
            "deliveryDistrict": delivery_ilce,
            "vehicleCount": 1,
            "loadType": load_type.upper() if isinstance(load_type, str) else "KOMPLE",
            "weight": weight,
            "price": price,
            "pricingMode": final_pricing_mode,
            "requiredVehicleTypes": final_vehicle_types,
            "description": description,
            "_phone": tel # Internal field for ID lookup
        }

        return payload

    def _get_load_fingerprint(self, payload):
        """İlan için benzersiz bir parmak izi oluşturur"""
        def normalize(val):
            if isinstance(val, list):
                vals = sorted([str(v).lower().strip() for v in val if v])
                return ",".join(vals)
            return str(val or '').lower().strip()

        # Rota, Yük Tipi, Araç Tipi ve Sahibi bazlı parmak izi
        fp_parts = [
            normalize(payload.get('pickupCity')),
            normalize(payload.get('pickupIlce') or payload.get('pickupDistrict')),
            normalize(payload.get('deliveryCity')),
            normalize(payload.get('deliveryIlce') or payload.get('deliveryDistrict')),
            normalize(payload.get('loadType')),
            normalize(payload.get('requiredVehicleTypes')),
            str(payload.get('ownerUserId', '')).strip()
        ]
        return "|".join(fp_parts)

    def is_load_duplicate_on_remote(self, payload, remote_loads, session_fingerprints=None):
        """İlanın YükBurada üzerinde veya bu oturumda zaten olup olmadığını kontrol eder"""
        current_fp = self._get_load_fingerprint(payload)
        
        # 1. Bu oturumda gönderilenler arasında var mı?
        if session_fingerprints and current_fp in session_fingerprints:
            return True

        # 2. Canlı sistemde var mı?
        if not remote_loads:
            return False
        
        for load in remote_loads:
            # Remote load'u payload formatına benzeterek parmak izini al
            remote_fp = self._get_load_fingerprint(load)
            if current_fp == remote_fp:
                return True
        return False

    def periodic_remote_cleanup(self):
        """YükBurada üzerindeki mükerrer ilanlarımızı tarar ve temizler (10 dk'da bir)."""
        self.logger.info("🧹 Periyodik YükBurada mükerrer temizliği başlatılıyor...")
        
        # 1. Tüm canlı ilanları çek
        live_loads = self.fetch_live_loads()
        if not live_loads:
            self.logger.info("Temizlenecek canlı ilan bulunamadı.")
            return 0

        # 2. Sadece bizim user_id'lerimize ait olanları grupla
        # (Self.known_users içindeki tüm user_id'leri kontrol et)
        my_user_ids = set(str(uid) for uid in self.known_users.values())
        if self.config.get('owner_user_id'):
            my_user_ids.add(str(self.config['owner_user_id']))

        my_loads = []
        for load in live_loads:
            owner_id = str(load.get('ownerUserId', ''))
            if not owner_id and isinstance(load.get('ownerInfo'), dict):
                owner_id = str(load['ownerInfo'].get('id', ''))
            
            if owner_id in my_user_ids:
                my_loads.append(load)

        if not my_loads:
            self.logger.info("Bize ait canlı ilan bulunamadı.")
            return 0

        # 3. Mükerrerleri tespit et (En yeniyi korumak için tersten tara)
        # my_loads genellikle API'den geldiği gibi (karmaşık veya tarihe göre olabilir)
        # createdAt'e göre sıralayalım
        try:
            my_loads.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        except: pass

        fingerprints = set()
        to_delete = []
        
        for load in my_loads:
            fp = self._get_load_fingerprint(load)
            if fp in fingerprints:
                # Zaten daha yenisi (sıraladığımız için) listeye eklendi, bu mükerrerdir
                load_id = load.get('id')
                if load_id:
                    to_delete.append(load_id)
            else:
                fingerprints.add(fp)

        # 4. Silme işlemleri
        deleted_count = 0
        for load_id in to_delete:
            try:
                url = f"{self.api_base_url}/api/Loads/{load_id}"
                # Silme işlemi için master token kullanabiliriz (yetkili ise)
                # veya ilan sahibinin token'ını bulmalıyız.
                # Şimdilik mevcut session (master) ile deneyelim.
                resp = self.session.delete(url, timeout=20)
                if resp.ok:
                    deleted_count += 1
                    self.logger.info(f"🗑️ Mükerrer ilan silindi: {load_id}")
            except Exception as e:
                self.logger.error(f"İlan {load_id} silinemedi: {e}")

        if deleted_count > 0:
            self.logger.info(f"✨ Toplam {deleted_count} mükerrer ilan temizlendi.")
        else:
            self.logger.info("Mükerrer ilan bulunamadı.")
            
        return deleted_count

    def cleanup_old_loads(self, owner_user_id):
        """Delete loads older than 1 hour for the given user"""
        if not owner_user_id:
            return

        try:
            # 1. Fetch live loads
            url = f"{self.api_base_url}/api/Loads"
            
            response = self.session.get(url, timeout=30)
            if not response.ok:
                return

            loads_data = response.json()
            loads = []
            
            # Handle different response structures
            if isinstance(loads_data, list):
                loads = loads_data
            elif isinstance(loads_data, dict) and 'data' in loads_data:
                loads = loads_data['data']
            
            if not loads:
                return

            # 2. Filter by owner and time
            now = datetime.now()
            threshold = now - timedelta(hours=1)
            
            count = 0
            for load in loads:
                # Check ownership
                load_owner = str(load.get('ownerUserId', ''))
                # Also check nested ownerInfo if top level is missing
                if not load_owner and isinstance(load.get('ownerInfo'), dict):
                    load_owner = str(load['ownerInfo'].get('id', ''))
                
                if load_owner != str(owner_user_id):
                    continue
                    
                # Check time
                created_at_str = load.get('createdAt')
                if not created_at_str:
                    continue
                    
                try:
                    # Handle ISO format (simple clean up)
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str[:-1]
                    
                    # Split fractional seconds to avoid format issues
                    clean_date_str = created_at_str.split('.')[0]
                    created_at = datetime.fromisoformat(clean_date_str)
                    
                    if created_at < threshold:
                        # 3. Delete old load
                        load_id = load.get('id')
                        if load_id:
                            del_url = f"{self.api_base_url}/api/Loads/{load_id}"
                            del_resp = self.session.delete(del_url, timeout=30)
                            if del_resp.ok:
                                count += 1
                                self.logger.info(f"Deleted old load {load_id} for user {owner_user_id} (Created: {created_at})")
                except Exception as ex:
                    continue

            if count > 0:
                self.logger.info(f"Cleaned up {count} old loads for user {owner_user_id}")
                
        except Exception as e:
            self.logger.warning(f"Cleanup warning (non-critical): {e}")

    def submit_single_load(self, payload, token=None):
        """Submit a single load to the API"""
        url = f"{self.api_base_url}/api/Loads"
        
        # Otomatik token ve owner tespiti
        phone = payload.pop('_phone', None)
        if not token and phone:
            user_info = self.get_or_create_user_with_merge(phone)
            if user_info:
                token = user_info.get('access_token')
                payload['ownerUserId'] = user_info.get('user_id')
                self.logger.info(f"Auto-detected token for {phone}")

        if not payload.get('ownerUserId') and not token:
             self.logger.error("No ownerUserId or token available for submission. Skipping.")
             return {"success": False, "error": "No owner detected"}

        # Dinamik token ayarı
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code not in [200, 201]:
                self.logger.error(f"Submission error: {response.status_code} - {response.text}")
            response.raise_for_status()

            res_data = response.json() if response.content else {}
            # Single load response might be the object itself, extract ID
            load_id = res_data.get('id', 'unknown') if isinstance(res_data, dict) else str(res_data)

            self.logger.info(f"Successfully submitted load. ID: {load_id}")
            
            # Başarılı gönderimi kaydet
            self._mark_as_submitted(payload)
            
            # Eski ilanları temizle (1 saatten eski olanlar)
            owner_id = payload.get('ownerUserId')
            if owner_id:
                self.cleanup_old_loads(owner_id)
            
            return {
                "success": True,
                "load_id": load_id,
                "response": res_data
            }

        except Exception as e:
            self.logger.error(f"Failed to submit load: {e}")
            # Safely get pickupCity for the return
            p_city = "unknown"
            if isinstance(payload, dict):
                p_city = payload.get("pickupCity", "unknown")
                
            return {
                "success": False,
                "load_id": p_city,
                "error": str(e)
            }

    def register_phone_number(self, phone_number, full_name=None, email=None, address=None):
        """Register a phone number as a user"""
        url = f"{self.api_base_url}/api/Users/register"
        
        payload = {
            "fullName": full_name or phone_number,
            "phoneNumber": phone_number,
            "secondaryPhoneNumber": phone_number,
            "email": email or "",
            "address": address or "",
            "role": 0
        }

        # Register için ayrı session kullan, authorization olmadan
        import requests
        try:
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 409:  # Conflict - already exists
                self.logger.info(f"Phone number {phone_number} already registered, skipping")
                return {
                    "success": True,
                    "already_exists": True,
                    "message": "Phone number already registered"
                }
            
            response.raise_for_status()
            
            self.logger.info(f"Successfully registered phone number: {phone_number}")
            
            return {
                "success": True,
                "already_exists": False,
                "response": response.json() if response.content else None
            }

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to register phone number {phone_number}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def login_user(self, phone_number):
        """Login user with phone number and get access token"""
        url = f"{self.api_base_url}/api/Users/login"
        
        payload = {
            "phoneNumber": phone_number
        }

        # Login için ayrı session kullan, authorization olmadan
        import requests
        try:
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 404:
                return {
                    "success": False, 
                    "status": 404, 
                    "error": "User not found"
                }

            response.raise_for_status()
            
            data = response.json()
            access_token = data.get('accessToken') or data.get('token')
            
            if access_token:
                # Update session headers with the new token
                self.session.headers.update({
                    'Authorization': f'Bearer {access_token}'
                })
                
                # JWT token'dan user id'yi çıkar
                import base64
                try:
                    # JWT payload kısmını decode et
                    payload_part = access_token.split('.')[1]
                    # Base64 decode
                    import binascii
                    payload_decoded = base64.urlsafe_b64decode(payload_part + '==')
                    import json
                    token_data = json.loads(payload_decoded)
                    user_id = token_data.get('sub')
                    
                    self.logger.info(f"Successfully logged in user: {phone_number}, user_id: {user_id}")
                    return {
                        "success": True,
                        "access_token": access_token,
                        "user_id": user_id,
                        "user_data": data
                    }
                except Exception as decode_error:
                    self.logger.warning(f"Could not decode JWT token: {decode_error}")
                    return {
                        "success": True,
                        "access_token": access_token,
                        "user_data": data
                    }
            else:
                self.logger.error(f"Login response does not contain access token for {phone_number}")
                return {
                    "success": False,
                    "error": "No access token in response"
                }

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to login user {phone_number}: {e}")
            return {
                "success": False,
                "error": str(e)
            }


    def normalize_phone_variants(self, phone):
        """Use centralized variants from phone_utils"""
        return get_phone_variants(phone)

    def get_or_create_user_with_merge(self, phone):
        """Smartly handle login, merging redundant accounts, or creating new one"""
        variants = self.normalize_phone_variants(phone)
        if not variants:
            return None
            
        found_accounts = [] # List of {phone, user_id, token, fullName}
        
        self.logger.info(f"Investigating accounts for {phone} variants: {variants}")
        
        # 1. Probe all variants
        for v in variants:
            login_res = self.login_user(v)
            if login_res.get('success'):
                token = login_res.get('access_token')
                user_id = login_res.get('user_id')
                
                # Fetch profile to check name
                name = v # default
                try:
                    # Try alternate endpoint directly for reliability
                    alt_url = f"{self.api_base_url}/api/Users/{user_id}"
                    resp = requests.get(alt_url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
                    if resp.ok:
                        data = resp.json()
                        name = data.get('fullName', v)
                except:
                    pass
                
                found_accounts.append({
                    "phone": v,
                    "user_id": user_id,
                    "access_token": token,
                    "fullName": name
                })
        
        # 2. If none found, register with '0' prefix
        if not found_accounts:
            primary_v = variants[0] # The '0' prefix variant
            self.logger.info(f"No account found for prefix variants. Registering new: {primary_v}")
            reg_info = self.config.get('registration_info', {})
            reg_res = self.register_phone_number(
                primary_v,
                full_name=reg_info.get('fullName', primary_v),
                email=reg_info.get('email', 'kuyusuzyusuf123@gmail.com')
            )
            # Login after reg
            if reg_res.get('success'):
                login_res = self.login_user(primary_v)
                if login_res.get('success'):
                    return {
                        "access_token": login_res.get('access_token'),
                        "user_id": login_res.get('user_id'),
                        "fullName": primary_v
                    }
            return None

        # 3. Multiple found - select primary and delete others
        import re
        def is_real_name(name):
            if not name: return False
            # If name is just digits, it's not a "real" name
            return not re.match(r'^[\d\s\-\+]+$', str(name).strip())

        # Sort: accounts with real names first, then by variant priority
        found_accounts.sort(key=lambda x: (not is_real_name(x['fullName']), variants.index(x['phone'])))
        
        primary = found_accounts[0]
        others = found_accounts[1:]
        
        self.logger.info(f"Selected primary account: {primary['phone']} (Name: {primary['fullName']}, ID: {primary['user_id']})")
        
        # 4. Migrate and Delete redundant variants
        for other in others:
            self.logger.warning(f"Merging/Migrating account variant: {other['phone']} (ID: {other['user_id']})")
            
            # Migrate assets before deleting
            self._migrate_assets(other, primary)
            
            try:
                # Use their own token to delete themselves
                headers = {'Authorization': f'Bearer {other["access_token"]}'}
                del_url = f"{self.api_base_url}/api/Users/{other['user_id']}"
                resp = requests.delete(del_url, headers=headers, timeout=10)
                if resp.ok:
                    self.logger.info(f"Successfully deleted merged account variant: {other['phone']}")
            except Exception as e:
                self.logger.error(f"Could not delete redundant variant {other['phone']}: {e}")
                
        return primary

    def _migrate_assets(self, source_acc, target_acc):
        """Migrate loads and vehicles from source account to target account"""
        source_headers = {'Authorization': f'Bearer {source_acc["access_token"]}'}
        target_headers = {'Authorization': f'Bearer {target_acc["access_token"]}'}
        
        # 1. Migrate Loads
        try:
            # Try to fetch source loads
            load_url = f"{self.api_base_url}/api/Loads/my-loads"
            resp = requests.get(load_url, headers=source_headers, timeout=10)
            if resp.ok:
                loads = resp.json()
                if isinstance(loads, dict) and 'items' in loads: loads = loads['items']
                
                if loads and isinstance(loads, list):
                    self.logger.info(f"Found {len(loads)} loads to migrate from {source_acc['phone']}")
                    for load in loads:
                        # Prepare payload for target (remove IDs and specific fields)
                        new_load = load.copy()
                        for key in ['id', 'createdAt', 'updatedAt', 'ownerInfo', 'ownerUserId']:
                            new_load.pop(key, None)
                        
                        new_load['ownerUserId'] = target_acc['user_id']
                        
                        # Re-submit to target
                        submit_url = f"{self.api_base_url}/api/Loads"
                        requests.post(submit_url, json=new_load, headers=target_headers, timeout=10)
        except Exception as e:
            self.logger.error(f"Error migrating loads: {e}")

        # 2. Migrate Vehicles
        try:
            veh_url = f"{self.api_base_url}/api/Vehicles/user/{source_acc['user_id']}"
            resp = requests.get(veh_url, headers=source_headers, timeout=10)
            if resp.ok:
                vehicles = resp.json()
                if vehicles and isinstance(vehicles, list):
                    self.logger.info(f"Found {len(vehicles)} vehicles to migrate from {source_acc['phone']}")
                    for veh in vehicles:
                        new_veh = veh.copy()
                        for key in ['id', 'createdAt', 'updatedAt', 'ownerInfo', 'userId']:
                            new_veh.pop(key, None)
                        
                        new_veh['userId'] = target_acc['user_id']
                        
                        # Re-submit to target
                        submit_veh_url = f"{self.api_base_url}/api/Vehicles"
                        requests.post(submit_veh_url, json=new_veh, headers=target_headers, timeout=10)
        except Exception as e:
            self.logger.error(f"Error migrating vehicles: {e}")

    def get_user_info(self, access_token):
        """Get user info using access token"""
        url = f"{self.api_base_url}/api/User/me"  # Try with /api/User/me
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            owner_id = data.get('id') or data.get('userId') or data.get('ownerId')
            
            self.logger.info(f"Successfully got user info, owner_id: {owner_id}")
            return {
                "success": True,
                "owner_id": owner_id,
                "user_data": data
            }

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get user info: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _mark_as_submitted(self, payload):
        """Gönderilen kayıtları işaretle"""
        submitted_file = 'gonderilmis_kayitlar.json'
        try:
            if os.path.exists(submitted_file):
                with open(submitted_file, 'r', encoding='utf-8') as f:
                    submitted = json.load(f)
            else:
                submitted = []
            
            # Kayıt ID'sini oluştur (pickupCity + deliveryCity + timestamp)
            record_id = f"{payload.get('pickupCity')}_{payload.get('destinations', [{}])[0].get('deliveryCity')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            submitted.append({
                'id': record_id,
                'payload': payload,
                'timestamp': datetime.now().isoformat()
            })
            
            with open(submitted_file, 'w', encoding='utf-8') as f:
                json.dump(submitted, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to mark as submitted: {e}")

    def submit_batch_loads(self, payloads, token=None):
        """Submit multiple loads in batch"""
        url = f"{self.api_base_url}/api/Loads/batch"

        # Dinamik token ayarı
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
            self.logger.info(f"Using provided token for batch submission")

        try:
            response = self.session.post(url, json=payloads, headers=headers, timeout=60)
            response.raise_for_status()

            self.logger.info(f"Successfully submitted batch of {len(payloads)} loads")
            return {
                "success": True,
                "batch_size": len(payloads),
                "response": response.json() if response.content else None
            }

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to submit batch: {e}")
            return {
                "success": False,
                "batch_size": len(payloads),
                "error": str(e)
            }

    def process_approved_loads(self, use_batch=True, batch_size=10):
        """Process all approved loads"""
        records = self.load_approved_records()
        if not records:
            self.logger.warning("No approved records found")
            return []

        # Daha önce gönderilenleri filtrele
        records_to_send = self._filter_already_submitted(records)
        if not records_to_send:
            self.logger.info("All records have been submitted already")
            return []
        
        self.logger.info(f"Processing {len(records_to_send)} new records (filtered from {len(records)} total)")

        # 1. Uzaktaki (YükBurada) canlı ilanları çek
        remote_loads = self.fetch_live_loads()
        
        results = []

        if use_batch:
            # Group by owner AND token to submit separate batches
            # structure: {owner_id: {"token": token, "payloads": []}}
            owner_groups = {} 
            
            session_fps = set()
            for record in records_to_send:
                payload = self.transform_record_to_payload(record)
                phone = payload.pop('_phone', None)
                
                # NORMAL GÖNDERİM KURALLARI:
                # 1. Mesajdaki numara (phone), 2. Gönderen numara
                # Fallback to master (config) is REMOVED as per user request.
                
                owner_id = None
                token = None
                
                if phone:
                    user_info = self.get_or_create_user_with_merge(phone)
                    if user_info:
                        owner_id = user_info.get('user_id')
                        token = user_info.get('access_token')
                
                if not owner_id:
                    self.logger.warning(f"⚠️ İlan sahibi tespit edilemedi, atlanıyor: {payload.get('pickupCity')} -> {payload.get('deliveryCity')}")
                    continue
                
                payload['ownerUserId'] = owner_id
                
                # ANLIK MÜKERRER KONTROLÜ (Oturum bazlı takipli)
                if self.is_load_duplicate_on_remote(payload, remote_loads, session_fingerprints=session_fps):
                    self.logger.info(f"🚫 [MÜKERRER ENGEL] İlan YükBurada'da zaten var veya bu batch'te gönderildi: {payload.get('pickupCity')} -> {payload.get('deliveryCity')}")
                    continue

                if owner_id not in owner_groups:
                    owner_groups[owner_id] = {"token": token, "payloads": []}
                owner_groups[owner_id]["payloads"].append(payload)
                
                # Bu batch için işaretle
                session_fps.add(self._get_load_fingerprint(payload))

            # Submit batches
            for owner_id, group in owner_groups.items():
                payloads = group["payloads"]
                token = group["token"]
                # Split large batches by batch_size
                for i in range(0, len(payloads), batch_size):
                    chunk = payloads[i:i + batch_size]
                    result = self.submit_batch_loads(chunk, token=token)
                    results.append(result)
        else:
            # Process individually
            session_fps = set()
            for record in records_to_send:
                payload = self.transform_record_to_payload(record)
                phone = payload.pop('_phone', None)
                
                owner_id = None
                token = None
                
                if phone:
                    user_info = self.get_or_create_user_with_merge(phone)
                    if user_info:
                        owner_id = user_info.get('user_id')
                        token = user_info.get('access_token')
                
                if not owner_id:
                    self.logger.warning(f"⚠️ İlan sahibi tespit edilemedi, atlanıyor: {payload.get('pickupCity')} -> {payload.get('deliveryCity')}")
                    continue
                
                payload['ownerUserId'] = owner_id

                # ANLIK MÜKERRER KONTROLÜ (Oturum bazlı takipli)
                if self.is_load_duplicate_on_remote(payload, remote_loads, session_fingerprints=session_fps):
                    self.logger.info(f"🚫 [MÜKERRER ENGEL] İlan YükBurada'da zaten var veya az önce gönderildi: {payload.get('pickupCity')} -> {payload.get('deliveryCity')}")
                    continue

                result = self.submit_single_load(payload, token=token)
                results.append(result)
                
                if result.get("success"):
                    session_fps.add(self._get_load_fingerprint(payload))

        return results

        return results
    
    def _filter_already_submitted(self, records):
        """Daha önce gönderilen kayıtları filtrele"""
        submitted_file = 'gonderilmis_kayitlar.json'
        
        # Gönderilenleri yükle
        submitted_ids = set()
        if os.path.exists(submitted_file):
            try:
                with open(submitted_file, 'r', encoding='utf-8') as f:
                    submitted = json.load(f)
                # Her kaydın unique ID'sini oluştur
                for item in submitted:
                    payload = item.get('payload', {})
                    # ID: pickupCity + deliveryCity (timestamp olmadan, çünkü aynı rota tekrar gönderilebilir)
                    record_signature = f"{payload.get('pickupCity')}_{payload.get('destinations', [{}])[0].get('deliveryCity')}"
                    submitted_ids.add(record_signature)
            except Exception as e:
                self.logger.warning(f"Failed to load submitted records: {e}")
        
        # Henüz gönderilmeyenleri filtrele
        filtered = []
        for record in records:
            # Record'un signature'ını oluştur
            pickup = record.get('yuklenme_yeri_ili', record.get('nereden_il', record.get('pickupCity', '')))
            delivery = record.get('varış_yeri_ili', record.get('nereye_il', record.get('deliveryCity', '')))
            
            # Eski format için parse et
            if not pickup and 'nerden' in record:
                nerden_parts = record.get('nerden', '').split()
                pickup = nerden_parts[0] if nerden_parts else ''
            if not delivery and 'nereye' in record:
                nereye_parts = record.get('nereye', '').split()
                delivery = nereye_parts[0] if nereye_parts else ''
            
            record_signature = f"{pickup}_{delivery}"
            
            if record_signature not in submitted_ids:
                filtered.append(record)
        
        return filtered

    def save_results(self, results, filename=None):
        """Save submission results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"submission_results_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Results saved to {filename}")

def main():
    # Initialize submitter
    submitter = YukBuradaSubmitter()

    # Process approved loads
    submitter.logger.info("Starting submission of approved loads...")
    results = submitter.process_approved_loads(use_batch=True, batch_size=5)

    # Save results
    submitter.save_results(results)

    # Summary
    successful = sum(1 for r in results if r.get("success", False))
    total = len(results)
    submitter.logger.info(f"Submission completed: {successful}/{total} successful")

    logger.info(f"Submission completed: {successful}/{total} successful")
    logger.info(f"Check yukburada_submission.log for details")

if __name__ == "__main__":
    main()
