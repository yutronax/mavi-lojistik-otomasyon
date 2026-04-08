# -*- coding: utf-8 -*-
"""
Lokasyon Yardımcı Modülü

Mahalle eşleştirmeleri ve tanıdık yer yönetimi için yardımcı fonksiyonlar.
"""

import json
import logging
import difflib
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from src.utils.file_operations import load_json_safe

logger = logging.getLogger(__name__)


class LocationHelper:
    """
    Mahalle ve tanıdık yer yönetimi için yardımcı sınıf.
    
    Özellikler:
    - Mahalle → İl/İlçe eşleştirmesi
    - Özel tanıdık yer ekleme/arama
    - Fuzzy matching ile esnek arama
    """
    
    def __init__(self, data_dir: str, data_service=None):
        """
        Args:
            data_dir: Data klasörünün yolu
            data_service: Opsiyonel DataService veya MongoDataService örneği
        """
        self.data_dir = Path(data_dir)
        self.data_service = data_service
        self.tanidk_yerler_file = self.data_dir / 'tanidk_yerler.json'
        self.il_ilce_mahalle_file = self.data_dir / 'il_ilçe_mahalle.json'
        self.il_ilceler_file = self.data_dir / 'il_ilçeler.json'
        
        # Cache
        self._tanidk_yerler = None
        self._mahalle_index = None

    def load_il_ilce_mahalle(self) -> List[Dict]:
        """Tüm il/ilçe/mahalle verisini yükle (Öncelik: MongoDB)"""
        try:
            # Önce MongoDB'den dene
            if self.data_service and hasattr(self.data_service, 'load_config'):
                mongo_data = self.data_service.load_config('il_ilce_mahalle')
                if mongo_data:
                    return mongo_data
            
            # Yerel dosya fallback
            if self.il_ilce_mahalle_file.exists():
                with open(self.il_ilce_mahalle_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"İl/İlçe/Mahalle verisi yüklenemedi: {e}")
            return []
        
    def load_tanidk_yerler(self) -> Dict:
        """Tanıdık yerler verisini yükle (Öncelik: MongoDB)"""
        try:
            # Try MongoDB first if available
            if self.data_service and hasattr(self.data_service, 'load_config'):
                mongo_data = self.data_service.load_config('tanidk_yerler')
                if mongo_data:
                    return mongo_data
            
            # Local fallback
            if self.tanidk_yerler_file.exists():
                with open(self.tanidk_yerler_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"custom_locations": [], "mahalle_eslesmeleri": {}}
        except Exception as e:
            logger.error(f"Tanıdık yerler yüklenemedi: {e}")
            return {"custom_locations": [], "mahalle_eslesmeleri": {}}
    
    def save_tanidk_yerler(self, data: Dict) -> bool:
        """Tanıdık yerler verisini kaydet (Öncelik: MongoDB)"""
        try:
            # Sync to MongoDB first
            mongo_success = False
            if self.data_service and hasattr(self.data_service, 'save_config'):
                mongo_success = self.data_service.save_config('tanidk_yerler', data)
            
            # Local backup always
            with open(self.tanidk_yerler_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self._tanidk_yerler = None  # Cache'i temizle
            self._mahalle_index = None
            return mongo_success if self.data_service else True
        except Exception as e:
            logger.error(f"Tanıdık yerler kaydedilemedi: {e}")
            return False
    def _normalize_text(self, text: str) -> str:
        """Türkçe karakterleri normalize et ve küçük harfe çevir"""
        if not text: return ""
        text = text.lower()
        replacements = {
            'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c'
        }
        for tr, en in replacements.items():
            text = text.replace(tr, en)
        return text.strip()

    def build_mahalle_index(self) -> Dict[str, List[Tuple[str, str]]]:
        """
        Mahalle → [(İl, İlçe)] eşleştirme indeksi oluştur
        Hem orijinal hem de normalize edilmiş hallerini saklar.
        """
        if self._mahalle_index is not None:
            return self._mahalle_index
        
        index = {}
    
        # İl varsayılanlarını yükle
        il_defaults = {}
        try:
            from src.utils.file_operations import load_json_safe
            il_data = load_json_safe(self.il_ilceler_file)
            for item in il_data:
                il_defaults[item.get('il', '').upper()] = item.get('varsayılan_ilçe', 'Merkez')
        except:
            pass
    
        # 1. Ana Veritabanını İndeksle (il_ilçe_mahalle.json)
        full_data = self.load_il_ilce_mahalle()
        for il_item in full_data:
            il_adi = il_item.get('il')
            if not il_adi: continue
            
            # İl adını da indekse ekle (Örn: "ANKARA" -> (ANKARA, MERKEZ))
            # İl arandığında genellikle varsayılan merkez ilçe kastedilir
            il_orig = il_adi.lower().strip()
            il_norm = self._normalize_text(il_adi)
            default_ilce = il_defaults.get(il_adi.upper(), "Merkez")
            
            for k in set([il_orig, il_norm]):
                if k not in index: index[k] = []
                if (il_adi, default_ilce) not in index[k]:
                    index[k].append((il_adi, default_ilce))

            for ilce_item in il_item.get('ilceler', []):
                ilce_adi = ilce_item.get('ilce')
                if not ilce_adi: continue
                
                # İlçe adını da indekse ekle (Örn: "Arnavutköy" -> (İSTANBUL, Arnavutköy))
                ilce_orig = ilce_adi.lower().strip()
                ilce_norm = self._normalize_text(ilce_adi)
                for k in set([ilce_orig, ilce_norm]):
                    if k not in index: index[k] = []
                    if (il_adi, ilce_adi) not in index[k]:
                        index[k].append((il_adi, ilce_adi))
                
                mahalleler = ilce_item.get('mahalleler', [])
                for mahalle in mahalleler:
                    # Orijinal anahtar
                    m_orig = mahalle.lower().strip()
                    # Normalize anahtar (Hadimkoy -> hadimkoy)
                    m_norm = self._normalize_text(mahalle)
                    
                    for key in set([m_orig, m_norm]):
                        if key not in index:
                            index[key] = []
                        if (il_adi, ilce_adi) not in index[key]:
                            index[key].append((il_adi, ilce_adi))

        # 2. Özel Tanıdık Yerleri İndeksle
        custom_data = self.load_tanidk_yerler()
        
        # A. Özel Yer Kayıtları (List)
        for loc in custom_data.get('custom_locations', []):
            yer_adi = loc.get('yer_adi')
            if not yer_adi: continue
            
            il, ilce = loc.get('il'), loc.get('ilce')
            m_orig = yer_adi.lower().strip()
            m_norm = self._normalize_text(yer_adi)
            
            for key in set([m_orig, m_norm]):
                if key not in index:
                    index[key] = []
                if (il, ilce) not in index[key]:
                    index[key].insert(0, (il, ilce)) # Öncelikli

        # B. Mahalle Eşleşmeleri Tanımları (Dict)
        mahalle_eslesmeleri = custom_data.get('mahalle_eslesmeleri', {})
        for il, ilceler in mahalle_eslesmeleri.items():
            for ilce, mahalleler in ilceler.items():
                for mahalle in mahalleler:
                    m_orig = mahalle.lower().strip()
                    m_norm = self._normalize_text(mahalle)
                    
                    for key in set([m_orig, m_norm]):
                        if key not in index:
                            index[key] = []
                        if (il, ilce) not in index[key]:
                            index[key].insert(0, (il, ilce))
        
        # 3. Yurtdışı Ülkelerini İndeksleme KALDIRILDI (Sadece Türkiye Verisi)
        # Artık sadece yerel mahalleler öncelikli.

        self._mahalle_index = index
        return index
    
    def search_neighborhood_fully(self, query: str) -> List[Tuple[str, str, str]]:
        """
        Sorgu ile eşleşen TÜM mahalle/ilçe/il'leri getir. Normalizasyon destekli.
        (SADECE TÜRKİYE VERİSİ)
        """
        if not query or len(query) < 2:
            return []
            
        index = self.build_mahalle_index()
        query_norm = self._normalize_text(query)
        results = []
        
        # 1. Tam, Kısmi ve Önek Eşleşmeleri
        for key, locations in index.items():
            if query_norm in key or key in query_norm:
                for il, ilce in locations:
                    # Yurt dışı filtresi (Güvenlik önlemi olarak kalabilir)
                    if ilce != "Yurt Dışı":
                        results.append((il, ilce, key.upper()))
        
        # 2. Fuzzy Eşleşmeler
        if len(results) < 3 and len(query_norm) > 3:
            all_keys = list(index.keys())
            matches = difflib.get_close_matches(query_norm, all_keys, n=5, cutoff=0.7)
            
            for match_key in matches:
                if query_norm not in match_key:
                    for il, ilce in index[match_key]:
                        if ilce != "Yurt Dışı":
                            res = (il, ilce, match_key.upper())
                            if res not in results:
                                results.append(res)
        
        # 3. YAPAY ZEKA TAHMİNİ (Sadece hiçbir sonuç bulunamazsa)
        if not results:
            logger.info(f"Yapay Zeka Tahmini baslatiliyor: {query}")
            parts = query_norm.split()
            for part in parts:
                if len(part) < 4: continue
                matches = difflib.get_close_matches(part, list(index.keys()), n=3, cutoff=0.6)
                for m in matches:
                    for il, ilce in index[m]:
                        if ilce != "Yurt Dışı":
                            res = (il, ilce, m.upper() + " (AI Tahmini)")
                            if res not in results:
                                results.append(res)

        return results
    
    def find_location_by_mahalle(self, mahalle: str, filter_il: str = None) -> Optional[Tuple[str, str]]:
        """
        Mahalle adından İl/İlçe bul
        
        Args:
            mahalle: Mahalle adı
            filter_il: Eğer belirtilirse sadece bu ildeki mahallelerde arar
            
        Returns:
            (İl, İlçe) tuple veya None
        """
        if not mahalle:
            return None
        
        index = self.build_mahalle_index()
        mahalle_lower = mahalle.lower().strip()
        
        # Filtreleme için yardımcı fonksiyon
        def is_match_allowed(found_il: str) -> bool:
            if not filter_il:
                return True
            # Türkçe karakter duyarlı karşılaştırma (basit çözüm)
            return filter_il.lower() in found_il.lower() or found_il.lower() in filter_il.lower()

        # 1. Tam Eşleşme
        if mahalle_lower in index:
            matches = index[mahalle_lower]
            # Filtreye uygun olanı bul
            for match in matches:
                il, ilce = match
                if is_match_allowed(il):
                    return match
        
        # 2. Kısmi Eşleşme (Substring)
        if len(mahalle_lower) > 3:
            for key, locations in index.items():
                if key == mahalle_lower: continue

                if mahalle_lower in key or key in mahalle_lower:
                    for match in locations:
                        il, ilce = match
                        if is_match_allowed(il):
                            return match

        # 3. Fuzzy Eşleşme (Yazım hatası toleransı)
        # Sadece yeterince uzunsa
        if len(mahalle_lower) > 4:
            all_mahalleler = list(index.keys())
            
            # Hassasiyeti artırdık: 0.8 -> 0.6
            matches = difflib.get_close_matches(mahalle_lower, all_mahalleler, n=3, cutoff=0.6)
            
            for best_match in matches:
                locations = index.get(best_match)
                if locations:
                    for match in locations:
                        il, ilce = match
                        if is_match_allowed(il):
                            logger.info(f"Fuzzy eşleşme bulundu: '{mahalle}' -> '{best_match}' ({il}/{ilce})")
                            return match
        
        return None
    
    def add_custom_location(self, yer_adi: str, il: str, ilce: str, aciklama: str = "") -> bool:
        """
        Yeni tanıdık yer ekle
        
        Args:
            yer_adi: Yer adı (örn: "Erciyes", "Çarşı")
            il: İl adı
            ilce: İlçe adı
            aciklama: Opsiyonel açıklama
            
        Returns:
            Başarılı ise True
        """
        try:
            data = self.load_tanidk_yerler()
            
            # Yeni lokasyon
            new_location = {
                "yer_adi": yer_adi,
                "il": il.upper(),
                "ilce": ilce,
                "aciklama": aciklama,
                "ekleyen": "kullanici",
                "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Aynı yer var mı kontrol et
            custom_locations = data.get('custom_locations', [])
            for loc in custom_locations:
                if (loc.get('yer_adi', '').lower() == yer_adi.lower() and
                    loc.get('il', '').upper() == il.upper() and
                    loc.get('ilce', '') == ilce):
                    logger.info(f"Bu yer zaten mevcut: {yer_adi}")
                    return False
            
            custom_locations.append(new_location)
            data['custom_locations'] = custom_locations
            
            return self.save_tanidk_yerler(data)
            
        except Exception as e:
            logger.error(f"Tanıdık yer eklenemedi: {e}")
            return False
    
    def find_custom_location(self, yer_adi: str) -> Optional[Dict]:
        """
        Tanıdık yer ara
        
        Args:
            yer_adi: Aranacak yer adı
            
        Returns:
            Lokasyon bilgisi veya None
        """
        if not yer_adi:
            return None
        
        data = self.load_tanidk_yerler()
        custom_locations = data.get('custom_locations', [])
        yer_lower = yer_adi.lower().strip()
        
        # Tam eşleşme
        for loc in custom_locations:
            if loc.get('yer_adi', '').lower() == yer_lower:
                return loc
        
        # Kısmi eşleşme
        for loc in custom_locations:
            loc_name = loc.get('yer_adi', '').lower()
            if yer_lower in loc_name or loc_name in yer_lower:
                return loc
        
        # 3. Fuzzy Eşleşme
        if len(yer_lower) > 3:
            loc_names = [loc.get('yer_adi', '').lower() for loc in custom_locations]
            matches = difflib.get_close_matches(yer_lower, loc_names, n=1, cutoff=0.7) # Biraz daha esnek (0.7)
            
            if matches:
                best_match = matches[0]
                # Match'i bulup orjinal objeyi dön
                for loc in custom_locations:
                    if loc.get('yer_adi', '').lower() == best_match:
                        logger.info(f"Custom yer fuzzy eşleşme: '{yer_adi}' -> '{loc.get('yer_adi')}'")
                        return loc

        return None
    
    def add_mahalle_to_ilce(self, il: str, ilce: str, mahalle: str) -> bool:
        """
        İlçeye yeni mahalle ekle
        
        Args:
            il: İl adı
            ilce: İlçe adı
            mahalle: Mahalle adı
            
        Returns:
            Başarılı ise True
        """
        try:
            data = self.load_tanidk_yerler()
            mahalle_eslesmeleri = data.get('mahalle_eslesmeleri', {})
            
            il_upper = il.upper()
            
            # İl yoksa ekle
            if il_upper not in mahalle_eslesmeleri:
                mahalle_eslesmeleri[il_upper] = {}
            
            # İlçe yoksa ekle
            if ilce not in mahalle_eslesmeleri[il_upper]:
                mahalle_eslesmeleri[il_upper][ilce] = []
            
            # Mahalle zaten var mı?
            mahalleler = mahalle_eslesmeleri[il_upper][ilce]
            if mahalle not in mahalleler:
                mahalleler.append(mahalle)
                data['mahalle_eslesmeleri'] = mahalle_eslesmeleri
                return self.save_tanidk_yerler(data)
            else:
                logger.info(f"Mahalle zaten mevcut: {mahalle}")
                return False
                
        except Exception as e:
            logger.error(f"Mahalle eklenemedi: {e}")
            return False
    
    def get_all_custom_locations(self) -> List[Dict]:
        """Tüm tanıdık yerleri getir"""
        data = self.load_tanidk_yerler()
        return data.get('custom_locations', [])
    
    def delete_custom_location(self, yer_adi: str, il: str, ilce: str) -> bool:
        """Tanıdık yer sil"""
        try:
            data = self.load_tanidk_yerler()
            custom_locations = data.get('custom_locations', [])
            
            # Silmek istenen yeri bul
            new_locations = [
                loc for loc in custom_locations
                if not (loc.get('yer_adi', '').lower() == yer_adi.lower() and
                       loc.get('il', '').upper() == il.upper() and
                       loc.get('ilce', '') == ilce)
            ]
            
            if len(new_locations) < len(custom_locations):
                data['custom_locations'] = new_locations
                return self.save_tanidk_yerler(data)
            else:
                logger.warning(f"Silinecek yer bulunamadı: {yer_adi}")
                return False
                
        except Exception as e:
            logger.error(f"Tanıdık yer silinemedi: {e}")
            return False
    
    
    def add_mahalle_to_main_db(self, il: str, ilce: str, mahalle: str) -> bool:
        """
        Ana veritabanına (il_ilçe_mahalle.json) yeni bir mahalle kaydı ekler.
        Eksik olan İl veya İlçe varsa onları da hiyerarşik olarak oluşturur.
        """
        try:
            full_data = self.load_il_ilce_mahalle()
            il_upper = il.upper().strip()
            ilce_upper = ilce.upper().strip()
            mahalle_upper = mahalle.upper().strip()
            
            # 1. İli bul veya oluştur
            target_il = None
            for item in full_data:
                if item.get('il', '').upper() == il_upper:
                    target_il = item
                    break
            
            if not target_il:
                target_il = {"il": il_upper, "ilceler": []}
                full_data.append(target_il)
            
            # 2. İlçeyi bul veya oluştur
            target_ilce = None
            for item in target_il.get('ilceler', []):
                if item.get('ilce', '').upper() == ilce_upper:
                    target_ilce = item
                    break
            
            if not target_ilce:
                target_ilce = {"ilce": ilce_upper, "mahalleler": []}
                target_il['ilceler'].append(target_ilce)
            
            # 3. Mahalleyi ekle
            if mahalle_upper not in [m.upper() for m in target_ilce.get('mahalleler', [])]:
                target_ilce['mahalleler'].append(mahalle_upper)
                
                # 4. Kaydet
                success = False
                try:
                    # Local backup
                    with open(self.il_ilce_mahalle_file, 'w', encoding='utf-8') as f:
                        json.dump(full_data, f, ensure_ascii=False, indent=2)
                    
                    # Global sync to MongoDB
                    if self.data_service and hasattr(self.data_service, 'save_config'):
                        success = self.data_service.save_config('il_ilce_mahalle', full_data)
                    else:
                        success = True
                    
                    self._mahalle_index = None  # İndeksi temizle
                    return success
                except Exception as e:
                    logger.error(f"İl/İlçe/Mahalle kaydedilemedi: {e}")
                    return False
            else:
                logger.debug(f"Mahalle zaten mevcut: {mahalle_upper} ({ilce_upper}/{il_upper})")
                return False
                
        except Exception as e:
            logger.error(f"Ana veritabanına mahalle eklenemedi: {e}")
            return False

    def search_location(self, query: str) -> Optional[Tuple[str, str]]:
        """
        Akıllı lokasyon arama
        
        Algoritma:
        1. Tanıdık yerlerde ara
        2. Metin içinde İLÇE geçiyor mu? (Varsa direkt dön)
        3. Metin içinde İL geçiyor mu? (Varsa mahalle aramasında filtre olarak kullan)
        4. Kalan metni mahalle olarak ara
        
        Args:
            query: Arama sorgusu (örn: "Kadıköy Moda", "Ankara Cumhuriyet", "Moda")
            
        Returns:
            (İl, İlçe) tuple veya None
        """
        if not query:
            return None
            
        # 1. Tanıdık yerlerde ara
        custom_loc = self.find_custom_location(query)
        if custom_loc:
            return (custom_loc.get('il'), custom_loc.get('ilce'))

        # İndeksleri ve listeleri hazırla
        # TODO: Performans için bunları cache'lemek iyi olur
        # Şu anlık her çağrıda yapıyoruz ama veri bellekte olduğu için çok dert değil
        full_data = self.load_il_ilce_mahalle()
        
        all_iller = {} # il_lower -> real_il_name
        all_ilceler = {} # ilce_lower -> (real_il_name, real_ilce_name)
        
        for item in full_data:
            il = item.get('il')
            all_iller[il.lower()] = il
            for ilce_item in item.get('ilceler', []):
                ilce = ilce_item.get('ilce')
                # İlçe ismini il ile eşleştir
                all_ilceler[ilce.lower()] = (il, ilce)

        # Sorguyu parçalara ayır
        query_parts = [p.strip() for p in query.lower().split() if len(p.strip()) > 2]
        
        detected_il = None
        
        # 2.A. Önce İL Tespiti Yap (Tüm sorguda)
        temp_parts = []
        for part in query_parts:
            if part in all_iller:
                detected_il = all_iller[part]
            else:
                temp_parts.append(part)
        
        # İl bulunduysa, sorgudan o kelimeyi çıkardık (temp_parts)
        # Bulunmadıysa tüm parçalar duruyor
        if detected_il:
            target_parts = temp_parts
        else:
            target_parts = query_parts # İl yoksa orijinal sorguya dön
            
        remaining_parts = []
        
        # 2.B. İlçe ve Mahalle Ayrımı
        has_merkez = any(p == 'merkez' for p in target_parts)
        
        for part in target_parts:
            # İlçe Tespiti
            if part in all_ilceler and part != 'merkez':
                real_il, real_ilce = all_ilceler[part]
                
                if detected_il is None:
                    return (real_il, real_ilce)
                elif detected_il.lower() == real_il.lower():
                    return (real_il, real_ilce)
                else:
                    remaining_parts.append(part)
            else:
                remaining_parts.append(part)
        
        # --- MERKEZ KONTROLÜ (Büyükşehirler ve Normal İller için) ---
        if has_merkez and detected_il:
            # İl_ilçeler verisinden bu ilin bilgilerini bul
            from src.utils.file_operations import load_json_safe
            il_data = load_json_safe(self.il_ilceler_file)
            for item in il_data:
                if item.get('il', '').lower() == detected_il.lower():
                    # 1. Eğer bu ilin ilçeleri arasında "Merkez" VARSA onu kullan
                    sub_ilceleri = [x.lower() for x in item.get('ilçe', [])]
                    if 'merkez' in sub_ilceleri:
                        logger.info(f"Resmi Merkez tespiti: {detected_il} -> Merkez")
                        return (detected_il, "Merkez")
                    
                    # 2. Eğer "Merkez" yoksa (Büyükşehir), varsayılanı kullan
                    default_ilce = item.get('varsayılan_ilçe')
                    if default_ilce:
                        logger.info(f"Büyükşehir Merkez tespiti: {detected_il} -> {default_ilce}")
                        return (detected_il, default_ilce)
                    break
        
        # 3. Mahalle Araması
        mahalle_query = " ".join(remaining_parts)
        mahalle_result = None
        if mahalle_query: 
            mahalle_result = self.find_location_by_mahalle(mahalle_query, filter_il=detected_il)
            
        if mahalle_result:
            return mahalle_result
            
        # --- FALLBACK: Sadece İl Tespit Edildiyse Varsayılan İlçeyi Döndür ---
        if detected_il:
            from src.utils.file_operations import load_json_safe 
            il_data = load_json_safe(self.il_ilceler_file)
            if il_data:
                for item in il_data:
                    if item.get('il', '').upper() == detected_il.upper():
                        default_ilce = item.get('varsayılan_ilçe')
                        if default_ilce:
                            logger.info(f"Sadece İl tespiti ({detected_il}): Varsayilan ilceye yönlendiriliyor -> {default_ilce}")
                            return (detected_il, default_ilce)
            
        return None


# Kullanım örneği
if __name__ == "__main__":
    import os
    from src.utils.common import get_root_path
    
    root = get_root_path()
    data_dir = os.path.join(root, 'data')
    
    helper = LocationHelper(data_dir)
    
    # Test: Mahalle ara
    result = helper.find_location_by_mahalle("Moda")
    print(f"Moda → {result}")
    
    # Test: Tanıdık yer ekle
    helper.add_custom_location("Erciyes", "KAYSERİ", "Kocasinan", "Erciyes Dağı bölgesi")
    
    # Test: Tanıdık yer ara
    result = helper.find_custom_location("Erciyes")
    print(f"Erciyes → {result}")
