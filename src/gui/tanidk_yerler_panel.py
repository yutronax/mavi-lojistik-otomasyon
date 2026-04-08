# -*- coding: utf-8 -*-
"""
Tanıdık Yerler Yönetim Paneli - Sade Manuel Giriş ve Google Arama Odaklı
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import os
from datetime import datetime
from src.utils.location_helper import LocationHelper

logger = logging.getLogger(__name__)

class TanidikYerlerManager:
    """
    Tanıdık yerler yönetimi için GUI sınıfı.
    Sadeleştirilmiş yapı: Google arama yardımı ve manuel kayıt odağı.
    """
    
    def __init__(self, parent_gui):
        self.parent = parent_gui
        self.root = parent_gui.root
        self.COLORS = parent_gui.COLORS
        
        # Location helper
        from src.utils.common import get_root_path
        root_path = get_root_path()
        data_dir = os.path.join(root_path, 'data')
        self.location_helper = LocationHelper(data_dir)
        
        self.window = None
        self.location_tree = None
        self.all_iller = []
        self.il_ilceler_data = []
        self.form_entries = {}
        
    def open_window(self):
        """Tanıdık yerler yönetim penceresini aç"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return
        
        # Önce verileri yükleyelim ki il listesi hazır olsun
        self.load_data()
        
        self.window = tk.Toplevel(self.root)
        self.window.title("📍 Tanıdık Yerler ve Mahalle Rehberi")
        self.window.geometry("1100x750")
        self.window.configure(bg=self.COLORS['bg'])
        
        # --- HEADER ---
        header = tk.Frame(self.window, bg=self.COLORS['primary'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text="📍 Tanıdık Yerler & Mahalle Rehber Yönetimi",
            font=("Segoe UI", 16, "bold"),
            bg=self.COLORS['primary'],
            fg='white'
        ).pack(side=tk.LEFT, padx=20, pady=12)

        # ℹ️ Bilgi Butonu
        tk.Button(
            header,
            text="ℹ️ Nasıl Çalışır?",
            font=("Segoe UI", 10, "bold"),
            bg='#f8fafc', fg=self.COLORS['primary'],
            relief='flat', padx=15, pady=5,
            command=self.show_button_info,
            cursor='hand2'
        ).pack(side=tk.RIGHT, padx=20, pady=12)

        
        # --- MAIN CONTAINER ---
        main_container = tk.Frame(self.window, bg=self.COLORS['bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # 1. LEFT: GUIDE BOX
        left_panel = tk.Frame(main_container, bg=self.COLORS['bg'], width=240)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        guide_box = tk.LabelFrame(
            left_panel, 
            text="📖 REHBER", 
            font=("Segoe UI", 10, "bold"),
            bg='#fff3cd', fg='#856404',
            padx=10, pady=10
        )
        guide_box.pack(fill=tk.X)
        
        guide_text = (
            "✍️ Mahalle Ekleme:\n"
            "Mahalleyi yazın,\n"
            "İl ve İlçe seçimini (Düzenle\n"
            "ekranındaki gibi) yapın.\n\n"
            "🔍 OTOMATİK BULMA:\n"
            "Mahalle adını yazdığınızda\n"
            "veritabanında varsa İl ve İlçe\n"
            "otomatik olarak seçilir.\n\n"
            "🔥 ANA VERİTABANI:\n"
            "Buraya kaydedilen yerler,\n"
            "WhatsApp mesajlarında\n"
            "OTOMATİK tanınır."
        )
        tk.Label(guide_box, text=guide_text, font=("Segoe UI", 9), bg='#fff3cd', fg='#856404', justify=tk.LEFT, anchor='nw').pack(fill=tk.X)
        
        # 2. CENTER: REGISTERED LIST
        center_panel = tk.LabelFrame(
            main_container,
            text="📋 Kayıtlı Özel Yerleriniz",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLORS['bg'], fg=self.COLORS['text'],
            padx=10, pady=10
        )
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        tree_container = tk.Frame(center_panel, bg='white')
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll = tk.Scrollbar(tree_container)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.location_tree = ttk.Treeview(
            tree_container,
            columns=('yer', 'il', 'ilce', 'not'),
            show='headings',
            yscrollcommand=tree_scroll.set
        )
        self.location_tree.heading('yer', text='Yer Adı')
        self.location_tree.heading('il', text='İl')
        self.location_tree.heading('ilce', text='İlçe')
        self.location_tree.heading('not', text='Not')
        
        self.location_tree.column('yer', width=140)
        self.location_tree.column('il', width=100)
        self.location_tree.column('ilce', width=100)
        self.location_tree.column('not', width=120)
        
        self.location_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.location_tree.yview)
        
        list_btns = tk.Frame(center_panel, bg=self.COLORS['bg'], pady=10)
        list_btns.pack(fill=tk.X)
        
        tk.Button(list_btns, text="🗑️ Seçiliyi Sil", font=("Segoe UI", 9, "bold"), bg=self.COLORS['danger'], fg='white', command=self.delete_selected_location, padx=10).pack(side=tk.LEFT, padx=5)
        tk.Button(list_btns, text="🔄 Yenile", font=("Segoe UI", 9), bg='#6c757d', fg='white', command=self.refresh_location_list, padx=10).pack(side=tk.LEFT, padx=5)
        
        # 3. RIGHT: Manual Entry
        right_panel = tk.Frame(main_container, bg=self.COLORS['bg'], width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        right_panel.pack_propagate(False)
        
        # B. Manual Form
        manual_frame = tk.LabelFrame(
            right_panel,
            text="✍️ Manuel Mahalle Tanımla",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLORS['bg'], fg=self.COLORS['text'],
            padx=5, pady=15
        )
        manual_frame.pack(fill=tk.BOTH, expand=True)
        
        def create_lab(txt):
            return tk.Label(manual_frame, text=txt, font=("Segoe UI", 9, "bold"), bg=self.COLORS['bg'], fg='#444')
            
        create_lab("Mahalle / Yer Adı:").pack(anchor=tk.W, padx=10)
        self.yer_adi_entry = tk.Entry(manual_frame, font=("Segoe UI", 12))
        self.yer_adi_entry.pack(fill=tk.X, pady=(0, 5), padx=10)
        self.yer_adi_entry.bind('<FocusOut>', lambda e: self.auto_detect_location())
        self.yer_adi_entry.bind('<Return>', lambda e: self.auto_detect_location())

        # AKILLI SORGU BUTONU (GEMINI)
        self.btn_smart_search = tk.Button(
            manual_frame,
            text="🧠 AKILLI BUL (Yapay Zeka)",
            font=("Segoe UI", 9, "bold"),
            bg='#6366f1', fg='white',
            relief='flat', padx=10, pady=5,
            command=self.ask_gemini_location,
            cursor='hand2'
        )
        self.btn_smart_search.pack(fill=tk.X, pady=(0, 15), padx=10)
        
        # İl ve İlçe seçimi (Düzenle ekranındaki sistemin aynısı)
        self.form_entries = {}
        il_list = self.all_iller
        
        self.il_entry = self.parent.create_autocomplete_field(manual_frame, "İl:", il_list, "", self.form_entries, 'il')
        self.ilce_entry = self.parent.create_autocomplete_field(manual_frame, "İlçe:", [], "", self.form_entries, 'ilce', depends_on='il')
        
        # Alanlara tıklandığında veya odaklanıldığında listeyi otomatik aç
        def auto_open(e, entry_key):
            lb = self.form_entries.get(f"{entry_key}_listbox")
            if lb:
                self.window.after(50, lambda: lb.pack(fill=tk.X, padx=2, pady=(0, 2)))

        self.il_entry.bind('<FocusIn>', lambda e: auto_open(e, 'il'))
        self.ilce_entry.bind('<FocusIn>', lambda e: auto_open(e, 'ilce'))

        
        # Save Button
        tk.Button(
            manual_frame,
            text="🔥 ANA VERİTABANINA KAYDET",
            font=("Segoe UI", 11, "bold"),
            bg=self.COLORS['success'], fg='white',
            height=2, command=self.add_manual_to_main_db,
            cursor='hand2'
        ).pack(fill=tk.X, padx=10, pady=20)
        
        self.refresh_location_list()
        
    def load_data(self):
        try:
            self.il_ilceler_data = self.parent.data_service.load_il_ilceler()
            self.all_iller = sorted([item['il'] for item in self.il_ilceler_data])
        except:
            self.il_ilceler_data = []
            self.all_iller = []

    def ask_gemini_location(self):
        """Gemini'ye bu yerin nereye bağlı olduğunu sorar"""
        yer = self.yer_adi_entry.get().strip()
        if not yer:
            messagebox.showwarning("Uyarı", "Lütfen bir yer adı girin!")
            return
            
        try:
            self.btn_smart_search.config(text="⌛ Soruluyor...", state='disabled')
            self.window.update()
            
            from src.utils.gemini_client import GeminiClient
            client = GeminiClient()
            if not client.client:
                messagebox.showerror("Hata", "Gemini API bağlantısı kurulamadı. Lütfen .env dosyasını kontrol edin.")
                return
            
            prompt = f"'{yer}' neresidir? Lütfen sadece TÜRKİYE içindeki IL ve ILCE bilgisini şu formatta ver: IL: ..., ILCE: ... (Başka hiçbir şey yazma, eğer bulamazsan BILINMIYOR yaz)"
            response = client.generate_text_only(prompt)
            
            if not response or "BILINMIYOR" in response.upper():
                messagebox.showinfo("Sonuç", f"Yapay zeka '{yer}' yerini bulamadı.")
                return

            import re
            # Daha esnek regex
            il_match = re.search(r'(?:IL|SEHIR|ŞEHİR):\s*([^,\n\.\(\)]+)', response, re.IGNORECASE)
            ilce_match = re.search(r'(?:ILCE|İLÇE|İLCESİ|İLÇESİ):\s*([^,\n\.\(\)]+)', response, re.IGNORECASE)
            
            if il_match and ilce_match:
                ai_il = il_match.group(1).strip().upper()
                ai_ilce = ilce_match.group(1).strip().upper()
                
                # İller listesinden en yakın eşleşmeyi bul
                from src.utils.common import normalize_turkish_text
                norm_ai_il = normalize_turkish_text(ai_il)
                
                exact_il = None
                for item in self.il_ilceler_data:
                    current_il = item['il']
                    if current_il == ai_il or normalize_turkish_text(current_il) == norm_ai_il:
                        exact_il = current_il
                        break
                
                if exact_il:
                    self.il_entry.delete(0, tk.END)
                    self.il_entry.insert(0, exact_il)
                    self.parent.update_location_combos(self.il_entry, self.ilce_entry)
                    
                    # İlçeler listesinden eşleşme bul
                    ilceler = self.ilce_entry['values']
                    norm_ai_ilce = normalize_turkish_text(ai_ilce)
                    exact_ilce = None
                    for c in ilceler:
                        if c.upper() == ai_ilce or normalize_turkish_text(c) == norm_ai_ilce:
                            exact_ilce = c
                            break
                    
                    if exact_ilce:
                        self.ilce_entry.set(exact_ilce)
                        messagebox.showinfo("Başarılı", f"Yapay Zeka Tespiti:\nİl: {exact_il}\nİlçe: {exact_ilce}")
                    else:
                        self.ilce_entry.set(ai_ilce.title())
                        messagebox.showinfo("Kısmi Sonuç", f"İl bulundu: {exact_il}\nİlçe (Listede yok): {ai_ilce.title()}")
                else:
                    messagebox.showinfo("Yanıt", f"Yapay zeka '{ai_il}' dedi ancak bu il listemizde yok.\n\nTam Yanıt: {response}")
            else:
                messagebox.showinfo("Yanıt", f"Yapay zeka yanıtı formatlanamadı:\n\n{response}")
                    
        except Exception as e:
            messagebox.showerror("Hata", f"Yapay zeka sorgusu sırasında hata oluştu: {str(e)}")
        finally:
            self.btn_smart_search.config(text="🧠 AKILLI BUL (Yapay Zeka)", state='normal')

    def auto_detect_location(self):
        """Yer adı girildiğinde veritabanında varsa otomatik doldurur"""
        yer = self.yer_adi_entry.get().strip()
        if len(yer) < 2: return
        
        res = self.location_helper.search_location(yer)
        if res:
            il, ilce = res
            self.il_entry.delete(0, tk.END)
            self.il_entry.insert(0, il.upper())
            self.parent.update_location_combos(self.il_entry, self.ilce_entry)
            self.ilce_entry.set(ilce)

    def ask_gemini_location(self):
        """Gemini'ye bu yerin nereye bağlı olduğunu sorar"""
        yer = self.yer_adi_entry.get().strip()
        if not yer:
            messagebox.showwarning("Uyarı", "Lütfen bir yer adı girin!")
            return
            
        try:
            self.btn_smart_search.config(text="⌛ Soruluyor...", state='disabled')
            self.window.update()
            
            from src.utils.gemini_client import GeminiClient
            client = GeminiClient()
            if not client.client:
                messagebox.showerror("Hata", "Gemini API bağlantısı kurulamadı. Lütfen .env dosyasını kontrol edin.")
                return
            
            prompt = f"'{yer}' neresidir? Lütfen sadece TÜRKİYE içindeki IL ve ILCE bilgisini şu formatta ver: IL: ..., ILCE: ... (Başka hiçbir şey yazma, eğer bulamazsan BILINMIYOR yaz)"
            response = client.generate_text_only(prompt)
            
            if not response or "BILINMIYOR" in response.upper():
                messagebox.showinfo("Sonuç", f"Yapay zeka '{yer}' yerini bulamadı.")
                return

            import re
            # Daha esnek regex
            il_match = re.search(r'(?:IL|SEHIR|ŞEHİR):\s*([^,\n\.\(\)]+)', response, re.IGNORECASE)
            ilce_match = re.search(r'(?:ILCE|İLÇE|İLCESİ|İLÇESİ):\s*([^,\n\.\(\)]+)', response, re.IGNORECASE)
            
            if il_match and ilce_match:
                ai_il = il_match.group(1).strip().upper()
                ai_ilce = ilce_match.group(1).strip().upper()
                
                # İller listesinden en yakın eşleşmeyi bul
                from src.utils.common import normalize_turkish_text
                norm_ai_il = normalize_turkish_text(ai_il)
                
                exact_il = None
                for item in self.il_ilceler_data:
                    current_il = item['il']
                    if current_il == ai_il or normalize_turkish_text(current_il) == norm_ai_il:
                        exact_il = current_il
                        break
                
                if exact_il:
                    self.il_entry.delete(0, tk.END)
                    self.il_entry.insert(0, exact_il)
                    self.parent.update_location_combos(self.il_entry, self.ilce_entry)
                    
                    # İlçeler listesinden eşleşme bul
                    ilceler = self.ilce_entry['values']
                    norm_ai_ilce = normalize_turkish_text(ai_ilce)
                    exact_ilce = None
                    for c in ilceler:
                        if c.upper() == ai_ilce or normalize_turkish_text(c) == norm_ai_ilce:
                            exact_ilce = c
                            break
                    
                    if exact_ilce:
                        self.ilce_entry.set(exact_ilce)
                        messagebox.showinfo("Başarılı", f"Yapay Zeka Tespiti:\nİl: {exact_il}\nİlçe: {exact_ilce}")
                    else:
                        self.ilce_entry.set(ai_ilce.title())
                        messagebox.showinfo("Kısmi Sonuç", f"İl bulundu: {exact_il}\nİlçe (Listede yok): {ai_ilce.title()}")
                else:
                    messagebox.showinfo("Yanıt", f"Yapay zeka '{ai_il}' dedi ancak bu il listemizde yok.\n\nTam Yanıt: {response}")
            else:
                messagebox.showinfo("Yanıt", f"Yapay zeka yanıtı formatlanamadı:\n\n{response}")
                    
        except Exception as e:
            messagebox.showerror("Hata", f"Yapay zeka sorgusu sırasında hata oluştu: {str(e)}")
        finally:
            self.btn_smart_search.config(text="🧠 AKILLI BUL (Yapay Zeka)", state='normal')

    def add_manual_to_main_db(self):
        # 1. Mahalle adını BÜYÜK HARFE çevir (User requirement)
        mah = self.yer_adi_entry.get().strip().upper()
        
        il = self.il_entry.get().strip().upper()
        ilce = self.ilce_entry.get().strip()
        
        if not mah or not il or not ilce:
            messagebox.showwarning("Eksik", "Lütfen Mahalle, İl ve İlçe bilgilerini doldurun!")
            return
        
        if self.location_helper.add_mahalle_to_main_db(il, ilce, mah):
            # Ayrıca özel listeye de ekle
            self.location_helper.add_custom_location(mah, il, ilce, "Ana Veriden")
            self.refresh_location_list()
            self.yer_adi_entry.delete(0, tk.END)
            self.il_entry.delete(0, tk.END)
            self.ilce_entry.set('')
            try:
                self.parent.status_label.config(text="✅ Mahalle veritabanına eklendi.")
            except: pass
        else:
            messagebox.showwarning("Bilgi", "Bu mahalle zaten kayıtlı.")


    def refresh_location_list(self):
        if not self.location_tree: return
        for item in self.location_tree.get_children():
            self.location_tree.delete(item)
        locations = self.location_helper.get_all_custom_locations()
        for loc in reversed(locations):
            self.location_tree.insert('', tk.END, values=(loc.get('yer_adi'), loc.get('il'), loc.get('ilce'), loc.get('aciklama')))

    def delete_selected_location(self):
        sel = self.location_tree.selection()
        if not sel: return
        vals = self.location_tree.item(sel[0])['values']
        if messagebox.askyesno("Silme", f"'{vals[0]}' kaydını silmek istiyor musunuz?"):
            if self.location_helper.delete_custom_location(vals[0], vals[1], vals[2]):
                self.refresh_location_list()

    def show_button_info(self):
        """Butonların ve sistemin çalışması hakkında bilgi verir"""
        info_text = (
            "🚀 SİSTEM NASIL ÇALIŞIR?\n\n"
            "1️⃣ GOOGLE'DA ARA:\n"
            "Sol üstteki kutucuğa bir mahalle adı yazıp butona basarsanız, tarayıcınızda otomatik Google araması açılır. "
            "Böylece bilinmeyen yerlerin nereye bağlı olduğunu teyit edebilirsiniz.\n\n"
            "2️⃣ MANUEL MAHALLE TANIMLA:\n"
            "• Mahalle Adı: Tanıtmak istediğiniz yeri yazın.\n"
            "• İl/İlçe: Kutucuğa tıkladığınızda liste otomatik açılır. Yazmaya başlayıp filtreleyebilir, ENTER ile hızlıca seçebilirsiniz.\n\n"
            "3️⃣ ANA VERİTABANINA KAYDET:\n"
            "Bu buton, yazdığınız yeri ana veriye kalıcı olarak işler. Artık WhatsApp'tan gelen mesajlarda bu mahalle geçiyorsa "
            "sistem onu otomatik olarak tanıyacaktır.\n\n"
            "4️⃣ SEÇİLİYİ SİL:\n"
            "Listeden bir kaydı seçip bu butona basarsanız, o yeri sistem hafızasından çıkarır.\n\n"
            "💡 İPUCU: İlçe kutusuna bir şey yazıp Enter'a basarsanız, sistem o ilçenin hangi ile bağlı olduğunu bulup otomatik doldurabilir!"
        )
        messagebox.showinfo("ℹ️ Buton ve Sistem Rehberi", info_text)


# --- STANDALONE EXECUTION SUPPORT ---

class StandaloneTanidikYerlerApp:
    """Tanıdık Yerler panelini tek başına çalıştırmak için sarmalayıcı"""
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Mavi Lojistik - Mahalle Yönetimi")
        self.root.geometry("1100x750")
        
        # Mavi Lojistik renk ve font stilleri
        self.COLORS = {
            'primary': '#1a56db', 
            'bg': '#f3f4f6', 
            'surface': 'white', 
            'text': '#111827',
            'danger': '#dc2626',
            'success': '#16a34a'
        }
        self.font_normal = ('Segoe UI', 10)
        
        # Mock Data Service
        from src.services.data_service import DataService
        from src.utils.common import get_root_path
        self.data_service = DataService(get_root_path())
        
        # Initialize Manager
        self.manager = TanidikYerlerManager(self)
        self.manager.open_window()
        
        # Standalone pencere kapatıldığında ana root'u da kapat
        self.manager.window.protocol("WM_DELETE_WINDOW", self.root.destroy)
        # Ana root'u gizle (manager.window'u kullanıyoruz)
        self.root.withdraw()

    def create_autocomplete_field(self, parent, label, values, val, form_dict, key, depends_on=None):
        """masaustu_uygulama.py'deki fonksiyonun basitleştirilmiş hali"""
        f = tk.Frame(parent, bg=self.COLORS['bg'])
        f.pack(fill=tk.X, pady=5, padx=10)
        tk.Label(f, text=label, width=15, anchor='w', font=('Segoe UI', 9, 'bold'), bg=self.COLORS['bg']).pack(side=tk.LEFT)
        
        entry = ttk.Combobox(f, values=values, font=('Segoe UI', 10))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if val: entry.set(val)
        
        form_dict[key] = entry
        return entry

    def update_location_combos(self, il_entry, ilce_entry):
        """İl değiştiğinde ilçe listesini güncelle"""
        il = il_entry.get()
        ilceler = self.get_ilce_list(il)
        ilce_entry.config(values=ilceler)

    def get_ilce_list(self, il_name):
        data = self.data_service.load_il_ilceler()
        for item in data:
            if item['il'].upper() == il_name.upper():
                return item.get('ilçe', [])
        return []

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = StandaloneTanidikYerlerApp()
    app.run()

