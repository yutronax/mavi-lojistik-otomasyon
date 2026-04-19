import flet as ft
import os
import asyncio
import json
from src.gui.styles import AppColors, AppStyles
from src.services.data_service import DataService
from src.services.data_service_async import AsyncDataService
from src.utils.text_utils import generate_keyword_variants

class ManagementCenterPage:
    def __init__(self, page: ft.Page):
        self.page = page
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        self.data_service = AsyncDataService(DataService(self.root_dir))
        
        # UI State
        self.yuk_rules = [] # yuk_tipi.json içeriği
        self.base_options = {} # araç/kasa/yük temel tipleri
        
        self.yuk_list_view = ft.ListView(expand=True, spacing=10, padding=10)
        self.search_entry = ft.TextField(
            label="Yük Ara", 
            prefix_icon="search", 
            on_change=lambda e: asyncio.create_task(self._filter_yuk(e)),
            border_radius=10
        )
        
        # Form Alanları
        self.keyword_field = ft.TextField(label="Orijinal Mesajdaki Kelime", border_radius=10)
        self.priority_field = ft.TextField(label="Öncelik (1000)", border_radius=10, value="1000")
        self.yuk_type_dropdown = ft.Dropdown(label="Yük Tipi", border_radius=10)
        self.arac_type_dropdown = ft.Dropdown(label="Araç Tipi", border_radius=10)
        self.kasa_type_dropdown = ft.Dropdown(label="Kasa Tipi", border_radius=10)

    async def _load_yuk_data(self):
        """Yük tanımlama verilerini ve dropdown seçeneklerini yükler"""
        try:
            # Dropdown seçeneklerini yükle
            self.base_options = await self.data_service.load_arac_kasa_tipleri()
            
            self.yuk_type_dropdown.options = [ft.dropdown.Option(opt) for opt in self.base_options.get('yuk_tipleri', [])]
            self.arac_type_dropdown.options = [ft.dropdown.Option(opt) for opt in self.base_options.get('arac_tipleri', [])]
            self.kasa_type_dropdown.options = [ft.dropdown.Option(opt) for opt in self.base_options.get('kasa_tipleri', [])]
            
            # Mevcut tanımları yükle
            self.yuk_rules = await self.data_service.load_yuk_tipleri()
            
            await self._refresh_yuk_list()
            self.page.update()
        except Exception as e:
            print(f"Yönetim verisi yükleme hatası: {e}")

    async def _refresh_yuk_list(self, filter_text=""):
        items = []
        filter_text = filter_text.lower()
        
        for idx, rule in enumerate(self.yuk_rules):
            key = rule.get('orjinal mesajdaki', '')
            if filter_text and filter_text not in key.lower():
                continue
                
            out = rule.get('kesin_cikti', {})
            subtitle = f"Yük: {out.get('YÜKÜN TİPİ', '-')}, Araç: {out.get('ARAÇ TİPİ', '-')}, Kasa: {out.get('KASA TİPİ', '-')}"
            
            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.INVENTORY_2, color=AppColors.PRIMARY),
                    title=ft.Text(key, weight="bold"),
                    subtitle=ft.Text(subtitle, size=12),
                    trailing=ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=AppColors.DANGER,
                        on_click=lambda e, i=idx: asyncio.create_task(self._delete_yuk_tanimi(i))
                    ),
                    bgcolor=AppColors.SURFACE,
                    border_radius=10,
                )
            )
        self.yuk_list_view.controls = items
        self.yuk_list_view.update()

    async def _filter_yuk(self, e):
        await self._refresh_yuk_list(e.control.value)

    async def _save_yuk_tanimi(self, e):
        try:
            keyword = self.keyword_field.value.strip().upper()
            if not keyword:
                self._show_error("Anahtar kelime boş olamaz!")
                return
            
            # Varyasyonları üret
            variants = generate_keyword_variants(keyword)
            # (Basitleştirme: Eski koddaki tüm mantığı Flet'e taşıyoruz)
            
            new_rule = {
                "orjinal mesajdaki": keyword,
                "priority": int(self.priority_field.value or 1000),
                "kesin_cikti": {
                    "YÜKÜN TİPİ": [self.yuk_type_dropdown.value] if self.yuk_type_dropdown.value else [],
                    "ARAÇ TİPİ": [self.arac_type_dropdown.value] if self.arac_type_dropdown.value else [],
                    "KASA TİPİ": [self.kasa_type_dropdown.value] if self.kasa_type_dropdown.value else []
                },
                "variants": variants
            }
            
            self.yuk_rules.append(new_rule)
            await self.data_service.save_yuk_tipleri(self.yuk_rules)
            
            # Temizlik ve yenileme
            self.keyword_field.value = ""
            await self._refresh_yuk_list()
            self._show_success(f"'{keyword}' ve {len(variants)} varyasyonu kaydedildi.")
            
        except Exception as e:
            self._show_error(f"Kaydetme hatası: {e}")

    async def _delete_yuk_tanimi(self, index):
        try:
            del self.yuk_rules[index]
            await self.data_service.save_yuk_tipleri(self.yuk_rules)
            await self._refresh_yuk_list()
            self._show_success("Tanım silindi.")
        except Exception as e:
            self._show_error(f"Silme hatası: {e}")

    def _show_error(self, msg):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=AppColors.DANGER)
        self.page.snack_bar.open = True
        self.page.update()

    def _show_success(self, msg):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=AppColors.SUCCESS)
        self.page.snack_bar.open = True
        self.page.update()

    async def get_view(self):
        # TabBar (Üst navigasyon) - Modern Stil
        self.tab_bar = ft.TabBar(
            tabs=[
            ft.Tab(text="Yük Tanımlama", icon=ft.Icons.INVENTORY_2_ROUNDED),
                ft.Tab(text="Mahalle Yönetimi", icon=ft.Icons.LOCATION_ON_ROUNDED),
                ft.Tab(text="Grup Ayarları", icon=ft.Icons.GROUPS_ROUNDED),
                ft.Tab(text="Kara Liste", icon=ft.Icons.BLOCK_ROUNDED),
            ],
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_MUTED,
            indicator_padding=5,
        )
        
        # TabBarView (İçerik alanı)
        self.tab_view = ft.TabBarView(
            controls=[
                self._setup_yuk_tanim(),
                await self._setup_mahalle(),
                self._setup_gruplar(),
                self._setup_kara_liste(),
            ],
            expand=True
        )

        # Tabs ana taşıyıcı
        tabs_container = ft.Tabs(
            content=ft.Column([
                ft.Container(self.tab_bar, bgcolor=AppColors.SURFACE, padding=ft.Padding.symmetric(vertical=0, horizontal=10)),
                ft.Container(self.tab_view, expand=True, padding=10)
            ], expand=True),
            length=4
        )

        content = ft.Column(
            [
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, color=AppColors.PRIMARY, size=18),
                        ft.Text("Yönetim Merkezi", size=24, weight="bold", color=AppColors.TEXT),
                    ]),
                    ft.IconButton(
                        icon=ft.Icons.SYNC,
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda _: asyncio.create_task(self._load_yuk_data()),
                        tooltip="Verileri Yenile"
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(color="white10", height=30),
                tabs_container,
            ],
            expand=True,
        )

        # İlk yükleme
        asyncio.create_task(self._load_yuk_data())
        return content

    def _setup_yuk_tanim(self):
        return ft.Row([
            # Sol taraf: Liste
            ft.Container(
                content=ft.Column([
                    ft.Container(self.search_entry, padding=ft.Padding.only(bottom=10)),
                    ft.Container(self.yuk_list_view, expand=True, bgcolor=AppColors.BG_DEEP, border_radius=12)
                ]),
                expand=2,
                padding=15,
                bgcolor=AppColors.SURFACE,
                border_radius=15,
                shadow=[AppStyles.CARD_SHADOW]
            ),
            # Sağ taraf: Form
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.ADD_BOX_ROUNDED, color=AppColors.SUCCESS),
                        ft.Text("Yeni Yük Tanımı", size=18, weight="bold", color=AppColors.TEXT),
                    ]),
                    ft.Divider(color="white10"),
                    self.keyword_field,
                    self.priority_field,
                    self.yuk_type_dropdown,
                    self.arac_type_dropdown,
                    self.kasa_type_dropdown,
                    ft.Button(
                        content="TANIMI KAYDET", 
                        icon=ft.Icons.SAVE,
                        bgcolor=AppColors.SUCCESS,
                        color="white", 
                        on_click=lambda e: asyncio.create_task(self._save_yuk_tanimi(e)),
                        width=float("inf"),
                        height=50
                    ),
                ], scroll=ft.ScrollMode.ADAPTIVE, spacing=15),
                expand=1,
                padding=20,
                bgcolor=AppColors.SURFACE,
                border_radius=15,
                shadow=[AppStyles.CARD_SHADOW],
            )
        ], expand=True, spacing=20)

    async def _setup_mahalle(self):
        # Mahalle UI Veri
        self.il_data = [] # il_ilçe_mahalle.json içeriği
        self.il_dropdown = ft.Dropdown(label="İl Seçin", expand=True)
        self.il_dropdown.on_select = self._on_il_change
        
        self.ilce_dropdown = ft.Dropdown(label="İlçe Seçin", expand=True)
        self.ilce_dropdown.on_select = self._on_ilce_change
        self.mahalle_list_view = ft.ListView(expand=True, spacing=5)
        self.new_mahalle_field = ft.TextField(label="Yeni Mahalle Adı", expand=True)

        asyncio.create_task(self._load_il_data())

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.LOCATION_ON_ROUNDED, color=AppColors.ACCENT, size=18),
                    ft.Text("Mahalle & Bölge Yönetimi", size=18, weight="bold", color=AppColors.TEXT),
                ]),
                ft.Divider(color="white10"),
                ft.Row([
                    self.il_dropdown,
                    self.ilce_dropdown
                ], spacing=10),
                ft.Row([
                    self.new_mahalle_field,
                    ft.IconButton(
                        icon=ft.Icons.ADD_LOCATION_ALT_ROUNDED,
                        icon_color="white",
                        bgcolor=AppColors.PRIMARY,
                        on_click=lambda _: asyncio.create_task(self._add_mahalle()),
                        tooltip="Mahalle Ekle"
                    )
                ], spacing=10),
                ft.Text("Kayıtlı Mahalleler", size=12, weight="bold", color=AppColors.TEXT_MUTED),
                ft.Container(
                    content=self.mahalle_list_view,
                    expand=True,
                    bgcolor=AppColors.BG_DEEP,
                    border_radius=12,
                    padding=5
                )
            ], spacing=15),
            padding=20,
            bgcolor=AppColors.SURFACE,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW],
        )

    # --- Asenkron Metodlar: Mahalle ---
    async def _load_il_data(self):
        try:
            self.il_data = await self.data_service.load_il_ilceler()
            self.il_dropdown.options = [ft.dropdown.Option(item['il']) for item in self.il_data]
            self.il_dropdown.update()
        except Exception as e:
            self._show_error(f"İl verisi yükleme hatası: {e}")

    def _on_il_change(self, e):
        il_name = self.il_dropdown.value
        ilceler = next((item['ilceler'] for item in self.il_data if item['il'] == il_name), [])
        self.ilce_dropdown.options = [ft.dropdown.Option(item['ilce']) for item in ilceler]
        self.ilce_dropdown.value = None
        self.mahalle_list_view.controls = []
        self.page.update()

    def _on_ilce_change(self, e):
        asyncio.create_task(self._refresh_mahalle_list())

    async def _refresh_mahalle_list(self):
        il_name = self.il_dropdown.value
        ilce_name = self.ilce_dropdown.value
        if not il_name or not ilce_name: return

        il_item = next((item for item in self.il_data if item['il'] == il_name), None)
        if not il_item: return
        
        ilce_item = next((item for item in il_item['ilceler'] if item['ilce'] == ilce_name), None)
        if not ilce_item: return

        items = []
        for m in ilce_item.get('mahalleler', []):
            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.LOCATION_ON, color=AppColors.ACCENT),
                    title=ft.Text(m),
                    trailing=ft.IconButton(icon=ft.Icons.DELETE, on_click=lambda e, mname=m: asyncio.create_task(self._delete_mahalle(mname)))
                )
            )
        self.mahalle_list_view.controls = items
        self.mahalle_list_view.update()

    async def _add_mahalle(self):
        mname = self.new_mahalle_field.value.strip()
        il_name = self.il_dropdown.value
        ilce_name = self.ilce_dropdown.value
        if not mname or not il_name or not ilce_name: return

        try:
            il_item = next((item for item in self.il_data if item['il'] == il_name), None)
            ilce_item = next((item for item in il_item['ilceler'] if item['ilce'] == ilce_name), None)
            
            if 'mahalleler' not in ilce_item: ilce_item['mahalleler'] = []
            if mname not in ilce_item['mahalleler']:
                ilce_item['mahalleler'].append(mname)
                # save_config kullan
                await self.data_service.save_config('il_ilce_mahalle', self.il_data)
                self.new_mahalle_field.value = ""
                await self._refresh_mahalle_list()
                self._show_success(f"'{mname}' mahallesi eklendi.")
        except Exception as e:
            self._show_error(f"Mahalle ekleme hatası: {e}")

    async def _delete_mahalle(self, mname):
        il_name = self.il_dropdown.value
        ilce_name = self.ilce_dropdown.value
        try:
            il_item = next((item for item in self.il_data if item['il'] == il_name), None)
            ilce_item = next((item for item in il_item['ilceler'] if item['ilce'] == ilce_name), None)
            
            if mname in ilce_item['mahalleler']:
                ilce_item['mahalleler'].remove(mname)
                await self.data_service.save_config('il_ilce_mahalle', self.il_data)
                await self._refresh_mahalle_list()
                self._show_success("Mahalle silindi.")
        except Exception as e:
            self._show_error(f"Mahalle silme hatası: {e}")

    def _setup_gruplar(self):
        # Grup Listesi UI
        self.groups_list_view = ft.ListView(expand=True, spacing=5)
        self.group_name_field = ft.TextField(label="Grup Adı", expand=True)
        self.group_id_field = ft.TextField(label="WhatsApp Group ID", expand=True)

        asyncio.create_task(self._load_groups_data())

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.GROUPS_ROUNDED, color=AppColors.PRIMARY, size=24),
                    ft.Text("WhatsApp Grup Yönetimi", size=18, weight="bold", color=AppColors.TEXT),
                ]),
                ft.Divider(color="white10"),
                ft.Row([
                    self.group_name_field,
                    self.group_id_field,
                    ft.IconButton(
                        icon=ft.Icons.ADD_ROUNDED,
                        bgcolor=AppColors.PRIMARY,
                        icon_color="white",
                        on_click=lambda _: asyncio.create_task(self._add_group())
                    )
                ], spacing=10),
                ft.Button(
                    content="WhatsApp'tan Grupları Çek", 
                    icon=ft.Icons.SYNC,
                    bgcolor=AppColors.PRIMARY,
                    color="white",
                    on_click=lambda _: asyncio.create_task(self._fetch_whatsapp_groups()),
                    width=float("inf"),
                    height=45
                ),
                ft.Text("Kayıtlı Gruplar", size=12, weight="bold", color=AppColors.TEXT_MUTED),
                ft.Container(
                    content=self.groups_list_view,
                    expand=True,
                    bgcolor=AppColors.BG_DEEP,
                    border_radius=12,
                    padding=5
                )
            ], spacing=15),
            padding=20,
            bgcolor=AppColors.SURFACE,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW],
        )

    def _setup_kara_liste(self):
        # Kara Liste UI
        self.blacklist_list_view = ft.ListView(expand=True, spacing=5)
        self.blacklist_field = ft.TextField(label="Telefon Numarası (Örn: 905xxxxxxxxx)", expand=True)

        asyncio.create_task(self._load_blacklist_data())

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.BLOCK_ROUNDED, color=AppColors.DANGER, size=18),
                    ft.Text("Müşteri Kara Listesi", size=18, weight="bold", color=AppColors.TEXT),
                ]),
                ft.Divider(color="white10"),
                ft.Row([
                    self.blacklist_field,
                    ft.IconButton(
                        icon=ft.Icons.PERSON_ADD_ROUNDED,
                        bgcolor=AppColors.DANGER,
                        icon_color="white",
                        on_click=lambda _: asyncio.create_task(self._add_blacklist())
                    )
                ], spacing=10),
                ft.Text("Engellenen Numaralar", size=12, weight="bold", color=AppColors.TEXT_MUTED),
                ft.Container(
                    content=self.blacklist_list_view,
                    expand=True,
                    bgcolor=AppColors.BG_DEEP,
                    border_radius=12,
                    padding=5
                )
            ], spacing=15),
            padding=20,
            bgcolor=AppColors.SURFACE,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW],
        )

    # --- Asenkron Metodlar: Kara Liste ---
    async def _load_blacklist_data(self):
        try:
            self.blacklist = await self.data_service.load_blacklist()
            items = []
            for phone in self.blacklist:
                items.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.BLOCK, color=AppColors.DANGER),
                        title=ft.Text(phone),
                        trailing=ft.IconButton(icon=ft.Icons.DELETE, on_click=lambda e, p=phone: asyncio.create_task(self._delete_blacklist(p)))
                    )
                )
            self.blacklist_list_view.controls = items
            self.blacklist_list_view.update()
        except Exception as e:
            self._show_error(f"Kara liste yükleme hatası: {e}")

    async def _add_blacklist(self):
        phone = self.blacklist_field.value.strip()
        if not phone: return
        try:
            self.blacklist.append(phone)
            await self.data_service.save_blacklist(self.blacklist)
            self.blacklist_field.value = ""
            await self._load_blacklist_data()
            self._show_success("Numara kara listeye eklendi.")
        except Exception as e:
            self._show_error(f"Ekleme hatası: {e}")

    async def _delete_blacklist(self, phone):
        try:
            self.blacklist.remove(phone)
            await self.data_service.save_blacklist(self.blacklist)
            await self._load_blacklist_data()
            self._show_success("Numara kara listeden çıkarıldı.")
        except Exception as e:
            self._show_error(f"Silme hatası: {e}")

    # --- Asenkron Metodlar: Gruplar ---
    async def _load_groups_data(self):
        try:
            self.groups = await self.data_service.load_saved_groups()
            items = []
            for group in self.groups:
                items.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.GROUPS, color=AppColors.PRIMARY),
                        title=ft.Text(group.get('name', 'Adsız Grup')),
                        subtitle=ft.Text(group.get('id', '-')),
                        trailing=ft.IconButton(icon=ft.Icons.DELETE, on_click=lambda e, g=group: asyncio.create_task(self._delete_group(g)))
                    )
                )
            self.groups_list_view.controls = items
            self.groups_list_view.update()
        except Exception as e:
            self._show_error(f"Grup yükleme hatası: {e}")

    async def _add_group(self):
        name = self.group_name_field.value.strip()
        gid = self.group_id_field.value.strip()
        if not name or not gid: return
        try:
            self.groups.append({"name": name, "id": gid})
            await self.data_service.save_groups(self.groups)
            self.group_name_field.value = ""
            self.group_id_field.value = ""
            await self._load_groups_data()
            self._show_success("Grup kaydedildi.")
        except Exception as e:
            self._show_error(f"Ekleme hatası: {e}")

    async def _delete_group(self, group_obj):
        try:
            self.groups.remove(group_obj)
            await self.data_service.save_groups(self.groups)
            await self._load_groups_data()
            self._show_success("Grup silindi.")
        except Exception as e:
            self._show_error(f"Silme hatası: {e}")

    async def _fetch_whatsapp_groups(self):
        try:
            self._show_success("API'den gruplar çekiliyor, lütfen bekleyin...")
            
            # Whapi fetcher'ı asenkron sarmalayıcı ile çağır
            from src.fetchers.whapi_fetcher import fetch_groups
            
            loop = asyncio.get_event_loop()
            all_groups = await loop.run_in_executor(None, fetch_groups)
            
            if not all_groups:
                self._show_error("WhatsApp'tan hiç grup çekilemedi. Token'ı kontrol edin.")
                return

            saved_ids = {g.get('id') for g in self.groups}
            
            # Dialog içeriği için liste oluştur
            choice_list = ft.ListView(expand=True, spacing=5, height=400)
            
            async def add_and_close(group_data):
                if group_data['id'] not in saved_ids:
                    self.groups.append({"name": group_data['name'], "id": group_data['id']})
                    await self.data_service.save_groups(self.groups)
                    await self._load_groups_data()
                self.page.dialog.open = False
                self.page.update()

            for g in all_groups:
                g_id = g.get('id', '')
                g_name = g.get('name') or g.get('subject', 'Adsız Grup')
                is_saved = g_id in saved_ids
                
                choice_list.controls.append(
                    ft.ListTile(
                        title=ft.Text(g_name, size=12),
                        subtitle=ft.Text(g_id, size=10),
                        trailing=ft.IconButton(
                            icon=ft.Icons.ADD_CIRCLE if not is_saved else ft.Icons.CHECK_CIRCLE,
                            icon_color=AppColors.SUCCESS if not is_saved else "grey",
                            disabled=is_saved,
                            on_click=lambda e, gd={'name': g_name, 'id': g_id}: asyncio.create_task(add_and_close(gd))
                        )
                    )
                )

            self.page.dialog = ft.AlertDialog(
                title=ft.Text("WhatsApp Grupları"),
                content=choice_list,
                actions=[
                    ft.TextButton("Kapat", on_click=lambda _: setattr(self.page.dialog, 'open', False) or self.page.update())
                ]
            )
            self.page.dialog.open = True
            self.page.update()
            
        except Exception as e:
            self._show_error(f"WhatsApp grup çekme hatası: {e}")
