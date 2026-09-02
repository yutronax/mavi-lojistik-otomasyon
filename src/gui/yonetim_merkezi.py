import sys
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import webbrowser
import urllib.parse
from datetime import datetime

# Proje kök dizinini belirle ve sys.path'e ekle
def fix_python_path():
    if getattr(sys, 'frozen', False):
        root = os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(current_dir))
    
    if root not in sys.path:
        sys.path.insert(0, root)
    return root

ROOT_DIR = fix_python_path()

# Configure logging for Yonetim Merkezi
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(ROOT_DIR, 'logs', f'TanimlamaMerkezi_{datetime.now().strftime("%Y%m%d")}.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TanimlamaMerkezi")

from src.utils.location_helper import LocationHelper
from src.services.data_service import DataService
from src.services.mongo_service import MongoDataService
from src.utils.common import get_root_path
from src.gui.components.autocomplete import AutocompleteEntry
from src.gui.components.tag_selector import TagSelector
from src.utils.text_utils import generate_keyword_variants
from src.fetchers.whapi_fetcher import setup_webhook
from src.gui.components.managers import BlacklistManager, GroupManager
from src.utils.server_manager import ServerManager
import threading

class YonetimMerkeziApp:
    def __init__(self, parent_gui=None, start_tab=None):
        self.parent_gui = parent_gui
        try:
            if parent_gui:
                self.root = tk.Toplevel(parent_gui.root)
                self.root.transient(parent_gui.root)
            else:
                self.root = tk.Tk()

            self.root.title("Mavi Lojistik - Tanımlama Merkezi")
            self.root.geometry("1200x800")
            
            # Renk Paleti
            self.COLORS = {
                'bg': '#f3f4f6',
                'nav_bg': '#ffffff',
                'active_nav': '#4f46e5',   # Canlı Mor/Mavi
                'inactive_nav': '#e5e7eb', # Soluk Gri
                'success': '#16a34a',
                'danger': '#dc2626',
                'text': '#111827',
                'surface': 'white'
            }
            
            self.root.configure(bg=self.COLORS['bg'])
            
            if not parent_gui:
                self.root.protocol("WM_DELETE_WINDOW", self.on_close)
            else:
                self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
            
            # Global Data
            root_path = get_root_path()
            self.data_dir = os.path.join(root_path, 'data')
            self.yuk_tipi_file = os.path.join(self.data_dir, 'yuk_tipi.json')
            # Initialize MongoDB Service (primary for shared data)
            try:
                self.data_service = MongoDataService()
                logger.info("Yonetim Merkezi: Using MongoDB as primary data source.")
            except Exception as e:
                logger.error(f"Yonetim Merkezi: MongoDB connection failed, falling back to local DataService: {e}")
                self.data_service = DataService(root_path)
            
            self.location_helper = LocationHelper(self.data_dir, data_service=self.data_service)
            
            # Navigation Bar
            self.setup_nav()
            
            # Load Autocomplete Data
            ak = self.data_service.load_arac_kasa_tipleri()
            self.autocomplete_data = {
                'arac': ak.get('arac_tipleri', []),
                'kasa': ak.get('kasa_tipleri', []),
                'yuk': ak.get('yuk_tipleri', [])
            }
        except Exception as e:
            logger.error(f"Initialization error: {e}", exc_info=True)
            messagebox.showerror("Başlatma Hatası", f"Uygulama başlatılamadı: {e}")
            raise
        
        # Container Frame
        self.container = tk.Frame(self.root, bg=self.COLORS['bg'])
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # Panels
        self.yuk_frame = tk.Frame(self.container, bg=self.COLORS['bg'])
        self.mahalle_frame = tk.Frame(self.container, bg=self.COLORS['bg'])
        self.group_frame = tk.Frame(self.container, bg=self.COLORS['bg'])
        self.blacklist_frame = tk.Frame(self.container, bg=self.COLORS['bg'])
        self.vps_frame = tk.Frame(self.container, bg=self.COLORS['bg'])
        self.settings_frame = tk.Frame(self.container, bg=self.COLORS['bg'])
        
        self.setup_yuk_panel()
        self.setup_mahalle_panel()
        self.setup_group_panel()
        self.setup_blacklist_panel()
        self.vps_auto_onay_var = tk.BooleanVar(value=False)
        self.setup_vps_panel()
        self.setup_settings_panel()
        
        # Default view
        if start_tab == 'group':
            self.show_group_panel()
        elif start_tab == 'blacklist':
            self.show_blacklist_panel()
        elif start_tab == 'settings':
            self.show_settings_panel()
        else:
            self.show_yuk_panel()

    def setup_nav(self):
        nav_frame = tk.Frame(self.root, bg=self.COLORS['nav_bg'], height=60)
        nav_frame.pack(fill=tk.X, side=tk.TOP)
        nav_frame.pack_propagate(False)
        
        btn_style = {"font": ("Segoe UI", 11, "bold"), "relief": "flat", "padx": 25, "cursor": "hand2"}
        
        self.btn_yuk = tk.Button(
            nav_frame, text="📦 YÜK TANIMLAMA", 
            command=self.show_yuk_panel, **btn_style
        )
        self.btn_yuk.pack(side=tk.LEFT, fill=tk.Y, padx=(20, 5), pady=5)
        
        self.btn_mahalle = tk.Button(
            nav_frame, text="📍 MAHALLE", 
            command=self.show_mahalle_panel, **btn_style
        )
        self.btn_mahalle.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        self.btn_group = tk.Button(
            nav_frame, text="📱 GRUPLAR", 
            command=self.show_group_panel, **btn_style
        )
        self.btn_group.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        self.btn_blacklist = tk.Button(
            nav_frame, text="🚫 KARA LİSTE", 
            command=self.show_blacklist_panel, **btn_style
        )
        self.btn_blacklist.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        self.btn_vps = tk.Button(
            nav_frame, text="🖥️ VPS KONTROL", 
            command=self.show_vps_panel, **btn_style
        )
        self.btn_vps.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        self.btn_settings = tk.Button(
            nav_frame, text="⚙️ SİSTEM AYARLARI", 
            command=self.show_settings_panel, **btn_style
        )
        self.btn_settings.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        tk.Label(
            nav_frame, text="Mavi Lojistik Bilgi Merkezi", 
            font=("Segoe UI", 10, "italic"), bg=self.COLORS['nav_bg'], fg="#666"
        ).pack(side=tk.RIGHT, padx=20)

    def show_yuk_panel(self):
        self.mahalle_frame.pack_forget()
        self.group_frame.pack_forget()
        self.blacklist_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.vps_frame.pack_forget()
        self.yuk_frame.pack(fill=tk.BOTH, expand=True)
        self.btn_yuk.config(bg=self.COLORS['active_nav'], fg='white')
        self.btn_mahalle.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_group.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_blacklist.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_vps.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_settings.config(bg=self.COLORS['inactive_nav'], fg='#666')

    def show_mahalle_panel(self):
        self.yuk_frame.pack_forget()
        self.group_frame.pack_forget()
        self.blacklist_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.vps_frame.pack_forget()
        self.mahalle_frame.pack(fill=tk.BOTH, expand=True)
        self.btn_mahalle.config(bg=self.COLORS['active_nav'], fg='white')
        self.btn_yuk.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_group.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_blacklist.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_vps.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_settings.config(bg=self.COLORS['inactive_nav'], fg='#666')

    def show_group_panel(self):
        self.yuk_frame.pack_forget()
        self.mahalle_frame.pack_forget()
        self.blacklist_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.vps_frame.pack_forget()
        self.group_frame.pack(fill=tk.BOTH, expand=True)
        self.btn_group.config(bg=self.COLORS['active_nav'], fg='white')
        self.btn_yuk.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_mahalle.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_blacklist.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_vps.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_settings.config(bg=self.COLORS['inactive_nav'], fg='#666')

    def show_blacklist_panel(self):
        self.yuk_frame.pack_forget()
        self.mahalle_frame.pack_forget()
        self.group_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.vps_frame.pack_forget()
        self.blacklist_frame.pack(fill=tk.BOTH, expand=True)
        self.btn_blacklist.config(bg=self.COLORS['active_nav'], fg='white')
        self.btn_yuk.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_mahalle.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_group.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_vps.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_settings.config(bg=self.COLORS['inactive_nav'], fg='#666')

    def show_groups(self):
        """Alias for show_group_panel"""
        self.show_group_panel()

    def show_blacklist(self):
        """Alias for show_blacklist_panel"""
        self.show_blacklist_panel()

    def show_vps_panel(self):
        self.yuk_frame.pack_forget()
        self.mahalle_frame.pack_forget()
        self.group_frame.pack_forget()
        self.blacklist_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.vps_frame.pack(fill=tk.BOTH, expand=True)
        self.btn_vps.config(bg=self.COLORS['active_nav'], fg='white')
        self.btn_yuk.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_mahalle.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_group.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_blacklist.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_settings.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_yuk.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_mahalle.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_group.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_blacklist.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_settings.config(bg=self.COLORS['inactive_nav'], fg='#666')

    def show_settings_panel(self):
        self.yuk_frame.pack_forget()
        self.mahalle_frame.pack_forget()
        self.group_frame.pack_forget()
        self.blacklist_frame.pack_forget()
        self.vps_frame.pack_forget()
        self.settings_frame.pack(fill=tk.BOTH, expand=True)
        self.btn_settings.config(bg=self.COLORS['active_nav'], fg='white')
        self.btn_yuk.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_mahalle.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_group.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_blacklist.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_vps.config(bg=self.COLORS['inactive_nav'], fg='#666')

    # --- YÜK TANIMLAMA PANELİ ---
    def setup_yuk_panel(self):
        # Sol Liste / Sağ Form Yapısı
        paned = tk.PanedWindow(self.yuk_frame, orient=tk.HORIZONTAL, bg=self.COLORS['bg'], sashwidth=2)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # SOL: Liste
        left_frame = tk.Frame(paned, bg='white')
        paned.add(left_frame, width=700)
        
        # Search Box
        search_f = tk.Frame(left_frame, bg='white', padx=10, pady=10)
        search_f.pack(fill=tk.X)
        tk.Label(search_f, text="🔍 Ara:", bg='white', font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.yuk_search_entry = tk.Entry(search_f, font=("Segoe UI", 10))
        self.yuk_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        def force_up(event, widget):
            from src.utils.common import normalize_turkish_text
            pos = widget.index(tk.INSERT)
            val = widget.get()
            norm = normalize_turkish_text(val)
            if val != norm:
                widget.delete(0, tk.END)
                widget.insert(0, norm)
                widget.icursor(pos)

        self.yuk_search_entry.bind('<KeyRelease>', lambda e: (force_up(e, self.yuk_search_entry), self.filter_yuk_list()), add='+')
        
        # Treeview
        columns = ('msg', 'yuk', 'arac', 'kasa', 'pri')
        self.yuk_tree = ttk.Treeview(left_frame, columns=columns, show='headings')
        self.yuk_tree.heading('msg', text='Mesaj İçeriği')
        self.yuk_tree.heading('yuk', text='Yük')
        self.yuk_tree.heading('arac', text='Araç')
        self.yuk_tree.heading('kasa', text='Kasa')
        self.yuk_tree.heading('pri', text='Öncelik')
        
        self.yuk_tree.column('msg', width=250)
        self.yuk_tree.column('yuk', width=100)
        self.yuk_tree.column('arac', width=100)
        self.yuk_tree.column('kasa', width=100)
        self.yuk_tree.column('pri', width=50)
        
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.yuk_tree.yview)
        self.yuk_tree.configure(yscrollcommand=scrollbar.set)
        
        self.yuk_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # SAĞ: Form
        right_frame = tk.Frame(paned, bg=self.COLORS['bg'], padx=15)
        paned.add(right_frame)
        
        form_title = tk.Label(right_frame, text="➕ Yeni Yük Tanımı", font=("Segoe UI", 12, "bold"), bg=self.COLORS['bg'])
        form_title.pack(pady=(0, 15), anchor=tk.W)
        
        def create_entry(parent, label):
            tk.Label(parent, text=label, bg=self.COLORS['bg'], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
            e = tk.Entry(parent, font=("Segoe UI", 11))
            e.pack(fill=tk.X, pady=(0, 10))
            
            def force_up(event, widget=e):
                from src.utils.common import normalize_turkish_text
                pos = widget.index(tk.INSERT)
                val = widget.get()
                norm = normalize_turkish_text(val)
                if val != norm:
                    widget.delete(0, tk.END)
                    widget.insert(0, norm)
                    widget.icursor(pos)
            
            e.bind('<KeyRelease>', force_up, add='+')
            return e

        self.yuk_msg_entry = create_entry(right_frame, "Orijinal Mesajdaki Kelime (Anahtar):")
        self.yuk_pri_entry = create_entry(right_frame, "Öncelik (Sayı - Örn: 1000):")
        self.yuk_pri_entry.insert(0, "1000")
        
        tk.Label(right_frame, text="Yükün Tipi:", bg=self.COLORS['bg'], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.yuk_type_selector = TagSelector(right_frame, available_values=self.autocomplete_data['yuk'], bg=self.COLORS['bg'])
        self.yuk_type_selector.pack(fill=tk.X, pady=(0, 10))

        tk.Label(right_frame, text="Araç Tipi:", bg=self.COLORS['bg'], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.yuk_arac_selector = TagSelector(right_frame, available_values=self.autocomplete_data['arac'], bg=self.COLORS['bg'])
        self.yuk_arac_selector.pack(fill=tk.X, pady=(0, 10))

        tk.Label(right_frame, text="Kasa Tipi:", bg=self.COLORS['bg'], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.yuk_kasa_selector = TagSelector(right_frame, available_values=self.autocomplete_data['kasa'], bg=self.COLORS['bg'])
        self.yuk_kasa_selector.pack(fill=tk.X, pady=(0, 10))

        self.yuk_not_entry = create_entry(right_frame, "Notlar:")
        
        # Buttons
        btn_f = tk.Frame(right_frame, bg=self.COLORS['bg'])
        btn_f.pack(fill=tk.X, pady=20)
        
        tk.Button(
            btn_f, text="💾 KAYDET", bg=self.COLORS['success'], fg='white', 
            font=("Segoe UI", 11, "bold"), height=2, command=self.save_yuk_entry
        ).pack(fill=tk.X, pady=5)
        
        tk.Button(
            btn_f, text="🗑️ SEÇİLİYİ SİL", bg=self.COLORS['danger'], fg='white',
            font=("Segoe UI", 10, "bold"), command=self.delete_yuk_entry
        ).pack(fill=tk.X, pady=5)
        
        self.refresh_yuk_list()

    def filter_yuk_list(self):
        query = self.yuk_search_entry.get().lower()
        for item in self.yuk_tree.get_children():
            self.yuk_tree.delete(item)
        
        for entry in self.all_yuk_data:
            msg = entry.get('orjinal mesajdaki', '').lower()
            if query in msg:
                self.yuk_tree.insert('', tk.END, values=(
                    entry.get('orjinal mesajdaki'),
                    entry.get('kesin_cikti', {}).get('YÜKÜN TİPİ', ''),
                    entry.get('kesin_cikti', {}).get('ARAÇ TİPİ', ''),
                    entry.get('kesin_cikti', {}).get('KASA TİPİ', ''),
                    entry.get('priority', 0)
                ))

    def refresh_yuk_list(self):
        try:
            if os.path.exists(self.yuk_tipi_file):
                with open(self.yuk_tipi_file, 'r', encoding='utf-8') as f:
                    self.all_yuk_data = json.load(f)
            else:
                self.all_yuk_data = []
        except:
            self.all_yuk_data = []
        self.filter_yuk_list()

    def save_yuk_entry(self):
        msg = self.yuk_msg_entry.get().strip()
        pri = self.yuk_pri_entry.get().strip()
        y_types = self.yuk_type_selector.get_values()
        a_types = self.yuk_arac_selector.get_values()
        k_types = self.yuk_kasa_selector.get_values()
        notlar = self.yuk_not_entry.get().strip()
        
        if not msg:
            messagebox.showwarning("Eksik", "Anahtar kelime boş olamaz!")
            return
            
        try:
            pri_int = int(pri)
        except:
            pri_int = 1000

        # 🚀 KOMBINASYON SISTEMI (Rule 1, 2, 3)
        variants = generate_keyword_variants(msg)
        
        msg_confirm = f"'{msg}' anahtarı için {len(variants)} farklı varyasyon oluşturuldu.\n\n"
        msg_confirm += ", ".join(variants[:10]) + ("..." if len(variants) > 10 else "")
        msg_confirm += "\n\nHepsini kaydetmek istiyor musunuz?"
        
        if len(variants) > 1 and not messagebox.askyesno("Kombinasyon Onayı", msg_confirm):
            variants = [msg.upper()]
        
        added_count = 0
        updated_count = 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for v in variants:
            # Find existing entry
            existing_entry = None
            for entry in self.all_yuk_data:
                if entry.get('orjinal mesajdaki', '').upper() == v:
                    existing_entry = entry
                    break
            
            if existing_entry:
                # Update existing
                existing_entry["priority"] = pri_int
                existing_entry["kesin_cikti"] = {
                    "YÜKÜN TİPİ": y_types,
                    "ARAÇ TİPİ": a_types,
                    "KASA TİPİ": k_types
                }
                existing_entry["notlar"] = notlar
                existing_entry["added_at"] = now_str # Update timestamp
                updated_count += 1
            else:
                # Add new
                new_entry = {
                    "orjinal mesajdaki": v,
                    "priority": pri_int,
                    "kesin_cikti": {
                        "YÜKÜN TİPİ": y_types,
                        "ARAÇ TİPİ": a_types,
                        "KASA TİPİ": k_types
                    },
                    "notlar": notlar,
                    "added_at": now_str
                }
                self.all_yuk_data.append(new_entry)
                added_count += 1
        
        try:
            with open(self.yuk_tipi_file, 'w', encoding='utf-8') as f:
                json.dump(self.all_yuk_data, f, ensure_ascii=False, indent=2)
            self.refresh_yuk_list()
            msg_res = ""
            if added_count > 0: msg_res += f"{added_count} yeni tanım eklendi. "
            if updated_count > 0: msg_res += f"{updated_count} mevcut tanım güncellendi."
            messagebox.showinfo("Başarılı", msg_res if msg_res else "Değişiklik yapılmadı.")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}")

    def delete_yuk_entry(self):
        sel = self.yuk_tree.selection()
        if not sel: return
        
        vals = self.yuk_tree.item(sel[0])['values']
        msg_to_del = vals[0]
        
        if messagebox.askyesno("Onay", f"'{msg_to_del}' tanımını silmek istiyor musunuz?"):
            self.all_yuk_data = [e for e in self.all_yuk_data if e.get('orjinal mesajdaki') != msg_to_del]
            with open(self.yuk_tipi_file, 'w', encoding='utf-8') as f:
                json.dump(self.all_yuk_data, f, ensure_ascii=False, indent=2)
            self.refresh_yuk_list()

    # --- MAHALLE TANIMLAMA PANELİ ---
    def setup_mahalle_panel(self):
        # Sol Liste / Sağ Form Yapısı
        paned = tk.PanedWindow(self.mahalle_frame, orient=tk.HORIZONTAL, bg=self.COLORS['bg'], sashwidth=2)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # SOL: Liste
        left_f = tk.Frame(paned, bg='white')
        paned.add(left_f, width=600)
        
        cols = ('yer', 'il', 'ilce', 'not')
        self.loc_tree = ttk.Treeview(left_f, columns=cols, show='headings')
        self.loc_tree.heading('yer', text='Yer/Mahalle')
        self.loc_tree.heading('il', text='İl')
        self.loc_tree.heading('ilce', text='İlçe')
        self.loc_tree.heading('not', text='Not')
        
        self.loc_tree.column('yer', width=150)
        self.loc_tree.column('il', width=100)
        self.loc_tree.column('ilce', width=120)
        
        scroll = ttk.Scrollbar(left_f, orient="vertical", command=self.loc_tree.yview)
        self.loc_tree.configure(yscrollcommand=scroll.set)
        self.loc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # SAĞ: Form & Arama
        right_f = tk.Frame(paned, bg=self.COLORS['bg'], padx=15)
        paned.add(right_f)
        
        # Manual Entry Section
        m_f = tk.LabelFrame(right_f, text="✍️ Yeni Mahalle Ekle", bg=self.COLORS['bg'], font=("Segoe UI", 10, "bold"), padx=10, pady=10)
        m_f.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(m_f, text="Mahalle / Yer Adı:", bg=self.COLORS['bg']).pack(anchor=tk.W)
        self.m_yer_entry = tk.Entry(m_f, font=("Segoe UI", 11))
        self.m_yer_entry.pack(fill=tk.X, pady=(0, 5))
        
        def force_up(event, widget=self.m_yer_entry):
            from src.utils.common import normalize_turkish_text
            pos = widget.index(tk.INSERT)
            val = widget.get()
            norm = normalize_turkish_text(val)
            if val != norm:
                pos_before = widget.index(tk.INSERT)
                widget.delete(0, tk.END)
                widget.insert(0, norm)
                widget.icursor(pos)

        self.m_yer_entry.bind('<KeyRelease>', lambda e: force_up(e), add='+')
        self.m_yer_entry.bind('<FocusOut>', lambda e: self.auto_detect_location())
        self.m_yer_entry.bind('<Return>', lambda e: self.auto_detect_location())
        
        # AI Button
        self.btn_ai = tk.Button(m_f, text="🧠 AKILLI BUL (AI)", bg='#6366f1', fg='white', font=("Segoe UI", 9, "bold"), command=self.ask_ai_loc)
        self.btn_ai.pack(fill=tk.X, pady=(0, 15))
        
        # İl / İlçe
        tk.Label(m_f, text="İl:", bg=self.COLORS['bg']).pack(anchor=tk.W)
        self.m_il_combo = AutocompleteEntry(m_f, completevalues=[], font=("Segoe UI", 11))
        self.m_il_combo.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(m_f, text="İlçe:", bg=self.COLORS['bg']).pack(anchor=tk.W)
        self.m_ilce_combo = AutocompleteEntry(m_f, completevalues=[], font=("Segoe UI", 11))
        self.m_ilce_combo.pack(fill=tk.X, pady=(0, 10))
        
        # Fill İl list
        il_data = self.data_service.load_il_ilceler()
        iller = sorted([i['il'] for i in il_data])
        self.m_il_combo.completevalues = iller
        self.m_il_combo.config(values=iller)
        self.m_il_combo.bind("<<ComboboxSelected>>", self.on_il_select)
        
        tk.Label(m_f, text="Mevcut Mahalleler:", bg=self.COLORS['bg'], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(10, 0))
        
        # Frame for Listbox and Scrollbar
        list_f = tk.Frame(m_f, bg=self.COLORS['bg'])
        list_f.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.m_existing_list = tk.Listbox(list_f, font=("Segoe UI", 10), height=8)
        list_scroll = ttk.Scrollbar(list_f, orient="vertical", command=self.m_existing_list.yview)
        self.m_existing_list.configure(yscrollcommand=list_scroll.set)
        
        self.m_existing_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.m_ilce_combo.bind("<<ComboboxSelected>>", self.on_ilce_select)
        self.m_ilce_combo.bind("<Return>", lambda e: self.on_ilce_select(e))

        # Action Buttons
        btn_f = tk.Frame(m_f, bg=self.COLORS['bg'])
        btn_f.pack(fill=tk.X, pady=10)
        
        tk.Button(btn_f, text="🚀 VERİTABANINA EKLE", bg=self.COLORS['success'], fg='white', font=("Segoe UI", 11, "bold"), height=2, command=self.save_mahalle).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(btn_f, text="🗑️ SEÇİLİ MAHALLEYİ SİL", bg=self.COLORS['danger'], fg='white', font=("Segoe UI", 9), command=self.delete_existing_mahalle).pack(side=tk.RIGHT, padx=5)
        
        self.refresh_loc_list()

    def on_il_select(self, event):
        il = self.m_il_combo.get()
        il_data = self.data_service.load_il_ilceler()
        for item in il_data:
            if item.get('il', '').upper() == il.upper():
                ilceler = item.get('ilçe', [])
                self.m_ilce_combo.set("")
                self.m_ilce_combo.completevalues = ilceler
                self.m_ilce_combo.config(values=ilceler)
                self.m_existing_list.delete(0, tk.END)
                break

    def on_ilce_select(self, event=None):
        il = self.m_il_combo.get().strip().upper()
        ilce = self.m_ilce_combo.get().strip().upper()
        if not il or not ilce: return
        
        self.m_existing_list.delete(0, tk.END)
        
        # Load from main DB via LocationHelper
        full_data = self.location_helper.load_il_ilce_mahalle()
        for il_item in full_data:
            if il_item.get('il', '').upper() == il:
                for ilce_item in il_item.get('ilceler', []):
                    if ilce_item.get('ilce', '').upper() == ilce:
                        mahalleler = sorted(ilce_item.get('mahalleler', []))
                        for m in mahalleler:
                            self.m_existing_list.insert(tk.END, m)
                        return

    def refresh_loc_list(self):
        for item in self.loc_tree.get_children():
            self.loc_tree.delete(item)
        locations = self.location_helper.get_all_custom_locations()
        for loc in reversed(locations):
            self.loc_tree.insert('', tk.END, values=(loc.get('yer_adi'), loc.get('il'), loc.get('ilce'), loc.get('aciklama')))

    def save_mahalle(self):
        yer = self.m_yer_entry.get().strip().upper()
        il = self.m_il_combo.get().strip().upper()
        ilce = self.m_ilce_combo.get().strip()
        
        if not yer or not il or not ilce:
            messagebox.showwarning("Eksik", "Tüm alanları doldurun!")
            return
            
        if self.location_helper.add_mahalle_to_main_db(il, ilce, yer):
            self.location_helper.add_custom_location(yer, il, ilce, "Yönetim Merkezi")
            self.refresh_loc_list()
            self.on_ilce_select() # Refresh existing list
            self.m_yer_entry.delete(0, tk.END)
            messagebox.showinfo("Tamam", "Mahalle eklendi.")
        else:
            messagebox.showerror("Hata", "Mahalle eklenemedi!")

    def delete_existing_mahalle(self):
        sel_idx = self.m_existing_list.curselection()
        if not sel_idx:
            messagebox.showwarning("Seçim Yok", "Silinecek mahalleyi listeden seçin!")
            return
            
        mahalle = self.m_existing_list.get(sel_idx[0])
        il = self.m_il_combo.get().strip().upper()
        ilce = self.m_ilce_combo.get().strip().upper()
        
        if messagebox.askyesno("Onay", f"'{mahalle}' mahallesini ANA VERİTABANINDAN silmek istediğinize emin misiniz?"):
            full_data = self.location_helper.load_il_ilce_mahalle()
            for il_item in full_data:
                if il_item.get('il', '').upper() == il:
                    for ilce_item in il_item.get('ilceler', []):
                        if ilce_item.get('ilce', '').upper() == ilce:
                            m_list = ilce_item.get('mahalleler', [])
                            if mahalle in m_list:
                                m_list.remove(mahalle)
                                # Save back to MongoDB & Local
                                if self.data_service and hasattr(self.data_service, 'save_config'):
                                    self.data_service.save_config('il_ilce_mahalle', full_data)
                                
                                # Local backup
                                with open(self.location_helper.il_ilce_mahalle_file, 'w', encoding='utf-8') as f:
                                    json.dump(full_data, f, ensure_ascii=False, indent=2)
                                
                                self.on_ilce_select()
                                messagebox.showinfo("Tamam", "Mahalle silindi.")
                                return

    def delete_mahalle(self):
        sel = self.loc_tree.selection()
        if not sel: return
        vals = self.loc_tree.item(sel[0])['values']
        if messagebox.askyesno("Onay", f"'{vals[0]}' silinsin mi?"):
            if self.location_helper.delete_custom_location(vals[0], vals[1], vals[2]):
                self.refresh_loc_list()

    def auto_detect_location(self):
        """Yer adı girildiğinde veritabanında varsa otomatik doldurur"""
        yer = self.m_yer_entry.get().strip()
        if len(yer) < 2: return
        
        res = self.location_helper.search_location(yer)
        if res:
            il, ilce = res
            self.m_il_combo.set(il.upper())
            self.on_il_select(None)
            self.m_ilce_combo.set(ilce)
            # Opsiyonel: Statü çubuğu veya görsel bildirim eklenebilir
            # print(f"Bulundu: {il} / {ilce}")

    def ask_ai_loc(self):
        yer = self.m_yer_entry.get().strip()
        if not yer: 
            messagebox.showwarning("Uyarı", "Lütfen bir yer adı girin!")
            return
            
        try:
            self.btn_ai.config(text="⌛ Soruluyor...", state='disabled')
            self.root.update()
            
            from src.utils.gemini_client import GeminiClient
            client = GeminiClient()
            
            if not client.client:
                messagebox.showerror("Hata", "Yapay Zeka (Gemini) başlatılamadı.\nLütfen API Anahtarınızı kontrol edin.")
                return

            prompt = f"'{yer}' neresidir? Sadece Türkiye'deki IL ve ILCE bilgisini ver. Format: IL: ..., ILCE: ... (Bilinmiyorsa veya Türkiye dışındaysa BILINMIYOR yaz)"
            response = client.generate_text_only(prompt)
            
            if not response or "BILINMIYOR" in response.upper():
                messagebox.showinfo("Sonuç", f"'{yer}' için bir sonuç bulunamadı.")
                return

            import re
            # Daha esnek regex (Bazı modeller IL: yerine Şehir: vb. diyebiliyor veya boşluk bırakmayabiliyor)
            il_m = re.search(r'(?:IL|SEHIR|ŞEHİR):\s*([^,\n\.\(\)]+)', response, re.IGNORECASE)
            ilce_m = re.search(r'(?:ILCE|İLÇE|İLCESİ|İLÇESİ):\s*([^,\n\.\(\)]+)', response, re.IGNORECASE)
            
            if il_m and ilce_m:
                ai_il = il_m.group(1).strip().upper()
                ai_ilce = ilce_m.group(1).strip().upper()
                
                # İller listesinden en yakın eşleşmeyi bul (ASCII/Türkçe karakter farklarını aşmak için)
                from src.utils.common import normalize_turkish_text
                norm_ai_il = normalize_turkish_text(ai_il)
                
                il_data = self.data_service.load_il_ilceler()
                exact_il = None
                for item in il_data:
                    current_il = item['il']
                    if current_il == ai_il or normalize_turkish_text(current_il) == norm_ai_il:
                        exact_il = current_il
                        break
                
                if exact_il:
                    self.m_il_combo.set(exact_il)
                    self.on_il_select(None)
                    
                    # İlçeler listesinden eşleşme bul
                    ilceler = self.m_ilce_combo['values']
                    norm_ai_ilce = normalize_turkish_text(ai_ilce)
                    exact_ilce = None
                    for c in ilceler:
                        if c.upper() == ai_ilce or normalize_turkish_text(c) == norm_ai_ilce:
                            exact_ilce = c
                            break
                    
                    if exact_ilce:
                        self.m_ilce_combo.set(exact_ilce)
                        messagebox.showinfo("Başarılı", f"Yapay zeka tespiti:\n\nİl: {exact_il}\nİlçe: {exact_ilce}")
                    else:
                        # İlçe listesinde yoksa AI'dan geleni yaz (yine de yardımcı olur)
                        self.m_ilce_combo.set(ai_ilce.title())
                        messagebox.showinfo("Kısmi Sonuç", f"İl bulundu: {exact_il}\nİlçe (Listede yok ama AI): {ai_ilce.title()}")
                else:
                    messagebox.showwarning("Belirsiz", f"AI '{ai_il}' dedi ancak bu il listemizde yok.\n\nTam Yanıt: {response}")
            else:
                messagebox.showwarning("Yanıt Anlaşılamadı", f"AI yanıtı beklenen formatta değil:\n\n{response}")
                
        except Exception as e:
            messagebox.showerror("Hata", f"Yapay zeka sorgusu sırasında bir hata oluştu:\n{e}")
        finally:
            self.btn_ai.config(text="🧠 AKILLI BUL (AI)", state='normal')

    def setup_group_panel(self):
        # Initialize GroupManager with the group_frame as container
        self.group_manager = GroupManager(self, container=self.group_frame)
        self.group_manager.open_group_management()

    def setup_blacklist_panel(self):
        # Initialize BlacklistManager with the blacklist_frame as container
        self.blacklist_manager = BlacklistManager(self, container=self.blacklist_frame)
        self.blacklist_manager.open_window()

    def setup_settings_panel(self):
        main_f = tk.Frame(self.settings_frame, bg=self.COLORS['bg'], padx=40, pady=40)
        main_f.pack(fill=tk.BOTH, expand=True)
        
        title = tk.Label(main_f, text="⚙️ Sistem ve Bakım Ayarları", font=("Segoe UI", 16, "bold"), bg=self.COLORS['bg'])
        title.pack(anchor=tk.W, pady=(0, 30))
        
        # Reset Section
        reset_f = tk.LabelFrame(main_f, text="⚡ Veri Temizliği", font=("Segoe UI", 11, "bold"), bg='white', padx=20, pady=20)
        reset_f.pack(fill=tk.X)
        
        tk.Label(
            reset_f, 
            text="Bu işlem; son 2 saat dışındaki TÜM ham mesajları, ayrıştırılmış verileri ve işlem loglarını kalıcı olarak siler.\nOnayladığınız kayıtlar (onaylanan_kayitlar.json) bu işlemden ETKİLENMEZ.",
            bg='white', justify=tk.LEFT, font=("Segoe UI", 10)
        ).pack(anchor=tk.W, pady=(0, 15))
        
        tk.Button(
            reset_f, text="💥 SİSTEMİ SIFIRLA (Son 2 Saat Hariç)", 
            bg=self.COLORS['danger'], fg='white', font=("Segoe UI", 10, "bold"),
            padx=20, pady=10, command=self.trigger_hard_reset
        ).pack(anchor=tk.W)

        # Webhook Section
        webhook_f = tk.LabelFrame(main_f, text="🔌 Tetikleyici (Webhook) Ayarları", font=("Segoe UI", 11, "bold"), bg='white', padx=20, pady=20)
        webhook_f.pack(fill=tk.X, pady=(30, 0))
        
        tk.Label(
            webhook_f, 
            text="Mesajların saniyesinde gelmesi için Webhook URL'nizi (ngrok vb.) buraya girin.\nBu işlem Whapi hesabınızın güvenlik puanını artırır.",
            bg='white', justify=tk.LEFT, font=("Segoe UI", 10)
        ).pack(anchor=tk.W, pady=(0, 10))
        
        url_frame = tk.Frame(webhook_f, bg='white')
        url_frame.pack(fill=tk.X)
        
        self.webhook_url_entry = tk.Entry(url_frame, font=("Segoe UI", 11), width=50)
        self.webhook_url_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.webhook_url_entry.insert(0, "https://")
        
        tk.Button(
            url_frame, text="✅ AYARLARI UYGULA", 
            bg=self.COLORS['active_nav'], fg='white', font=("Segoe UI", 9, "bold"),
            padx=15, command=self.trigger_webhook_setup
        ).pack(side=tk.LEFT)

    def show_settings_panel(self):
        self.yuk_frame.pack_forget()
        self.mahalle_frame.pack_forget()
        self.group_frame.pack_forget()
        self.blacklist_frame.pack_forget()
        self.vps_frame.pack_forget()
        self.settings_frame.pack(fill=tk.BOTH, expand=True)
        self.btn_settings.config(bg=self.COLORS['active_nav'], fg='white')
        self.btn_yuk.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_mahalle.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_group.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_blacklist.config(bg=self.COLORS['inactive_nav'], fg='#666')
        self.btn_vps.config(bg=self.COLORS['inactive_nav'], fg='#666')

    def trigger_webhook_setup(self):
        url = self.webhook_url_entry.get().strip()
        if not url or url == "https://":
            messagebox.showwarning("Geçersiz URL", "Lütfen geçerli bir Webhook URL'si girin.")
            return
            
        if messagebox.askyesno("Onay", f"Webhook URL'si olarak şu adres ayarlanacak:\n{url}\n\nEmin misiniz?"):
            success = setup_webhook(url)
            if success:
                messagebox.showinfo("Başarılı", "Webhook ayarları Whapi tarafında başarıyla güncellendi!\nArtık mesajlar anında tetiklenecektir.")
            else:
                messagebox.showerror("Hata", "Webhook ayarları güncellenemedi. Token veya bağlantı hatası oluşmuş olabilir.")

    def trigger_hard_reset(self):
        if not messagebox.askyesno("⚠ SİSTEMİ SIFIRLA", "Son 2 saat dışındaki tüm veriler ve loglar kalıcı olarak silinecektir.\n\nEmin misiniz?"):
            return
            
        try:
            res = self.data_service.manual_reset_history(hours_back=2.0)
            
            summary = "Sıfırlama Tamamlandı!\n\n"
            summary += f"Toplam Silinen Kayıt: {res.get('total_removed', 0)}\n"
            for f, stats in res.get('files', {}).items():
                summary += f"- {f}: {stats['removed']} adet silindi.\n"
                
            messagebox.showinfo("Başarılı", summary)
        except Exception as e:
            messagebox.showerror("Hata", f"Sıfırlama sırasında bir hata oluştu: {str(e)}")

    # --- VPS KONTROL PANELİ ---
    def setup_vps_panel(self):
        self._load_ssh_config()
        self.server_manager = ServerManager(ssh_config=self.ssh_config)
        
        main_f = tk.Frame(self.vps_frame, bg=self.COLORS['bg'], padx=40, pady=20)
        main_f.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_f = tk.Frame(main_f, bg=self.COLORS['bg'])
        header_f.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(header_f, text="🖥️ VPS Kontrol Merkezi", font=("Segoe UI", 16, "bold"), bg=self.COLORS['bg']).pack(side=tk.LEFT)
        
        self.vps_status_label = tk.Label(header_f, text="DURUM: BEKLENİYOR...", font=("Segoe UI", 10, "bold"), bg='#e5e7eb', padx=10, pady=5)
        self.vps_status_label.pack(side=tk.RIGHT)

        # Sunucu Bilgi Çubuğu (Otonom)
        info_f = tk.Frame(main_f, bg='white', padx=20, pady=15, highlightbackground="#e5e7eb", highlightthickness=1)
        info_f.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(info_f, text="🌐 Sunucu IP:", font=("Segoe UI", 9, "bold"), bg='white', fg='#666').pack(side=tk.LEFT, padx=(0, 5))
        self.vps_ip_label = tk.Label(info_f, text=self.ssh_config.get('host', 'Tanımsız'), font=("Segoe UI", 10), bg='white')
        self.vps_ip_label.pack(side=tk.LEFT, padx=(0, 20))
        
        tk.Label(info_f, text="👤 Kullanıcı:", font=("Segoe UI", 9, "bold"), bg='white', fg='#666').pack(side=tk.LEFT, padx=(0, 5))
        self.vps_user_label = tk.Label(info_f, text=self.ssh_config.get('user', 'root'), font=("Segoe UI", 10), bg='white')
        self.vps_user_label.pack(side=tk.LEFT, padx=(0, 20))
        
        tk.Label(info_f, text="🔑 Bağlantı:", font=("Segoe UI", 9, "bold"), bg='white', fg='#666').pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(info_f, text="SSH Anahtarı (Otonom)", font=("Segoe UI", 10, "italic"), bg='white', fg='#16a34a').pack(side=tk.LEFT)
        
        # Ayarları düzenleme butonu (Küçük ve sağda)
        tk.Button(info_f, text="⚙️ Düzenle", bg='#f3f4f6', relief='flat', font=("Segoe UI", 8), command=self._edit_vps_settings_dialog).pack(side=tk.RIGHT)
        
        # Stats Frame
        stats_f = tk.Frame(main_f, bg=self.COLORS['bg'])
        stats_f.pack(fill=tk.X, pady=(0, 20))
        
        self.cpu_label = self._create_stat_widget(stats_f, "CPU", "0%")
        self.ram_label = self._create_stat_widget(stats_f, "RAM", "0 MB")
        self.uptime_label = self._create_stat_widget(stats_f, "DURUM", "Bilinmiyor")
        
        # Controls Frame
        ctrl_f = tk.LabelFrame(main_f, text="🚀 Sunucu Operasyonları", font=("Segoe UI", 11, "bold"), bg='white', padx=20, pady=20)
        ctrl_f.pack(fill=tk.X, pady=(0, 20))
        
        self.vps_start_btn = tk.Button(ctrl_f, text="▶ BAŞLAT", bg=self.COLORS['success'], fg='white', font=("Segoe UI", 10, "bold"), 
                  width=20, height=2, command=lambda: self._run_vps_command("start"))
        self.vps_start_btn.pack(side=tk.LEFT, padx=10)
        
        self.vps_stop_btn = tk.Button(ctrl_f, text="⏹ DURDUR", bg=self.COLORS['danger'], fg='white', font=("Segoe UI", 10, "bold"), 
                  width=20, height=2, command=lambda: self._run_vps_command("stop"))
        self.vps_stop_btn.pack(side=tk.LEFT, padx=10)
        
        self.vps_deploy_btn = tk.Button(ctrl_f, text="📤 SUNUCUYA YÜKLE", bg='#6366f1', fg='white', font=("Segoe UI", 10, "bold"), 
                  width=20, height=2, command=self._trigger_deployment)
        self.vps_deploy_btn.pack(side=tk.LEFT, padx=10)

        # Auto-Onay Toggle
        auto_f = tk.Frame(ctrl_f, bg='white')
        auto_f.pack(side=tk.RIGHT, padx=20)
        
        tk.Label(auto_f, text="OTOMATİK SEVKİYAT ONAYI", font=("Segoe UI", 8, "bold"), bg='white', fg='#666').pack()
        self.auto_onay_toggle = tk.Checkbutton(auto_f, text="PASİF", variable=self.vps_auto_onay_var, 
                                            onvalue=True, offvalue=False, font=("Segoe UI", 10, "bold"),
                                            bg='white', activebackground='white', command=self._toggle_vps_auto_onay)
        self.auto_onay_toggle.pack()
        
        # Terminal Frame
        term_f = tk.LabelFrame(main_f, text="📄 Terminal & Sistem Logları (Otonom Takip)", font=("Segoe UI", 11, "bold"), bg='white', padx=10, pady=10)
        term_f.pack(fill=tk.BOTH, expand=True)
        
        self.vps_terminal = scrolledtext.ScrolledText(term_f, bg='#050a18', fg='#00ff00', font=("Consolas", 10), height=15)
        self.vps_terminal.pack(fill=tk.BOTH, expand=True)
        
        # Start periodic update
        self._update_vps_status_loop()

    def _create_stat_widget(self, parent, title, initial_val):
        frame = tk.Frame(parent, bg='white', padx=15, pady=10, highlightbackground="#e5e7eb", highlightthickness=1)
        frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Label(frame, text=title, font=("Segoe UI", 8), bg='white', fg='#666').pack(anchor=tk.W)
        val_label = tk.Label(frame, text=initial_val, font=("Segoe UI", 12, "bold"), bg='white')
        val_label.pack(anchor=tk.W)
        return val_label

    def _update_vps_status_loop(self):
        def _task():
            # Sadece geçerli bir host varsa sorgula
            if not self.ssh_config or not self.ssh_config.get('host'):
                self.root.after(0, lambda: self.vps_status_label.config(text="DURUM: AYAR BEKLENİYOR", bg='#e5e7eb', fg='#666'))
                return

            try:
                # Durum özeti ve Logları aynı anda çek (Otonom)
                stats = self.server_manager.get_status_summary()
                logs = self.server_manager.get_logs(lines=50)
                
                # Auto-Onay ayarını MongoDB'den oku (Senkronizasyon için)
                auto_onay = self.data_service.load_config('vps_auto_onay', False)
                
                self.root.after(0, lambda: self._apply_vps_stats(stats, auto_onay))
                self.root.after(0, lambda: self._show_logs_in_terminal(logs))
            except:
                pass
        
        threading.Thread(target=_task, daemon=True).start()
        self.root.after(10000, self._update_vps_status_loop) # 10 seconds

    def _edit_vps_settings_dialog(self):
        """Sunucu ayarlarını düzenlemek için basit bir dialog açar"""
        dialog = tk.Toplevel(self.root)
        dialog.title("VPS Ayarlarını Düzenle")
        dialog.geometry("300x250")
        dialog.padx = 20
        dialog.pady = 20
        
        tk.Label(dialog, text="Sunucu IP:").pack(pady=(10, 0))
        host_e = tk.Entry(dialog)
        host_e.pack(pady=5)
        host_e.insert(0, self.ssh_config.get('host', ''))
        
        tk.Label(dialog, text="Kullanıcı:").pack(pady=(10, 0))
        user_e = tk.Entry(dialog)
        user_e.pack(pady=5)
        user_e.insert(0, self.ssh_config.get('user', 'root'))
        
        def save():
            self.ssh_config['host'] = host_e.get().strip()
            self.ssh_config['user'] = user_e.get().strip()
            
            config_path = os.path.join(get_root_path(), "data", "ssh_config.json")
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(self.ssh_config, f)
                
                self.vps_ip_label.config(text=self.ssh_config['host'])
                self.vps_user_label.config(text=self.ssh_config['user'])
                self.server_manager = ServerManager(ssh_config=self.ssh_config)
                dialog.destroy()
                messagebox.showinfo("Başarılı", "Ayarlar güncellendi.")
            except Exception as e:
                messagebox.showerror("Hata", str(e))
                
        tk.Button(dialog, text="KAYDET", bg=self.COLORS['success'], fg='white', command=save).pack(pady=20)

    def _load_ssh_config(self):
        config_path = os.path.join(get_root_path(), "data", "ssh_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.ssh_config = json.load(f)
            except:
                self.ssh_config = {}
        else:
            self.ssh_config = {}

    def _apply_vps_stats(self, stats, auto_onay=False):
        try:
            status = stats.get('status', 'BİLİNMİYOR')
            color = self.COLORS['success'] if status == 'ONLINE' else self.COLORS['danger']
            self.vps_status_label.config(text=f"DURUM: {status}", bg=color, fg='white')
            self.cpu_label.config(text=f"{stats.get('cpu', 0)}%")
            self.ram_label.config(text=f"{int(stats.get('memory', 0))} MB")
            self.uptime_label.config(text="Çalışıyor" if status == 'ONLINE' else "Kapalı")
            
            # Auto-Onay UI Güncelle
            self.vps_auto_onay_var.set(auto_onay)
            if auto_onay:
                self.auto_onay_toggle.config(text="✅ AKTİF", fg=self.COLORS['success'])
            else:
                self.auto_onay_toggle.config(text="❌ PASİF", fg=self.COLORS['danger'])

            # Buton durumlarını güncelle
            if status.upper() == 'ONLINE':
                self.vps_start_btn.config(state=tk.DISABLED, bg='#e5e7eb')
                self.vps_stop_btn.config(state=tk.NORMAL, bg=self.COLORS['danger'])
            else:
                self.vps_start_btn.config(state=tk.NORMAL, bg=self.COLORS['success'])
                self.vps_stop_btn.config(state=tk.DISABLED, bg='#e5e7eb')
        except:
            pass

    def _toggle_vps_auto_onay(self):
        """Otomatik onay ayarını MongoDB'ye kaydeder"""
        new_state = self.vps_auto_onay_var.get()
        success = self.data_service.save_config('vps_auto_onay', new_state)
        if success:
            if new_state:
                self.auto_onay_toggle.config(text="✅ AKTİF", fg=self.COLORS['success'])
            else:
                self.auto_onay_toggle.config(text="❌ PASİF", fg=self.COLORS['danger'])
        else:
            messagebox.showerror("Hata", "Ayar kaydedilemedi!")
            self.vps_auto_onay_var.set(not new_state) # Geri al

    def _run_vps_command(self, cmd):
        def _task():
            # Butonları geçici olarak devre dışı bırak
            self.root.after(0, lambda: self.vps_start_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.vps_stop_btn.config(state=tk.DISABLED))
            
            if cmd == "start": success, out = self.server_manager.start()
            elif cmd == "stop": success, out = self.server_manager.stop()
            else: return
            
            if not success:
                self.root.after(0, lambda: messagebox.showerror("Hata", out))
            
            # Logları anında güncelle
            logs = self.server_manager.get_logs(lines=50)
            self.root.after(0, lambda: self._show_logs_in_terminal(logs))
        
        threading.Thread(target=_task, daemon=True).start()

    def _refresh_vps_logs(self):
        def _task():
            try:
                logs = self.server_manager.get_logs(lines=50)
                self.root.after(0, lambda: self._show_logs_in_terminal(logs))
            except Exception as e:
                self.root.after(0, lambda: self._show_logs_in_terminal(f"Log okuma hatası: {e}"))
            
        threading.Thread(target=_task, daemon=True).start()

    def _trigger_deployment(self):
        """Yereldeki dosyaları sunucuya yükleyen scripti çalıştırır"""
        if not messagebox.askyesno("Sunucuya Yükle", "Yereldeki güncel kodlar sunucuya yüklenecek ve servisler yeniden başlatılacak.\n\nEmin misiniz?"):
            return
            
        def _task():
            try:
                self.root.after(0, lambda: self._show_logs_in_terminal(">>> Deployment başlatıldı. Lütfen bekleyin...\n"))
                
                # PowerShell scriptini çalıştır
                script_path = os.path.join(get_root_path(), "deploy_vps.ps1")
                process = subprocess.Popen(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    encoding='utf-8',
                    errors='replace',
                    cwd=get_root_path()
                )
                
                for line in process.stdout:
                    self.root.after(0, lambda l=line: self.vps_terminal.insert(tk.END, l))
                    self.root.after(0, lambda: self.vps_terminal.see(tk.END))
                
                process.wait()
                if process.returncode == 0:
                    self.root.after(0, lambda: messagebox.showinfo("Başarılı", "Proje sunucuya başarıyla yüklendi!"))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Hata", "Yükleme sırasında bir sorun oluştu. Terminal loglarını kontrol edin."))
                    
                self._refresh_vps_logs()
            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("Hata", f"Deployment hatası: {err_msg}"))
        
        threading.Thread(target=_task, daemon=True).start()

    def _show_logs_in_terminal(self, logs):
        try:
            self.vps_terminal.delete('1.0', tk.END)
            self.vps_terminal.insert(tk.END, logs)
            self.vps_terminal.see(tk.END)
        except:
            pass

    def on_close(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = YonetimMerkeziApp()
    app.run()
