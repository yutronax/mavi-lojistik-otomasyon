import os
import sys
import json
import logging
import threading
import time
import requests
import tkinter as tk
from tkinter import ttk, messagebox

# Adjust path to find src
current_dir = os.path.dirname(os.path.abspath(__file__))
root_path = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

logger = logging.getLogger("Managers")

try:
    from src.utils.phone_utils import normalize_phone
    from src.fetchers.whapi_fetcher import fetch_all_messages, WHAPI_TOKEN, patch_dns
    import src.fetchers.whapi_fetcher as mavi_whap
except ImportError as e:
    logger.error(f"Required modules not found: {e}")
    if 'normalize_phone' not in locals():
        normalize_phone = lambda x: x
    WHAPI_TOKEN = None

class BlacklistManager:
    """Kara liste yönetimi için yardımcı sınıf"""
    def __init__(self, parent_gui, container=None):
        self.parent = parent_gui
        self.root = parent_gui.root
        self.data_service = parent_gui.data_service
        self.COLORS = parent_gui.COLORS
        self.window = None
        self.container = container # If provided, embed in this frame
        self.blacklist = self.data_service.load_blacklist()

    def open_window(self):
        if self.container:
            self._setup_ui(self.container)
            return

        if self.window and tk.Toplevel.winfo_exists(self.window):
            self.window.lift()
            return

        self.window = tk.Toplevel(self.root)
        self.window.title("🚫 KARA LİSTE YÖNETİMİ")
        self.window.geometry("500x600")
        self.window.configure(bg=self.COLORS.get('background', '#f1f5f9'))
        self.window.transient(self.root)
        self._setup_ui(self.window)

    def _setup_ui(self, parent):
        # Header (only if Toplevel)
        if isinstance(parent, tk.Toplevel):
            header = tk.Frame(parent, bg=self.COLORS.get('danger', '#dc2626'), height=50)
            header.pack(fill=tk.X)
            tk.Label(header, text="🚫 KARA LİSTE (ENGELENENLER)", font=('Segoe UI', 12, 'bold'), bg=self.COLORS.get('danger', '#dc2626'), fg='white').pack(pady=12)

        # Input Area
        input_frame = tk.Frame(parent, bg=self.COLORS.get('surface', 'white'), padx=20, pady=10)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(input_frame, text="Yeni Numara Ekle:", bg=self.COLORS.get('surface', 'white'), font=('Segoe UI Semibold', 9)).pack(anchor='w')
        
        entry_frame = tk.Frame(input_frame, bg=self.COLORS.get('surface', 'white'))
        entry_frame.pack(fill=tk.X, pady=5)
        
        self.phone_entry = tk.Entry(entry_frame, font=('Segoe UI', 11), relief='flat', highlightthickness=1, highlightbackground=self.COLORS.get('border', '#e5e7eb'))
        self.phone_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.phone_entry.bind('<Return>', lambda e: self.add_number())

        tk.Button(entry_frame, text="EKLE", bg=self.COLORS.get('primary', '#1a56db'), fg='white', font=('Segoe UI Bold', 9), relief='flat', padx=15, command=self.add_number).pack(side=tk.LEFT, padx=(10, 0))

        # Control Buttons (Top of List)
        ctrl_frame = tk.Frame(parent, bg=self.COLORS.get('surface', 'white'), padx=10, pady=5)
        ctrl_frame.pack(fill=tk.X, padx=10)
        
        tk.Button(ctrl_frame, text="🗑️ SEÇİLİ OLANLARI SİL", bg=self.COLORS.get('danger', '#dc2626'), fg='white', font=('Segoe UI Bold', 10), relief='flat', command=self.remove_number, cursor='hand2').pack(fill=tk.X, pady=5)

        # List Area with Listbox
        list_frame = tk.Frame(parent, bg=self.COLORS.get('surface', 'white'), padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        tk.Label(list_frame, text="Engellenen Numaralar (Birden fazla seçebilirsiniz):", bg=self.COLORS.get('surface', 'white'), font=('Segoe UI Semibold', 9)).pack(anchor='w', pady=(0, 5))

        # Listbox for MULTIPLE selection
        self.listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, font=('Segoe UI', 11), relief='flat', highlightthickness=1, highlightbackground=self.COLORS.get('border', '#e5e7eb'), height=15)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(fill=tk.BOTH, expand=True)

        self.refresh_list()

    def refresh_list(self):
        self.blacklist = self.data_service.load_blacklist()
        self.listbox.delete(0, tk.END)
        for num in sorted(self.blacklist):
            self.listbox.insert(tk.END, num)

    def add_number(self):
        num = self.phone_entry.get().strip()
        if not num: return
        
        norm = normalize_phone(num)
        if not norm:
            messagebox.showwarning("Geçersiz Numara", "Lütfen geçerli bir telefon numarası girin.")
            return
            
        if norm in self.blacklist:
            messagebox.showinfo("Bilgi", "Bu numara zaten listede.")
            return
            
        self.blacklist.append(norm)
        if self.data_service.save_blacklist(self.blacklist):
            self.phone_entry.delete(0, tk.END)
            self.refresh_list_and_gui()
        else:
            messagebox.showerror("Hata", "Kaydedilemedi!")

    def remove_number(self):
        selected_indices = self.listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Uyarı", "Lütfen kaldırılacak numaraları seçin.")
            return
            
        selected_nums = [self.listbox.get(i) for i in selected_indices]
        count = len(selected_nums)
        
        if messagebox.askyesno("Onay", f"Seçilen {count} numarayı kara listeden kaldırmak istiyor musunuz?"):
            removed_count = 0
            for num in selected_nums:
                if num in self.blacklist:
                    self.blacklist.remove(num)
                    removed_count += 1
            
            if removed_count > 0:
                if self.data_service.save_blacklist(self.blacklist):
                    self.refresh_list_and_gui()
                    messagebox.showinfo("Bilgi", f"{removed_count} numara listeden kaldırıldı.")

    def refresh_list_and_gui(self):
        self.refresh_list()
        if hasattr(self.parent, 'refresh_messages'):
            self.parent.refresh_messages()

class GroupManager:
    """Grup yönetimi için yardımcı sınıf"""
    
    def __init__(self, parent_gui, container=None):
        self.parent = parent_gui
        self.root = parent_gui.root
        self.COLORS = parent_gui.COLORS
        self.container = container
        
        from dotenv import load_dotenv
        load_dotenv()
        self.token = os.getenv('WHATSAPP_TOKEN')
        
        if not self.token:
            if WHAPI_TOKEN and len(WHAPI_TOKEN) > 10:
                self.token = WHAPI_TOKEN
                logger.info("Using fallback WHAPI_TOKEN from whapi_fetcher.")

        if not self.token:
            logger.error("WHATSAPP_TOKEN not found!")
        
        self.data_service = self.parent.data_service
        self.groups_window = None
        
        try:
            patch_dns()
        except: pass

        if hasattr(self.data_service, 'user_data_dir'):
             self.group_cache_file = os.path.join(self.data_service.user_data_dir, 'temp_groups_cache.json')
        else:
             from src.utils.common import get_user_data_dir
             self.group_cache_file = str(get_user_data_dir() / 'temp_groups_cache.json')
        
        self.all_api_groups = []
        self._startup_fetch()

    def _startup_fetch(self):
        def worker():
            cached = self.load_group_cache()
            if cached and len(cached) > 0:
                self.all_api_groups = cached
                if self.root:
                    try: self.root.after(0, self._auto_refresh_ui_if_open)
                    except: pass
                return

            groups = self.fetch_groups_from_api()
            if groups:
                self.all_api_groups = groups
                self.save_group_cache(groups)
                if self.root:
                    try: self.root.after(0, self._auto_refresh_ui_if_open)
                    except: pass
        
        threading.Thread(target=worker, daemon=True).start()

    def _auto_refresh_ui_if_open(self):
        # Update if window OR embedded panel exists
        if (self.groups_window and tk.Toplevel.winfo_exists(self.groups_window)) or self.container:
            self.load_saved_groups_to_tree()
            self.filter_api_groups()
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"✅ {len(self.all_api_groups)} grup yüklendi")

    def save_group_cache(self, groups):
        try:
            with open(self.group_cache_file, 'w', encoding='utf-8') as f:
                json.dump(groups, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save group cache: {e}")

    def load_group_cache(self):
        try:
            if os.path.exists(self.group_cache_file):
                with open(self.group_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except: pass
        return None

    def _make_api_request(self, method, url, headers=None, timeout=30, params=None, retries=3):
        for attempt in range(retries):
            try:
                response = requests.request(method, url, headers=headers, timeout=timeout, params=params)
                if response.status_code == 200: return response
                elif response.status_code == 429:
                    time.sleep((attempt + 1) * 2)
            except:
                time.sleep((attempt + 1) * 3)
        return None

    def fetch_groups_from_api(self):
        try:
            headers = {"accept": "application/json", "Authorization": f"Bearer {self.token}"}
            base_url = "https://gate.whapi.cloud/groups"
            all_groups = []
            limit = 100
            offset = 0
            while True:
                params = {"count": limit, "offset": offset}
                response = self._make_api_request("GET", base_url, headers=headers, timeout=60, params=params)
                if not response or response.status_code != 200: break
                data = response.json()
                groups_batch = data.get('groups', [])
                if not groups_batch: break
                all_groups.extend(groups_batch)
                if len(groups_batch) < limit: break
                offset += limit
                time.sleep(1)
            return all_groups
        except: return []

    def load_saved_groups(self):
        try:
            return self.data_service.load_saved_groups()
        except Exception as e:
            logger.error(f"Error loading saved groups via DataService: {e}")
            return []

    def save_groups(self, groups):
        try:
            if self.data_service.save_groups(groups):
                try:
                    if hasattr(mavi_whap, 'reload_chat_info'):
                        mavi_whap.reload_chat_info()
                except: pass
                return True
            return False
        except Exception as e:
            messagebox.showerror("Kayıt Hatası", f"Hata: {e}")
            return False

    def open_group_management(self):
        if self.container:
            self._setup_ui(self.container)
            return

        if self.groups_window and tk.Toplevel.winfo_exists(self.groups_window):
            self.groups_window.lift()
            return

        self.groups_window = tk.Toplevel(self.root)
        self.groups_window.title("📱 WhatsApp Grup Yönetimi")
        self.groups_window.geometry("1200x800")
        try: self.groups_window.state('zoomed')
        except: pass
        self._setup_ui(self.groups_window)

    def _setup_ui(self, parent):
        parent.configure(bg=self.COLORS.get('background', '#f1f5f9'))
        
        # Header (Top-level only)
        if isinstance(parent, tk.Toplevel):
            header = tk.Frame(parent, bg=self.COLORS.get('primary', '#1a56db'), height=50)
            header.pack(fill=tk.X)
            tk.Label(header, text="📱 WHATSAPP GRUP YÖNETİMİ", font=('Segoe UI', 14, 'bold'), bg=self.COLORS.get('primary', '#1a56db'), fg='white').pack(side=tk.LEFT, padx=20, pady=10)

        content = tk.Frame(parent, bg=self.COLORS.get('background', '#f1f5f9'))
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left: Saved Groups
        left_panel = tk.LabelFrame(content, text="💾 Kaydedilmiş Gruplar", font=('Segoe UI', 10, 'bold'), bg=self.COLORS.get('surface', 'white'))
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        saved_header = tk.Frame(left_panel, bg=self.COLORS.get('surface', 'white'))
        saved_header.pack(fill=tk.X, padx=5, pady=(5,0))
        
        self.trash_normal_bg = '#f8d7da'
        self.trash_normal_fg = '#721c24'
        self.trash_frame = tk.Frame(saved_header, bg=self.trash_normal_bg, width=48, height=28)
        self.trash_frame.pack(side=tk.LEFT, padx=(0,6), pady=2)
        self.trash_label = tk.Label(self.trash_frame, text='🗑️', bg=self.trash_normal_bg, fg=self.trash_normal_fg)
        self.trash_label.pack(expand=True)

        self.saved_refresh_button = tk.Button(saved_header, text='🔄', bg=self.COLORS.get('primary_light', '#3b82f6'), fg='white', width=3, command=self.load_saved_groups_to_tree)
        self.saved_refresh_button.pack(side=tk.RIGHT)
        # Saved Groups List
        self.saved_tree = ttk.Treeview(left_panel, columns=("name", "id"), show="headings", selectmode="extended")
        self.saved_tree.heading("name", text="Grup Adı")
        self.saved_tree.heading("id", text="ID")
        self.saved_tree.column("id", width=150)
        self.saved_tree.pack(fill=tk.BOTH, expand=True)
        
        # Bind events for reordering
        self.saved_tree.bind('<ButtonPress-1>', self.on_tree_button_press)
        self.saved_tree.bind('<B1-Motion>', self.on_tree_motion)
        self.saved_tree.bind('<ButtonRelease-1>', self.on_tree_button_release)

        # Right: API Groups
        right_panel = tk.LabelFrame(content, text="🌐 WhatsApp'tan Gruplar", font=('Segoe UI', 10, 'bold'), bg=self.COLORS.get('surface', 'white'))
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        search_frame = tk.Frame(right_panel, bg=self.COLORS.get('surface', 'white'))
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(search_frame, text="🔍 Ara:", bg=self.COLORS.get('surface', 'white')).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.filter_api_groups())
        tk.Entry(search_frame, textvariable=self.search_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.api_tree = ttk.Treeview(right_panel, columns=('name', 'id', 'members', 'status'), show='headings', height=15, selectmode='extended')
        self.api_tree.heading('name', text='Grup Adı'); self.api_tree.heading('id', text='Grup ID'); self.api_tree.heading('members', text='Üye'); self.api_tree.heading('status', text='Durum')
        self.api_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Bind events for adding via Drag and Drop
        self.api_tree.bind('<ButtonPress-1>', self.on_tree_button_press)
        self.api_tree.bind('<B1-Motion>', self.on_tree_motion)
        self.api_tree.bind('<ButtonRelease-1>', self.on_tree_button_release)

        tk.Button(right_panel, text="➕ Seçili Grubu Ekle", bg=self.COLORS.get('success', '#059669'), fg='white', font=('Segoe UI', 9, 'bold'), command=self.add_selected_group).pack(fill=tk.X, padx=5, pady=5)

        self.status_label = tk.Label(parent, text="Hazır", bg='#e9ecef', anchor='w')
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM)

        self.load_saved_groups_to_tree()
        self.filter_api_groups()

    def load_saved_groups_to_tree(self):
        for item in self.saved_tree.get_children(): self.saved_tree.delete(item)
        for g in self.load_saved_groups():
            self.saved_tree.insert('', tk.END, values=(g.get('name', '???'), g.get('id', '')))

    def filter_api_groups(self):
        for item in self.api_tree.get_children(): self.api_tree.delete(item)
        query = self.search_var.get().lower()
        saved_ids = {g.get('id') for g in self.load_saved_groups()}
        for g in self.all_api_groups:
            name = g.get('name', '???')
            gid = g.get('id', '')
            if query in name.lower() or query in gid.lower():
                status = "✅ Kayıtlı" if gid in saved_ids else "➕ Eklenebilir"
                self.api_tree.insert('', tk.END, values=(name, gid, str(len(g.get('participants', []))), status))

    def add_selected_group(self):
        sel = self.api_tree.selection()
        if not sel: return
        vals = self.api_tree.item(sel[0]).get('values', [])
        name, gid = vals[0], vals[1]
        saved = self.load_saved_groups()
        if any(g.get('id') == gid for g in saved): return
        saved.append({'name': name, 'id': gid})
        if self.save_groups(saved): self.load_saved_groups_to_tree(); self.filter_api_groups()

    # Drag and Drop Methods (Simplified for migration)
    def on_tree_button_press(self, event):
        tree = event.widget
        item = tree.identify_row(event.y)
        if not item: return
        
        # Select the item if not already selected (for single drag start)
        if item not in tree.selection():
            tree.selection_set(item)
            
        self._drag_data = {'item': item, 'tree': tree, 'initial_x': event.x_root, 'initial_y': event.y_root}
        tree.config(cursor="hand2")
        self.status_label.config(text="👆 Sürükleniyor... Bırakmak istediğiniz yere taşıyın.")

    def on_tree_motion(self, event):
        if not hasattr(self, '_drag_data'): return
        tree = self._drag_data['tree']
        
        # Visual feedback: highlight target row if in same tree
        target_tree = event.widget.winfo_containing(event.x_root, event.y_root)
        if target_tree == self.saved_tree:
            target_item = self.saved_tree.identify_row(event.y_root - self.saved_tree.winfo_rooty())
            if target_item:
                self.saved_tree.selection_set(target_item)
        elif target_tree == self.trash_frame or target_tree == self.trash_label:
            self.trash_frame.config(bg='#f5c6cb') # Hover effect
        else:
            self.trash_frame.config(bg=self.trash_normal_bg)

    def on_tree_button_release(self, event):
        if not hasattr(self, '_drag_data'): return
        src_item = self._drag_data['item']
        src_tree = self._drag_data['tree']
        
        # Reset visual state
        src_tree.config(cursor="")
        self.trash_frame.config(bg=self.trash_normal_bg)
        self.status_label.config(text="Hazır")
        
        # Identify drop target
        target_widget = src_tree.winfo_containing(event.x_root, event.y_root)
        
        if src_tree == self.saved_tree:
            # 1. Trash check
            if target_widget in [self.trash_frame, self.trash_label]:
                self.delete_all_selected()
            
            # 2. Reorder logic
            elif target_widget == self.saved_tree:
                target_item = self.saved_tree.identify_row(event.y_root - self.saved_tree.winfo_rooty())
                if target_item and target_item != src_item:
                    items = list(self.saved_tree.get_children())
                    idx_src = items.index(src_item)
                    idx_target = items.index(target_item)
                    
                    saved = self.load_saved_groups()
                    if 0 <= idx_src < len(saved) and 0 <= idx_target < len(saved):
                        group = saved.pop(idx_src)
                        saved.insert(idx_target, group)
                        if self.save_groups(saved):
                            self.load_saved_groups_to_tree()
        
        elif src_tree == self.api_tree:
            # 3. Add to saved list
            if target_widget == self.saved_tree:
                self.add_selected_groups_via_drag()

        if hasattr(self, '_drag_data'):
            del self._drag_data

    def add_selected_groups_via_drag(self):
        sel = self.api_tree.selection()
        if not sel: return
        
        saved = self.load_saved_groups()
        added_count = 0
        
        for item in sel:
            vals = self.api_tree.item(item).get('values', [])
            if len(vals) < 2: continue
            name, gid = vals[0], vals[1]
            
            if not any(g.get('id') == gid for g in saved):
                saved.append({'name': name, 'id': gid})
                added_count += 1
        
        if added_count > 0:
            if self.save_groups(saved):
                self.load_saved_groups_to_tree()
                self.filter_api_groups()
                self.status_label.config(text=f"✅ {added_count} grup eklendi")

    def delete_all_selected(self):
        sel = self.saved_tree.selection()
        if not sel: return
        
        if messagebox.askyesno("Onay", f"{len(sel)} adet grubu silmek istiyor musunuz?"):
            saved = self.load_saved_groups()
            ids_to_remove = [self.saved_tree.item(i)['values'][1] for i in sel]
            new_saved = [g for g in saved if g.get('id') not in ids_to_remove]
            if self.save_groups(new_saved):
                self.load_saved_groups_to_tree()
                self.filter_api_groups()

    def delete_selected(self, item):
        vals = self.saved_tree.item(item).get('values', [])
        if not vals: return
        gid = vals[1]
        if messagebox.askyesno("Onay", f"'{vals[0]}' grubunu silmek istiyor musunuz?"):
            saved = self.load_saved_groups()
            saved = [g for g in saved if g.get('id') != gid]
            if self.save_groups(saved): self.load_saved_groups_to_tree(); self.filter_api_groups()

    def refresh_api_groups(self):
        self.status_label.config(text="🔄 API'den çekiliyor...")
        def worker():
            g = self.fetch_groups_from_api()
            if g:
                self.all_api_groups = g
                self.save_group_cache(g)
                self.parent.root.after(0, self.filter_api_groups)
                self.parent.root.after(0, lambda: self.status_label.config(text=f"✅ {len(g)} grup güncellendi"))
        threading.Thread(target=worker, daemon=True).start()
