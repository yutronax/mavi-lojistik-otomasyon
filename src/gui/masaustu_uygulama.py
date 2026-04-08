# lojistik_gui.py
import warnings
# Suppress Google Generative AI deprecation warnings
warnings.filterwarnings("ignore", category=FutureWarning, message=".*google.generativeai.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*google.generativeai.*")

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import os
import copy  # Geri alma özelliği için kopyalama kütüphanesi
from datetime import datetime, date, timedelta, time
from typing import Dict, List, Optional
import threading
import time
import requests
import subprocess
import sys
import logging

# Proje kök dizinini belirle ve sys.path'e ekle
def get_root_path():
    """Root dizin yolunu döndür"""
    if getattr(sys, 'frozen', False):
        # PyInstaller ile paketlenmişse
        return os.path.dirname(sys.executable)
        
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # src/gui -> src -> maviLojistik
    return os.path.dirname(os.path.dirname(current_dir))

ROOT_DIR = get_root_path()
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'src'))
sys.path.insert(0, os.path.join(ROOT_DIR, 'src', 'fetchers'))

# Import modüller
from tools.submit_approved_loads import YukBuradaSubmitter
from src.fetchers import mavi_whap

# Import new architecture components
from src.services.data_service import DataService
from src.services.mongo_service import MongoDataService
from src.services.submission_queue import SubmissionQueue
from src.models.shipment import Shipment
from src.gui.components.autocomplete import AutocompleteEntry
from src.gui.components.tag_selector import TagSelector
from src.utils.phone_utils import normalize_phone
from src.utils.common import normalize_turkish_text
from src.utils.location_helper import LocationHelper

# Import collector helpers so GUI can start continuous fetch+process
import logging
logger = logging.getLogger(__name__)

try:
    from src.parsers.veri_cekici_ayristirici import fetch_all_messages, sync_to_queue, process_unprocessed_messages
    VERI_CEKICI_INTEGRATION = True
except Exception as e:
    # Use print if logger fails, but now logger is defined
    try:
        logger.error(f"Veri cekici entegrasyonu yüklenemedi: {e}")
    except:
        print(f"Error loading veri_cekici_ayristirici: {e}")
    VERI_CEKICI_INTEGRATION = False

# WhatsApp API senkronizasyon modülü
try:
    from src.fetchers.whapi_fetcher import fetch_all_messages, sync_to_queue, patch_dns
    WHAPI_AVAILABLE = True
except ImportError:
    WHAPI_AVAILABLE = False
    logger.debug(" whapi_fetcher modülü yüklenemedi")

# WhatsApp Webhook Server
try:
    from src.api.webhook_server import run_server, stop_server
    WEBHOOK_SERVER_AVAILABLE = True
except ImportError:
    WEBHOOK_SERVER_AVAILABLE = False
    logger.debug(" webhook_server modülü yüklenemedi")

# Moved to src.gui.components.managers
from src.gui.components.managers import BlacklistManager, GroupManager


# --- MAIN APPLICATION GUI ---




class LojistikYonetimGUI:
    def __init__(self, root):
        self.root = root
        self.ROOT_DIR = ROOT_DIR
        self.logger = logger

        self.COLORS = {
            'primary': '#1a56db',           # Koyu mavi - ana renk
            'primary_light': '#3b82f6',      # Açık mavi
            'primary_dark': '#1e40af',       # Daha koyu mavi
            'secondary': '#374151',          # Koyu gri
            'success': '#059669',            # Yeşil
            'success_light': '#d1fae5',      # Açık yeşil arka plan
            'warning': '#d97706',            # Turuncu
            'warning_light': '#fef3c7',      # Açık sarı arka plan
            'danger': '#dc2626',             # Kırmızı
            'danger_light': '#fee2e2',       # Açık kırmızı arka plan
            'background': '#f1f5f9',         # Açık gri-mavi arka plan
            'surface': '#ffffff',            # Beyaz yüzey
            'surface_alt': '#f8fafc',        # Alternatif yüzey
            'text': '#111827',               # Koyu metin
            'text_light': '#6b7280',         # Açık metin
            'text_muted': '#9ca3af',         # Soluk metin
            'border': '#e5e7eb',             # Sınır rengi
            'border_light': '#f3f4f6',       # Açık sınır
            'panel_bg': '#f8fafc',           # Yan panel arka plan
            'header_gradient': '#1e3a8a',    # Header gradient başlangıç
            'accent': '#7c3aed',             # Vurgu rengi (mor)
            'accent_light': '#a78bfa'        # Açık vurgu
        }
        # Hybrid Data Strategy: Optimized for performance but synchronized for config
        self.local_service = DataService(ROOT_DIR)
        self.data_service = self.local_service # Main data source is still local for speed
        
        # Initialize MongoDB Service for shared data (Blacklist, Groups, etc.)
        self.mongo_service = None
        self.mongo_mode = False
        try:
            self.mongo_service = MongoDataService()
            self.mongo_mode = True
            # Attach for synchronization
            self.data_service.mongo_service = self.mongo_service
            self.logger.info("MongoDB service connected for shared data (Blacklist, etc.)")
        except Exception as e:
            self.logger.warning(f"MongoDB connection failed, operating in LOCAL-ONLY mode: {e}")

        self.location_helper = LocationHelper(os.path.join(ROOT_DIR, 'data'), data_service=self.data_service)
        
        # Standardized file paths
        self.onaylananlar_file = self.data_service.onaylananlar_file
        self.onaylanmamis_ayristirilmis_file = self.data_service.onaylanmamis_file
        self.il_ilceler_file = self.data_service.il_ilceler_file
        self.yuk_tipi_file = self.data_service.yuk_tipi_file
        self.arac_yuk_kasa_tipleri_file = self.data_service.arac_kasa_file
        
        # Load configuration data
        self.il_ilceler_data = self.data_service.load_il_ilceler()
        self.yuk_tipi_data = self.data_service.load_yuk_tipleri()
        self.arac_yuk_kasa_tipleri_data = self.data_service.load_arac_kasa_tipleri()

        # PRE-FETCH SHARED DATA FROM MONGO (If available)
        if self.mongo_mode and self.mongo_service:
            try:
                # Sync local blacklist with Mongo at startup
                m_blacklist = self.mongo_service.load_blacklist()
                if m_blacklist:
                    self.data_service.save_blacklist(m_blacklist)
                    self.logger.info(f"Synchronized {len(m_blacklist)} blacklist entries from MongoDB.")
            except Exception as e:
                self.logger.error(f"Error syncing MongoDB blacklist: {e}")
        self.arac_yuk_kasa_tipleri_data = self.data_service.load_arac_kasa_tipleri()

        self.management_center_window = None
        self.root.title("🚚 LOJİSTİK YÖNETİM SİSTEMİ")
        # Ana pencere tam ekran olmayacak; sadece maksimum pencere (taskbar görünür)
        try:
            self.root.state('zoomed')
        except Exception:
            # Fallback geometry
            self.root.geometry("1600x900")
        self.root.configure(bg=self.COLORS['background'])
        
        # Pencere kapatma event'i
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.font_heading = ('Segoe UI Semibold', 18, 'bold')
        self.font_subheading = ('Segoe UI Semibold', 12, 'bold')
        self.font_normal = ('Segoe UI', 10)
        self.font_small = ('Segoe UI', 9)
        self.font_tiny = ('Segoe UI', 8)
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Button stili
        self.style.configure('TButton',
                           font=self.font_normal,
                           padding=8,
                           relief='flat',
                           background=self.COLORS['primary'],
                           foreground='white',
                           borderwidth=0)
                           
        self.style.map('TButton',
                     background=[('active', self.COLORS['primary_light']),
                                ('pressed', self.COLORS['primary_dark'])])
        
        # Ana Treeview stili
        self.style.configure('Treeview',
                           font=self.font_small,
                           rowheight=38,
                           background=self.COLORS['surface'],
                           fieldbackground=self.COLORS['surface'],
                           foreground=self.COLORS['text'],
                           borderwidth=0)
        
        self.style.configure('Treeview.Heading',
                           font=('Segoe UI Semibold', 9, 'bold'),
                           background=self.COLORS['primary'],
                           foreground='white',
                           relief='flat',
                           padding=8)
        
        self.style.map('Treeview.Heading',
                     background=[('active', self.COLORS['primary_light'])])
                           
        self.style.map('Treeview',
                     background=[('selected', self.COLORS['primary'])],
                     foreground=[('selected', 'white')])
        
        # Scrollbar stili
        self.style.configure('Vertical.TScrollbar',
                           background=self.COLORS['border'],
                           troughcolor=self.COLORS['surface_alt'],
                           borderwidth=0,
                           arrowsize=14)
        
        self.style.configure('Horizontal.TScrollbar',
                           background=self.COLORS['border'],
                           troughcolor=self.COLORS['surface_alt'],
                           borderwidth=0)
        
        
        # DataService initialized earlier (see around line 1130)
        
        # PHASE 5: Unified logging with daily files and performance monitoring
        from src.utils.logging_config import setup_logger, log_operation
        self.logger = setup_logger('MaviLojistikGUI', log_dir=os.path.join(ROOT_DIR, 'logs'))
        
        # Log application startup
        log_operation(self.logger, "GUI_STARTUP", {
            "root_dir": ROOT_DIR,
            "data_service": "initialized",
            "config_files": "loaded"
        })
        
        # Veri yapıları
        self.unprocessed_data = {} # Initialize early to prevent race conditions
        self.all_messages: List[Dict] = []
        self.all_messages_original: List[Dict] = []
        self.current_message_index: int = 0
        self.current_message: Optional[Dict] = None
        
        # Otomatik Onay Özelliği
        self.auto_approval_var = tk.BooleanVar(value=False)
        
        self.current_shipments: List[Dict] = []
        self.current_shipment_index: int = 0
        self.shipment_backup: Optional[Dict] = None # Geri alma için
        
        # Initialize background submission queue
        self.submitter = None 
        try:
            # Create submitter with proper auth
            # Ensure we can import the submitter class
            self.submitter = YukBuradaSubmitter()
            
            # Initialize queue with this submitter
            self.submission_queue = SubmissionQueue(self.submitter)
            self.submission_queue.start()
            self.logger.info("Submission queue initialized and started.")
        except Exception as e:
            self.logger.error(f"Failed to initialize validation queue: {e}")
            self.submission_queue = None

        self.updating_table = False
        self._sync_in_progress = False
        
        # 1. PURGE OLD DATA on startup (Policy: Keep only today's messages)
        try:
            purged_count = self.data_service.purge_old_messages(keep_only_today=True)
            if purged_count > 0:
                self.logger.info(f"🧹 Başlangıç temizliği: {purged_count} eski mesaj silindi.")
        except Exception as e:
            self.logger.error(f"Başlangıç temizliği sırasında hata: {e}")

        # 2. Load and Merge (Hybrid: Local + Mongo Sync)
        self.unprocessed_data = self.load_unprocessed_parsed_data()
        self.selected_shipments = set()
        self.hovered_item = None
        self.active_shipment_index = None
        self.active_item_id = None
        self.time_filter_manual_override = False
        self._suspend_time_var_trace = False
        # track last automatic filter update to avoid excessive updates
        self._last_auto_filter_update = None
        self.side_panel_width = 450
        self.side_panel_handle = None
        self._side_drag_start_x = None
        self._side_initial_width = None
        
        # Blacklist and Group Management transitions
        
        # Veri çekici servis kontrolü
        self.veri_cekici_process = None
        self.veri_cekici_running = False
        self.live_loads_window = None
        self.submitter = None # Lazily initialized
        
        # UI Kurulumu
        self.setup_ui()
        self.load_messages_from_file()
        
        # DEBUG: Log message counts
        self.logger.info(f"🔍 DEBUG: After load_messages_from_file:")
        self.logger.info(f"  - all_messages_original: {len(self.all_messages_original)}")
        self.logger.info(f"  - all_messages: {len(self.all_messages)}")
        
        # Başlangıçta son 15 dakikayı otomatik filtrele
        self.filter_messages_by_time()
        
        # DEBUG: Log after filter
        self.logger.info(f"🔍 DEBUG: After filter_messages_by_time:")
        self.logger.info(f"  - all_messages: {len(self.all_messages)}")
        self.logger.info(f"  - Counter label exists: {hasattr(self, 'message_counter_label')}")
        
        if self.all_messages:
            self.logger.info(f"🔍 DEBUG: Loading message at index 0")
            self.load_message_at_index(0)
        else:
            self.logger.warning("⚠️ DEBUG: No messages to display!")
            self.status_label.config(text="İşlenecek mesaj yok")
            try:
                self.message_counter_label.config(text="0/0")
            except:
                pass
        
        # REMOVED: Otomatik yenileme kaldırıldı - kullanıcı manuel yenileyecek
        # self.start_periodic_file_check()
        
        # WhatsApp otomatik senkronizasyonu veri çekici servisinde çalışıyor (her 5 dk)
        # GUI'de otomatik senkronizasyon yapılmaz - sadece manuel buton kullanılır
        
        # Webhook Optimizasyonu devrede: Arayüz ve Webhook Sunucusu Birlikte Başlar
        self.logger.info("Auto-starting Webhook & Local Refresh Service...")
        self.root.after(1000, self.start_veri_cekici)
        
        # Periodic Local Refresh: Keep UI up to date with local file changes (Background Thread)
        self.root.after(5000, self.start_periodic_refresh)

    def start_periodic_refresh(self):
        """Starts a background thread to poll for local file updates every 30 seconds."""
        if getattr(self, '_sync_in_progress', False):
            # Already refreshing, check again in 5 seconds
            self.root.after(5000, self.start_periodic_refresh)
            return

        # Capture thread-unsafe UI variables on main thread
        try:
            minutes = int(self.minutes_filter_var.get())
        except:
            minutes = 60
            
        current_msg_id = None
        if hasattr(self, 'current_message') and self.current_message:
            current_msg_id = self.current_message.get('message_id') or self.current_message.get('id')

        def background_task():
            self._sync_in_progress = True
            try:
                # Perform local refresh in background
                self.refresh_messages(silent=True, from_thread=True, override_minutes=minutes, override_msg_id=current_msg_id)
                self.logger.debug("✅ Periodic local refresh completed.")
            except Exception as e:
                self.logger.error(f"❌ Periodic refresh thread error: {e}")
            finally:
                self._sync_in_progress = False
                # Schedule next refresh (15 seconds for more responsive UI)
                self.root.after(15000, self.start_periodic_refresh)

        # Launch background worker
        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()

    def start_mongo_sync(self):
        """Metod kaldırıldı - start_periodic_refresh kullanılıyor."""
        pass

    def setup_group_manager(self):
        """Metod artık gereksiz, Management Center üzerinden yönetiliyor"""
        pass

    def open_management_center(self, tab=None):
        """Yönetim Merkezi'ni açar ve gerekirse belirli bir sekmeye odaklanır"""
        try:
            from src.gui.yonetim_merkezi import YonetimMerkeziApp
            
            # Eğer pencere zaten açıksa öne getir
            if self.management_center_window is not None and self.management_center_window.winfo_exists():
                self.management_center_window.lift()
                if tab:
                    # TODO: Implement tab switching if already open
                    pass
                return

            self.management_center_window = tk.Toplevel(self.root)
            app = YonetimMerkeziApp(self.management_center_window)
            
            # Eğer sekme belirtilmişse oraya geç
            if tab == 'group':
                app.show_groups()
            elif tab == 'blacklist':
                app.show_blacklist()
                
        except Exception as e:
            self.logger.error(f"Yönetim Merkezi açılamadı: {e}")
            messagebox.showerror("Hata", f"Yönetim Merkezi yüklenirken bir sorun oluştu:\n{e}")


    def update_clock(self):
        """Saati güncelleyen fonksiyon"""
        now = datetime.now()
        current_time = now.strftime("%d.%m.%Y %H:%M:%S")
        self.time_label.config(text=current_time)

        # REMOVED: Auto-refresh the sliding-window filter periodically (caused UI resets)
        # if not self.time_filter_manual_override and hasattr(self, 'minutes_filter_var'):
        #     if not hasattr(self, '_last_auto_filter_update') or self._last_auto_filter_update is None:
        #         self._last_auto_filter_update = now
        #         self.filter_messages_by_time()
        #     else:
        #         if (now - self._last_auto_filter_update).total_seconds() >= 30:
        #             self._last_auto_filter_update = now
        #             self.filter_messages_by_time()

        self.root.after(1000, self.update_clock)
    
    def setup_ui(self):
        """Arayüz bileşenlerini oluştur"""
        # --- HEADER ---
        header_frame = tk.Frame(self.root, bg=self.COLORS['header_gradient'], height=70)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        # Gölge efekti için alt çizgi
        header_shadow = tk.Frame(self.root, bg=self.COLORS['border'], height=1)
        header_shadow.pack(fill=tk.X)
        
        header_content = tk.Frame(header_frame, bg=self.COLORS['header_gradient'])
        header_content.pack(fill=tk.BOTH, expand=True, padx=25)
        
        # Logo ve başlık container
        title_container = tk.Frame(header_content, bg=self.COLORS['header_gradient'])
        title_container.pack(side=tk.LEFT, pady=12)
        
        tk.Label(title_container, text="🚚", font=('Segoe UI', 24), bg=self.COLORS['header_gradient'], fg='white').pack(side=tk.LEFT, padx=(0, 10))
        
        title_text = tk.Frame(title_container, bg=self.COLORS['header_gradient'])
        title_text.pack(side=tk.LEFT)
        tk.Label(title_text, text="LOJİSTİK YÖNETİM SİSTEMİ", font=('Segoe UI Semibold', 18, 'bold'), bg=self.COLORS['header_gradient'], fg='white').pack(anchor='w')
        tk.Label(title_text, text="Mavi Lojistik", font=('Segoe UI', 9), bg=self.COLORS['header_gradient'], fg='#93c5fd').pack(anchor='w')
        
        # Saat container - sağ taraf
        time_container = tk.Frame(header_content, bg=self.COLORS['header_gradient'])
        time_container.pack(side=tk.RIGHT, pady=15)
        
        self.time_label = tk.Label(time_container, text="", font=('Segoe UI Semibold', 11), bg=self.COLORS['header_gradient'], fg='#e0e7ff')
        self.time_label.pack()
        self.update_clock()

        # --- FİLTRE PANELİ ---
        self.setup_filter_panel()
        self.sort_shipments_by_time()  # Her zaman zamana göre sırala

        # --- ANA KONTEYNER (PanedWindow yerine Pack kullanacağız, dinamik resize için) ---
        self.main_container = tk.Frame(self.root, bg=self.COLORS['background'])
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 1. SOL PANEL (Mesaj İçeriği) - Sabit Genişlik
        self.left_pane = tk.Frame(self.main_container, bg=self.COLORS['surface'], width=350)
        self.left_pane.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        self.left_pane.pack_propagate(False)
        self.setup_left_pane()

        # 4. YAN PANEL (Dinamik - Başlangıçta gizli) - EN SAĞA EKLENİR
        self.side_panel = tk.Frame(self.main_container, bg=self.COLORS['panel_bg'], width=0)
        # Pack edilmiyor, ihtiyaç olunca pack edilecek

        self.right_pane = tk.Frame(self.main_container, bg=self.COLORS['surface'], width=200)
        self.right_pane.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        self.right_pane.pack_propagate(False)
        self.setup_right_pane()

        # 2. ORTA PANEL (Tablo) - Esnek
        self.center_pane = tk.Frame(self.main_container, bg=self.COLORS['surface'])
        self.center_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.setup_center_pane()
        
        # 5. ALT PANEL (Son 10 Canlı Mesaj)
        self.bottom_pane = tk.Frame(self.root, bg=self.COLORS['surface'], height=180)
        self.bottom_pane.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 5))
        self.bottom_pane.pack_propagate(False)
        self.setup_bottom_pane()
        
        # --- STATUS BAR ---
        self.setup_status_bar()

    def setup_filter_panel(self):
        filter_frame = tk.Frame(self.root, bg=self.COLORS['surface'], height=50)
        filter_frame.pack(fill=tk.X, padx=10, pady=(8, 0))
        filter_frame.pack_propagate(False)
        
        # Alt gölge çizgisi
        tk.Frame(self.root, bg=self.COLORS['border'], height=1).pack(fill=tk.X, padx=10)

        content = tk.Frame(filter_frame, bg=self.COLORS['surface'])
        content.pack(expand=True, fill=tk.Y)

        # Zaman filtresi: Son X dakika (kaydırmalı pencere)
        tk.Label(content, text="⏱ Son X dakika:", bg=self.COLORS['surface'], fg=self.COLORS['text'], font=('Segoe UI Semibold', 9)).pack(side=tk.LEFT, padx=(10, 5))

        minutes_options = ['10', '20', '40', '60']
        self.minutes_filter_var = tk.StringVar(value='60')
        self.minutes_filter_combo = ttk.Combobox(content, textvariable=self.minutes_filter_var, values=minutes_options, width=8, font=('Segoe UI', 9), state='readonly')
        self.minutes_filter_combo.pack(side=tk.LEFT)
        self.minutes_filter_combo.bind('<<ComboboxSelected>>', self._on_minutes_filter_change)

        tk.Button(content, text="🔍 Filtrele", bg=self.COLORS['primary'], fg='white', command=self.filter_messages_by_time, font=('Segoe UI', 9), relief='flat', padx=12, pady=4, cursor='hand2').pack(side=tk.LEFT, padx=(15, 5))
        tk.Button(content, text="↻ Sıfırla", bg=self.COLORS['secondary'], fg='white', command=self.reset_time_filter, font=('Segoe UI', 9), relief='flat', padx=12, pady=4, cursor='hand2').pack(side=tk.LEFT)
        
        # Adding missing "Canlı Yayındaki Yükler" button
        tk.Button(content, text="📡 CANLI YAYINDAKİ YÜKLER", bg=self.COLORS['accent'], fg='white', command=self.open_live_loads_window, font=('Segoe UI', 9, 'bold'), relief='flat', padx=15, pady=4, cursor='hand2').pack(side=tk.LEFT, padx=(20, 0))

    def setup_left_pane(self):
        # Üst çerçeve ile rounded görünüm
        header = tk.Frame(self.left_pane, bg=self.COLORS['accent'], height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="📄 ORJİNAL MESAJ", font=('Segoe UI Semibold', 10, 'bold'), bg=self.COLORS['accent'], fg='white').pack(side=tk.LEFT, padx=12, pady=8)
        
        content = tk.Frame(self.left_pane, bg=self.COLORS['surface'], padx=8, pady=8)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Mesaj Detay Paneli (Accordion Style)
        info_container = tk.Frame(content, bg=self.COLORS['surface_alt'], relief='flat')
        info_container.pack(fill=tk.X, pady=(0, 8))
        
        # 1. Toggle Button (Header)
        self.info_toggle_btn = tk.Button(info_container, text="ℹ️ Detaylar ▼", 
                                       font=('Segoe UI Semibold', 9), 
                                       bg=self.COLORS['surface_alt'], 
                                       fg=self.COLORS['text'],
                                       anchor='w', relief='flat', cursor='hand2',
                                       command=self.toggle_info_panel)
        self.info_toggle_btn.pack(fill=tk.X, padx=5, pady=2)
        
        # 2. Hidden Detail Panel
        self.info_panel = tk.Frame(info_container, bg=self.COLORS['surface_alt'], padx=10, pady=5)
        # Başlangıçta gizli (pack etmiyoruz)
        
        # Grid layout for details
        self.info_panel.columnconfigure(1, weight=1)
        
        def add_detail_row(parent, row, label, var_name):
            tk.Label(parent, text=label, font=('Segoe UI', 8, 'bold'), bg=self.COLORS['surface_alt'], fg=self.COLORS['text_muted'], anchor='w').grid(row=row, column=0, sticky='w', pady=1)
            lbl = tk.Label(parent, text="-", font=('Segoe UI', 8), bg=self.COLORS['surface_alt'], fg=self.COLORS['text'], anchor='w', wraplength=250)
            lbl.grid(row=row, column=1, sticky='we', pady=1)
            setattr(self, var_name, lbl)
            
        add_detail_row(self.info_panel, 0, "Grup:", "detail_group_label")
        add_detail_row(self.info_panel, 1, "Zaman:", "detail_time_label")
        add_detail_row(self.info_panel, 2, "Gönderen:", "detail_sender_label")
        add_detail_row(self.info_panel, 3, "Numara:", "detail_sender_num_label")
        
        self.is_info_panel_open = False
        
        # YENI: Navigation butonları (Prev/Next)
        nav_frame = tk.Frame(content, bg=self.COLORS['surface'])
        nav_frame.pack(fill=tk.X, pady=(0, 4))
        
        # Önceki mesaj butonu
        prev_btn = tk.Button(nav_frame, text="◀", font=('Segoe UI', 12), 
                             bg=self.COLORS['primary'], fg='white',
                             relief='flat', padx=12, pady=2,
                             command=self.prev_message)
        prev_btn.pack(side=tk.LEFT, padx=(0, 2))
        
        # Mesaj sayacı (ortada)
        self.message_counter_label = tk.Label(nav_frame, text="0/0", 
                                              font=('Segoe UI', 9), 
                                              bg=self.COLORS['surface'], 
                                              fg=self.COLORS['text'])
        self.message_counter_label.pack(side=tk.LEFT, expand=True)
        
        # Sonraki mesaj butonu
        next_btn = tk.Button(nav_frame, text="▶", font=('Segoe UI', 12),
                            bg=self.COLORS['primary'], fg='white',
                            relief='flat', padx=12, pady=2,
                            command=self.next_message)
        next_btn.pack(side=tk.RIGHT, padx=(2, 0))
        
        # Mesaj metin alanı - daha güzel border
        text_frame = tk.Frame(content, bg=self.COLORS['border'], padx=1, pady=1)
        text_frame.pack(fill=tk.BOTH, expand=True)
        self.message_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, font=('Consolas', 10), height=1, bg=self.COLORS['surface'], fg=self.COLORS['text'], relief='flat', padx=8, pady=8)
        self.message_text.pack(fill=tk.BOTH, expand=True)
        
        # FIX: Mouse wheel ile mesaj değiştirme
        self.message_text.bind('<MouseWheel>', self.on_mouse_wheel_message)

    def toggle_info_panel(self):
        """Detay panelini aç/kapat"""
        if getattr(self, 'is_info_panel_open', False):
            self.info_panel.pack_forget()
            try:
                self.info_toggle_btn.config(text=f"{getattr(self, '_current_summary', 'Detaylar')} ▼")
            except: pass
            self.is_info_panel_open = False
        else:
            self.info_panel.pack(fill=tk.X, after=self.info_toggle_btn)
            try:
                self.info_toggle_btn.config(text=f"{getattr(self, '_current_summary', 'Detaylar')} ▲")
            except: pass
            self.is_info_panel_open = True

    def setup_center_pane(self):
        header = tk.Frame(self.center_pane, bg=self.COLORS['primary'], height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="📋 SEVKİYAT LİSTESİ", font=('Segoe UI Semibold', 10, 'bold'), bg=self.COLORS['primary'], fg='white').pack(side=tk.LEFT, padx=12, pady=8)
        
        content = tk.Frame(self.center_pane, bg=self.COLORS['surface'], padx=8, pady=8)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Araç çubuğu - daha modern
        toolbar = tk.Frame(content, bg=self.COLORS['surface_alt'], pady=5, padx=5)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        
        # Araç çubuğu - daha modern
        toolbar = tk.Frame(content, bg=self.COLORS['surface_alt'], pady=5, padx=5)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        
        # Toolbar Buttons (Onayla, Sil, Düzenle, Ekle)
        common_btn_style = {'font': ('Segoe UI Semibold', 8, 'bold'), 'relief': 'flat', 'padx': 15, 'pady': 3, 'cursor': 'hand2'}
        
        # ONAYLA
        self.btn_approve = tk.Button(toolbar, text="✅ ONAYLA", bg=self.COLORS['success'], fg='white', command=self.approve_shipment, **common_btn_style)
        self.btn_approve.pack(side=tk.LEFT, padx=(10, 0))
        
        # SİL
        self.btn_delete = tk.Button(toolbar, text="🗑️ SİL", bg=self.COLORS['danger'], fg='white', command=self.delete_selected_shipment, **common_btn_style)
        self.btn_delete.pack(side=tk.LEFT, padx=(5, 0))
        
        # DÜZENLE
        self.btn_edit = tk.Button(toolbar, text="✏️ DÜZENLE", bg=self.COLORS['warning'], fg='#1f2937', command=self.toggle_edit_mode, **common_btn_style)
        self.btn_edit.pack(side=tk.LEFT, padx=(5, 0))
        
        # EKLE
        self.btn_add = tk.Button(toolbar, text="➕ EKLE", bg=self.COLORS['primary_light'], fg='white', command=self.add_new_shipment, **common_btn_style)
        self.btn_add.pack(side=tk.LEFT, padx=(5, 0))
        
        # Tablo - border ile çerçeveli
        table_border = tk.Frame(content, bg=self.COLORS['border'], padx=1, pady=1)
        table_border.pack(fill=tk.BOTH, expand=True)
        
        table_container = tk.Frame(table_border, bg=self.COLORS['surface'])
        table_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar_y = ttk.Scrollbar(table_container, orient='vertical')
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x = ttk.Scrollbar(table_container, orient='horizontal')
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.shipment_table = ttk.Treeview(
            table_container,
            columns=('checkbox', 'nerden', 'nereye', 'arac_tipi', 'kasa_tipi', 'yuk_tipi', 'fiyat', 'telefon'),
            show='headings',
            selectmode='none',
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )
        
        scrollbar_y.config(command=self.shipment_table.yview)
        scrollbar_x.config(command=self.shipment_table.xview)
        
        self.shipment_table.heading('checkbox', text='☐', command=self.toggle_select_all_shipments)
        self.shipment_table.heading('nerden', text='Nereden')
        self.shipment_table.heading('nereye', text='Nereye')
        self.shipment_table.heading('arac_tipi', text='Araç')
        self.shipment_table.heading('kasa_tipi', text='Kasa')
        self.shipment_table.heading('yuk_tipi', text='Yük')
        self.shipment_table.heading('fiyat', text='Fiyat')
        self.shipment_table.heading('telefon', text='Telefon')
        # self.shipment_table.heading('aciklama', text='Açıklama') # Removed from view
        
        self.shipment_table.column('checkbox', width=35, anchor='center')
        self.shipment_table.column('nerden', width=120)
        self.shipment_table.column('nereye', width=120)
        self.shipment_table.column('arac_tipi', width=115)
        self.shipment_table.column('kasa_tipi', width=115)
        self.shipment_table.column('yuk_tipi', width=95)
        self.shipment_table.column('fiyat', width=80)
        self.shipment_table.column('telefon', width=125)
        # self.shipment_table.column('aciklama', width=160)

        # Satır renkleri - zebra efekti ve seçim
        self.shipment_table.tag_configure('checked', background=self.COLORS['success_light'])
        self.shipment_table.tag_configure('active_row', background=self.COLORS['primary'], foreground='white')
        self.shipment_table.tag_configure('odd', background=self.COLORS['surface'])
        self.shipment_table.tag_configure('even', background=self.COLORS['surface_alt'])
        
        self.shipment_table.pack(fill=tk.BOTH, expand=True)
        
        # Eventler
        self.shipment_table.bind('<Double-1>', self.on_cell_double_click)
        self.shipment_table.bind('<Button-1>', self.on_table_click)
        
        # Alt butonlar kaldırıldı (yukarı taşındı)
        # btn_frame = tk.Frame(content, height=45, bg=self.COLORS['surface_alt'])
        # btn_frame.pack(fill=tk.X, pady=(8,0))

    def setup_right_pane(self):
        header = tk.Frame(self.right_pane, bg=self.COLORS['secondary'], height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="⚙️ İŞLEMLER", font=('Segoe UI Semibold', 10, 'bold'), bg=self.COLORS['secondary'], fg='white').pack(side=tk.LEFT, padx=12, pady=8)
        
        content = tk.Frame(self.right_pane, bg=self.COLORS['surface'], padx=12, pady=12)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Kayıt sayacı - vurgulu
        counter_frame = tk.Frame(content, bg=self.COLORS['primary'], padx=10, pady=8)
        counter_frame.pack(fill=tk.X, pady=(0, 12))
        self.record_counter_label = tk.Label(counter_frame, text="Kayıt: 0", font=('Segoe UI Semibold', 13, 'bold'), fg='white', bg=self.COLORS['primary'])
        self.record_counter_label.pack()
        
        # Ayırıcı
        tk.Frame(content, height=1, bg=self.COLORS['border']).pack(fill=tk.X, pady=8)
        
        btn_style = {'font': ('Segoe UI Semibold', 9, 'bold'), 'height': 2, 'cursor': 'hand2', 'relief': 'flat'}
        
        
        tk.Frame(content, height=15, bg=self.COLORS['surface']).pack() # Spacer
        
        # Bölüm başlığı
        tk.Label(content, text="Mesaj İşlemleri", font=('Segoe UI Semibold', 9, 'bold'), bg=self.COLORS['surface'], fg=self.COLORS['text_light']).pack(anchor='w', pady=(0, 5))
        
        # Otomatik Onay Toggle (NEW)
        auto_approve_frame = tk.Frame(content, bg='#f3f4f6', padx=10, pady=8, highlightthickness=1, highlightbackground=self.COLORS['border'])
        auto_approve_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Checkbutton(auto_approve_frame, text="🤖 OTOMATİK ONAY", 
                       variable=self.auto_approval_var,
                       font=('Segoe UI Semibold', 10),
                       bg='#f3f4f6', activebackground='#f3f4f6',
                       fg=self.COLORS['primary'],
                       cursor='hand2').pack(side=tk.LEFT)
        
        tk.Button(content, text="🗑️ HIZLI SİL\n(Onaysız)", bg=self.COLORS['danger'], fg='white', command=self.quick_delete_message, activebackground='#b91c1c', **btn_style).pack(fill=tk.X, pady=4)
        tk.Button(content, text="🔄 YENİLE", bg=self.COLORS['success'], fg='white', command=self.manual_refresh, activebackground='#047857', **btn_style).pack(fill=tk.X, pady=4)
        
        # --- Servis Yönetimi (Terminal) ---
        tk.Frame(content, height=15, bg=self.COLORS['surface']).pack() # Spacer
        tk.Label(content, text="📡 SERVİS YÖNETİMİ", font=('Segoe UI Semibold', 9, 'bold'), 
                 bg=self.COLORS['surface'], fg=self.COLORS['text_muted']).pack(anchor='w', pady=(5, 5))
        
        
        # --- FIX: Define missing attributes for Threaded Fetcher ---
        # Status Label replace button
        self.veri_cekici_status_label = tk.Label(content, text="⚪ Başlatılıyor...", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['surface'], fg=self.COLORS['text_muted'])
        self.veri_cekici_status_label.pack(anchor='w', pady=(5, 5))
        
        # Aliases for compatibility
        self.continuous_fetch_status_label = self.veri_cekici_status_label
        # Dummy button references to prevent crashes if referenced elsewhere
        self.veri_cekici_button = tk.Button(self.root) 
        self.continuous_fetch_button = tk.Button(self.root)
        self.launch_service_btn = tk.Button(self.root)
        # -------------------------------------------------------------
        
        tk.Label(content, text="* WhatsApp senkronizasyonu bu\nservis içinde otomatik çalışır.", 
                 font=('Segoe UI', 8, 'italic'), bg=self.COLORS['surface'], 
                 fg=self.COLORS['text_muted'], justify='left').pack(anchor='w', pady=(0, 10))


        # Navigasyon (En altta) - daha modern
        nav_frame = tk.Frame(self.right_pane, bg=self.COLORS['surface_alt'], pady=12)
        nav_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        nav_btn_style = {'font': ('Segoe UI', 12), 'width': 4, 'bg': self.COLORS['primary'], 'fg': 'white', 'relief': 'flat', 'cursor': 'hand2'}
        self.prev_msg_button = tk.Button(nav_frame, text="◀", command=self.load_previous_message, **nav_btn_style)
        self.prev_msg_button.pack(side=tk.LEFT, padx=8)
        
        # FIX: Renamed to avoid override
        self.message_counter_label_right = tk.Label(nav_frame, text="0/0", font=('Segoe UI Semibold', 10, 'bold'), bg=self.COLORS['surface_alt'], fg=self.COLORS['text'])
        self.message_counter_label_right.pack(side=tk.LEFT, expand=True)
        
        self.next_msg_button = tk.Button(nav_frame, text="▶", command=self.load_next_message, **nav_btn_style)
        self.next_msg_button.pack(side=tk.RIGHT, padx=8)


    def launch_parser_in_terminal(self):
        """Starts the veri_cekici_ayristirici.py in internal thread mode."""
        self.logger.info("Veri çekici başlatma isteği (Thread Mode)")
        self.start_veri_cekici()



    def setup_status_bar(self):
        # Üst gölge
        tk.Frame(self.root, height=1, bg=self.COLORS['border']).pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_bar = tk.Frame(self.root, height=28, bg=self.COLORS['surface_alt'])
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = tk.Label(self.status_bar, text="✅ Hazır", font=('Segoe UI', 9), bg=self.COLORS['surface_alt'], fg=self.COLORS['text_light'])
        self.status_label.pack(side=tk.LEFT, padx=15)
        
        self.message_count_label = tk.Label(self.status_bar, text="0 mesaj", font=('Segoe UI', 9), bg='#e9ecef')
        self.message_count_label.pack(side=tk.RIGHT, padx=10)

    # --- YAN PANEL YÖNETİMİ ---
    
    def open_side_panel(self, title, width=None):
        """Yan paneli açar ve içeriği temizler"""
        if width is None:
            width = self.side_panel_width
        # Önce mevcut içeriği temizle
        for widget in self.side_panel.winfo_children():
            widget.destroy()
            
        self.side_panel.config(width=width, bg=self.COLORS['panel_bg'])
        # Side panel'i sağa, sağdaki buton panelinin soluna veya sağına koyabiliriz.
        # "Ana ekran daralsın" dendiği için side_panel'i main_container içinde en sağa pack ediyoruz.
        # Ancak right_pane zaten sağda. side_panel'i right_pane'in soluna koymak mantıklı olabilir veya right_pane'in sağına.
        # En temiz görünüm için right_pane'in SOLUNA koyalım (tablonun sağına).
        
        # Mevcut pack sırasını bozmadan araya girmek için:
        self.right_pane.pack_forget() # Önce sağ paneli kaldır
        self.center_pane.pack_forget() # Orta paneli kaldır
        
        # Yeniden sırala: Sol (sabit) -> Orta (esnek) -> (kayar handle) -> Yan (dinamik) -> Sağ (sabit)
        self.left_pane.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        self.center_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.side_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=0) # Yan panel
        self.right_pane.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0)) # Butonlar en sağda kalsın
        
        if not self.side_panel_handle:
            self.side_panel_handle = tk.Frame(self.main_container, width=6, bg='#cbd5f5', cursor='sb_h_double_arrow')
        else:
            self.side_panel_handle.pack_forget()
        self.side_panel_handle.pack(side=tk.RIGHT, fill=tk.Y)
        self._bind_side_panel_handle()
        
        self.side_panel.pack_propagate(False) # Boyutu koru
        
        # Panel Başlığı
        header = tk.Frame(self.side_panel, bg=self.COLORS['secondary'], height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text=title, font=('Segoe UI', 11, 'bold'), bg=self.COLORS['secondary'], fg='white').pack(side=tk.LEFT, padx=10)
        tk.Button(header, text="✖", bg='#dc3545', fg='white', font=('Segoe UI', 8, 'bold'), width=3, command=self.close_side_panel).pack(side=tk.RIGHT, padx=5, pady=5)

        return self.side_panel

    def close_side_panel(self):
        """Yan paneli kapatır"""
        self.side_panel.pack_forget()
        if self.side_panel_handle:
            self.side_panel_handle.pack_forget()
        # Düzeni yenilemek gerekmez, pack_forget otomatik alanı diğerlerine verir (expand=True olan center_pane'e).

    # --- DÜZENLEME PENCERESİ (Entegre) ---

    def edit_selected_shipment(self):
        if not self.current_shipments or self.current_shipment_index >= len(self.current_shipments):
            messagebox.showwarning("Uyarı", "Düzenlenecek sevkiyat bulunamadı veya seçilmedi.")
            return

        # Yedek al (Geri alma için)
        self.shipment_backup = copy.deepcopy(self.current_shipments[self.current_shipment_index])
        
        panel = self.open_side_panel("✏️ SEVKİYAT DÜZENLE", width=800)
        shipment = self.current_shipments[self.current_shipment_index]
        
        # Scrollable Frame
        canvas = tk.Canvas(panel, bg=self.COLORS['panel_bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.COLORS['panel_bg'])
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=780) # Width ayarı önemli
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=5)
        scrollbar.pack(side="right", fill="y")
        self._enable_mousewheel_scrolling(scroll_frame, canvas)
        
        # Form
        form_entries = {}
        
        # Kaydet Butonu (En üstte)
        btn_frame_top = tk.Frame(scroll_frame, bg=self.COLORS['panel_bg'])
        btn_frame_top.pack(fill=tk.X, pady=(10, 5), padx=10)
        
        tk.Button(btn_frame_top, text="💾 KAYDET", bg='#28a745', fg='white', font=('Segoe UI', 10, 'bold'),
                 command=lambda: self.save_edit_changes(shipment, form_entries), height=2).pack(fill=tk.X)
        
        # Geri Al Butonu (En üstte)
        tk.Button(scroll_frame, text="↩️ Değişiklikleri Geri Al", bg='#6c757d', fg='white', 
                 command=lambda: self.restore_original_shipment(shipment),
                 font=('Segoe UI', 9)).pack(fill=tk.X, pady=10, padx=10)

        # Yer Değiştir Butonu
        tk.Button(scroll_frame, text="🔄 Yer Değiştir", bg='#17a2b8', fg='white', 
                 command=lambda: self.swap_locations(nereden_il_combo, nereden_ilce_combo, nereye_il_combo, nereye_ilce_combo),
                 font=('Segoe UI', 9)).pack(fill=tk.X, pady=(0, 10), padx=10)

        self.create_form_field(scroll_frame, "Firma Adı:", shipment.get('isim', ''), form_entries, 'isim')
        
        # İl/İlçe seçimleri - JSON'dan direkt al, normalize et
        il_list = sorted([item['il'] for item in self.il_ilceler_data])
        
        # Nereden İl - mevcut değeri normalize et
        current_nereden_il = self._normalize_il_name(shipment.get('nereden_il', ''))
        nereden_il_combo = self.create_autocomplete_field(scroll_frame, "Nereden İl:", il_list, current_nereden_il, form_entries, 'nereden_il')
        
        # Nereden İlçe (Dinamik güncelleme için referans tutma)
        nereden_ilce_vals = self.get_ilce_list(current_nereden_il)
        # İlçe değeri yoksa varsayılan ilçeyi seç
        nereden_ilce_default = shipment.get('nereden_ilce', '') or self._get_default_ilce(current_nereden_il)
        nereden_ilce_combo = self.create_autocomplete_field(scroll_frame, "Nereden İlçe:", nereden_ilce_vals, nereden_ilce_default, form_entries, 'nereden_ilce', depends_on='nereden_il')
        
        def update_nereden(event=None):
            il = nereden_il_combo.get()
            vals = self.get_ilce_list(il)
            # İlçe listesini güncelle (autocomplete field için)
            form_entries['nereden_ilce_values'] = vals
            if vals:
                # Mevcut ilçe seçiliyse koru, yoksa varsayılan ilçeyi seç
                current_ilce = nereden_ilce_combo.get()
                if current_ilce in vals:
                    pass  # Mevcut değeri koru
                else:
                    # Varsayılan ilçeyi seç
                    default = self._get_default_ilce(il)
                    nereden_ilce_combo.delete(0, tk.END)
                    nereden_ilce_combo.insert(0, default if default in vals else (vals[0] if vals else ''))
            else:
                nereden_ilce_combo.delete(0, tk.END)

        # İl değişikliğini izle - autocomplete için özel event handling
        def on_nereden_il_change(*args):
            # Kısa bir delay ile güncelle
            scroll_frame.after(100, update_nereden)

        # İl entry'sinde değişiklik olduğunda ilçeleri güncelle (her tuş basımında, ufak bir gecikmeyle)
        nereden_il_combo.bind('<KeyRelease>', lambda e: scroll_frame.after(100, update_nereden), add='+')
        nereden_il_combo.bind('<FocusOut>', lambda e: scroll_frame.after(200, update_nereden))

        # Nereye İl - mevcut değeri normalize et
        current_nereye_il = self._normalize_il_name(shipment.get('nereye_il', ''))
        nereye_il_combo = self.create_autocomplete_field(scroll_frame, "Nereye İl:", il_list, current_nereye_il, form_entries, 'nereye_il')
        nereye_ilce_vals = self.get_ilce_list(current_nereye_il)
        # İlçe değeri yoksa varsayılan ilçeyi seç
        nereye_ilce_default = shipment.get('nereye_ilce', '') or self._get_default_ilce(current_nereye_il)
        nereye_ilce_combo = self.create_autocomplete_field(scroll_frame, "Nereye İlçe:", nereye_ilce_vals, nereye_ilce_default, form_entries, 'nereye_ilce', depends_on='nereye_il')
        
        def update_nereye(event=None):
            il = nereye_il_combo.get()
            vals = self.get_ilce_list(il)
            # İlçe listesini güncelle (autocomplete field için)
            form_entries['nereye_ilce_values'] = vals
            if vals:
                # Mevcut ilçe seçiliyse koru, yoksa varsayılan ilçeyi seç
                current_ilce = nereye_ilce_combo.get()
                if current_ilce in vals:
                    pass  # Mevcut değeri koru
                else:
                    # Varsayılan ilçeyi seç
                    default = self._get_default_ilce(il)
                    nereye_ilce_combo.delete(0, tk.END)
                    nereye_ilce_combo.insert(0, default if default in vals else (vals[0] if vals else ''))
            else:
                nereye_ilce_combo.delete(0, tk.END)

        # Nereye il değişikliğini izle
        def on_nereye_il_change(*args):
            scroll_frame.after(100, update_nereye)

        nereye_il_combo.bind('<KeyRelease>', lambda e: scroll_frame.after(100, update_nereye), add='+')
        nereye_il_combo.bind('<FocusOut>', lambda e: scroll_frame.after(200, update_nereye))

        # TAG SELECTOR: Araç/Kasa/Yük Tipi (Tag-based selection with X buttons)
        
        # Araç Tipi
        arac_label = tk.Label(scroll_frame, text="Araç Tipi:", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg'], anchor='w')
        arac_label.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        arac_selector = TagSelector(scroll_frame, self.arac_yuk_kasa_tipleri_data.get('arac_tipleri', []),
                                    bg=self.COLORS['panel_bg'])
        arac_selector.pack(fill=tk.X, padx=10, pady=5)
        current_arac = self.parse_type_to_list(shipment.get('arac_tipi', []))
        arac_selector.set_values(current_arac)
        form_entries['arac_tipi'] = arac_selector
        
        # Kasa Tipi
        kasa_label = tk.Label(scroll_frame, text="Kasa Tipi:", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg'], anchor='w')
        kasa_label.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        kasa_selector = TagSelector(scroll_frame, self.arac_yuk_kasa_tipleri_data.get('kasa_tipleri', []),
                                    bg=self.COLORS['panel_bg'])
        kasa_selector.pack(fill=tk.X, padx=10, pady=5)
        current_kasa = self.parse_type_to_list(shipment.get('kasa_tipi', []))
        kasa_selector.set_values(current_kasa)
        form_entries['kasa_tipi'] = kasa_selector
        
        # Yük Tipi
        yuk_label = tk.Label(scroll_frame, text="Yük Tipi:", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg'], anchor='w')
        yuk_label.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        yuk_selector = TagSelector(scroll_frame, self.arac_yuk_kasa_tipleri_data.get('yuk_tipleri', []),
                                   bg=self.COLORS['panel_bg'])
        yuk_selector.pack(fill=tk.X, padx=10, pady=5)
        current_yuk = self.parse_type_to_list(shipment.get('yuk_tipi', []))
        yuk_selector.set_values(current_yuk)
        form_entries['yuk_tipi'] = yuk_selector
        
        # Telefon - Listbox yerine normal Entry
        self.create_form_field(scroll_frame, "Telefon:", shipment.get('telefon', ''), form_entries, 'telefon')
        self.create_form_field(scroll_frame, "Fiyat:", shipment.get('fiyat', ''), form_entries, 'fiyat')
        
        # Açıklama
        lbl = tk.Label(scroll_frame, text="Açıklama:", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg'], anchor='w')
        lbl.pack(fill=tk.X, padx=10, pady=(10, 0))
        txt = tk.Text(scroll_frame, height=4, font=('Segoe UI', 9))
        txt.insert(1.0, shipment.get('aciklama', ''))
        txt.pack(fill=tk.X, padx=10, pady=5)
        form_entries['aciklama'] = txt
        
        # Kaydet Butonu (Alt kısımdan kaldırıldı - yukarı alındı)
        # btn_frame = tk.Frame(scroll_frame, bg=self.COLORS['panel_bg'])
        # btn_frame.pack(fill=tk.X, pady=20, padx=10)
        # tk.Button(btn_frame, text="💾 KAYDET", ...).pack(fill=tk.X)

        # --- Changelog Entry (Phase 22) ---
        # This section is a changelog entry and is commented out to maintain Python syntax.
        # It should ideally be in a separate documentation file like task.md.
        #
        # - [x] **Araç Alt Tipi Manuel Kural Temizliği (Phase 19)**
        #     - [x] Kullanıcı onayı alınarak `yuk_tipi.json` dosyasında sonradan eklenmiş olup, "PARÇA" kelimesini "KOMPLE" olarak zorunlu kılan iki adet kullanıcı-tanımlı hata veren kural silindi.
        #     - [x] `VehicleTypeMatcher` sisteminin doğal regex kuralları ile 1/TIRA PARCA gibi kompleks testler başarıyla çalıştırıldı.
        #
        # - [x] **Noktalama İşareti ve Satırbaşı Parse Hatası Çözümü (Phase 20)**
        #     - [x] İlanlardaki bitişik noktalama işaretleri (`DAMPERLİ/TIR`, `10 TEKER+PARÇA`, `AÇIK,TENTELİ`) temizlenirken kelimelerin birbirine yapışması hatası regex ile düzeltildi (`DAMPERLİTIR` -> `DAMPERLİ TIR`).
        #     - [x] Yeni mantık sayesinde arka arkaya farklı araç, kasa ve yük tipleri aynı metin içinde kolayca ayrıştırılabilecek.
        #
        # - [x] **Canlı İzle Paneli Veri Okuma Hatası Çözümü (Phase 21)**
        #     - [x] Canlı İzle paneline mesajların düşmeme sorununun, yeni MongoDB sisteminden string olarak dönen `2026-03-05T20:33:33` formatındaki 'T' karakterinin `datetime.strptime` tarafından reddedilmesi olduğu keşfedildi.
        #     - [x] Parse hatası (ValueError) `try-except` ile yakalandı ve Unix Timestamp yedeği ile birleştirilerek tarih algılama mekanizması güçlendirildi.
        #     - [x] ISO formatlı metinlerden `T` karakterini atan güvenli bir dönüşüm kodu yazıldı.
        #
        # - [x] **Tkinter Yenileme (Refresh) Çökmesi Kesin Çözüm (Phase 22)**
        #     - [x] Yenileme işlemi UI donmaması için Thread içerisine alındığında, Thread yasadışı olarak `minutes_filter_var.get()` ve `message_count_label.config()` gibi Tkinter bileşenlerine eriştiğinden uygulamanın çöktüğü (crash) anlaşıldı.
        #     - [x] `filter_messages_by_time` ve `load_messages_from_file` fonksiyonları `update_ui=False` argümanıyla izole edildi.
        #     - [x] Thread (arka plan) yalnızca hafıza IO işlemleri ile sınırlanırken UI güncellemeleri yalnızca `root.after(0)` callback'lerine taşınarak deadlock sorunları kesin olarak çözüldü.
        # --- End Changelog Entry ---

    def get_ilce_list(self, il_name):
        """İl adına göre ilçe listesini döndür (case-insensitive)"""
        if not il_name:
            return []
        # İl ismini normalize et (büyük harf, Türkçe karakterler korunur)
        il_name_normalized = il_name.strip().upper()
        for item in self.il_ilceler_data:
            if item['il'].upper() == il_name_normalized:
                return item.get('ilçe', [])
        return []

    def find_il_by_ilce(self, ilce_name):
        """Find the province (il) and canonical ilçe for a given ilçe name.
        Returns (il, ilce_canonical) if there's exactly one match across data, otherwise (None, None).
        Matching is case-insensitive."""
        if not ilce_name:
            return (None, None)
        needle = ilce_name.strip().lower()
        matches = []
        for item in self.il_ilceler_data:
            for ilce in item.get('ilçe', []):
                if ilce.lower() == needle:
                    matches.append((item.get('il'), ilce))
        if len(matches) == 1:
            return matches[0]
        # If no exact equals, try startswith matches to help when user typed partial
        for item in self.il_ilceler_data:
            for ilce in item.get('ilçe', []):
                if ilce.lower().startswith(needle):
                    matches.append((item.get('il'), ilce))
        if len(matches) == 1:
            return matches[0]
        return (None, None)

    def _normalize_il_name(self, il_name):
        """İl ismini JSON'daki formata normalize et"""
        if not il_name:
            return ''
        il_normalized = il_name.strip().upper()
        # JSON'daki il listesinde ara
        for item in self.il_ilceler_data:
            if item['il'].upper() == il_normalized:
                return item['il']  # JSON'daki orjinal formatı döndür
        # Bulunamazsa girilen değeri döndür
        return il_name.strip()
    
    def _get_default_ilce(self, il_name):
        """İl adına göre varsayılan ilçeyi döndür (il_ilçeler.json'dan)"""
        if not il_name:
            return ''
        il_normalized = il_name.strip().upper()
        for item in self.il_ilceler_data:
            if item['il'].upper() == il_normalized:
                return item.get('varsayılan_ilçe', '')
        return ''
    
    def restore_original_shipment(self, current_shipment_ref):
        """Yedekten geri yükler"""
        if self.shipment_backup:
            # Referans üzerinden güncelleme (Dictionary içeriğini değiştir)
            current_shipment_ref.clear()
            current_shipment_ref.update(self.shipment_backup)
            
            # Formu kapat ve yeniden aç (güncel verilerle)
            self.edit_selected_shipment()
            self.status_label.config(text="↩️ Değişiklikler geri alındı.")

    def save_edit_changes(self, shipment, form_entries):
        for field_name, widget in form_entries.items():
            if isinstance(widget, tk.Text):
                shipment[field_name] = widget.get(1.0, tk.END).strip()
            elif isinstance(widget, tk.Listbox):
                shipment[field_name] = ', '.join(widget.get(0, tk.END))
            elif isinstance(widget, dict): # Checkboxlar
                shipment[field_name] = [k for k, v in widget.items() if v.get()]
            elif isinstance(widget, TagSelector):  # TAG SELECTOR
                shipment[field_name] = widget.get_values()
            elif isinstance(widget, ttk.Combobox) or isinstance(widget, tk.Entry):
                value = widget.get().strip()
                # İl alanlarını normalize et
                if field_name in ['nereden_il', 'nereye_il']:
                    value = self._normalize_il_name(value)
                # Telefon temizle (sadece rakamlar)
                elif field_name == 'telefon':
                    value = ''.join(filter(str.isdigit, value))
                # İlçe alanlarını case-insensitive olarak canonicalize if possible
                if field_name in ['nereden_ilce', 'nereye_ilce']:
                    vals = form_entries.get(f"{field_name}_values", [])
                    for v in vals:
                        if v.lower() == value.lower():
                            value = v
                            break
                
                # FIX: Fiyat boşsa "Sorunuz" yaz
                if field_name == 'fiyat' and not value:
                    value = 'Sorunuz'
                
                shipment[field_name] = value
        
        
        # EXPLICIT SYNC: Ensure changes propagate to self.unprocessed_data
        if self.current_message:
            msg_id = self.current_message.get('id')
            if msg_id and msg_id in self.unprocessed_data:
                # Update the source record with current shipments
                self.unprocessed_data[msg_id]['shipments'] = self.current_shipments
        
        self.update_shipment_list()
        self.save_unprocessed_data() # Dosyaya da yaz
        self.status_label.config(text="✅ Kayıt güncellendi.")
        self.close_side_panel()

    def swap_locations(self, nereden_il_combo, nereden_ilce_combo, nereye_il_combo, nereye_ilce_combo):
        """Nereden ve nereye bilgilerini yer değiştir"""
        # Mevcut değerleri al
        nereden_il = nereden_il_combo.get()
        nereden_ilce = nereden_ilce_combo.get()
        nereye_il = nereye_il_combo.get()
        nereye_ilce = nereye_ilce_combo.get()
        
        # Yer değiştir
        nereden_il_combo.delete(0, tk.END)
        nereden_il_combo.insert(0, nereye_il)
        nereden_ilce_combo.delete(0, tk.END)
        nereden_ilce_combo.insert(0, nereye_ilce)
        nereye_il_combo.delete(0, tk.END)
        nereye_il_combo.insert(0, nereden_il)
        nereye_ilce_combo.delete(0, tk.END)
        nereye_ilce_combo.insert(0, nereden_ilce)
        
        # İl değiştiğinde ilçeleri güncelle
        self.update_location_combos(nereden_il_combo, nereden_ilce_combo)
        self.update_location_combos(nereye_il_combo, nereye_ilce_combo)

    def update_location_combos(self, il_combo, ilce_combo):
        """İl değiştiğinde ilçe listesini güncelle (autocomplete için)"""
        il = il_combo.get()
        vals = self.get_ilce_list(il)
        # İlçe listesini güncelle (form_entries'e kaydet)
        # Bu fonksiyon çağrıldığında form_entries'e erişimimiz yok, bu yüzden farklı yaklaşım
        if vals:
            current_ilce = ilce_combo.get()
            if current_ilce in vals:
                pass  # Mevcut değeri koru
            else:
                # Varsayılan ilçeyi seç
                default = self._get_default_ilce(il)
                ilce_combo.delete(0, tk.END)
                ilce_combo.insert(0, default if default in vals else vals[0])
        else:
            ilce_combo.delete(0, tk.END)

    def edit_multiple_shipments(self):
        """Çoklu sevkiyat düzenleme - seçili tüm sevkiyatlara ortak değişiklik uygular"""
        if not self.selected_shipments:
            messagebox.showwarning("Uyarı", "Düzenlenecek sevkiyat seçilmedi.")
            return

        # Yedek al (Geri alma için)
        self.shipment_backups = {}
        for idx in self.selected_shipments:
            if idx < len(self.current_shipments):
                self.shipment_backups[idx] = copy.deepcopy(self.current_shipments[idx])
        
        panel = self.open_side_panel("✏️ ÇOKLU SEVKİYAT DÜZENLE", width=800)
        
        # Scrollable Frame
        canvas = tk.Canvas(panel, bg=self.COLORS['panel_bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.COLORS['panel_bg'])
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=780)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=5)
        scrollbar.pack(side="right", fill="y")
        self._enable_mousewheel_scrolling(scroll_frame, canvas)
        
        # Form
        form_entries = {}
        
        # Kaydet Butonu (En üstte)
        btn_frame_top = tk.Frame(scroll_frame, bg=self.COLORS['panel_bg'])
        btn_frame_top.pack(fill=tk.X, pady=(10, 5), padx=10)
        
        tk.Button(btn_frame_top, text="💾 TÜMÜNÜ GÜNCELLE", bg='#28a745', fg='white', font=('Segoe UI', 10, 'bold'),
                 command=lambda: self.save_multiple_edit_changes(form_entries), height=2).pack(fill=tk.X)
        
        # Geri Al Butonu (En üstte)
        tk.Button(scroll_frame, text="↩️ Değişiklikleri Geri Al", bg='#6c757d', fg='white', 
                 command=self.restore_multiple_shipments,
                 font=('Segoe UI', 9)).pack(fill=tk.X, pady=10, padx=10)

        # Yer Değiştir Butonu
        tk.Button(scroll_frame, text="🔄 Yer Değiştir", bg='#17a2b8', fg='white', 
                 command=lambda: self.swap_locations(nereden_il_combo, nereden_ilce_combo, nereye_il_combo, nereye_ilce_combo),
                 font=('Segoe UI', 9)).pack(fill=tk.X, pady=(0, 10), padx=10)

        # Bilgilendirme
        info_label = tk.Label(scroll_frame, text=f"⚠️ {len(self.selected_shipments)} sevkiyat seçildi. Değişiklikler tümüne uygulanacak.", 
                            bg='#fff3cd', fg='#856404', font=('Segoe UI', 9, 'bold'))
        info_label.pack(fill=tk.X, padx=10, pady=5)
        
        # İl/İlçe seçimleri - JSON'dan direkt al
        il_list = sorted([item['il'] for item in self.il_ilceler_data])
        
        # Nereden İl
        nereden_il_combo = self.create_autocomplete_field(scroll_frame, "Nereden İl:", il_list, "", form_entries, 'nereden_il')

        # Nereden İlçe (Dinamik güncelleme için referans tutma)
        nereden_ilce_combo = self.create_autocomplete_field(scroll_frame, "Nereden İlçe:", [], "", form_entries, 'nereden_ilce', depends_on='nereden_il')
        def update_nereden(event=None):
            il = nereden_il_combo.get()
            vals = self.get_ilce_list(il)
            # İlçe listesini güncelle (autocomplete için)
            form_entries['nereden_ilce_values'] = vals
            if vals:
                nereden_ilce_combo.delete(0, tk.END)
                nereden_ilce_combo.insert(0, vals[0])
            else:
                nereden_ilce_combo.delete(0, tk.END)
        nereden_il_combo.bind('<KeyRelease>', update_nereden, add='+')

        # Nereye İl
        nereye_il_combo = self.create_autocomplete_field(scroll_frame, "Nereye İl:", il_list, "", form_entries, 'nereye_il')
        nereye_ilce_combo = self.create_autocomplete_field(scroll_frame, "Nereye İlçe:", [], "", form_entries, 'nereye_ilce', depends_on='nereye_il')
        
        def update_nereye(event=None):
            il = nereye_il_combo.get()
            vals = self.get_ilce_list(il)
            # İlçe listesini güncelle (autocomplete için)
            form_entries['nereye_ilce_values'] = vals
            if vals:
                nereye_ilce_combo.delete(0, tk.END)
                nereye_ilce_combo.insert(0, vals[0])
            else:
                nereye_ilce_combo.delete(0, tk.END)
        nereye_il_combo.bind('<KeyRelease>', update_nereye, add='+')

        # Checkboxlar - boş başlat (kullanıcı seçsin)
        arac_vars = self.create_checkbox_field(scroll_frame, "Araç Tipi:", self.arac_yuk_kasa_tipleri_data.get('arac_tipleri', []), [], form_entries, 'arac_tipi')
        # Kasa tipi için varsayılan AÇIK ve KAPALI seçili
        default_kasa = [] # Kullanıcı isteği: Varsayılan boş olsun
        self.create_checkbox_field(scroll_frame, "Kasa Tipi:", self.arac_yuk_kasa_tipleri_data.get('kasa_tipleri', []), default_kasa, form_entries, 'kasa_tipi')
        
        def on_yuk_tipi_change(key, option):
            """Yük tipi değiştiğinde araç tipini otomatik güncelle"""
            if key == 'yuk_tipi' and option == 'PALETLİ':
                yuk_vars = form_entries.get('yuk_tipi', {})
                if yuk_vars.get('PALETLİ', tk.BooleanVar()).get():
                    # PALETLİ seçildiğinde tüm araç tiplerini seç
                    for arac_opt, arac_var in arac_vars.items():
                        arac_var.set(True)
                else:
                    # PALETLİ kaldırıldığında araç tiplerini temizle
                    for arac_opt, arac_var in arac_vars.items():
                        arac_var.set(False)
        
        self.create_checkbox_field(scroll_frame, "Yük Tipi:", self.arac_yuk_kasa_tipleri_data.get('yuk_tipleri', []), [], form_entries, 'yuk_tipi', callback=on_yuk_tipi_change)
        
        self.create_form_field(scroll_frame, "Fiyat:", "", form_entries, 'fiyat')
        self.create_form_field(scroll_frame, "Telefon:", "", form_entries, 'telefon')
        
        # Açıklama
        lbl = tk.Label(scroll_frame, text="Açıklama:", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg'], anchor='w')
        lbl.pack(fill=tk.X, padx=10, pady=(10, 0))
        txt = tk.Text(scroll_frame, height=4, font=('Segoe UI', 9))
        txt.pack(fill=tk.X, padx=10, pady=5)
        form_entries['aciklama'] = txt
        
        # Kaydet Butonu (Alt kısımdan kaldırıldı - yukarı alındı)
        # btn_frame = tk.Frame(scroll_frame, bg=self.COLORS['panel_bg'])
        # btn_frame.pack(fill=tk.X, pady=20, padx=10)
        # tk.Button(btn_frame, text="💾 TÜMÜNÜ GÜNCELLE", ...).pack(fill=tk.X)

    def restore_multiple_shipments(self):
        """Çoklu sevkiyat yedeklerinden geri yükler"""
        if self.shipment_backups:
            for idx, backup in self.shipment_backups.items():
                if idx < len(self.current_shipments):
                    self.current_shipments[idx].clear()
                    self.current_shipments[idx].update(backup)
            
            # Formu kapat ve yeniden aç
            self.edit_multiple_shipments()
            self.status_label.config(text="↩️ Çoklu değişiklikler geri alındı.")

    def save_multiple_edit_changes(self, form_entries):
        """Çoklu sevkiyat değişikliklerini uygular"""
        updated_count = 0
        for idx in self.selected_shipments:
            if idx >= len(self.current_shipments):
                continue
                
            shipment = self.current_shipments[idx]
            
            for field_name, widget in form_entries.items():
                if isinstance(widget, tk.Text):
                    value = widget.get(1.0, tk.END).strip()
                    if value:  # Sadece dolu değerleri uygula
                        shipment[field_name] = value
                elif isinstance(widget, dict): # Checkboxlar
                    selected_values = [k for k, v in widget.items() if v.get()]
                    if selected_values:  # Sadece seçili değerler varsa uygula
                        shipment[field_name] = selected_values
                elif isinstance(widget, ttk.Combobox) or isinstance(widget, tk.Entry):
                    value = widget.get().strip()
                    if value:  # Sadece dolu değerleri uygula
                        # İl alanlarını normalize et
                        if field_name in ['nereden_il', 'nereye_il']:
                            value = self._normalize_il_name(value)
                        # Telefon temizle (sadece rakamlar)
                        elif field_name == 'telefon':
                            value = ''.join(filter(str.isdigit, value))
                        # İlçe alanlarını case-insensitive olarak canonicalize if possible
                        if field_name in ['nereden_ilce', 'nereye_ilce']:
                            vals = form_entries.get(f"{field_name}_values", [])
                            for v in vals:
                                if v.lower() == value.lower():
                                    value = v
                                    break
                        shipment[field_name] = value
            
            updated_count += 1
        
        
        # EXPLICIT SYNC: Ensure changes propagate to self.unprocessed_data
        if self.current_message:
            msg_id = self.current_message.get('id')
            if msg_id and msg_id in self.unprocessed_data:
                # Update the source record with current shipments
                self.unprocessed_data[msg_id]['shipments'] = self.current_shipments

        self.update_shipment_list()
        self.save_unprocessed_data()
        self.status_label.config(text=f"✅ {updated_count} kayıt güncellendi.")
        self.close_side_panel()

    # --- ONAYLANANLAR PENCERESİ (Entegre & Revize) ---

    def show_approved_records(self):
        panel = self.open_side_panel("📋 ONAYLANAN KAYITLAR", width=600)

        # Veri Yükle - Veritabanı API'sinden çek
        records = []
        try:
            submitter = YukBuradaSubmitter()
            records = submitter.load_approved_records()
        except Exception as e:
            self.status_label.config(text=f"Veritabanı bağlantı hatası: {str(e)}")
            # Fallback to local file
            try:
                if os.path.exists(self.onaylananlar_file):
                    with open(self.onaylananlar_file, 'r', encoding='utf-8') as f:
                        records = json.load(f)
            except: pass

        if records:
            # KATI KURAL: Sadece son 1 SAATE ait olanları göster
            time_threshold = datetime.now() - timedelta(hours=1)
            all_records = list(records)
            records = []
            for r in all_records:
                dt = self._get_message_datetime(r)
                if dt and dt >= time_threshold:
                    records.append(r)

        if not records:
            tk.Label(panel, text="Onaylanan kayıt bulunamadı.", bg=self.COLORS['panel_bg']).pack(pady=20)
            return

        # Üst kısım: Liste (Treeview)
        list_frame = tk.Frame(panel, bg='white')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ('nereden', 'nereye', 'info', 'tarih')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        
        tree.heading('nereden', text='Nereden')
        tree.heading('nereye', text='Nereye')
        tree.heading('info', text='Araç/Kasa Bilgisi')
        tree.heading('tarih', text='Tarih')
        
        tree.column('nereden', width=100)
        tree.column('nereye', width=100)
        tree.column('info', width=150)
        tree.column('tarih', width=100)
        
        tree_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Alt kısım: Detay Alanı
        detail_frame = tk.Frame(panel, bg=self.COLORS['panel_bg'], height=200)
        detail_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        detail_frame.pack_propagate(False)
        
        tk.Label(detail_frame, text="🔍 SEÇİLİ KAYIT DETAYLARI", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg']).pack(anchor='w', pady=(5,0))
        
        detail_text = scrolledtext.ScrolledText(detail_frame, height=8, font=('Segoe UI', 9), state='disabled')
        detail_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Listeyi Doldur (Sadeleştirilmiş görünüm)
        # En son eklenen en üstte
        for i, rec in enumerate(reversed(records)):
            kombinasyonlar = rec.get('arac_kasa_kombinasyon_listesi', []) or rec.get('requiredVehicleTypes', [])
            
            # Görünen özet bilgi
            if kombinasyonlar:
                ozet_bilgi = f"{kombinasyonlar[0]}"
                if len(kombinasyonlar) > 1:
                    ozet_bilgi += f" (+{len(kombinasyonlar)-1} diğer)"
            else:
                ozet_bilgi = "-"
            
            # API ve yerel format uyumluluğu
            nereden_il = rec.get('nereden_il') or rec.get('pickupCity', '')
            nereden_ilce = rec.get('nereden_ilce') or rec.get('pickupDistrict', '')
            nereye_il = rec.get('nereye_il') or rec.get('deliveryCity', '')
            nereye_ilce = rec.get('nereye_ilce') or rec.get('deliveryDistrict', '')
            
            nerden = f"{nereden_il} {nereden_ilce}"
            nereye = f"{nereye_il} {nereye_ilce}"
            tarih = (rec.get('onay_tarihi') or rec.get('createdAt', '')).split(' ')[0].split('T')[0]
            
            # Orijinal indexi saklamak için (tersten olduğu için hesapla)
            real_index = len(records) - 1 - i
            tree.insert("", "end", values=(nerden, nereye, ozet_bilgi, tarih), tags=(str(real_index),))

        # Seçim Olayı
        def on_select(event):
            selected = tree.selection()
            if not selected: return
            
            item = tree.item(selected[0])
            idx = int(item['tags'][0])
            rec = records[idx]
            
            # Detay oluştur
            text = f"FİRMA: {rec.get('isim', '-')}\n"
            text += f"GÜZERGAH: {rec.get('nereden_il')} -> {rec.get('nereye_il')}\n"
            text += f"TELEFON: {rec.get('telefon', '-')}\n"
            text += f"FİYAT: {rec.get('fiyat', '-')}\n"
            text += f"YÜK TİPİ: {self.format_type_list_to_string(rec.get('yuk_tipi'))}\n"
            text += f"--------------------------------------------------\n"
            text += f"ARAÇ-KASA KOMBİNASYONLARI ({len(rec.get('arac_kasa_kombinasyon_listesi', []))} adet):\n"
            for k in rec.get('arac_kasa_kombinasyon_listesi', []):
                text += f" • {k}\n"
            text += f"--------------------------------------------------\n"
            text += f"GÖNDERİCİ: {rec.get('message_info', {}).get('sender_name', '-')}\n"
            text += f"AÇIKLAMA: {rec.get('aciklama', '')}"
            
            detail_text.config(state='normal')
            detail_text.delete(1.0, tk.END)
            detail_text.insert(1.0, text)
            detail_text.config(state='disabled')
            
        tree.bind('<<TreeviewSelect>>', on_select)

    def show_parsed_records(self):
        """Ayrıştırılmış tüm mesajları göster"""
        panel = self.open_side_panel("📊 AYRIŞTIRMA SONUÇLARI", width=700)
        
        # Veri yükle
        parsed_data = []
        try:
            # Onaylanmamış ayrıştırılmış dosyasını oku
            if os.path.exists(self.onaylanmamis_ayristirilmis_file):
                with open(self.onaylanmamis_ayristirilmis_file, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
                    
                # KATI KURAL: Sadece son 1 SAATE ait mesajları göster
                time_threshold = datetime.now() - timedelta(hours=1)
                
                for msg in all_data:
                    msg_dt = self._get_message_datetime(msg)
                    if msg_dt and msg_dt >= time_threshold:
                        parsed_data.append(msg)
                        
        except Exception as e:
            error_msg = f"Dosya okuma hatası: {str(e)}"
            tk.Label(panel, text=error_msg, bg=self.COLORS['panel_bg'], fg='red').pack(pady=20)
            self.status_label.config(text=error_msg)
            return
        
        if not parsed_data:
            tk.Label(panel, text=f"Bugün ({today.strftime('%d.%m.%Y')}) için ayrıştırılmış mesaj bulunamadı.", 
                    bg=self.COLORS['panel_bg']).pack(pady=20)
            return
        
        # Arama ve filtre çubuğu
        search_frame = tk.Frame(panel, bg=self.COLORS['panel_bg'])
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(search_frame, text="🔍 Ara:", bg=self.COLORS['panel_bg'], font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0,5))
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, font=('Segoe UI', 9))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Üst kısım: Liste (Treeview)
        list_frame = tk.Frame(panel, bg='white')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ('durum', 'grup', 'nereden', 'nereye', 'tarih', 'sevkiyat')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        
        tree.heading('durum', text='Durum')
        tree.heading('grup', text='Grup')
        tree.heading('nereden', text='Nereden')
        tree.heading('nereye', text='Nereye')
        tree.heading('tarih', text='Tarih')
        tree.heading('sevkiyat', text='Sevkiyat')
        
        tree.column('durum', width=60, anchor='center')
        tree.column('grup', width=120)
        tree.column('nereden', width=100)
        tree.column('nereye', width=100)
        tree.column('tarih', width=90)
        tree.column('sevkiyat', width=80, anchor='center')
        
        tree_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Alt kısım: Detay Alanı
        detail_frame = tk.Frame(panel, bg=self.COLORS['panel_bg'], height=250)
        detail_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        detail_frame.pack_propagate(False)
        
        tk.Label(detail_frame, text="🔍 MESAJ DETAYLARI", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg']).pack(anchor='w', pady=(5,0))
        
        detail_text = scrolledtext.ScrolledText(detail_frame, height=12, font=('Consolas', 9), state='disabled', wrap=tk.WORD)
        detail_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Listeyi doldur
        def populate_tree(filter_text=""):
            # Mevcut öğeleri temizle
            for item in tree.get_children():
                tree.delete(item)
            
            filter_text = filter_text.lower()
            
            # En yeni mesajlar önce gösterilsin
            for i, msg in enumerate(reversed(parsed_data)):
                # Mesaj bilgileri
                msg_info = msg.get('message_info', {})
                group_name = msg_info.get('group_name', '-')
                timestamp = msg_info.get('timestamp_readable', '')
                shipments = msg.get('shipments', [])
                
                # Durum kontrolü
                if msg.get('processing_status') == 'failed':
                    durum = '❌'
                elif shipments:
                    durum = '✅'
                else:
                    durum = '⚠️'
                
                # İlk sevkiyatın bilgileri
                if shipments:
                    first_ship = shipments[0]
                    nereden = f"{first_ship.get('nereden_il', '')} {first_ship.get('nereden_ilce', '')}".strip()
                    nereye = f"{first_ship.get('nereye_il', '')} {first_ship.get('nereye_ilce', '')}".strip()
                else:
                    nereden = '-'
                    nereye = '-'
                
                tarih = timestamp.split(' ')[0] if timestamp else '-'
                sevkiyat_sayisi = str(len(shipments))
                
                # Filtre uygula
                if filter_text:
                    search_text = f"{group_name} {nereden} {nereye} {tarih}".lower()
                    if filter_text not in search_text:
                        continue
                
                # Orijinal indeksi sakla (ters çevrilmiş)
                real_index = len(parsed_data) - 1 - i
                tree.insert("", "end", values=(durum, group_name, nereden, nereye, tarih, sevkiyat_sayisi), 
                           tags=(str(real_index),))
        
        # Arama fonksiyonu
        def on_search(*args):
            populate_tree(search_var.get())
        
        search_var.trace('w', on_search)
        
        # İlk yükleme
        populate_tree()
        
        # Seçim olayı
        def on_select(event):
            selected = tree.selection()
            if not selected:
                return
            
            item = tree.item(selected[0])
            idx = int(item['tags'][0])
            msg = parsed_data[idx]
            
            # Detay oluştur
            msg_info = msg.get('message_info', {})
            shipments = msg.get('shipments', [])
            
            text = f"{'='*60}\n"
            text += f"GRUP: {msg_info.get('group_name', '-')}\n"
            text += f"GÖNDEREN: {msg_info.get('sender_name', '-')}\n"
            text += f"TARİH: {msg_info.get('timestamp_readable', '-')}\n"
            text += f"DURUM: {msg.get('processing_status', 'unknown')}\n"
            text += f"{'='*60}\n\n"
            
            # Orijinal mesaj
            text += f"📄 ORJİNAL MESAJ:\n"
            text += f"{'-'*60}\n"
            # Add sender info for verification
            sender_num = msg_info.get('sender_number') or msg_info.get('from', '')
            if sender_num:
                 # Clean up for display (remove @s.whatsapp.net)
                 sender_num = str(sender_num).split('@')[0]
                 text += f"ℹ️ Mesajı gönderen no: {sender_num}\n"
            text += f"{msg_info.get('text', '-')}\n"
            text += f"{'-'*60}\n\n"
            
            # Sevkiyatlar
            if shipments:
                text += f"📦 SEVKİYATLAR ({len(shipments)} adet):\n"
                text += f"{'='*60}\n"
                for idx_ship, ship in enumerate(shipments, 1):
                    text += f"\n▶ Sevkiyat #{idx_ship}:\n"
                    text += f"  Nereden: {ship.get('nereden_il', '')} / {ship.get('nereden_ilce', '')}\n"
                    text += f"  Nereye: {ship.get('nereye_il', '')} / {ship.get('nereye_ilce', '')}\n"
                    text += f"  Araç: {', '.join(ship.get('arac_tipi', []))}\n"
                    text += f"  Kasa: {', '.join(ship.get('kasa_tipi', []))}\n"
                    text += f"  Yük: {', '.join(ship.get('yuk_tipi', []))}\n"
                    text += f"  Fiyat: {ship.get('fiyat', '-')}\n"
                    text += f"  Telefon: {', '.join(ship.get('telefon', []))}\n"
                    text += f"  Açıklama: {ship.get('aciklama', '-')}\n"
                    text += f"  {'-'*58}\n"
            else:
                text += f"\n⚠️ Sevkiyat bilgisi bulunamadı.\n"
            
            # Hata mesajı varsa
            if msg.get('error'):
                text += f"\n❌ HATA:\n{msg.get('error')}\n"
            
            detail_text.config(state='normal')
            detail_text.delete(1.0, tk.END)
            detail_text.insert(1.0, text)
            detail_text.config(state='disabled')
        
        tree.bind('<<TreeviewSelect>>', on_select)
        
        # İstatistik etiketi
        stats_frame = tk.Frame(panel, bg=self.COLORS['panel_bg'])
        stats_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        
        success_count = sum(1 for m in parsed_data if m.get('shipments'))
        failed_count = sum(1 for m in parsed_data if m.get('processing_status') == 'failed')
        total_shipments = sum(len(m.get('shipments', [])) for m in parsed_data)
        
        stats_text = f"📊 İstatistik: {len(parsed_data)} mesaj | ✅ {success_count} başarılı | ❌ {failed_count} hatalı | 📦 {total_shipments} sevkiyat"
        tk.Label(stats_frame, text=stats_text, font=('Segoe UI', 8), bg=self.COLORS['panel_bg'], fg=self.COLORS['text_muted']).pack(anchor='w')
        
        self.status_label.config(text=f"📊 {len(parsed_data)} ayrıştırılmış mesaj yüklendi")


    # --- YARDIMCI METODLAR ---
    
    def quick_delete_message(self):
        """Onay sormadan mesajı siler ve sonrakine geçer"""
        if not self.current_message: return
        self._remove_message_by_id(self.current_message.get('id', ''), "🗑️ Mesaj hızlı silindi.")
    
    # ... (Diğer mevcut metodlar aynen korunur veya küçük revizyonlar yapılır) ...
    # Aşağıda class'ın geri kalan gerekli parçaları (helperlar, mouse wheel vb.)
    
    def on_mouse_wheel_message(self, event):
        if event.delta > 0: self.load_previous_message()
        else: self.load_next_message()
        return 'break'

    def filter_messages_in_last_minutes(self, messages, minutes, now_dt=None):
        """Return messages whose datetime is within last `minutes` minutes from now_dt.
        Includes a 2-hour 'future' buffer to handle clock drift between server and client.
        Results are sorted newest first.
        """
        now_dt = now_dt or datetime.now()
        window_start = now_dt - timedelta(minutes=int(minutes))
        # Support up to 2 hours in the future to handle clock drift/timezone issues
        window_end = now_dt + timedelta(hours=2) 
        
        filtered = []
        for msg in messages:
            dt = self._get_message_datetime(msg)
            if not dt:
                continue
            # Relaxed range: Allow slightly future messages due to server clock differences
            if dt >= window_start and dt <= window_end:
                filtered.append((dt, msg))
        
        filtered.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in filtered]

    def filter_messages_by_time(self, update_ui=True, override_minutes=None):
        """Apply sliding window filter: show messages from now()-Xmin .. now()."""
        try:
            minutes = 60
            if override_minutes is not None:
                minutes = override_minutes
            elif hasattr(self, 'minutes_filter_var'):
                try:
                    minutes = int(self.minutes_filter_var.get())
                except Exception:
                    minutes = 60
            
            # STRICT RULE: Maximum 60 minutes for UI visibility
            if minutes > 60:
                self.logger.warning(f"⚠️ Filter {minutes}m requested, but capping at strict 60m rule.")
                minutes = 60

            now_dt = datetime.now()
            self.logger.info(f"🔍 Filtering {len(self.all_messages_original)} messages with {minutes} minute window")
            
            # FIX: Mevcut mesajı kaydet
            current_msg_id = None
            if hasattr(self, 'current_message') and self.current_message:
                current_msg_id = self.current_message.get('message_id') or self.current_message.get('id')
            
            filtered = self.filter_messages_in_last_minutes(self.all_messages_original, minutes, now_dt=now_dt)
            
            self.logger.info(f"🔍 After filter: {len(filtered)} messages remain")

            self.all_messages = filtered
            
            # FIX: Mevcut mesajı bul ve index'i koru
            new_index = 0
            if current_msg_id:
                msg_id_target = str(current_msg_id)
                for i, msg in enumerate(self.all_messages):
                    this_id = str(msg.get('message_id') or msg.get('id') or '')
                    if this_id == msg_id_target:
                        new_index = i
                        break
            

            self.current_message_index = new_index
            self.current_message_index = new_index

            if not self.all_messages:
                self.logger.info(f"ℹ️ No messages in strict {minutes}m window.")
            
            if not update_ui:
                return

            if self.all_messages:
                # We have messages (either primary or fallback)
                is_fallback = len(filtered) == 0
                
                # If fallback, we usually want to jump to the first message
                # If not fallback, we try to maintain index
                idx_to_load = 0 if is_fallback else new_index
                
                self.load_message_at_index(idx_to_load)
                try:
                    self.message_counter_label.config(text=f"{idx_to_load+1}/{len(self.all_messages)}")
                except:
                    pass
                
                if is_fallback:
                    # In strict mode, fallback should practically not happen or be equivalent to the filter
                    self.status_label.config(text=f"⏱ Son {minutes} dakika: {len(self.all_messages)} mesaj", foreground="black")
                else:
                    self.status_label.config(text=f"⏱ Son {minutes} dakika: {len(self.all_messages)} mesaj", foreground="black")
                
                self.logger.info(f"✅ Displaying message {idx_to_load+1}/{len(self.all_messages)}")
            else:
                self.status_label.config(text=f"⏱ Son {minutes} dakika - mesaj yok", foreground="red")
                self.logger.warning(f"⚠️ No messages in strict {minutes}m filter window.")
        except Exception as e:
            self.logger.error(f"Filter error: {e}", exc_info=True)
            if update_ui:
                self.status_label.config(text=f"Filtre hatası: {str(e)}")
                try:
                    self.message_count_label.config(text=f"{len(self.all_messages)} mesaj")
                except:
                    pass
    
    def _get_message_datetime(self, msg):
        """Mesajın tam datetime nesnesini döndür (DataService uyumlu)"""
        try:
            # 1. Root level timestamp fields
            ts = msg.get('message_timestamp') or msg.get('timestamp') or msg.get('createdAt')
            if ts:
                try:
                    ts_val = float(ts)
                    if ts_val > 10**12: ts_val /= 1000 # Milliseconds
                    elif ts_val > 10**10: ts_val /= 1000 # Early milliseconds
                    return datetime.fromtimestamp(ts_val)
                except: pass

            # 2. Readable string fields
            for k in ['timestamp_readable', 'message_date', 'parse_timestamp']:
                val = msg.get(k) or msg.get('message_info', {}).get(k)
                if not val or not isinstance(val, str): continue
                try:
                    # ISO or space variants
                    if 'T' in val:
                        return datetime.fromisoformat(val.split('.')[0].replace('Z', '+00:00'))
                    elif ' ' in val:
                        return datetime.strptime(val.split('.')[0], "%Y-%m-%d %H:%M:%S")
                except: continue

            # 3. Nested message_info.timestamp
            mi = msg.get('message_info', {})
            if isinstance(mi, dict):
                ts = mi.get('timestamp')
                if ts:
                    try:
                        ts_val = float(ts)
                        if ts_val > 10**12: ts_val /= 1000
                        return datetime.fromtimestamp(ts_val)
                    except: pass
            
            # 4. time_str fallback
            time_str = msg.get('time_str') or msg.get('time') or mi.get('time_str') or mi.get('time')
            if time_str:
                try:
                    t = datetime.strptime(time_str.strip(), '%H:%M').time()
                    return datetime.combine(date.today(), t)
                except: pass

            return None
        except Exception as e:
            self.logger.debug(f"Date extraction failed: {e}")
            return None
    
    def _on_time_filter_manual_change(self, event=None):
        """Kullanıcı saat aralığını elle değiştirdiğinde otomatik güncellemeyi durdur"""
        if getattr(self, '_suspend_time_var_trace', False):
            return
        self.time_filter_manual_override = True
    
    def update_time_filter_to_now(self, now=None):
        """Saat aralığını tüm güne sabitle (00:00 - 23:59)."""
        if not hasattr(self, 'start_time_var') or not hasattr(self, 'end_time_var'):
            return

        self._suspend_time_var_trace = True
        self.start_time_var.set("00:00")
        self.end_time_var.set("23:59")
        self._suspend_time_var_trace = False

    def _on_minutes_filter_change(self, event=None):
        """Kullanıcı dakika filtresini değiştirdiğinde çağrılır"""
        self.time_filter_manual_override = True
        self.filter_messages_by_time()

    def reset_time_filter(self):
        # Geri yükle varsayılan dakika değeri ve otomatik moda dön
        self.time_filter_manual_override = False
        if hasattr(self, 'minutes_filter_var'):
            self.minutes_filter_var.set('60')
        # Filtresiz moda dön ve tabloyu yenile
        self.filter_messages_by_time()
    
    def _on_time_var_trace(self, *args):
        if self._suspend_time_var_trace:
            return
        self.time_filter_manual_override = True
    
    def _get_message_time(self, message_info):
        if not message_info:
            return None
        ts_str = message_info.get('timestamp_readable')
        if ts_str:
            try:
                return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S').time()
            except: pass
        msg_id = message_info.get('id')
        if msg_id and msg_id in self.unprocessed_data:
            parse_ts = self.unprocessed_data[msg_id].get('parse_timestamp')
            if parse_ts:
                try:
                    return datetime.fromisoformat(parse_ts).time()
                except: pass
        return None
    
    def _time_in_range(self, start, end, target):
        if start <= end:
            return start <= target <= end
        return target >= start or target <= end

    def _enable_mousewheel_scrolling(self, widget, target_canvas):
        def _on_mousewheel(event):
            delta = 0
            if event.delta:
                # 3x Hız çarpanı eklendi (Kullanıcı isteği: Scroll hassasiyeti)
                delta = int(-1 * (event.delta / 120)) * 3
            elif event.num == 4:
                delta = -3
            elif event.num == 5:
                delta = 3
            if delta:
                target_canvas.yview_scroll(delta, "units")
                return "break"
        def _bind_wheel(event):
            widget.bind_all("<MouseWheel>", _on_mousewheel)
            widget.bind_all("<Button-4>", _on_mousewheel)
            widget.bind_all("<Button-5>", _on_mousewheel)
        def _unbind_wheel(event):
            widget.unbind_all("<MouseWheel>")
            widget.unbind_all("<Button-4>")
            widget.unbind_all("<Button-5>")
        widget.bind("<Enter>", _bind_wheel)
        widget.bind("<Leave>", _unbind_wheel)

    def _update_side_panel_width(self, new_width):
        new_width = max(300, min(800, int(new_width)))
        self.side_panel_width = new_width
        self.side_panel.config(width=new_width)
    
    def _bind_side_panel_handle(self):
        if not self.side_panel_handle:
            return
        self.side_panel_handle.bind("<ButtonPress-1>", self._start_side_panel_resize)
        self.side_panel_handle.bind("<B1-Motion>", self._perform_side_panel_resize)
    
    def _start_side_panel_resize(self, event):
        self._side_drag_start_x = event.x_root
        self._side_initial_width = self.side_panel_width
    
    def _perform_side_panel_resize(self, event):
        if self._side_drag_start_x is None:
            return
        delta = self._side_drag_start_x - event.x_root
        new_width = self._side_initial_width - delta
        self._update_side_panel_width(new_width)

    # Diğer gerekli yükleme/kaydetme metodları (Mevcut koddan alınmıştır)
    def load_il_ilceler(self):
        try:
            with open(self.il_ilceler_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error in {self.il_ilceler_file}: {e}")
            messagebox.showerror(
                "Veri Hatası",
                f"İl/İlçe dosyası bozuk:\n{self.il_ilceler_file}\n\nProgram çalışmayabilir!"
            )
            return []
        except IOError as e:
            self.logger.error(f"IO error reading {self.il_ilceler_file}: {e}")
            messagebox.showerror(
                "Dosya Hatası",
                f"İl/İlçe dosyası okunamadı:\n{self.il_ilceler_file}"
            )
            return []
    def load_yuk_tipi(self):
        try:
            with open(self.yuk_tipi_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error in {self.yuk_tipi_file}: {e}")
            messagebox.showwarning(
                "Veri Hatası",
                f"Yük tipi dosyası bozuk:\n{self.yuk_tipi_file}\n\nBoş liste kullanılacak."
            )
            return []
        except IOError as e:
            self.logger.error(f"IO error reading {self.yuk_tipi_file}: {e}")
            return []
    def load_arac_yuk_kasa_tipleri(self):
        try:
            with open(self.arac_yuk_kasa_tipleri_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error in {self.arac_yuk_kasa_tipleri_file}: {e}")
            messagebox.showwarning(
                "Veri Hatası",
                f"Araç/Kasa tipi dosyası bozuk:\n{self.arac_yuk_kasa_tipleri_file}\n\nVarsayılan değerler kullanılacak."
            )
            return {'arac_tipleri': [], 'kasa_tipleri': [], 'yuk_tipleri': []}
        except IOError as e:
            self.logger.error(f"IO error reading {self.arac_yuk_kasa_tipleri_file}: {e}")
            return {'arac_tipleri': [], 'kasa_tipleri': [], 'yuk_tipleri': []}

    def _get_entry_date(self, item):
        """Mesaj/parse kaydından tarih bilgisini çıkar (öncelik: timestamp_readable > timestamp > parse_timestamp)."""
        try:
            mi = item.get('message_info', {}) if isinstance(item, dict) else {}

            ts_readable = mi.get('timestamp_readable')
            if ts_readable:
                for fmt in ("%Y-%m-%d %H:%M:%S", None):
                    try:
                        if fmt:
                            return datetime.strptime(ts_readable, fmt).date()
                        return datetime.fromisoformat(ts_readable.replace('Z', '+00:00')).date()
                    except Exception:
                        continue

            ts = mi.get('timestamp')
            if ts is not None:
                try:
                    if isinstance(ts, (int, float)):
                        ts_val = ts / 1000 if ts > 10**12 else ts
                        return datetime.fromtimestamp(ts_val).date()
                    if isinstance(ts, str):
                        if ts.isdigit():
                            ts_val = int(ts)
                            ts_val = ts_val / 1000 if ts_val > 10**12 else ts_val
                            return datetime.fromtimestamp(ts_val).date()
                        return datetime.fromisoformat(ts.replace('Z', '+00:00')).date()
                except Exception:
                    pass

            parse_ts = item.get('parse_timestamp')
            if parse_ts:
                try:
                    return datetime.fromisoformat(parse_ts.replace('Z', '+00:00')).date()
                except Exception:
                    pass
        except Exception:
            pass
        return None
    
    def load_unprocessed_parsed_data(self):
        """Load unprocessed parsed messages from Local Storage only (MongoDB Sync removed for performance)."""
        try:
            # Load from Local Storage only
            messages_dict = self.data_service.load_unprocessed_messages(filter_today=False)
            self.logger.info(f"Loaded {len(messages_dict)} messages from local storage.")
            return messages_dict
        except Exception as e:
            self.logger.error(f"Error loading local messages: {e}")
            return {}

    def save_unprocessed_data(self, data=None):
        """Save unprocessed data via DataService (OPTIMIZED)"""
        try:
            # Use provided data or fallback to attribute
            data_to_save = data if data is not None else getattr(self, 'unprocessed_data', None)
            
            if data_to_save is None:
                self.logger.warning("No data to save in save_unprocessed_data")
                return False

            # Use DataService for atomic save with backup
            success = self.data_service.save_unprocessed_messages(data_to_save, merge=False)
            
            if success:
                self.logger.info(f"✅ Saved {len(data_to_save)} unprocessed messages via DataService")
                return True
            else:
                messagebox.showerror(
                    "Kayıt Hatası",
                    "Veriler kaydedilemedi.\nDataService hatası."
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Unexpected error saving via DataService: {e}", exc_info=True)
            messagebox.showerror(
                "Kritik Hata",
                f"Veri kaydetme sırasında hata:\n{str(e)}"
            )
            return False

    def load_messages_from_file(self, update_ui=True):
        # 1. PRE-LOAD SHARED DATA OUTSIDE LOOP (CRITICAL PERFORMANCE FIX)
        chat_groups_map = {}
        blacklist = set()
        valid_provinces = set()
        
        try:
            # Load groups
            groups = self.data_service.load_saved_groups()
            for g in groups:
                gid = g.get('id') or g.get('chat_id')
                name = g.get('name') or g.get('title') or g.get('group_name')
                if gid and name:
                    chat_groups_map[str(gid)] = name
            
            # Load blacklist once
            blacklist_list = self.data_service.load_blacklist()
            blacklist = set(normalize_phone(str(n)) for n in blacklist_list)
            
            # Load location data once
            full_loc_data = self.location_helper.load_il_ilce_mahalle()
            for item in full_loc_data:
                prov = item.get('il')
                if prov:
                    valid_provinces.add(normalize_turkish_text(prov))
        except Exception as e:
            self.logger.error(f"Error pre-loading data for refresh: {e}")

        self.all_messages = []
        to_remove_ids = []
        
        # 2. OPTIMIZED PROCESSING LOOP
        for mid, data in self.unprocessed_data.items():
            shipments = data.get('shipments', []) or data.get('routes', [])
            
            # A. BLACKLIST FILTER (Using cached set for O(1) lookup)
            mi = data.get('message_info', {})
            sender_num = mi.get('sender_number') or mi.get('from') or mi.get('sender')
            if sender_num:
                norm_sender = normalize_phone(str(sender_num))
                if norm_sender in blacklist:
                    continue 

            # B. STRICT LOCATION FILTER (Optimization: No nested loop logic unless needed)
            if not shipments:
                 continue

            invalid_loc_reason = None
            if valid_provinces: # Only filter if we have valid data
                for s in shipments:
                    n_il = normalize_turkish_text(s.get('nereden_il', ''))
                    t_il = normalize_turkish_text(s.get('nereye_il', ''))
                    if n_il and n_il not in valid_provinces:
                        invalid_loc_reason = f"Geçersiz Kalkış İl: {n_il}"
                        break
                    if t_il and t_il not in valid_provinces:
                        invalid_loc_reason = f"Geçersiz Varış İl: {t_il}"
                        break
            
            if invalid_loc_reason:
                # DEBUG level for international/unknown locations to avoid spamming the log
                self.logger.debug(f"ℹ️ Dış Konum ({mid}): {invalid_loc_reason}")
                # Relaxed: Don't skip the message, just mark it or log it
                # continue 

            # C. ANNOTATE AND PREPARE
            chat_id = mi.get('chat_id') or mi.get('chatid') or mi.get('chat')
            chat_name = chat_groups_map.get(str(chat_id)) if chat_id else None
            
            if not chat_name:
                chat_name = mi.get('sender_name') or mi.get('from_name') or chat_id or ''

            mi['chat_name'] = chat_name
            
            # Build final message object without expensive deepcopies
            message_data = data.copy()
            message_data['message_info'] = mi.copy()
            
            m_id = message_data.get('message_id') or message_data.get('id') or mid
            message_data['message_id'] = m_id
            message_data['id'] = m_id
                
            self.all_messages.append(message_data)
        
        # Clean up any marked removals
        if to_remove_ids:
            for rid in to_remove_ids:
                if rid in self.unprocessed_data:
                    del self.unprocessed_data[rid]
            self.save_unprocessed_data()
        
        self.all_messages_original = list(self.all_messages)
        
        if update_ui:
            def sync_ui():
                try:
                    self.message_count_label.config(text=f"{len(self.all_messages)} mesaj")
                    if hasattr(self, 'update_live_panel'):
                        self.update_live_panel()
                except: pass
            
            if threading.current_thread() is not threading.main_thread():
                self.root.after(0, sync_ui)
            else:
                sync_ui()
        
        self.logger.info(f"📊 Loaded {len(self.all_messages)} messages into all_messages list")

    def load_message_at_index(self, index):
        if not self.all_messages or index < 0 or index >= len(self.all_messages): 
            return
        
        self.current_message_index = index
        self.current_message = self.all_messages[index]
        self.selected_shipments.clear()
        self.reset_active_shipment()
        
        # FIX: Support both old and new message formats
        # Get message_id (new format) or id (old format)
        msg_id = self.current_message.get('message_id') or self.current_message.get('id', '')
        
        # Orijinal Mesajı Göster
        # Try to get body from message_info or root level
        mi = self.current_message.get('message_info', {})
        body = self.current_message.get('body') or mi.get('body', '')
        
        # Show chat/group name (prefer chat_name), then sender and timestamp
        chat_name = mi.get('chat_name') or self.current_message.get('chat_name') or '?'
        sender_name = mi.get('sender') or mi.get('sender_name') or '?'
        timestamp_readable = self.current_message.get('message_date') or mi.get('timestamp_readable', '?')
        
        # Format: [GroupName] Sender | Time
        summary = f"[{chat_name}] {sender_name} | {timestamp_readable}"
        self._current_summary = summary # Toggle butonu için sakla
        
        # Update Toggle Button Text
        arrow = "▲" if getattr(self, 'is_info_panel_open', False) else "▼"
        try:
            self.info_toggle_btn.config(text=f"{summary} {arrow}")
        except: pass
        
        # Update Details Panel
        try:
            self.detail_group_label.config(text=chat_name)
            self.detail_time_label.config(text=timestamp_readable)
            self.detail_sender_label.config(text=sender_name)
            
            # Sender Number cleaning
            sender_num = mi.get('sender_number') or mi.get('from') or mi.get('sender')
            s_num = sender_num
            if s_num:
                s_num = str(s_num).split('@')[0]
            self.detail_sender_num_label.config(text=s_num or "-")
        except: pass
        
        # Sender Info for Body (Keep redundant visual info in body?)
        # User asked to move it to the panel, so maybe we don't need it in the body text anymore?
        # But keeping it in body doesn't hurt. user said "orjinal mesaj metni orda buton olsun... hepsini oraya al"
        # Let's keep the body clean or just the text.
        # Removing the header from the text body as requested ("text body just text")
        
        self.message_text.config(state='normal')
        self.message_text.delete(1.0, tk.END)
        self.message_text.insert(1.0, body) # Sadece mesaj metni
        self.message_text.config(state='disabled')
        
        # Tabloyu Doldur
        # FIX: Get routes from current message (new format) or shipments from unprocessed_data (old format)
        if 'routes' in self.current_message:
            # New format: routes are in the message itself
            self.current_shipments = self.current_message.get('routes', [])
            self.logger.info(f"📦 Loading {len(self.current_shipments)} routes from message")
        elif msg_id and msg_id in self.unprocessed_data:
            # Old format: get shipments from unprocessed_data
            self.current_shipments = self.unprocessed_data[msg_id].get('shipments', [])
            self.logger.info(f"📦 Loading {len(self.current_shipments)} shipments from unprocessed_data")
        else:
            self.current_shipments = []
            self.logger.warning(f"⚠️ No routes/shipments found for message {msg_id}")
        
        self.update_shipment_list()
        
        # CRITICAL FIX: FORCE update BOTH counter labels
        total = len(self.all_messages)
        counter_text = f"{index+1}/{total}" if total > 0 else "0/0"
        
        # Method 1: Main Label (Left Pane)
        try:
            self.message_counter_label.config(text=counter_text)
            self.message_counter_label.update_idletasks()
            # Visual debug indicator (Yellow/Green alternate)
            self.message_counter_label.config(bg='#ffeb3b' if index % 2 == 0 else '#4caf50')
        except: pass
            
        # Method 2: Secondary Label (Right Pane)
        try:
            self.message_counter_label_right.config(text=counter_text)
        except: pass

        self.logger.info(f"📊 Counter updated: {counter_text}")
        self.close_side_panel() # Mesaj değişince yan paneli kapat

    def load_next_message(self):
        if self.current_message_index < len(self.all_messages) - 1:
            self.load_message_at_index(self.current_message_index + 1)
    
    def load_previous_message(self):
        if self.current_message_index > 0:
            self.load_message_at_index(self.current_message_index - 1)
    
    # YENI: Navigation method aliases for button commands
    def prev_message(self):
        """Önceki mesaja geç (buton için)"""
        self.load_previous_message()
    
    def next_message(self):
        """Sonraki mesaja geç (buton için)"""
        self.load_next_message()
    
    def on_mouse_wheel_message(self, event):
        """Mouse wheel ile mesaj değiştir"""
        # event.delta: pozitif = yukarı scroll, negatif = aşağı scroll
        # Windows: delta = +/-120
        if event.delta > 0:
            # Yukarı scroll = önceki mesaj
            self.prev_message()
        else:
            # Aşağı scroll = sonraki mesaj
            self.next_message()
        return "break"  # Event'in başka widget'lara yayılmasını engelle

    def update_shipment_list(self):
        """Sevkiyat listesini günceller - INDEX KORUMA FIX"""
        self.updating_table = True
        
        # Mevcut seçimleri ve aktif satırı koru
        selected_indices = self.selected_shipments.copy()
        active_index = self.active_shipment_index
        
        # Tabloyu temizle
        for i in self.shipment_table.get_children():
            self.shipment_table.delete(i)

        # Sevkiyat yoksa çık
        if not self.current_shipments:
            self.record_counter_label.config(text="Kayıt: 0")
            self.updating_table = False
            return

        items = []
        for index, s in enumerate(self.current_shipments):
            nerden = f"{s.get('nereden_il', '')} {s.get('nereden_ilce', '')}"
            nereye = f"{s.get('nereye_il', '')} {s.get('nereye_ilce', '')}"
            
            cb = '☑' if index in selected_indices else '☐'
            arac_info = self.format_type_list_to_string(s.get('arac_tipi'))
            kasa_info = self.format_type_list_to_string(s.get('kasa_tipi'))
            yuk_info = self.format_type_list_to_string(s.get('yuk_tipi'))
            telefon_info = self.format_type_list_to_string(s.get('telefon'))
            
            vals = (
                cb,
                nerden,
                nereye,
                arac_info,
                kasa_info,
                yuk_info,
                s.get('fiyat', ''),
                telefon_info
                # s.get('aciklama', '') # View removed
            )
            
            tags = [f"item_{index}"]
            if index in selected_indices:
                tags.append("checked")
            
            # Zebra efekti
            if index % 2 == 0:
                tags.append("even")
            else:
                tags.append("odd")
            
            item_id = self.shipment_table.insert("", "end", values=vals, tags=tuple(tags))
            items.append(item_id)
        
        self.record_counter_label.config(text=f"Kayıt: {len(self.current_shipments)}")
        
        # Seçimleri geri yükle
        self.selected_shipments = selected_indices
        self.active_shipment_index = active_index
        self.reapply_active_row(items)
        
        self.updating_table = False

    def on_table_click(self, event):
        region = self.shipment_table.identify_region(event.x, event.y)
        if region == 'cell':
            col = self.shipment_table.identify_column(event.x)
            item = self.shipment_table.identify_row(event.y)
            if not item: return
            
            # Indexi bul
            all_items = self.shipment_table.get_children()
            idx = all_items.index(item)
            self.current_shipment_index = idx
            
            if col == '#1': # Checkbox
                if idx in self.selected_shipments:
                    self.selected_shipments.remove(idx)
                    self.shipment_table.set(item, 'checkbox', '☐')
                    tags = list(self.shipment_table.item(item, 'tags'))
                    if 'checked' in tags: tags.remove('checked')
                    self.shipment_table.item(item, tags=tags)
                else:
                    self.selected_shipments.add(idx)
                    self.shipment_table.set(item, 'checkbox', '☑')
                    tags = list(self.shipment_table.item(item, 'tags'))
                    tags.append('checked')
                    tags.append('checked')
                    self.shipment_table.item(item, tags=tags)
            else:
                # Normal hücreye tıklandığında da seçimi değiştir
                if idx in self.selected_shipments:
                    self.selected_shipments.remove(idx)
                    self.shipment_table.set(item, 'checkbox', '☐')
                    tags = list(self.shipment_table.item(item, 'tags'))
                    if 'checked' in tags: tags.remove('checked')
                    self.shipment_table.item(item, tags=tags)
                else:
                    self.selected_shipments.add(idx)
                    self.shipment_table.set(item, 'checkbox', '☑')
                    tags = list(self.shipment_table.item(item, 'tags'))
                    tags.append('checked')
                    self.shipment_table.item(item, tags=tags)
            self.set_active_shipment(idx)
            return "break"

    def on_cell_double_click(self, event):
        self.edit_selected_shipment()

    def toggle_select_all_shipments(self):
        if not self.current_shipments: return
        all_items = self.shipment_table.get_children()
        
        if len(self.selected_shipments) == len(self.current_shipments):
            self.selected_shipments.clear()
            self.shipment_table.heading('checkbox', text='☐')
            for item in all_items:
                self.shipment_table.set(item, 'checkbox', '☐')
                # Tag temizle...
        else:
            self.selected_shipments = set(range(len(self.current_shipments)))
            self.shipment_table.heading('checkbox', text='☑')
            for item in all_items:
                self.shipment_table.set(item, 'checkbox', '☑')
        
        self.update_shipment_list() # Görünümü yenile

    def reset_active_shipment(self):
        self.active_shipment_index = None
        self._remove_active_row_tag()

    def _remove_active_row_tag(self):
        if self.active_item_id and self.shipment_table.exists(self.active_item_id):
            tags = [t for t in self.shipment_table.item(self.active_item_id, 'tags') if t != 'active_row']
            self.shipment_table.item(self.active_item_id, tags=tuple(tags))
        self.active_item_id = None

    def _apply_active_row_tag(self, item_id):
        if not item_id or not self.shipment_table.exists(item_id):
            self._remove_active_row_tag()
            return
        if self.active_item_id == item_id:
            return
        self._remove_active_row_tag()
        tags = list(self.shipment_table.item(item_id, 'tags'))
        if 'active_row' not in tags:
            tags.append('active_row')
        self.shipment_table.item(item_id, tags=tuple(tags))
        self.active_item_id = item_id

    def set_active_shipment(self, index):
        if not self.current_shipments:
            self.reset_active_shipment()
            return
        index = max(0, min(index, len(self.current_shipments) - 1))
        self.active_shipment_index = index
        items = self.shipment_table.get_children()
        if index < len(items):
            self._apply_active_row_tag(items[index])
        else:
            self._remove_active_row_tag()

    def reapply_active_row(self, items=None):
        if self.active_shipment_index is None:
            self._remove_active_row_tag()
            return
        if items is None:
            items = self.shipment_table.get_children()
        if not items:
            self._remove_active_row_tag()
            return
        idx = min(self.active_shipment_index, len(items) - 1)
        self.active_shipment_index = idx
        self._apply_active_row_tag(items[idx])

    def approve_shipment(self):
        if not self.selected_shipments:
            messagebox.showwarning("Uyarı", "Onaylanacak sevkiyat seçiniz.")
            return

        # Kuyruk kontrolü
        if not hasattr(self, 'submission_queue') or self.submission_queue is None:
             messagebox.showerror("Hata", "Gönderim kuyruğu başlatılamadı!")
             return

        # UI Güncellemesi (Kısa süreliğine butonları pasif yapıyoruz, sonra hemen açacağız)
        # Saniye bazında hissedilmez, sadece double-click önlemek için.
        # self.btn_approve.config(state='disabled') # Opsiyonel, kullanıcı hızlı olmak istiyor
        
        # Seçilen kayıtları topla
        indices = sorted(self.selected_shipments, reverse=True)
        msg_id = self.current_message.get('id', '')
        
        # 1. Kayıtları hazırla ve kuyruğa ekle
        for idx in indices:
            shipment = self.current_shipments[idx]
            
            # Kombinasyon üret
            at = self.parse_type_to_list(shipment.get('arac_tipi', []))
            kt = self.parse_type_to_list(shipment.get('kasa_tipi', []))
            combos = []
            if not at and not kt: combos = ['']
            elif not at: combos = kt
            elif not kt: combos = at
            else:
                for a in at:
                    for k in kt:
                        combos.append(f"{a}-{k}")
            
            new_s = shipment.copy()
            new_s['arac_kasa_kombinasyon_listesi'] = combos
            # Message info sadeleştirilmeli
            # Id'yi ekle ki loglarda takip edelim
            new_s['message_id'] = msg_id
            new_s['onay_tarihi'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Kuyruğa ekle
            self.submission_queue.add_task(new_s)

        # 2. Seçilenleri UI'dan ve veriden kalıcı olarak sil
        # Onaylananları dosyaya kaydetmek (Onaylananlar.json)
        # DİKKAT: API sonucu beklemeden "Başarılı varsayılarak" onaylananlara ekleyelim mi?
        # Kullanıcı "sistemden çıksın" dedi. Başarısız olursa "basarisiz_gonderimler.json"a gidiyor zaten.
        # Burda onaylananlar.json'a eklemek mantıklı, çünkü bir daha gelmemeli.
        
        successful_records_assumption = [self.current_shipments[idx] for idx in indices]
        try:
            self.data_service.save_approved_records(successful_records_assumption)
            self.logger.info(f"✅ {len(successful_records_assumption)} records saved to MongoDB.")
        except Exception as e:
            self.logger.error(f"Onaylananları kaydederken hata: {e}")

        # 3. Listeden sil (Memory & UI)
        for idx in indices:
            if idx < len(self.current_shipments):
                del self.current_shipments[idx]
        
        self.selected_shipments.clear()

        # 4. Mesaj durumu güncelle (Unprocessed Data Persistence)
        if not self.current_shipments:
             self._remove_message_by_id(msg_id, "Tüm sevkiyatlar onaylandı (Kuyruğa alındı).")
        else:
             self.save_unprocessed_data()
             self.update_shipment_list()
             # self.status_label.config(text=f"✅ {len(indices)} kayıt kuyruğa eklendi.") # Kullanıcıyı yormayalım
        
        # Hızlı geri bildirim
        # Toast message gibi bir şey eklenebilir ama şu anlık basit bırakalım.
        # Kullanıcı "paralel" istiyor, yani bekleme yapma.
        pass

    # _approve_shipment_thread ve _on_approve_complete metodlarına artık ihtiyaç yok.
    # Ancak _reset_approve_ui_state temizlik için kalsın veya silebiliriz.
    def _reset_approve_ui_state(self):
        pass

    def process_auto_approvals(self):
        """Kuyruktaki tüm mesajları otomatik olarak onaylar"""
        if not self.all_messages:
            return
            
        self.logger.info(f"🤖 Otomatik onay başlatıldı: {len(self.all_messages)} mesaj taranıyor...")
        
        # O anki mesaj listesinin kopyası üzerinden git (thread safety)
        messages_to_process = list(self.all_messages)
        approved_count = 0
        
        for msg in messages_to_process:
            try:
                if self.auto_approve_message(msg):
                    approved_count += 1
            except Exception as e:
                self.logger.error(f"Otomatik onay hatası (msg_id: {msg.get('id')}): {e}")
        
        if approved_count > 0:
            self.logger.info(f"✅ Otomatik onay tamamlandı: {approved_count} mesaj onaylandı.")
            # UI'ı ana thread'de yenile
            self.root.after(0, lambda: self.refresh_messages(silent=True))

    def auto_approve_message(self, msg_data):
        """Belirli bir mesajı otomatik olarak onaylar ve kuyruğa ekler"""
        if not msg_data:
            return False
            
        msg_id = str(msg_data.get('message_id') or msg_data.get('id', ''))
        # New format supports 'routes', old format 'shipments'
        shipments = msg_data.get('routes') or msg_data.get('shipments', [])
        
        if not shipments:
            return False
            
        # Submission queue kontrolü
        if not hasattr(self, 'submission_queue') or self.submission_queue is None:
            return False

        # Onaylananları topla
        approved_shipments = []
        for shipment in shipments:
            # Kombinasyon üret (approve_shipment ile aynı mantık)
            at = self.parse_type_to_list(shipment.get('arac_tipi', []))
            kt = self.parse_type_to_list(shipment.get('kasa_tipi', []))
            combos = []
            if not at and not kt: combos = ['']
            elif not at: combos = kt
            elif not kt: combos = at
            else:
                for a in at:
                    for k in kt:
                        combos.append(f"{a}-{k}")
            
            new_s = shipment.copy()
            new_s['arac_kasa_kombinasyon_listesi'] = combos
            new_s['message_id'] = msg_id
            new_s['onay_tarihi'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Kuyruğa ekle
            self.submission_queue.add_task(new_s)
            approved_shipments.append(shipment)

        # Veritabanına kaydet (MongoDB Sync)
        if approved_shipments:
            try:
                self.data_service.save_approved_records(approved_shipments)
            except Exception as e:
                self.logger.error(f"Otomatik onay kaydı hatası (msg_id: {msg_id}): {e}")

        # Mesajı unprocessed listesinden kaldır
        self._remove_message_by_id_silent(msg_id)
        return True

    def _remove_message_by_id_silent(self, mid):
        """UI'ı bozmadan (refresh yapmadan) mesajı bellekten ve dosyadan siler"""
        mid_str = str(mid)
        
        # 1. Dosyadan ve bellekten (unprocessed_data) sil
        if mid_str in self.unprocessed_data:
            msg = self.unprocessed_data[mid_str]
            body = msg.get('body') or msg.get('text') or msg.get('orjinal_mesaj')
            if not body:
                body = msg.get('message_info', {}).get('body') or msg.get('message_info', {}).get('text')
            
            if body:
                self.data_service.mark_content_as_processed(body)

            try:
                if hasattr(self.data_service, 'delete_unprocessed_message'):
                    self.data_service.delete_unprocessed_message(mid_str)
            except Exception as e:
                self.logger.error(f"Error deleting from MongoDB: {e}")

            del self.unprocessed_data[mid_str]
            self.save_unprocessed_data()

        # 2. msg listelerinden çıkar (all_messages)
        self.all_messages = [m for m in self.all_messages if str(m.get('id', '')) != mid_str]
        self.all_messages_original = [m for m in self.all_messages_original if str(m.get('id', '')) != mid_str]

    def delete_selected_shipment(self):
        if not self.selected_shipments:
            messagebox.showwarning("Uyarı", "Silinecek sevkiyat seçiniz.")
            return
        
        indices = sorted(self.selected_shipments, reverse=True)
        for idx in indices:
            del self.current_shipments[idx]
        
        self.selected_shipments.clear()
        
        # If no shipments left in this message, remove the message explicitly
        if not self.current_shipments:
             msg_id = self.current_message.get('id')
             self._remove_message_by_id(msg_id, "Tüm sevkiyatlar silindiği için mesaj kaldırıldı.")
        else:
             self.save_unprocessed_data()
             self.update_shipment_list()

    def delete_current_message(self):
        """Normal silme (onaylı)"""
        if messagebox.askyesno("Onay", "Mesajı tamamen silmek istiyor musunuz?"):
            self._remove_message_by_id(self.current_message.get('id'), "Mesaj silindi.")

    def _remove_message_by_id(self, mid, status_msg):
        mid_str = str(mid)  # Ensure ID is string for lookup
        if mid_str in self.unprocessed_data:
            # NEW: Mark content as processed explicitly so it's not fetched again
            msg = self.unprocessed_data[mid_str]
            # Try multiple fields for body content
            body = msg.get('body') or msg.get('text') or msg.get('orjinal_mesaj')
            if not body:
                body = msg.get('message_info', {}).get('body') or msg.get('message_info', {}).get('text')
            
            if body:
                self.logger.info(f"Marking content as processed for msg {mid_str}")
                self.data_service.mark_content_as_processed(body)
            else:
                self.logger.warning(f"Could not find body for msg {mid_str} to mark as processed")

            # MongoDB Sync: Explicitly delete from central DB
            try:
                if hasattr(self.data_service, 'delete_unprocessed_message'):
                    self.data_service.delete_unprocessed_message(mid_str)
            except Exception as e:
                self.logger.error(f"Error deleting from MongoDB: {e}")

            del self.unprocessed_data[mid_str]
            self.save_unprocessed_data()
        else:
             self.logger.warning(f"Message {mid_str} not found in unprocessed_data during removal")
            
        # Listelerden çıkar
        self.all_messages = [m for m in self.all_messages if str(m.get('id', '')) != mid_str]
        self.all_messages_original = [m for m in self.all_messages_original if str(m.get('id', '')) != mid_str]
        
        self.load_message_at_index(min(self.current_message_index, len(self.all_messages)-1) if self.all_messages else 0)
        
        if not self.all_messages:
            self.message_text.config(state='normal')
            self.message_text.delete(1.0, tk.END)
            self.message_text.config(state='disabled')
            self.shipment_table.delete(*self.shipment_table.get_children())
            
        self.status_label.config(text=status_msg)
        self.message_count_label.config(text=f"{len(self.all_messages)} mesaj")

    # Helper Form Oluşturucular (UI kodunu kısaltmak için)
    def create_form_field(self, parent, label, val, form_dict, key):
        f = tk.Frame(parent, bg=self.COLORS['panel_bg'])
        f.pack(fill=tk.X, pady=5, padx=10)
        tk.Label(f, text=label, width=15, anchor='w', font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg']).pack(side=tk.LEFT)
        e = tk.Entry(f, font=self.font_normal)
        e.insert(0, str(val))
        e.pack(side=tk.LEFT, fill=tk.X, expand=True)
        form_dict[key] = e

    def create_autocomplete_field(self, parent, label, values, val, form_dict, key, depends_on=None):
        """Autocomplete field with Entry + Listbox for city/district selection"""
        f = tk.Frame(parent, bg=self.COLORS['panel_bg'])
        f.pack(fill=tk.X, pady=5, padx=10)
        tk.Label(f, text=label, width=15, anchor='w', font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg']).pack(side=tk.LEFT)

        # Container for entry, button, and listbox
        container = tk.Frame(f, bg='white', highlightthickness=1, highlightbackground='#ced4da')
        container.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Entry widget (left side)
        entry = tk.Entry(container, font=self.font_normal, bg='white', relief='flat')
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2,0), pady=2)

        # Small separator / visual divider
        sep = tk.Frame(container, width=1, bg='#e5e7eb', height=20)
        sep.pack(side=tk.RIGHT, padx=(2,0), pady=4)

        # Toggle button to open full listbox (right side)
        btn_all = tk.Button(container, text='▾', width=2, relief='flat', bg='white')
        btn_all.pack(side=tk.RIGHT, padx=2, pady=2)

        # Listbox (initially hidden)
        listbox = tk.Listbox(container, font=self.font_normal, bg='white', selectmode=tk.SINGLE,
                           height=6, relief='flat', highlightthickness=0)
        listbox.pack(fill=tk.X, padx=2, pady=2)
        listbox.pack_forget()  # Initially hidden

        # Set initial value
        if val:
            entry.insert(0, val)

        # Store references
        form_dict[key] = entry
        form_dict[f"{key}_listbox"] = listbox
        form_dict[f"{key}_values"] = values

        # If this field depends on another (e.g., ilçe depends on il), disable until dependency is set
        if depends_on:
            parent_entry = form_dict.get(depends_on)
            def update_dependency_state(event=None):
                try:
                    text = parent_entry.get().strip() if parent_entry else ''
                except Exception:
                    text = ''
                if not text:
                    # Allow typing ilçe even if il is empty; enable full ilçe list across all provinces
                    entry.config(state='normal')
                    btn_all.config(state='normal')
                else:
                    entry.config(state='normal')
                    btn_all.config(state='normal')
            def update_values_from_parent(event=None):
                """If dependency looks like an il (province), fetch ilçe list from JSON and update values/listbox.
                If parent is empty, populate with all ilçe names (unique) so user can type/select ilçe directly."""
                try:
                    parent_text = parent_entry.get().strip() if parent_entry else ''
                except Exception:
                    parent_text = ''
                if parent_text:
                    # Use helper to get ilçe list for specific il
                    vals = self.get_ilce_list(parent_text)
                else:
                    # Flatten all ilçe names (unique) so user can choose ilçe without specifying il
                    all_ilceler = []
                    for item in self.il_ilceler_data:
                        for ilce in item.get('ilçe', []):
                            if ilce not in all_ilceler:
                                all_ilceler.append(ilce)
                    vals = sorted(all_ilceler)
                form_dict[f"{key}_values"] = vals
                # update listbox contents when showing all or if currently visible
                lb = form_dict.get(f"{key}_listbox")
                if lb:
                    lb.delete(0, tk.END)
                    for v in vals[:200]:
                        lb.insert(tk.END, v)
                update_dependency_state()

            def attempt_fill_parent_from_ilce(event=None):
                """If parent (il) is empty and user typed an ilçe, try to find the unique il for that ilçe and fill parent."""
                try:
                    ilce_text = entry.get().strip()
                    if not ilce_text:
                        return
                    il_found, ilce_canonical = self.find_il_by_ilce(ilce_text)
                    if il_found and parent_entry:
                        # Set parent il to canonical il
                        parent_entry.delete(0, tk.END)
                        parent_entry.insert(0, il_found)
                        # Update ilçe canonical text
                        if ilce_canonical:
                            entry.delete(0, tk.END)
                            entry.insert(0, ilce_canonical)
                        update_values_from_parent()
                except Exception:
                    pass

            # Initial state and values
            container.after(10, lambda: (update_dependency_state(), update_values_from_parent()))
            # Bind to parent's changes
            if parent_entry:
                parent_entry.bind('<KeyRelease>', lambda e: (update_values_from_parent(), None), add='+')
            # Allow user to type ilçe when il is empty and try to resolve il on Enter or focus out
            entry.bind('<Return>', lambda e: (attempt_fill_parent_from_ilce(), 'break'))
            entry.bind('<FocusOut>', lambda e: container.after(10, attempt_fill_parent_from_ilce))


        # Flags to track listbox interaction and full-list mode
        listbox_active = False
        listbox_showing_all = False

        # Event handlers
        def on_entry_key(event):
            """Handle key presses in entry"""
            if event.keysym == 'Return':  # Enter key
                # If listbox is visible and has selection, use that
                if listbox.winfo_ismapped():
                    selection = listbox.curselection()
                    if selection:
                        selected_text = listbox.get(selection[0])
                        entry.delete(0, tk.END)
                        entry.insert(0, selected_text)
                        hide_listbox()
                        return 'break'
                # Otherwise, accept current text
                hide_listbox()
                return 'break'  # Prevent default behavior
            elif event.keysym == 'Down':  # Down arrow
                # Show listbox and select first item; move focus to listbox so arrow keys work there
                filter_listbox()
                if listbox.size() > 0:
                    listbox.selection_clear(0, tk.END)
                    listbox.selection_set(0)
                    listbox.activate(0)
                    try:
                        listbox.focus_set()
                    except Exception:
                        pass
                return 'break'
            elif event.keysym == 'Up':  # Up arrow
                # Navigate in listbox if visible
                if listbox.winfo_ismapped() and listbox.size() > 0:
                    current = listbox.curselection()
                    if current:
                        new_index = max(0, current[0] - 1)
                        listbox.selection_clear(0, tk.END)
                        listbox.selection_set(new_index)
                        listbox.activate(new_index)
                    return 'break'
            elif event.keysym == 'Escape':  # Escape key
                hide_listbox()
                return 'break'
            elif event.keysym in ('BackSpace', 'Delete'):
                # Clear any auto-selection and update listbox
                try:
                    entry.selection_clear()
                except Exception:
                    pass
                container.after(10, filter_listbox)
                return None
            elif event.char and event.char.isprintable():
                # Printable characters: if user is replacing an existing selection (from autocomplete),
                # allow the default typing to replace it and do not re-run inline autocomplete immediately.
                try:
                    _ = entry.index('sel.first')
                    # there is a selection -> let default replace it, then update listbox
                    container.after(10, filter_listbox)
                    return None
                except tk.TclError:
                    # No selection -> attempt inline autocomplete (single exact startswith match only)
                    container.after(20, lambda: (inline_autocomplete(), filter_listbox()))
                    return None
            return None

        def on_entry_focus_out(event):
            """Hide listbox when entry loses focus"""
            # Only hide if not interacting with listbox
            if not listbox_active:
                container.after(200, hide_listbox)

        def on_listbox_select(event):
            """Handle listbox selection"""
            selection = listbox.curselection()
            if selection:
                selected_text = listbox.get(selection[0])
                entry.delete(0, tk.END)
                entry.insert(0, selected_text)
                entry.selection_clear()
            hide_listbox()

        def on_listbox_key(event):
            """Handle key presses in listbox"""
            if event.keysym == 'Return':  # Enter in listbox
                on_listbox_select(None)
            elif event.keysym == 'Escape':  # Escape in listbox
                listbox_active = False
                hide_listbox()
                entry.focus_set()
            elif event.keysym == 'Up':  # Up arrow in listbox
                current = listbox.curselection()
                if current and current[0] > 0:
                    listbox.selection_clear(0, tk.END)
                    listbox.selection_set(current[0] - 1)
                    listbox.activate(current[0] - 1)
            elif event.keysym == 'Down':  # Down arrow in listbox
                current = listbox.curselection()
                if current and current[0] < listbox.size() - 1:
                    listbox.selection_clear(0, tk.END)
                    listbox.selection_set(current[0] + 1)
                    listbox.activate(current[0] + 1)

        def on_listbox_enter(event):
            """Handle mouse entering listbox"""
            nonlocal listbox_active
            listbox_active = True

        def on_listbox_leave(event):
            """Handle mouse leaving listbox"""
            nonlocal listbox_active
            listbox_active = False

        def toggle_all(event=None):
            """Toggle showing the full list (all values) and focus the listbox for navigation."""
            nonlocal listbox_showing_all
            if listbox.winfo_ismapped() and listbox_showing_all:
                hide_listbox()
                listbox_showing_all = False
                return

            # Populate listbox with all values
            listbox.delete(0, tk.END)
            for it in values:
                listbox.insert(tk.END, it)
            listbox_showing_all = True
            show_listbox()
            try:
                listbox.focus_set()
                if listbox.size() > 0:
                    listbox.selection_clear(0, tk.END)
                    listbox.selection_set(0)
                    listbox.activate(0)
            except Exception:
                pass

        # Attach toggle to button and make Alt-Down also open full list
        btn_all.config(command=toggle_all)
        entry.bind('<Alt-Down>', lambda e: (toggle_all(), 'break'))

        def filter_listbox():
            """Filter listbox items based on entry text and show dropdown"""
            from src.utils.common import normalize_turkish_text
            nonlocal listbox_showing_all
            text = entry.get().strip()
            if not text:
                hide_listbox()
                return

            # Find matching items (contains, not just starts with) - Turkish character tolerant
            current_values = form_dict.get(f"{key}_values", values)
            normalized_text = normalize_turkish_text(text)
            matches = [item for item in current_values if normalized_text in normalize_turkish_text(item)]

            if matches:
                listbox.delete(0, tk.END)
                for match in matches[:10]:  # Limit to 10 items
                    listbox.insert(tk.END, match)
                # Filtered view is not 'showing_all'
                listbox_showing_all = False
                show_listbox()
            else:
                hide_listbox()

        def inline_autocomplete():
            """Inline autocomplete only when there is exactly one startswith match.
            Keeps the appended suffix selected so user can accept with Enter or overwrite by typing.
            Trigger only when user typed at least 2 characters."""
            from src.utils.common import normalize_turkish_text
            current_text = entry.get().strip()
            # Require at least 2 characters before attempting inline autocomplete
            if len(current_text) < 2:
                return
            # Prefer startswith matches for inline completion - Turkish character tolerant
            current_values = form_dict.get(f"{key}_values", values)
            normalized_text = normalize_turkish_text(current_text)
            starts = [item for item in current_values if normalize_turkish_text(item).startswith(normalized_text)]
            # Only auto-complete when there's exactly one clear startswith candidate
            if len(starts) == 1:
                match = starts[0]
                # Don't do anything if already exactly the same
                if match.lower() == current_text.lower():
                    return
                original_len = len(current_text)
                entry.delete(0, tk.END)
                entry.insert(0, match)
                try:
                    entry.selection_range(original_len, tk.END)
                    entry.icursor(original_len)
                except Exception:
                    pass
            # If no single startswith match, do nothing (filter_listbox will handle contains matches)

        def show_listbox():
            """Show the listbox without stealing focus from the entry."""
            listbox.pack(fill=tk.X, padx=2, pady=(0, 2))
            # Do NOT call focus_set() here to avoid stealing keyboard focus from the entry.
            # Focus should only move to the listbox when the user explicitly navigates (e.g., presses Down).


        def hide_listbox():
            """Hide the listbox"""
            listbox.pack_forget()

        # Bind events
        entry.bind('<KeyRelease>', on_entry_key)
        entry.bind('<FocusOut>', on_entry_focus_out)
        listbox.bind('<ButtonRelease-1>', on_listbox_select)
        listbox.bind('<KeyRelease>', on_listbox_key)
        listbox.bind('<Enter>', on_listbox_enter)
        listbox.bind('<Leave>', on_listbox_leave)

        return entry

    def create_checkbox_field(self, parent, label, options, current, form_dict, key, callback=None):
        f = tk.Frame(parent, bg=self.COLORS['panel_bg'])
        f.pack(fill=tk.X, pady=5, padx=10)
        tk.Label(f, text=label, width=15, anchor='nw', font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg']).pack(side=tk.LEFT)
        
        cont = tk.Frame(f, bg='white', highlightthickness=1, highlightbackground='#ced4da')
        cont.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        vars = {}
        for opt in options:
            v = tk.BooleanVar(value=opt in current)
            vars[opt] = v
            cb = tk.Checkbutton(cont, text=opt, variable=v, bg='white', anchor='w')
            cb.pack(fill=tk.X, padx=2)
            if callback:
                v.trace_add('write', lambda *args, cb_key=key, cb_opt=opt, cb_callback=callback: cb_callback(cb_key, cb_opt))
        form_dict[key] = vars
        return vars


    def parse_type_to_list(self, value):
        if isinstance(value, list): return [str(v).strip() for v in value if v]
        if not value: return []
        val_str = str(value).strip()
        if '+' in val_str: return [v.strip() for v in val_str.split('+') if v.strip()]
        if ',' in val_str: return [v.strip() for v in val_str.split(',') if v.strip()]
        return [val_str]

    def format_type_list_to_string(self, value):
        l = self.parse_type_to_list(value)
        # Tekil yap (duplicateleri kaldır, sırayı koru)
        seen = set()
        unique = []
        for item in l:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return ' - '.join(unique)

    def toggle_edit_mode(self):
        if len(self.selected_shipments) > 1:
            self.edit_multiple_shipments()
        else:
            self.edit_selected_shipment()

    def sort_shipments_by_time(self):
        """Sevkiyatları zamana göre sıralar (en yeni en üstte)"""
        if not self.current_shipments:
            return

        # Mesaj zamanına göre sırala (varsa)
        msg_time = None
        if self.current_message:
            msg_time = self._get_message_time(self.current_message)

        if msg_time:
            # Mesaj zamanına göre sırala (aynı zamanda olanlar için)
            self.current_shipments.sort(key=lambda x: x.get('created_time', datetime.now().isoformat()), reverse=True)
        else:
            # Varsayılan sıralama
            self.current_shipments.sort(key=lambda x: x.get('created_time', datetime.now().isoformat()), reverse=True)

        self.update_shipment_list()

    def create_multi_destination_field(self, parent, form_entries):
        """Çoklu 'Nereye' il/ilçe seçimi için dinamik liste"""
        
        frame = tk.LabelFrame(parent, text="🎯 Nereye (Çoklu Destinasyon)", 
                              font=('Segoe UI', 9, 'bold'),
                              bg=self.COLORS['panel_bg'],
                              fg=self.COLORS['text'],
                              padx=10, pady=10)
        frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Destinasyon listesi tutucusu
        destinations = []
        form_entries['nereye_destinations'] = destinations
        
        # Liste görüntüleme alanı
        list_frame = tk.Frame(frame, bg='white', relief='solid', borderwidth=1)
        list_frame.pack(fill=tk.X, pady=(0, 10))
        
        dest_listbox = tk.Listbox(list_frame, height=4, font=self.font_small, bg='white')
        dest_listbox.pack(fill=tk.X, padx=2, pady=2)
        
        # Yeni destinasyon ekleme alanı
        add_frame = tk.Frame(frame, bg=self.COLORS['panel_bg'])
        add_frame.pack(fill=tk.X)
        
        # İl seçimi
        il_frame = tk.Frame(add_frame, bg=self.COLORS['panel_bg'])
        il_frame.pack(fill=tk.X, pady=2)
        tk.Label(il_frame, text="İl:", width=6, anchor='w', 
                 font=('Segoe UI', 9), bg=self.COLORS['panel_bg']).pack(side=tk.LEFT)
        
        il_list = sorted([item['il'] for item in self.il_ilceler_data])
        temp_entries = {}
        nereye_il_entry = self.create_autocomplete_field(
            il_frame, "", il_list, "", temp_entries, 'temp_il'
        )
        
        # İlçe seçimi
        ilce_frame = tk.Frame(add_frame, bg=self.COLORS['panel_bg'])
        ilce_frame.pack(fill=tk.X, pady=2)
        tk.Label(ilce_frame, text="İlçe:", width=6, anchor='w',
                 font=('Segoe UI', 9), bg=self.COLORS['panel_bg']).pack(side=tk.LEFT)
        
        nereye_ilce_entry = self.create_autocomplete_field(
            ilce_frame, "", [], "", temp_entries, 'temp_ilce',
            depends_on='temp_il'
        )
        
        # İl değiştiğinde ilçeleri güncelle
        def update_ilce_list(event=None):
            il = nereye_il_entry.get()
            vals = self.get_ilce_list(il)
            temp_entries['temp_ilce_values'] = vals
            lb = temp_entries.get('temp_ilce_listbox')
            if lb:
                lb.delete(0, tk.END)
                for v in vals:
                    lb.insert(tk.END, v)
        
        nereye_il_entry.bind('<KeyRelease>', update_ilce_list, add='+')
        
        # Buton frame
        btn_frame = tk.Frame(add_frame, bg=self.COLORS['panel_bg'])
        btn_frame.pack(fill=tk.X, pady=5)
        
        def add_destination():
            il = nereye_il_entry.get().strip()
            ilce = nereye_ilce_entry.get().strip()
            
            if not il or not ilce:
                messagebox.showwarning("Uyarı", "İl ve ilçe seçmelisiniz!")
                return
            
            # Normalize
            il = self._normalize_il_name(il)
            
            # Ekle
            dest_str = f"{il} / {ilce}"
            if dest_str not in [d['display'] for d in destinations]:
                destinations.append({'il': il, 'ilce': ilce, 'display': dest_str})
                dest_listbox.insert(tk.END, dest_str)
                
                # Temizle
                nereye_il_entry.delete(0, tk.END)
                nereye_ilce_entry.delete(0, tk.END)
        
        def remove_destination():
            selection = dest_listbox.curselection()
            if selection:
                idx = selection[0]
                dest_listbox.delete(idx)
                destinations.pop(idx)
        
        tk.Button(btn_frame, text="➕ Ekle", bg=self.COLORS['success'], fg='white',
                 command=add_destination, cursor='hand2', width=10).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="➖ Çıkar", bg=self.COLORS['danger'], fg='white',
                 command=remove_destination, cursor='hand2', width=10).pack(side=tk.LEFT, padx=2)

    def add_new_shipment(self):
        """Yeni sevkiyat ekleme penceresi açar"""
        if not self.current_message:
            messagebox.showwarning("Uyarı", "Önce bir mesaj seçin!")
            return

        panel = self.open_side_panel("➕ YENİ SEVKİYAT EKLE", width=450)

        # Scrollable Frame
        canvas = tk.Canvas(panel, bg=self.COLORS['panel_bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.COLORS['panel_bg'])

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=430)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5)
        scrollbar.pack(side="right", fill="y")
        self._enable_mousewheel_scrolling(scroll_frame, canvas)

        # Form
        form_entries = {}

        self.create_form_field(scroll_frame, "Firma Adı:", "", form_entries, 'isim')

        # İl/İlçe seçimleri - JSON'dan direkt al
        il_list = sorted([item['il'] for item in self.il_ilceler_data])
        nereden_il_entry = self.create_autocomplete_field(scroll_frame, "Nereden İl:", il_list, "", form_entries, 'nereden_il')

        nereden_ilce_vals = []
        nereden_ilce_entry = self.create_autocomplete_field(scroll_frame, "Nereden İlçe:", nereden_ilce_vals, "", form_entries, 'nereden_ilce', depends_on='nereden_il')

        def update_nereden(event=None):
            il = nereden_il_entry.get()
            vals = self.get_ilce_list(il)
            # Update stored values and listbox contents for the nereden_ilce field
            form_entries['nereden_ilce_values'] = vals
            lb = form_entries.get('nereden_ilce_listbox')
            if lb:
                lb.delete(0, tk.END)
                for v in vals:
                    lb.insert(tk.END, v)
            # Keep ilçe empty for "Ekle" form; user will select or type an ilçe explicitly
            nereden_ilce_entry.delete(0, tk.END)
        nereden_il_entry.bind('<KeyRelease>', update_nereden, add='+')


        nereye_il_entry = self.create_autocomplete_field(scroll_frame, "Nereye İl:", il_list, "", form_entries, 'nereye_il')
        nereye_ilce_vals = []
        nereye_ilce_entry = self.create_autocomplete_field(scroll_frame, "Nereye İlçe:", nereye_ilce_vals, "", form_entries, 'nereye_ilce', depends_on='nereye_il')

        def update_nereye(event=None):
            il = nereye_il_entry.get()
            vals = self.get_ilce_list(il)
            # Update stored values and listbox contents for the nereye_ilce field
            form_entries['nereye_ilce_values'] = vals
            lb = form_entries.get('nereye_ilce_listbox')
            if lb:
                lb.delete(0, tk.END)
                for v in vals:
                    lb.insert(tk.END, v)
            # Keep ilçe empty for "Ekle" form; user will select or type an ilçe explicitly
            nereye_ilce_entry.delete(0, tk.END)
        nereye_il_entry.bind('<KeyRelease>', update_nereye, add='+')

        # TAG SELECTORS: Araç/Kasa/Yük Tipi
        
        # Araç Tipi
        tk.Label(scroll_frame, text="Araç Tipi:", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg'], anchor='w').pack(fill=tk.X, padx=10, pady=(10, 0))
        arac_selector = TagSelector(scroll_frame, self.arac_yuk_kasa_tipleri_data.get('arac_tipleri', []), bg=self.COLORS['panel_bg'])
        arac_selector.pack(fill=tk.X, padx=10, pady=5)
        form_entries['arac_tipi'] = arac_selector
        
        # Kasa Tipi
        tk.Label(scroll_frame, text="Kasa Tipi:", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg'], anchor='w').pack(fill=tk.X, padx=10, pady=(10, 0))
        kasa_selector = TagSelector(scroll_frame, self.arac_yuk_kasa_tipleri_data.get('kasa_tipleri', []), bg=self.COLORS['panel_bg'])
        kasa_selector.pack(fill=tk.X, padx=10, pady=5)
        # Varsayılan AÇIK/KAPALI
        default_kasa = ['AÇIK', 'KAPALI'] if 'AÇIK' in self.arac_yuk_kasa_tipleri_data.get('kasa_tipleri', []) and 'KAPALI' in self.arac_yuk_kasa_tipleri_data.get('kasa_tipleri', []) else []
        kasa_selector.set_values(default_kasa)
        form_entries['kasa_tipi'] = kasa_selector
        
        # Yük Tipi
        tk.Label(scroll_frame, text="Yük Tipi:", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg'], anchor='w').pack(fill=tk.X, padx=10, pady=(10, 0))
        yuk_selector = TagSelector(scroll_frame, self.arac_yuk_kasa_tipleri_data.get('yuk_tipleri', []), bg=self.COLORS['panel_bg'])
        yuk_selector.pack(fill=tk.X, padx=10, pady=5)
        form_entries['yuk_tipi'] = yuk_selector

        self.create_form_field(scroll_frame, "Telefon:", "", form_entries, 'telefon')
        self.create_form_field(scroll_frame, "Fiyat:", "", form_entries, 'fiyat')

        # Açıklama
        lbl = tk.Label(scroll_frame, text="Açıklama:", font=('Segoe UI', 9, 'bold'), bg=self.COLORS['panel_bg'], anchor='w')
        lbl.pack(fill=tk.X, padx=10, pady=(10, 0))
        txt = tk.Text(scroll_frame, height=4, font=('Segoe UI', 9))
        txt.pack(fill=tk.X, padx=10, pady=5)
        form_entries['aciklama'] = txt

        # Kaydet Butonu
        btn_frame = tk.Frame(scroll_frame, bg=self.COLORS['panel_bg'])
        btn_frame.pack(fill=tk.X, pady=20, padx=10)

        tk.Button(btn_frame, text="💾 KAYDET", bg='#28a745', fg='white', font=('Segoe UI', 10, 'bold'),
                 command=lambda: self.save_new_shipment(form_entries), height=2).pack(fill=tk.X)

    def save_new_shipment(self, form_entries):
        """Yeni sevkiyatı kaydeder"""
        # Form verilerini topla
        new_shipment = {}

        for field_name, widget in form_entries.items():
            if isinstance(widget, tk.Text):
                new_shipment[field_name] = widget.get(1.0, tk.END).strip()
            elif isinstance(widget, tk.Listbox):
                new_shipment[field_name] = ', '.join(widget.get(0, tk.END))
            elif isinstance(widget, dict): # Checkboxlar
                new_shipment[field_name] = [k for k, v in widget.items() if v.get()]
            elif isinstance(widget, TagSelector):  # TAG SELECTOR
                new_shipment[field_name] = widget.get_values()
            elif isinstance(widget, ttk.Combobox) or isinstance(widget, tk.Entry):
                value = widget.get().strip()
                # İl alanlarını normalize et
                if field_name in ['nereden_il', 'nereye_il']:
                    value = self._normalize_il_name(value)
                # İlçe alanlarında case-insensitive olarak JSON'daki canonical değeri kullan
                if field_name in ['nereden_ilce', 'nereye_ilce']:
                    vals = form_entries.get(f"{field_name}_values", [])
                    for v in vals:
                        if v.lower() == value.lower():
                            value = v
                            break
                            
                if field_name == 'fiyat' and not value:
                    value = 'Sorunuz'
                
                # Telefon temizle (sadece rakamlar)
                elif field_name == 'telefon':
                    value = ''.join(filter(str.isdigit, value))

                new_shipment[field_name] = value

        # Temel validasyon
        if not new_shipment.get('isim') or not new_shipment.get('nereden_il') or not new_shipment.get('nereye_il'):
            messagebox.showwarning("Uyarı", "Firma adı, nereden ve nereye bilgileri zorunludur!")
            return

        # Oluşturulma zamanı ekle
        new_shipment['created_time'] = datetime.now().isoformat()

        # Mevcut sevkiyatlara ekle
        msg_id = self.current_message.get('id', '')
        if msg_id not in self.unprocessed_data:
            self.unprocessed_data[msg_id] = {
                'message_id': msg_id,
                'message_info': self.current_message,
                'shipments': []
            }

        self.unprocessed_data[msg_id]['shipments'].append(new_shipment)
        self.current_shipments = self.unprocessed_data[msg_id]['shipments']

        # Dosyaya kaydet
        self.save_unprocessed_data()

        # Listeyi güncelle ve sırala
        self.sort_shipments_by_time()
        self.update_shipment_list()

        self.status_label.config(text="✅ Yeni sevkiyat eklendi.")
        self.close_side_panel()

    def start_periodic_file_check(self):
        # YENİ: Arayüz çökme hatalarını engellemek için periyodik yerel check devre dışı bırakıldı.
        self.logger.info("Yerel periyodik file-check otomatik döngüsü devre dışı (kullanıcı manuel yenileyecek).")
        return
    
    def manual_refresh(self):
        """Manuel yenileme - kullanıcı isteğiyle mesajları günceller"""
        if getattr(self, '_is_refreshing', False):
            return
            
        self._is_refreshing = True
        self.status_label.config(text="🔄 Yenileniyor (Arka Planda)...")
        self.root.update_idletasks()
        
        # Disable refresh buttons if possible
        if hasattr(self, 'refresh_btn'):
            try: self.refresh_btn.config(state='disabled')
            except: pass
            
        # Capture values in main thread before starting background task
        minutes = 60
        if hasattr(self, 'minutes_filter_var'):
            try: minutes = int(self.minutes_filter_var.get())
            except: pass
            
        current_msg_id = None
        if hasattr(self, 'current_message') and self.current_message:
            current_msg_id = self.current_message.get('message_id') or self.current_message.get('id')
            
        import threading
        t = threading.Thread(target=self._background_refresh_task, args=(minutes, current_msg_id), daemon=True)
        t.start()
        
    def _background_refresh_task(self, minutes, current_msg_id):
        """Arka planda (Thread içinde) ağır IO işlemlerini gerçekleştirir"""
        try:
            self.refresh_messages(silent=False, from_thread=True, override_minutes=minutes, override_msg_id=current_msg_id)
        except Exception as e:
            self.logger.error(f"Background refresh error: {e}", exc_info=True)
            self.root.after(0, lambda: self.status_label.config(text=f"[❌] Yenileme hatası: {e}"))
        finally:
            self.root.after(0, self._on_refresh_done)

    def _on_refresh_done(self):
        """Yenileme bitince butonları açar"""
        self._is_refreshing = False
        if hasattr(self, 'refresh_btn'):
            try: self.refresh_btn.config(state='normal')
            except: pass

    def refresh_messages(self, silent=False, from_thread=False, override_minutes=None, override_msg_id=None):
        """Dosyaları yeniden okuyup ekrandaki mesaj listesini yenile - ROBUST INDEX PERSISTENCE"""
        if not silent and not from_thread:
            # Sadece ana thread içerisindeyse idle tasks update yapılabilir
            self.status_label.config(text="🔄 Yenileniyor...")
            self.root.update_idletasks()
        
        previous_total = len(self.all_messages_original)
        
        # 1. Capture current ID robustly
        current_message_id = override_msg_id
        if current_message_id is None and hasattr(self, 'current_message') and self.current_message:
            current_message_id = self.current_message.get('message_id') or self.current_message.get('id')
            
        if current_message_id:
            self.logger.info(f"🔄 Positioning Capture: ID={current_message_id}")
            
        try:
            # 2. Reload data from disk (HEAVY IO)
            self.unprocessed_data = self.load_unprocessed_parsed_data()
            self.load_messages_from_file(update_ui=not from_thread)
            
            # 3. Apply time filtering (this reduces all_messages)
            # Use override_minutes to avoid thread-unsafe calls to minutes_filter_var.get()
            self.filter_messages_by_time(update_ui=not from_thread, override_minutes=override_minutes)
        except Exception as e:
            self.logger.error(f"Refresh error: {e}", exc_info=True)
            if from_thread:
                self.root.after(0, lambda err=e: self.status_label.config(text=f"[❌] Yenileme hatası: {err}"))
            else:
                self.status_label.config(text=f"[❌] Yenileme hatası: {e}")
            return
            
        def _update_ui():
            total = len(self.all_messages)
            if total == 0:
                self._reset_ui_empty()
                return
            
            # 4. Restore position using the captured ID
            target_index = 0
            if current_message_id:
                msg_id_target = str(current_message_id)
                for idx, msg in enumerate(self.all_messages):
                    this_id = str(msg.get('message_id') or msg.get('id') or '')
                    if this_id == msg_id_target:
                        target_index = idx
                        self.logger.info(f"✅ Success: Found message {msg_id_target} at new index {idx}")
                        break
                else:
                    self.logger.warning(f"⚠️ Warning: Could not find message {current_message_id} in current filter view")
            
            # 5. Load the message and update counter
            if not silent:
                # Kullanıcı manuel yenilediyse ekranı yenile
                self.load_message_at_index(target_index)
            else:
                if target_index >= 0 and current_message_id:
                    # Arka plan yenilemesinde o an açik olan mesaj silinmemişse (target_index ile bulunduysa)
                    # Formu SIFIRLAMA, sadece işaretçileri koru ve counter label'ı güncelle
                    self.current_message_index = target_index
                    try:
                        self.message_counter_label.config(text=f"{target_index + 1}/{total}")
                        self.message_counter_label_right.config(text=f"{target_index + 1}/{total}")
                    except: pass
                else:
                    # Arka plandaydı ama o anki mesaj onaylanıp listeden düştüyse mecburen yenisine atla
                    self.load_message_at_index(0 if self.all_messages else -1)
            
            # Status feedback
            added = len(self.all_messages_original) - previous_total
            if added > 0:
                self.status_label.config(text=f"📨 {added} yeni mesaj yüklendi")
            else:
                self.status_label.config(text="🔄 Mesaj listesi yenilendi")

            # Update Live Panel concurrently
            if hasattr(self, 'update_live_panel'):
                self.update_live_panel()

        if from_thread:
            self.root.after(0, _update_ui)
        else:
            _update_ui()

    def _reset_ui_empty(self):
        """UI'ı boş duruma getirir (mesaj kalmadığında)"""
        self.current_message = None
        self.current_shipments = []
        self.message_text.config(state='normal')
        self.message_text.delete(1.0, tk.END)
        self.message_text.config(state='disabled')
        self.shipment_table.delete(*self.shipment_table.get_children())
        self.status_label.config(text="🗑️ İşlenecek mesaj bulunamadı")
        try:
            self.message_counter_label.config(text="0/0")
            self.message_counter_label_right.config(text="0/0")
            self.record_counter_label.config(text="Kayıt: 0")
        except: pass



    def sync_whatsapp_messages(self):
        """WhatsApp'tan mesajları manuel olarak senkronize et"""
        if not WHAPI_AVAILABLE:
            messagebox.showwarning("Uyarı", "WhatsApp API modülü yüklenemedi")
            return
        
        def do_sync():
            try:
                self.sync_button.config(state='disabled', text="⏳ SENKRONİZE\nEDİLİYOR...")
                self.sync_status_label.config(text="Çekiliyor...")
                self.root.update()
                
                # Son 3 saatin mesajlarını çek (sadece kayıtlı gruplar)
                new_count = fetch_all_messages(hours_back=3, only_saved_groups=True)
                
                if new_count > 0:
                    sync_to_queue()
                    self.sync_status_label.config(text=f"✅ {new_count} yeni mesaj")
                    self.status_label.config(text=f"📲 WhatsApp: {new_count} yeni mesaj çekildi")
                    # Mesajları yenile
                    self.refresh_messages()
                else:
                    self.sync_status_label.config(text="✅ Güncel")
                    self.status_label.config(text="📲 WhatsApp: Yeni mesaj yok")
                
            except Exception as e:
                self.sync_status_label.config(text=f"❌ Hata")
                self.status_label.config(text=f"❌ WhatsApp hatası: {str(e)[:50]}")
            finally:
                self.sync_button.config(state='normal', text="📲 WHATSAPP\nSENKRONİZE")
        
        # Arka planda çalıştır
        threading.Thread(target=do_sync, daemon=True).start()
    
    def toggle_veri_cekici(self):
        """Veri çekici servisini başlat veya durdur"""
        if self.veri_cekici_running:
            self.stop_veri_cekici()
        else:
            self.start_veri_cekici()

    def toggle_continuous_fetch(self):
        """Toggle continuous fetch+process loop (started by GUI)"""
        if not VERI_CEKICI_INTEGRATION:
            messagebox.showerror("Hata", "Collector integration not available in this environment")
            return
        if getattr(self, 'continuous_fetch_running', False):
            self.stop_continuous_fetch()
        else:
            self.start_continuous_fetch()

    def start_continuous_fetch(self, poll_interval: int = 15):
        """Start a background thread that continuously processes local files and refreshes GUI."""
        if getattr(self, 'continuous_fetch_running', False):
            # messagebox.showinfo("Bilgi", "Sürekli çekim zaten çalışıyor")
            return
        self.continuous_fetch_running = True
        try:
             self.continuous_fetch_status_label.config(text="🟢 Çalışıyor", fg='#10b981')
        except: pass
        self.status_label.config(text="✅ Yerel arayüz tetikleyicisi başlatıldı")
        self._continuous_thread = threading.Thread(target=self._continuous_fetch_loop, args=(poll_interval,), daemon=True)
        self._continuous_thread.start()

    def stop_continuous_fetch(self):
        if not getattr(self, 'continuous_fetch_running', False):
            # messagebox.showinfo("Bilgi", "Sürekli çekim zaten durmuş")
            return
        self.continuous_fetch_running = False
        try:
             self.continuous_fetch_status_label.config(text="⚪ Durdu", fg=self.COLORS['text_muted'])
        except: pass
        self.status_label.config(text="🛑 Yerel arayüz tetikleyicisi durduruldu")

    def _continuous_fetch_loop(self, poll_interval: int = 15):
        """Loop: process local queue (run_once) -> refresh GUI -> sleep"""
        logger.info('Local GUI refresh loop started (interval=%s)', poll_interval)
        try:
            while getattr(self, 'continuous_fetch_running', False):
                try:
                    if VERI_CEKICI_INTEGRATION:
                        # Artık sadece kuyruğu işleyip UI yeniliyoruz. Whapi (API) isteklerini webhook hallediyor.
                        try:
                            logger.debug('Continuous: starting local processing...')
                            # Heavy task in this thread
                            process_unprocessed_messages(keep_only_today=True, run_once=True)
                            # Trigger UI refresh safely on the main thread to respect user's time filter
                            self.root.after(0, lambda: self.refresh_messages(silent=True))

                            # Otomatik Onay Kontrolü (NEW)
                            if self.auto_approval_var.get():
                                self.process_auto_approvals()
                        except Exception as e:
                            logger.error('Continuous: local processing error: %s', e)
                    else:
                        logger.warning("Veri çekici entegrasyonu yüklenemediği için işlem yapılamadı.")
                        self.root.after(0, lambda: self.status_label.config(text="⚠️ Entegrasyon hatası"))

                except Exception as e:
                    logger.error('Continuous fetch loop error: %s', e)
                # sleep
                for _ in range(int(poll_interval)):
                    if not getattr(self, 'continuous_fetch_running', False):
                        break
                    time.sleep(1)
        finally:
            self.root.after(0, lambda: self.continuous_fetch_status_label.config(text="⚪ Durdu", fg=self.COLORS['text_muted']))
            self.root.after(0, lambda: self.status_label.config(text="🛑 Yerel arayüz tetikleyicisi durdu"))
            logger.info('Local GUI refresh loop ended')    
    def start_veri_cekici(self):
        """Veri çekici servisini başlat (Internal Thread Mode)"""
        if getattr(self, 'continuous_fetch_running', False):
             return

        self.start_continuous_fetch()
        
        # Start Webhook Server & Orchestrator Loop via centralized module
        if WEBHOOK_SERVER_AVAILABLE:
            if not hasattr(self, 'webhook_thread') or self.webhook_thread is None or not self.webhook_thread.is_alive():
                try:
                    self.logger.info("Launching Webhook Server & Orchestrator Loop...")
                    self.webhook_thread = threading.Thread(
                        target=run_server, 
                        kwargs={'port': 8080, 'use_ngrok': None},
                        daemon=True
                    )
                    self.webhook_thread.start()
                except Exception as e:
                    self.logger.error(f"Failed to start background services: {e}")
                
        # UI Güncellemesi
        self.veri_cekici_running = True
        try:
            self.veri_cekici_status_label.config(text="🟢 Çalışıyor (Oto)", fg='#10b981')
        except: pass
        self.status_label.config(text="✅ Veri çekici ve Webhook servisi başlatıldı")
    
    def stop_veri_cekici(self):
        """Veri çekici servisini durdur (Internal Thread Mode)"""
        # SUBPROCESS YERİNE INTERNAL THREAD KULLANILIYOR
        
        if not getattr(self, 'continuous_fetch_running', False) and not self.veri_cekici_running:
             messagebox.showinfo("Bilgi", "Veri çekici zaten durmuş")
             return

        self.stop_continuous_fetch()
        
        # Stop Webhook Server Thread
        try:
            from src.api.webhook_server import stop_server
            stop_server()
            self.webhook_thread = None
            
            # Windows'ta pyngrok bazen askıda ngrok.exe bırakabiliyor
            try:
                import os
                os.system("taskkill /f /im ngrok.exe >nul 2>&1")
            except:
                pass
        except Exception as e:
            self.logger.error(f"Error stopping webhook server: {e}")
            
        # UI Güncellemesi
        self.veri_cekici_running = False
        self.veri_cekici_process = None
        # self.veri_cekici_button.config(text="▶️ VERİ ÇEKİCİ\nBAŞLAT", bg='#10b981', activebackground='#059669')
        try:
            self.veri_cekici_status_label.config(text="⚪ Durdu", fg=self.COLORS['text_muted'])
        except: pass
        self.status_label.config(text="🛑 Veri çekici servisi durduruldu")
    
    def _monitor_veri_cekici(self):
        """Veri çekici process'ini izle"""
        if not self.veri_cekici_process:
            return
        
        try:
            # Process bitene kadar bekle
            self.veri_cekici_process.wait()
            
            # Process bitti
            if self.veri_cekici_running:
                # Beklenmedik şekilde kapandı
                self.veri_cekici_running = False
                self.root.after(0, lambda: self.veri_cekici_button.config(
                    text="▶️ VERİ ÇEKİCİ\nBAŞLAT", 
                    bg='#10b981', 
                    activebackground='#059669'
                ))
                self.root.after(0, lambda: self.veri_cekici_status_label.config(
                    text="🔴 Beklenmedik şekilde durdu", 
                    fg='#ef4444'
                ))
                self.root.after(0, lambda: self.status_label.config(
                    text="⚠️ Veri çekici beklenmedik şekilde durdu"
                ))
        except:
            pass
    
    # ==================== PHASE 4: VALIDATION METHODS ====================
    
    def validate_shipment_data(self, shipment_dict):
        """
        Validate shipment data using Shipment model.
        
        Args:
            shipment_dict: Dictionary with shipment data
            
        Returns:
            (is_valid, error_message) tuple
        """
        from src.utils.logging_config import log_validation_error
        
        try:
            # Create Shipment object for validation
            shipment = Shipment.from_dict(shipment_dict)
            
            # Run validation
            valid, error_msg = shipment.validate()
            
            if not valid:
                log_validation_error(
                    self.logger,
                    "Shipment",
                    error_msg,
                    shipment_dict
                )
            
            return valid, error_msg
            
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def check_duplicate_shipment(self, shipment_dict):
        """
        Check if shipment is a duplicate.
        
        Checks for duplicates based on:
        - Same phone number
        - Same origin (nereden_il)
        - Same destination (nereye_il)
        
        Args:
            shipment_dict: Dictionary with shipment data
            
        Returns:
            (is_duplicate, duplicate_info) tuple
        """
        try:
            # Load approved records
            approved = self.data_service.load_approved_records()
            
            phone = shipment_dict.get('telefon', [])
            nereden_il = shipment_dict.get('nereden_il', '')
            nereye_il = shipment_dict.get('nereye_il', '')
            
            # Check each approved record
            for existing in approved:
                existing_phone = existing.get('telefon', [])
                existing_nereden = existing.get('nereden_il', '')
                existing_nereye = existing.get('nereye_il', '')
                
                # Match if phone and route are same
                if (phone and existing_phone and 
                    set(phone) & set(existing_phone) and  # Any phone number matches
                    nereden_il == existing_nereden and
                    nereye_il == existing_nereye):
                    
                    duplicate_info = {
                        'phone': existing_phone,
                        'route': f"{existing_nereden} → {existing_nereye}",
                        'company': existing.get('isim', 'Bilinmeyen')
                    }
                    
                    self.logger.warning(f"Duplicate shipment detected: {duplicate_info}")
                    return True, duplicate_info
            
            return False, None
            
        except Exception as e:
            self.logger.error(f"Error checking duplicates: {e}", exc_info=True)
            return False, None
    
    def validate_location(self, il, ilce):
        """
        Validate il/ilce combination.
        
        Args:
            il: Province name
            ilce: District name
            
        Returns:
            True if valid combination
        """
        try:
            for province in self.il_ilceler_data:
                if province.get('il') == il:
                    return ilce in province.get('ilceler', [])
            return False
        except Exception as e:
            self.logger.error(f"Error validating location: {e}")
            return False
    
    # ==================== END VALIDATION METHODS ====================
    
    def get_submitter(self):
        """Lazily initialize and return YukBuradaSubmitter"""
        if self.submitter is None:
            try:
                from tools.submit_approved_loads import YukBuradaSubmitter
                self.submitter = YukBuradaSubmitter()
            except Exception as e:
                self.logger.error(f"Failed to initialize submitter: {e}")
                self.root.after(0, lambda: messagebox.showerror("Hata", f"YükBurada bağlantısı kurulamadı: {e}"))
        return self.submitter

    def open_live_loads_window(self):
        """Yayında olan yükleri gösteren yeni paneli/pencereyi açar"""
        if self.live_loads_window and tk.Toplevel.winfo_exists(self.live_loads_window):
            self.live_loads_window.lift()
            return

        self.live_loads_window = tk.Toplevel(self.root)
        self.live_loads_window.title("📡 YAYINDA OLAN YÜKLER - YÜKBURADA")
        self.live_loads_window.geometry("1100x700")
        self.live_loads_window.configure(bg=self.COLORS['background'])
        
        # Header
        header = tk.Frame(self.live_loads_window, bg=self.COLORS['accent'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="📡 YAYINDA OLAN YÜKLER", font=('Segoe UI', 14, 'bold'), bg=self.COLORS['accent'], fg='white').pack(side=tk.LEFT, padx=20, pady=15)
        
        # Toolbar
        toolbar = tk.Frame(self.live_loads_window, bg=self.COLORS['surface_alt'], height=50)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        
        self.live_refresh_btn = tk.Button(toolbar, text="🔄 YENİLE", bg=self.COLORS['success'], fg='white', font=('Segoe UI Semibold', 9), relief='flat', padx=15, command=self.refresh_live_loads)
        self.live_refresh_btn.pack(side=tk.LEFT, padx=10, pady=10)
        
        self.live_status_label = tk.Label(toolbar, text="Veriler güncelleniyor...", bg=self.COLORS['surface_alt'], fg=self.COLORS['text'], font=('Segoe UI', 9))
        self.live_status_label.pack(side=tk.RIGHT, padx=20)

        # Table Frame
        table_frame = tk.Frame(self.live_loads_window, bg=self.COLORS['surface'], padx=10, pady=10)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview
        columns = ("id", "nereden", "nereye", "arac", "kasa", "yuk", "firma", "tarih")
        self.live_tree = ttk.Treeview(table_frame, columns=columns, show='headings')
        
        self.live_tree.heading("id", text="ID")
        self.live_tree.heading("nereden", text="NEREDEN")
        self.live_tree.heading("nereye", text="NEREYE")
        self.live_tree.heading("arac", text="ARAÇ")
        self.live_tree.heading("kasa", text="KASA")
        self.live_tree.heading("yuk", text="YÜK")
        self.live_tree.heading("firma", text="FİRMA")
        self.live_tree.heading("tarih", text="TARİH")
        
        self.live_tree.column("id", width=50)
        self.live_tree.column("nereden", width=150)
        self.live_tree.column("nereye", width=150)
        self.live_tree.column("arac", width=100)
        self.live_tree.column("kasa", width=100)
        self.live_tree.column("yuk", width=100)
        self.live_tree.column("firma", width=150)
        self.live_tree.column("tarih", width=120)
        
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.live_tree.yview)
        self.live_tree.configure(yscroll=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.live_tree.pack(fill=tk.BOTH, expand=True)
        
        # İlk yükleme
        self.refresh_live_loads()

    # --- ALT PANEL: CANLI İZLE (SON 10 MESAJ) ---
    def setup_bottom_pane(self):
        header = tk.Frame(self.bottom_pane, bg=self.COLORS['accent'], height=30)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="🔴 CANLI İZLE (Son 50 Dakika)", font=('Segoe UI Semibold', 9, 'bold'), bg=self.COLORS['accent'], fg='white').pack(side=tk.LEFT, padx=12, pady=5)
        
        content = tk.Frame(self.bottom_pane, bg=self.COLORS['surface'])
        content.pack(fill=tk.BOTH, expand=True)
        
        columns = ("zaman", "grup", "gonderen", "icerik")
        self.live_msg_tree = ttk.Treeview(content, columns=columns, show='headings', height=6)
        
        self.live_msg_tree.heading("zaman", text="Geliş Saati")
        self.live_msg_tree.heading("grup", text="Grup")
        self.live_msg_tree.heading("gonderen", text="Kimden")
        self.live_msg_tree.heading("icerik", text="Mesaj İçeriği")
        
        self.live_msg_tree.column("zaman", width=120, anchor=tk.CENTER)
        self.live_msg_tree.column("grup", width=180)
        self.live_msg_tree.column("gonderen", width=150)
        self.live_msg_tree.column("icerik", width=700)
        
        scrollbar = ttk.Scrollbar(content, orient=tk.VERTICAL, command=self.live_msg_tree.yview)
        self.live_msg_tree.configure(yscroll=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.live_msg_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.live_msg_tree.bind('<Double-1>', self.on_live_msg_double_click)
        self.live_msg_tree.bind('<ButtonRelease-1>', self.on_live_msg_click)

    def update_live_panel(self):
        """Son 50 dakikanın mesajlarını alt panele doldurur"""
        if not hasattr(self, 'live_msg_tree') or not self.all_messages_original:
            return
            
        # Clear existing
        for item in self.live_msg_tree.get_children():
            self.live_msg_tree.delete(item)
            
        from datetime import datetime, timedelta
        
        # Son 50 DAKİKA hesapla (KULLANICI İSTEĞİ)
        time_threshold = datetime.now() - timedelta(minutes=50)
        
        # Filtreyi geçebilen tüm mesajları tut (Sınır kaldırıldı)
        filtered_msgs = []
        for msg in reversed(self.all_messages_original):
            msg_dt = self._get_message_datetime(msg)
            if msg_dt and msg_dt >= time_threshold:
                filtered_msgs.append(msg)
        
        for msg in filtered_msgs:
            mi = msg.get('message_info', {})
            zaman = msg.get('message_date') or mi.get('timestamp_readable', '-')
            grup = mi.get('chat_name') or msg.get('chat_name') or '-'
            gonderen = mi.get('sender') or mi.get('sender_name') or '-'
            body = msg.get('body') or mi.get('body', '')
            
            # İçeriği tek satıra indirge ve kısalt
            body_short = " ".join(body.split())[:120] + ("..." if len(body) > 120 else "")
            
            # Original index in all_messages_original for loading
            try:
                msg_id = msg.get('message_id') or msg.get('id')
                idx = next(i for i, m in enumerate(self.all_messages) if m.get('message_id') == msg_id or m.get('id') == msg_id)
            except StopIteration:
                idx = -1
                
            item_id = self.live_msg_tree.insert('', tk.END, values=(zaman, grup, gonderen, body_short))
            # Tag the item with index data so we know which message it refers to
            self.live_msg_tree.item(item_id, tags=(str(idx),))
            
    def on_live_msg_click(self, event):
        """Alt paneldeki bir mesaja tıklandığında (veya çift tıklandığında) ana görüntüleyiciye yükler."""
        self._handle_live_msg_selection()
        
    def on_live_msg_double_click(self, event):
        self._handle_live_msg_selection()
        
    def _handle_live_msg_selection(self):
        selection = self.live_msg_tree.selection()
        if not selection: return
        item = selection[0]
        tags = self.live_msg_tree.item(item, 'tags')
        if tags and tags[0] != '-1':
            idx = int(tags[0])
            self.load_message_at_index(idx)

    def refresh_live_loads(self):
        """API'den yayında olan yükleri çeker ve tabloyu günceller"""
        # UI updates must happen in the main thread
        try:
            self.live_refresh_btn.config(state='disabled')
            self.live_status_label.config(text="📡 Yükler çekiliyor...")
        except: pass

        def worker():
            try:
                submitter = self.get_submitter()
                if not submitter:
                    self.live_loads_window.after(0, lambda: self.live_status_label.config(text="❌ Bağlantı hatası"))
                    self.live_loads_window.after(0, lambda: self.live_refresh_btn.config(state='normal'))
                    return

                all_records = submitter.fetch_live_loads()
                
                # STRICT 1-HOUR FILTER for Live Loads from external API
                time_threshold = datetime.now() - timedelta(hours=1)
                records = []
                for r in all_records:
                    try:
                        ca = r.get('createdAt', '')
                        if ca:
                            # ISO format: 2026-03-09T12:00:00.000Z
                            dt = datetime.fromisoformat(ca.replace('Z', '+00:00'))
                            if dt.replace(tzinfo=None) >= time_threshold:
                                records.append(r)
                        else:
                            # If no timestamp, assume live and show it
                            records.append(r)
                    except:
                        records.append(r)

                self.logger.info(f"Live loads fetched: {len(all_records)} total, {len(records)} within strict 1h window.")
                
                def update_ui():
                    try:
                        for item in self.live_tree.get_children():
                            self.live_tree.delete(item)
                        
                        for row in records:
                            row_id = row.get('id', '')
                            nereden = f"{row.get('pickupCity', '')} {row.get('pickupDistrict', '')}".strip() or "?"
                            nereye = f"{row.get('deliveryCity', '')} {row.get('deliveryDistrict', '')}".strip() or "?"
                            
                            arac = row.get('vehicleType', '')
                            kasa = row.get('bodyType', '')
                            yuk = row.get('loadType', '')
                            
                            # Safe access to ownerInfo
                            owner = row.get('ownerInfo')
                            firma = 'Unknown'
                            
                            if isinstance(owner, dict):
                                # Try phone first, then full name
                                p = owner.get('phoneNumber')
                                n = owner.get('fullName')
                                
                                if p and str(p).strip():
                                    firma = str(p).strip()
                                elif n and str(n).strip():
                                    firma = str(n).strip()
                            
                            # Debug logging to file
                            if firma == 'Unknown':
                                with open('gui_dump.txt', 'a', encoding='utf-8') as f:
                                    f.write(f"Record {row_id} has Unknown firma. ownerInfo raw: {owner}\n")
                                    f.write(f"Full row keys: {list(row.keys())}\n")

                            tarih = str(row.get('createdAt', ''))[:16].replace('T', ' ')
                            
                            self.live_tree.insert('', tk.END, values=(row_id, nereden, nereye, arac, kasa, yuk, firma, tarih))
                        
                        self.live_refresh_btn.config(state='normal')
                        self.live_status_label.config(text=f"✅ {len(records)} yük bulundu")
                    except Exception as ui_err:
                        self.logger.error(f"UI update error in live loads: {ui_err}")
                        self.live_status_label.config(text="❌ Arayüz hatası")
                        self.live_refresh_btn.config(state='normal')

                self.live_loads_window.after(0, update_ui)
                
            except Exception as e:
                self.logger.error(f"Refresh live loads error: {e}")
                self.live_loads_window.after(0, lambda: self.live_status_label.config(text="❌ Hata oluştu"))
                self.live_loads_window.after(0, lambda: self.live_refresh_btn.config(state='normal'))

        threading.Thread(target=worker, daemon=True).start()

    def on_closing(self):
        """Pencere kapatılırken temizlik işlemleri"""
        try:
            # Veri çekici çalışıyorsa durdur
            if hasattr(self, 'stop_veri_cekici'):
                self.stop_veri_cekici()
            
            # Webhook sunucusunu durdur
            if WEBHOOK_SERVER_AVAILABLE:
                self.logger.info("Stopping Webhook Server...")
                stop_server()
        except Exception as e:
            self.logger.error(f"Error during closing: {e}")
        
        # Pencereyi kapat
        self.root.destroy()
    
def main():
    root = tk.Tk()
    app = LojistikYonetimGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()