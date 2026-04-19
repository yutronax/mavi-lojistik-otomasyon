import flet as ft
import asyncio
import os
from datetime import datetime
from src.gui.styles import AppColors, AppStyles
from src.services.data_service import DataService
from src.services.data_service_async import AsyncDataService
from src.services.submission_queue import SubmissionQueue

class OperationCenterPage:
    def __init__(self, page: ft.Page):
        self.page = page
        # Root dizini belirle
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        self.data_service = AsyncDataService(DataService(self.root_dir))
        
        # UI State
        self.messages_cache = {}
        self.sorted_message_ids = []
        self.current_msg_index = 0
        self.service_process = None
        self.submitter = None
        self.submission_queue = None
        
        # Filtre Seçenekleri
        self.time_filter = ft.Dropdown(
            label="Zaman",
            options=[
                ft.dropdown.Option("10", "Son 10 Dakika"),
                ft.dropdown.Option("60", "Son 1 Saat"),
                ft.dropdown.Option("1440", "Bugün"),
                ft.dropdown.Option("all", "Tümü")
            ],
            value="all",
            width=150
        )
        self.time_filter.on_select = lambda _: asyncio.create_task(self.load_data())

        # --- SOL PANEL: Orijinal Mesaj ---
        self.orig_msg_text = ft.Text("Mesaj seçilmedi", size=12, color=AppColors.TEXT_MUTED)
        self.msg_nav_text = ft.Text("0/0", size=11, color="grey")
        
        self.left_pane = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.DESCRIPTION, color=AppColors.ACCENT, size=20),
                    ft.Text("ORİJİNAL MESAJ", size=14, weight="bold", color=AppColors.TEXT),
                    self.msg_nav_text
                ], alignment=ft.MainAxisAlignment.START),
                ft.Divider(color="white10"),
                ft.Container(
                    content=ft.Column([self.orig_msg_text], scroll=ft.ScrollMode.ALWAYS),
                    bgcolor=AppColors.BG_DEEP,
                    padding=15,
                    border_radius=12,
                    border=ft.Border.all(width=1, color="white10"),
                    height=450,
                ),
                ft.Row([
                    ft.IconButton(icon=ft.Icons.ARROW_BACK_IOS, on_click=lambda _: self.navigate_message(-1), icon_size=24, icon_color=AppColors.PRIMARY),
                    ft.IconButton(icon=ft.Icons.ARROW_FORWARD_IOS, on_click=lambda _: self.navigate_message(1), icon_size=24, icon_color=AppColors.PRIMARY),
                ], alignment=ft.MainAxisAlignment.CENTER)
            ], spacing=15),
            width=320,
            bgcolor=AppColors.SURFACE,
            padding=20,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW]
        )

        # --- ORTA PANEL: Sevkiyat Listesi (Yeni ListView Yapısı) ---
        self.shipments_list = ft.ListView(
            expand=True,
            spacing=10,
            padding=10,
        )

        self.center_pane = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.LIST_ALT, color=AppColors.PRIMARY, size=24),
                        ft.Text("SEVKİYAT LİSTESİ", size=18, weight="bold", color=AppColors.TEXT),
                    ]),
                    ft.Row([
                        self.time_filter,
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            on_click=lambda _: asyncio.create_task(self.load_data()),
                            tooltip="Yenile"
                        )
                    ])
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(color="white10"),
                ft.Container(
                    content=self.shipments_list,
                    expand=True,
                )
            ]),
            expand=True,
            bgcolor=AppColors.SURFACE,
            padding=20,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW]
        )

        # --- SAĞ PANEL: İşlemler ve Durum ---
        self.msg_count_text = ft.Text("0", size=18, weight="bold")
        self.pending_count_text = ft.Text("0", size=18, weight="bold")
        self.service_status_text = ft.Text("Servis Durdu", color=AppColors.TEXT_MUTED, size=12)
        self.service_status_icon = ft.Icon(ft.Icons.FIBER_MANUAL_RECORD, color="grey", size=12)

        self.right_pane = ft.Container(
            content=ft.Column([
                ft.Text("İSTATİSTİKLER", size=14, weight="bold", color=AppColors.TEXT_MUTED),
                ft.Divider(color="white10"),
                self._create_mini_stat("Mesajlar", self.msg_count_text, ft.Icons.MESSAGE),
                self._create_mini_stat("Bekleyen", self.pending_count_text, ft.Icons.HOURGLASS_EMPTY),
                
                ft.Divider(color="white10"),
                ft.Text("SERVİS YÖNETİMİ", size=12, weight="bold", color=AppColors.TEXT_MUTED),
                ft.Container(
                    content=ft.Row([self.service_status_icon, self.service_status_text], spacing=8),
                    padding=10,
                    bgcolor="white10",
                    border_radius=8
                ),
                ft.Column([
                    ft.Button(
                        content="SERVİSİ BAŞLAT", 
                        icon=ft.Icons.PLAY_ARROW,
                        bgcolor=AppColors.SUCCESS,
                        color="white",
                        on_click=lambda _: asyncio.create_task(self.start_service()),
                        width=float("inf"),
                        height=45
                    ),
                    ft.Button(
                        content="SERVİSİ DURDUR", 
                        icon=ft.Icons.STOP,
                        bgcolor=AppColors.DANGER,
                        color="white",
                        on_click=lambda _: asyncio.create_task(self.stop_service()),
                        width=float("inf"),
                        height=45
                    ),
                ], spacing=10),
            ], spacing=20),
            width=260,
            bgcolor=AppColors.SURFACE,
            padding=20,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW]
        )

    def _create_mini_stat(self, label, value_ctrl, icon_name):
        return ft.Container(
            content=ft.Row([
                ft.Icon(icon_name, color=AppColors.PRIMARY, size=24),
                ft.Column([
                    ft.Text(label, size=10, color=AppColors.TEXT_MUTED),
                    value_ctrl
                ], spacing=0)
            ], alignment=ft.MainAxisAlignment.START, spacing=15),
            bgcolor="white10",
            padding=ft.Padding.all(15),
            border_radius=12,
            border=ft.Border.all(width=1, color="white10")
        )

    async def _init_queue_async(self):
        def setup():
            try:
                from tools.submit_approved_loads import YukBuradaSubmitter
                self.submitter = YukBuradaSubmitter()
                self.submission_queue = SubmissionQueue(self.submitter)
                self.submission_queue.start()
            except Exception as e:
                print(f"DEBUG: Kuyruk hatasi: {e}")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, setup)

    async def load_data(self):
        try:
            if self.submitter is None:
                await self._init_queue_async()
            
            hours = 24
            if self.time_filter.value == "10": hours = 1/6 # 10 dk
            elif self.time_filter.value == "60": hours = 1
            elif self.time_filter.value == "all": hours = 24 * 30 # 30 gün
            
            print(f"DEBUG: Yüklenen saat filtresi: {hours}")
            self.messages_cache = await self.data_service.load_unprocessed_messages(hours_back=hours)
            print(f"DEBUG: messages_cache boyutu: {len(self.messages_cache)}")
            self.sorted_message_ids = sorted(self.messages_cache.keys(), reverse=True)
            
            if self.sorted_message_ids and self.current_msg_index >= len(self.sorted_message_ids):
                self.current_msg_index = 0
                
            new_controls = []
            pending_count = 0
            
            # Performans için sadece en güncel 100 mesajı göster
            limit = 100
            displayed_count = 0
            
            for mid in self.sorted_message_ids:
                msg = self.messages_cache[mid]
                shipments = msg.get('shipments', [])
                pending_count += len(shipments)
                
                if displayed_count < limit:
                    for idx, s in enumerate(shipments):
                        if displayed_count >= limit: break
                        
                        # Her sevkiyat için hafif bir kart (row container) oluştur
                        row_item = ft.Container(
                            content=ft.Row([
                                ft.Column([
                                    ft.Text(f"{s.get('nerden_il', '')} → {s.get('nereye_il', '')}", weight="bold", size=14),
                                    ft.Text(f"{s.get('arac_tipi', [''])[0]} / {s.get('yuk_tipi', [''])[0]}", size=11, color=AppColors.TEXT_MUTED),
                                ], expand=True, spacing=2),
                                ft.Text(s.get('fiyat', ''), color=AppColors.ACCENT, weight="bold", size=13),
                                ft.VerticalDivider(width=1, color="white10"),
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.Icons.CHECK_CIRCLE_OUTLINE, 
                                        icon_color=AppColors.SUCCESS, 
                                        icon_size=20,
                                        on_click=lambda _, mid=mid, idx=idx: asyncio.create_task(self.confirm_shipment(mid, idx)),
                                        tooltip="Onayla"
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_NOTE_ROUNDED, 
                                        icon_color=AppColors.WARNING, 
                                        icon_size=20,
                                        on_click=lambda _, mid=mid, idx=idx: self.open_edit_dialog(mid, idx),
                                        tooltip="Düzenle"
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_SWEEP_OUTLINED, 
                                        icon_color=AppColors.DANGER, 
                                        icon_size=20,
                                        on_click=lambda _, mid=mid, idx=idx: asyncio.create_task(self.delete_shipment(mid, idx)),
                                        tooltip="Sil"
                                    ),
                                ], spacing=0)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            padding=ft.Padding.symmetric(horizontal=15, vertical=10),
                            bgcolor=ft.Colors.with_opacity(0.05, "white"),
                            border_radius=10,
                            on_click=lambda _, m_id=mid: self.select_message_by_id(m_id),
                        )
                        new_controls.append(row_item)
                        displayed_count += 1
            
            self.shipments_list.controls = new_controls
            self.msg_count_text.value = str(len(self.messages_cache))
            self.pending_count_text.value = str(pending_count)
            self._update_nav_text()
            self.page.update()
            print("DEBUG: load_data başarıyla tamamlandı, UI güncellendi.")
            
        except Exception as e:
            print(f"DEBUG: load_data hatasi: {e}")

    def select_message_by_id(self, mid):
        if mid in self.sorted_message_ids:
            self.current_msg_index = self.sorted_message_ids.index(mid)
            self.show_message_detail(self.messages_cache[mid])
            self._update_nav_text()

    def navigate_message(self, delta):
        if not self.sorted_message_ids: return
        self.current_msg_index = (self.current_msg_index + delta) % len(self.sorted_message_ids)
        mid = self.sorted_message_ids[self.current_msg_index]
        self.show_message_detail(self.messages_cache[mid])
        self._update_nav_text()

    def _update_nav_text(self):
        total = len(self.sorted_message_ids)
        current = self.current_msg_index + 1 if total > 0 else 0
        self.msg_nav_text.value = f"{current}/{total}"
        self.page.update()

    def show_message_detail(self, msg):
        body = msg.get('body') or msg.get('text') or msg.get('orjinal_mesaj', "İçerik yok")
        self.orig_msg_text.value = body
        self.page.update()

    def open_edit_dialog(self, mid, idx):
        msg = self.messages_cache.get(mid)
        if not msg: return
        shipment = msg['shipments'][idx]
        
        nerden = ft.TextField(label="Nereden", value=shipment.get('nerden', ''), border_radius=10)
        nereye = ft.TextField(label="Nereye", value=shipment.get('nereye', ''), border_radius=10)
        fiyat = ft.TextField(label="Fiyat", value=shipment.get('fiyat', ''), border_radius=10)
        
        async def save_edit(e):
            shipment['nerden'] = nerden.value
            shipment['nereye'] = nereye.value
            shipment['fiyat'] = fiyat.value
            await self.data_service.save_unprocessed_messages(self.messages_cache)
            self.page.dialog.open = False
            await self.load_data()

        self.page.dialog = ft.AlertDialog(
            title=ft.Text("Sevkiyatı Düzenle"),
            content=ft.Column([nerden, nereye, fiyat], tight=True),
            actions=[
                ft.TextButton("İptal", on_click=lambda _: setattr(self.page.dialog, 'open', False) or self.page.update()),
                ft.Button(content="Kaydet", bgcolor=AppColors.SUCCESS, color="white", on_click=save_edit)
            ]
        )
        self.page.dialog.open = True
        self.page.update()

    async def confirm_shipment(self, mid, idx):
        # ... Mantik ayni, hizli guncelleme ...
        try:
            msg = self.messages_cache.get(mid)
            if not msg: return
            shipment = msg['shipments'][idx]
            shipment['onay_tarihi'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if self.submission_queue: self.submission_queue.add_task(shipment)
            await self.data_service.save_approved_records([shipment])
            del msg['shipments'][idx]
            if not msg['shipments']: await self.data_service.delete_unprocessed_message(mid)
            await self.load_data()
        except: pass

    async def delete_shipment(self, mid, idx):
        try:
            msg = self.messages_cache.get(mid)
            if not msg: return
            del msg['shipments'][idx]
            if not msg['shipments']: await self.data_service.delete_unprocessed_message(mid)
            await self.load_data()
        except: pass

    async def start_service(self):
        if self.service_process: return
        import subprocess, sys
        cmd = [sys.executable, os.path.join(self.root_dir, "src", "parsers", "veri_cekici_ayristirici.py")]
        self.service_process = subprocess.Popen(cmd, cwd=self.root_dir)
        self.service_status_icon.color = AppColors.SUCCESS
        self.service_status_text.value = "Servis Çalışıyor"
        self.page.update()

    async def stop_service(self):
        if not self.service_process: return
        self.service_process.terminate()
        self.service_process = None
        self.service_status_icon.color = "grey"
        self.service_status_text.value = "Servis Durdu"
        self.page.update()

    async def get_view(self):
        # İlk yükleme
        asyncio.create_task(self.load_data())
        
        return ft.Row(
            [
                self.left_pane,
                self.center_pane,
                self.right_pane
            ],
            spacing=15,
            expand=True
        )
