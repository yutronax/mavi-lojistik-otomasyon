# -*- coding: utf-8 -*-
import os
import json
import itertools
import re
import tkinter as tk
from tkinter import ttk, messagebox
import sys

# Proje kök dizinini ekle (src klasörüne erişim için)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from src.gui.components.tag_selector import TagSelector
    TAG_SELECTOR_AVAILABLE = True
except ImportError:
    TAG_SELECTOR_AVAILABLE = False

# --- CONFIGURATION ---
YUK_TIPI_FILE = os.path.join(BASE_DIR, "data", "yuk_tipi.json")
OPTIONS_FILE = os.path.join(BASE_DIR, "data", "arac_yuk_kasa_tipleri.json")

class AdvancedKeywordApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mavi Lojistik | Gelişmiş Yük Tanımlama Paneli")
        self.root.geometry("750x850") # Daha büyük panel
        self.root.configure(bg="#0f172a") # Dark mode (Slate 900)
        
        self.colors = {
            'bg': "#0f172a",
            'surface': "#1e293b",
            'accent': "#3b82f6",
            'text': "#f8fafc",
            'muted': "#94a3b8",
            'success': "#10b981",
            'border': "#334155"
        }

        self.load_options()
        self.setup_ui()

    def load_options(self):
        try:
            with open(OPTIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.options = data
        except:
            self.options = {"arac_tipleri": [], "kasa_tipleri": [], "yuk_tipleri": []}

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg=self.colors['accent'], height=70)
        header.pack(fill=tk.X)
        tk.Label(header, text="🚚 GELİŞMİŞ YÜK TANIMLA", font=("Segoe UI", 16, "bold"), 
                 bg=self.colors['accent'], fg="white").pack(pady=18)

        # Main Scrollable Area
        main_canvas = tk.Canvas(self.root, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = tk.Frame(main_canvas, bg=self.colors['bg'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=730)
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Form Container
        container = tk.Frame(scrollable_frame, bg=self.colors['bg'], padx=30, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        # 1. Input Section
        self.create_header_label(container, "1. KELİME VEYA KELİME GRUBU")
        self.entry = tk.Entry(container, bg=self.colors['surface'], fg="white", insertbackground="white", 
                             relief="flat", font=("Segoe UI", 12), borderwidth=15)
        self.entry.pack(fill=tk.X, pady=(5, 25))
        self.entry.bind("<KeyRelease>", lambda e: self.update_preview())

        # 2. Advanced Multi-Selectors (TagSelector like main app)
        self.create_header_label(container, "2. ÖZELLİK SEÇİMLERİ (ÇOKLU SEÇİM)")
        
        # Araç Tipi
        self.create_label(container, "ARAÇ TİPLERİ")
        if TAG_SELECTOR_AVAILABLE:
            self.arac_selector = TagSelector(container, self.options['arac_tipleri'], bg=self.colors['bg'])
            self.arac_selector.pack(fill=tk.X, pady=(5, 15))
        else:
            self.arac_var = tk.StringVar()
            self.create_fallback_combo(container, self.options['arac_tipleri'], self.arac_var)

        # Kasa Tipi
        self.create_label(container, "KASA TİPLERİ")
        if TAG_SELECTOR_AVAILABLE:
            self.kasa_selector = TagSelector(container, self.options['kasa_tipleri'], bg=self.colors['bg'])
            self.kasa_selector.pack(fill=tk.X, pady=(5, 15))
        else:
            self.kasa_var = tk.StringVar()
            self.create_fallback_combo(container, self.options['kasa_tipleri'], self.kasa_var)

        # Yük Tipi
        self.create_label(container, "YÜK TİPLERİ")
        if TAG_SELECTOR_AVAILABLE:
            self.yuk_selector = TagSelector(container, self.options['yuk_tipleri'], bg=self.colors['bg'])
            self.yuk_selector.pack(fill=tk.X, pady=(5, 15))
        else:
            self.yuk_var = tk.StringVar()
            self.create_fallback_combo(container, self.options['yuk_tipleri'], self.yuk_var)

        # 3. Preview Section
        self.create_header_label(container, "3. SİSTEME EKLENECEK VARYASYONLAR")
        self.preview_lbl = tk.Label(container, text="0 VARYASYON ÜRETİLDİ", font=("Segoe UI", 9, "bold"), 
                                   bg=self.colors['bg'], fg=self.colors['accent'])
        self.preview_lbl.pack(anchor="w", pady=(5, 0))

        self.preview_box = tk.Text(container, bg="#020617", fg=self.colors['muted'], font=("Consolas", 9),
                                 relief="flat", height=12, padx=15, pady=15)
        self.preview_box.pack(fill=tk.X, pady=(5, 25))

        # 4. Save Button
        save_btn = tk.Button(container, text="🚀 TÜM VARYASYONLARI SİSTEME EKLE", bg=self.colors['success'], fg="white",
                           font=("Segoe UI", 12, "bold"), relief="flat", cursor="hand2",
                           command=self.save, pady=15)
        save_btn.pack(fill=tk.X, pady=(0, 30))

    def create_header_label(self, parent, text):
        tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"), bg=self.colors['bg'], fg=self.colors['accent']).pack(anchor="w", pady=(10, 5))

    def create_label(self, parent, text):
        tk.Label(parent, text=text, font=("Segoe UI", 8, "bold"), bg=self.colors['bg'], fg=self.colors['muted']).pack(anchor="w", pady=(5, 0))

    def create_fallback_combo(self, parent, items, var):
        combo = ttk.Combobox(parent, values=items, textvariable=var, state="readonly")
        combo.pack(fill=tk.X, pady=(2, 10))

    def get_variants(self):
        raw = self.entry.get().strip().lower()
        if not raw: return []

        # 1. Sayı Kuralı
        num_map = {'0':'sıfır','1':'bir','2':'iki','3':'üç','4':'dört','5':'beş','6':'altı','7':'yedi','8':'sekiz','9':'dokuz'}
        text_num = re.sub(r'\d', lambda m: num_map.get(m.group(0), m.group(0)), raw)
        
        seeds = {raw, text_num}
        
        # 2. i/ı Kuralı
        final_seeds = set()
        for s in seeds:
            final_seeds.add(s)
            final_seeds.add(s.replace('i', 'ı'))
            final_seeds.add(s.replace('ı', 'i'))
            trans = str.maketrans("iı", "ıi")
            final_seeds.add(s.translate(trans))

        # 3. Permütasyon ve Birleştirme
        results = set()
        for seed in final_seeds:
            words = seed.split()
            if not words: continue
            for p in itertools.permutations(words):
                n = len(p)
                for i in range(2**(n-1)):
                    curr = p[0]
                    for j in range(n-1):
                        curr += p[j+1] if (i >> j) & 1 else " " + p[j+1]
                    results.add(curr)
        return sorted(list(results))

    def update_preview(self):
        vars = self.get_variants()
        self.preview_lbl.config(text=f"{len(vars)} VARYASYON ÜRETİLDİ")
        self.preview_box.delete(1.0, tk.END)
        self.preview_box.insert(tk.END, "\n".join(vars))

    def save(self):
        vars = self.get_variants()
        if not vars: 
            messagebox.showwarning("Uyarı", "Lütfen bir kelime girin.")
            return
        
        # Get selected values from TagSelectors
        if TAG_SELECTOR_AVAILABLE:
            selected_arac = self.arac_selector.get_values()
            selected_kasa = self.kasa_selector.get_values()
            selected_yuk = self.yuk_selector.get_values()
        else:
            selected_arac = [self.arac_var.get()] if self.arac_var.get() else []
            selected_kasa = [self.kasa_var.get()] if self.kasa_var.get() else []
            selected_yuk = [self.yuk_var.get()] if self.yuk_var.get() else []

        if not (selected_arac or selected_kasa or selected_yuk):
            messagebox.showwarning("Uyarı", "Lütfen en az bir özellik (Araç, Kasa veya Yük) seçin.")
            return

        try:
            with open(YUK_TIPI_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            existing = {item.get("orjinal mesajdaki", "").lower() for item in data}
            added = 0
            
            # Format outputs as "val1 + val2" if multiple selected
            def format_out(lst):
                return " + ".join(lst) if lst else None

            out_arac = format_out(selected_arac)
            out_kasa = format_out(selected_kasa)
            out_yuk = format_out(selected_yuk)

            for v in vars:
                if v.lower() not in existing:
                    entry = {
                        "orjinal mesajdaki": v.upper(),
                        "priority": 1000,
                        "kesin_cikti": {},
                        "notlar": f"Gelişmiş Tanımlayıcı: {self.entry.get()}"
                    }
                    if out_yuk: entry["kesin_cikti"]["YÜKÜN TİPİ"] = out_yuk
                    if out_arac: entry["kesin_cikti"]["ARAÇ TİPİ"] = out_arac
                    if out_kasa: entry["kesin_cikti"]["KASA TİPİ"] = out_kasa
                    data.append(entry)
                    added += 1
            
            with open(YUK_TIPI_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo("Başarılı", f"{added} yeni kural varyasyonu sisteme ekledi!")
            self.entry.delete(0, tk.END)
            if TAG_SELECTOR_AVAILABLE:
                self.arac_selector.clear()
                self.kasa_selector.clear()
                self.yuk_selector.clear()
            self.update_preview()
        except Exception as e:
            messagebox.showerror("Hata", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TCombobox", fieldbackground="#1e293b", background="#3b82f6", foreground="white")
    style.configure("Vertical.TScrollbar", background="#1e293b", bordercolor="#0f172a", arrowcolor="white")
    AdvancedKeywordApp(root)
    root.mainloop()
