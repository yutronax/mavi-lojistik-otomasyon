import flet as ft
import asyncio
import os
from datetime import datetime, timedelta
from src.gui.styles import AppColors, AppStyles
from src.services.data_service import DataService
from src.services.data_service_async import AsyncDataService
from src.services.submission_queue import SubmissionQueue
from src.utils.phone_utils import normalize_phone
from src.utils.validators import validate_shipment as _validate_shipment_fields


def _safe_list(v):
    """Değeri liste olarak döndür (str veya list)."""
    if isinstance(v, list):
        return v
    if v:
        return [str(v)]
    return []


def _first(lst):
    """Listenin ilk elemanını döndür, yoksa boş string."""
    return lst[0] if lst else ""


class OperationCenterPage:
    def __init__(self, page: ft.Page):
        self.page = page
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        self.data_service = AsyncDataService(DataService(self.root_dir))

        # UI State
        self.messages_cache = {}
        self.sorted_message_ids = []
        self.current_msg_index = 0
        self.selected_mid = None
        self.service_process = None
        self.submitter = None
        self.submission_queue = None
        self._is_loading = False
        self._init_done = False
        self._base_options = {}  # arac/kasa/yuk tipleri
        self.il_ilceler_data = []
        self.approved_records = []
        self.deleted_history = []
        self.selected_shipment_indices = set()

        # --- Filtre ---
        self.time_filter = ft.Dropdown(
            label="Zaman",
            options=[
                ft.dropdown.Option("10", "Son 10 Dakika"),
                ft.dropdown.Option("60", "Son 1 Saat"),
                ft.dropdown.Option("1440", "Bugün"),
                ft.dropdown.Option("all", "Tümü"),
            ],
            value="all",
            width=150,
        )
        self.time_filter.on_select = lambda _: asyncio.create_task(self.load_data())

        # ================================================================
        # SOL PANEL: Mesaj Listesi + Orijinal Mesaj Metni
        # ================================================================
        self.messages_list = ft.ListView(spacing=5, padding=6)
        self.orig_msg_text = ft.Text(
            "Bir mesaj seçin...", size=11, color=AppColors.TEXT_MUTED
        )
        self.msg_meta_text = ft.Text("", size=10, color=AppColors.TEXT_MUTED, italic=True)
        self.msg_nav_text = ft.Text("0/0", size=11, color="grey")

        _btn_style_primary = ft.ButtonStyle(
            overlay_color={
                ft.ControlState.HOVERED: ft.Colors.with_opacity(0.12, AppColors.PRIMARY),
                ft.ControlState.PRESSED: ft.Colors.with_opacity(0.25, AppColors.PRIMARY),
            }
        )

        self.left_pane = ft.Container(
            content=ft.Column(
                [
                    # Başlık
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.INBOX_ROUNDED, color=AppColors.ACCENT, size=18),
                            ft.Text(
                                "GELEN MESAJLAR", size=13, weight="bold", color=AppColors.TEXT
                            ),
                            self.msg_nav_text,
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    ft.Divider(color="white10"),
                    # Mesaj listesi (kaydırılabilir)
                    ft.Container(
                        content=self.messages_list,
                        expand=True,
                        bgcolor=AppColors.BG_DEEP,
                        border_radius=10,
                        padding=4,
                    ),
                    # Navigasyon okları
                    ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.ARROW_BACK_IOS,
                                on_click=lambda _: self.navigate_message(-1),
                                icon_size=20,
                                icon_color=AppColors.PRIMARY,
                                tooltip="Önceki Mesaj",
                                style=_btn_style_primary,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                on_click=lambda _: self.delete_current_message(),
                                icon_size=20,
                                icon_color=AppColors.DANGER,
                                tooltip="Mesajı Sil",
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ARROW_FORWARD_IOS,
                                on_click=lambda _: self.navigate_message(1),
                                icon_size=20,
                                icon_color=AppColors.PRIMARY,
                                tooltip="Sonraki Mesaj",
                                style=_btn_style_primary,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    # Orijinal mesaj bölümü
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.DESCRIPTION, color=AppColors.ACCENT, size=14),
                            ft.Text(
                                "ORİJİNAL MESAJ",
                                size=11,
                                weight="bold",
                                color=AppColors.TEXT_MUTED,
                            ),
                        ]
                    ),
                    self.msg_meta_text,
                    ft.Container(
                        content=ft.Column(
                            [self.orig_msg_text], scroll=ft.ScrollMode.ALWAYS
                        ),
                        bgcolor=AppColors.BG_DEEP,
                        padding=12,
                        border_radius=10,
                        border=ft.Border.all(width=1, color="white10"),
                        height=220,
                    ),
                ],
                spacing=10,
                expand=True,
            ),
            width=300,
            bgcolor=AppColors.SURFACE,
            padding=15,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW],
        )

        # ================================================================
        # ORTA PANEL: Seçili Mesajın Sevkiyatları
        # ================================================================
        self.shipments_list = ft.ListView(expand=True, spacing=10, padding=10)
        self.center_header_text = ft.Text(
            "SEVKİYAT LİSTESİ", size=16, weight="bold", color=AppColors.TEXT
        )

        self.center_pane = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.LIST_ALT, color=AppColors.PRIMARY, size=22),
                                    self.center_header_text,
                                    ft.IconButton(
                                        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                                        icon_color=AppColors.SUCCESS,
                                        on_click=lambda _: self.add_new_shipment(),
                                        tooltip="Yeni Sevkiyat Ekle",
                                        icon_size=20
                                    ),
                                ]
                            ),
                            ft.Row(
                                [
                                    self.time_filter,
                                    ft.IconButton(
                                        icon=ft.Icons.FILTER_ALT_OFF,
                                        on_click=lambda _: self._reset_time_filter(),
                                        tooltip="Filtreyi Sıfırla",
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.REFRESH,
                                        on_click=lambda _: asyncio.create_task(
                                            self.load_data()
                                        ),
                                        tooltip="Yenile",
                                        style=ft.ButtonStyle(
                                            overlay_color={
                                                ft.ControlState.HOVERED: ft.Colors.with_opacity(
                                                    0.1, AppColors.PRIMARY
                                                ),
                                                ft.ControlState.PRESSED: ft.Colors.with_opacity(
                                                    0.2, AppColors.PRIMARY
                                                ),
                                            }
                                        ),
                                    ),
                                ]
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(color="white10"),
                    ft.Container(content=self.shipments_list, expand=True),
                ]
            ),
            expand=True,
            bgcolor=AppColors.SURFACE,
            padding=20,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW],
        )

        # ================================================================
        # SAĞ PANEL: İstatistikler + Servis Kontrolü
        # ================================================================
        self.msg_count_text = ft.Text("0", size=18, weight="bold")
        self.pending_count_text = ft.Text("0", size=18, weight="bold")
        self.service_status_text = ft.Text(
            "Servis Durdu", color=AppColors.TEXT_MUTED, size=12
        )
        self.service_status_icon = ft.Icon(
            ft.Icons.FIBER_MANUAL_RECORD, color="grey", size=12
        )

        _btn_style_white = ft.ButtonStyle(
            overlay_color={
                ft.ControlState.HOVERED: ft.Colors.with_opacity(0.18, "white"),
                ft.ControlState.PRESSED: ft.Colors.with_opacity(0.35, "white"),
            }
        )

        self.right_pane = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "İSTATİSTİKLER", size=14, weight="bold", color=AppColors.TEXT_MUTED
                    ),
                    ft.Divider(color="white10"),
                    self._create_mini_stat("Mesajlar", self.msg_count_text, ft.Icons.MESSAGE),
                    self._create_mini_stat(
                        "Bekleyen", self.pending_count_text, ft.Icons.HOURGLASS_EMPTY
                    ),
                    ft.Divider(color="white10"),
                    ft.Text(
                        "SERVİS YÖNETİMİ", size=12, weight="bold", color=AppColors.TEXT_MUTED
                    ),
                    ft.Container(
                        content=ft.Row(
                            [self.service_status_icon, self.service_status_text], spacing=8
                        ),
                        padding=10,
                        bgcolor="white10",
                        border_radius=8,
                    ),
                    ft.Column(
                        [
                            ft.Button(
                                content="SERVİSİ BAŞLAT",
                                icon=ft.Icons.PLAY_ARROW,
                                bgcolor=AppColors.SUCCESS,
                                color="white",
                                on_click=lambda _: asyncio.create_task(self.start_service()),
                                width=float("inf"),
                                height=45,
                                style=_btn_style_white,
                            ),
                            ft.Button(
                                content="SERVİSİ DURDUR",
                                icon=ft.Icons.STOP,
                                bgcolor=AppColors.DANGER,
                                color="white",
                                on_click=lambda _: asyncio.create_task(self.stop_service()),
                                width=float("inf"),
                                height=45,
                                style=_btn_style_white,
                            ),
                        ],
                        spacing=10,
                    ),
                ],
                spacing=20,
            ),
            width=240,
            bgcolor=AppColors.SURFACE,
            padding=20,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW],
        )

    # ------------------------------------------------------------------
    # Yardımcı: Mini stat kartı
    # ------------------------------------------------------------------
    def _create_mini_stat(self, label, value_ctrl, icon_name):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon_name, color=AppColors.PRIMARY, size=24),
                    ft.Column(
                        [ft.Text(label, size=10, color=AppColors.TEXT_MUTED), value_ctrl],
                        spacing=0,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=15,
            ),
            bgcolor="white10",
            padding=ft.Padding.all(15),
            border_radius=12,
            border=ft.Border.all(width=1, color="white10"),
        )

    def _safe_update(self, ctrl):
        try:
            ctrl.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Kuyruk başlatma
    # ------------------------------------------------------------------
    async def _init_queue_async(self):
        if self._init_done:
            return
        self._init_done = True

        def setup():
            try:
                from tools.submit_approved_loads import YukBuradaSubmitter

                self.submitter = YukBuradaSubmitter()
                self.submission_queue = SubmissionQueue(self.submitter)
                self.submission_queue.start()
            except Exception as e:
                print(f"DEBUG: Kuyruk hatasi: {e}")
                self._init_done = False

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, setup)

    # ------------------------------------------------------------------
    # Veri Yükleme
    # ------------------------------------------------------------------
    async def load_data(self):
        if self._is_loading:
            return
        self._is_loading = True

        try:
            if self.submitter is None and not self._init_done:
                await self._init_queue_async()

            # Temel seçenekleri yükle (edit dialog için)
            if not self._base_options:
                try:
                    self._base_options = await self.data_service.load_arac_kasa_tipleri()
                    self.il_ilceler_data = await self.data_service.load_il_ilceler()
                    self.approved_records = await self.data_service.load_approved_records()
                except Exception:
                    pass

            hours = 24
            if self.time_filter.value == "10":
                hours = 1 / 6
            elif self.time_filter.value == "60":
                hours = 1
            elif self.time_filter.value == "all":
                hours = 24 * 30

            self.messages_cache = await self.data_service.load_unprocessed_messages(
                hours_back=hours
            )
            self.sorted_message_ids = sorted(self.messages_cache.keys(), reverse=True)

            if (
                self.sorted_message_ids
                and self.current_msg_index >= len(self.sorted_message_ids)
            ):
                self.current_msg_index = 0

            # Sol panel: mesaj listesini güncelle
            self._refresh_messages_list()

            # Seçili mesaj hala geçerliyse sadece sevkiyatları tazele
            if self.selected_mid and self.selected_mid in self.messages_cache:
                self._update_shipments_for_message(self.selected_mid)
                self._update_message_display()
            elif self.sorted_message_ids:
                self._select_message(self.sorted_message_ids[0])
            else:
                self._show_empty_center()

            # Sayaçlar
            total_pending = sum(
                len(m.get("shipments", [])) for m in self.messages_cache.values()
            )
            self.msg_count_text.value = str(len(self.messages_cache))
            self.pending_count_text.value = str(total_pending)
            self._update_nav_text()

            try:
                self.page.update()
            except Exception as e:
                if "session" not in str(e).lower() and "destroyed" not in str(e).lower():
                    print(f"DEBUG: OperationCenter update error: {e}")

        except Exception as e:
            if "destroyed session" not in str(e).lower():
                print(f"DEBUG: load_data hatasi: {e}")
        finally:
            self._is_loading = False

    # ------------------------------------------------------------------
    # Mesaj Listesi (Sol Panel)
    # ------------------------------------------------------------------
    def _refresh_messages_list(self):
        items = []
        for mid in self.sorted_message_ids:
            msg = self.messages_cache[mid]
            shipments = msg.get("shipments", [])
            is_selected = mid == self.selected_mid

            # Zaman
            dt = self._get_message_datetime(msg)
            time_str = dt.strftime("%H:%M") if dt else ""

            # Mesaj önizlemesi
            body = msg.get("body") or msg.get("text") or msg.get("orjinal_mesaj", "")
            preview = (body[:65] + "…") if len(body) > 65 else body

            badge_color = AppColors.PRIMARY if shipments else "grey600"

            items.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        time_str,
                                        size=10,
                                        color=AppColors.ACCENT,
                                        weight="bold",
                                    ),
                                    ft.Container(
                                        content=ft.Text(
                                            f"{len(shipments)} sevk.",
                                            size=10,
                                            color="white",
                                        ),
                                        bgcolor=badge_color,
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=10,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(
                                preview,
                                size=10,
                                color=AppColors.TEXT,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=4,
                    ),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    bgcolor=(
                        ft.Colors.with_opacity(0.15, AppColors.PRIMARY)
                        if is_selected
                        else ft.Colors.with_opacity(0.04, "white")
                    ),
                    border_radius=8,
                    border=ft.Border.all(
                        1, AppColors.PRIMARY if is_selected else "transparent"
                    ),
                    on_click=lambda e, m=mid: self._select_message(m),
                    ink=True,
                )
            )

        self.messages_list.controls = items
        self._safe_update(self.messages_list)

    # ------------------------------------------------------------------
    # Mesaj Seçimi
    # ------------------------------------------------------------------
    def _select_message(self, mid: str):
        self.selected_mid = mid
        if mid in self.sorted_message_ids:
            self.current_msg_index = self.sorted_message_ids.index(mid)
        self._update_message_display()
        self._update_shipments_for_message(mid)
        self._update_nav_text()
        self._refresh_messages_list()  # Seçili highlight'ı güncelle

    def navigate_message(self, direction):
        if not self.sorted_message_ids:
            return
        
        count = len(self.sorted_message_ids)
        if count == 0:
            return
            
        self.current_msg_index = (self.current_msg_index + direction) % count
        mid = self.sorted_message_ids[self.current_msg_index]
        self._select_message(mid)

    def _update_nav_text(self):
        total = len(self.sorted_message_ids)
        current = self.current_msg_index + 1 if total > 0 else 0
        self.msg_nav_text.value = f"{current}/{total}"
        self._safe_update(self.msg_nav_text)

    # ------------------------------------------------------------------
    # Orijinal Mesaj Metni (Sol Panel Alt)
    # ------------------------------------------------------------------
    def _update_message_display(self):
        if not self.selected_mid or self.selected_mid not in self.messages_cache:
            self.orig_msg_text.value = "Mesaj seçilmedi"
            self.msg_meta_text.value = ""
            return

        msg = self.messages_cache[self.selected_mid]
        body = (
            msg.get("body") or msg.get("text") or msg.get("orjinal_mesaj", "İçerik yok")
        )
        self.orig_msg_text.value = body

        # Meta bilgiler
        group = msg.get("group_name") or msg.get("group", "")
        sender = msg.get("sender") or msg.get("from", "")
        ts = msg.get("timestamp") or msg.get("time", "")
        time_str = ""
        if ts:
            try:
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts)
                else:
                    dt = datetime.strptime(str(ts).replace("T", " ")[:19], "%Y-%m-%d %H:%M:%S")
                time_str = dt.strftime("%d.%m %H:%M")
            except Exception:
                pass

        parts = []
        if group:
            parts.append(f"📱 {group}")
        if sender:
            parts.append(f"👤 {sender}")
        if time_str:
            parts.append(f"🕐 {time_str}")
        self.msg_meta_text.value = "  |  ".join(parts)

        self._safe_update(self.orig_msg_text)
        self._safe_update(self.msg_meta_text)

    # ------------------------------------------------------------------
    # Sevkiyat Listesi (Orta Panel) – Sadece seçili mesajın sevkiyatları
    # ------------------------------------------------------------------
    def _update_shipments_for_message(self, mid: str):
        msg = self.messages_cache.get(mid)
        if not msg:
            self._show_empty_center()
            return

        shipments = msg.get("shipments", [])
        if not shipments:
            self.shipments_list.controls = [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(
                                ft.Icons.LOCAL_SHIPPING_OUTLINED,
                                color=AppColors.TEXT_MUTED,
                                size=48,
                            ),
                            ft.Text(
                                "Bu mesajda bekleyen sevkiyat yok",
                                color=AppColors.TEXT_MUTED,
                                size=14,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    alignment=ft.alignment.Alignment(0, 0),
                    expand=True,
                    padding=50,
                )
            ]
            self._safe_update(self.shipments_list)
            return

        # --- Adım 7: Çoklu Seçim & Toplu İşlem Üst Çubuğu ---
        top_bar = ft.Container(
            content=ft.Row(
                [
                    ft.Checkbox(
                        label="Tümünü Seç",
                        value=len(self.selected_shipment_indices) == len(shipments) and len(shipments) > 0,
                        on_change=lambda e: self.toggle_select_all(e.control.value),
                        fill_color=AppColors.SUCCESS
                    ),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "Çoklu Düzenle",
                                icon=ft.Icons.EDIT_NOTE,
                                color="white",
                                bgcolor=AppColors.WARNING,
                                on_click=lambda _: self.open_bulk_edit_dialog(),
                                visible=len(self.selected_shipment_indices) > 0
                            ),
                            ft.ElevatedButton(
                                f"Seçilenleri Onayla ({len(self.selected_shipment_indices)})",
                                icon=ft.Icons.DONE_ALL,
                                color="white",
                                bgcolor=AppColors.SUCCESS,
                                on_click=lambda _: asyncio.create_task(self.confirm_selected_shipments()),
                                visible=len(self.selected_shipment_indices) > 0
                            )
                        ],
                        spacing=10
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            margin=ft.Margin.only(bottom=10)
        )
        
        new_controls = [top_bar]
        for idx, s in enumerate(shipments):
            # Checkbox state
            is_checked = idx in self.selected_shipment_indices
            nerden_il = s.get("nerden_il") or s.get("nereden_il", "")
            nerden_ilce = s.get("nerden_ilce") or s.get("nereden_ilce", "")
            nereye_il = s.get("nereye_il", "")
            nereye_ilce = s.get("nereye_ilce", "")

            from_str = nerden_il + (f"/{nerden_ilce}" if nerden_ilce else "")
            to_str = nereye_il + (f"/{nereye_ilce}" if nereye_ilce else "")
            route_str = f"{from_str}  →  {to_str}" if from_str or to_str else "Güzergah belirtilmemiş"

            arac_list = _safe_list(s.get("arac_tipi", []))
            kasa_list = _safe_list(s.get("kasa_tipi", []))
            yuk_list = _safe_list(s.get("yuk_tipi", []))

            tags = []
            for v in arac_list:
                if v:
                    tags.append(("🚛", v, AppColors.PRIMARY))
            for v in kasa_list:
                if v:
                    tags.append(("📦", v, AppColors.ACCENT))
            for v in yuk_list:
                if v:
                    tags.append(("⚡", v, AppColors.WARNING))

            fiyat = s.get("fiyat", "")
            telefon = s.get("telefon", "")
            aciklama = s.get("aciklama", "")
            isim = s.get("isim", "")

            tag_controls = [
                ft.Container(
                    content=ft.Text(f"{emoji} {val}", size=11, color="white"),
                    bgcolor=ft.Colors.with_opacity(0.18, color),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                    border_radius=20,
                )
                for emoji, val, color in tags
            ]

            secondary_row = ft.Row(
                [
                    *tag_controls,
                    ft.Container(expand=True),
                    ft.Text(telefon, size=11, color=AppColors.TEXT_MUTED) if telefon else ft.Container(),
                ],
                spacing=6,
                wrap=True,
            ) if (tag_controls or telefon) else ft.Container()

            aciklama_row = (
                ft.Text(aciklama, size=11, color=AppColors.TEXT_MUTED, italic=True)
                if aciklama
                else ft.Container()
            )

            def _icon_btn(icon, color, tooltip, callback):
                return ft.IconButton(
                    icon=icon,
                    icon_color=color,
                    icon_size=22,
                    tooltip=tooltip,
                    on_click=callback,
                    style=ft.ButtonStyle(
                        overlay_color={
                            ft.ControlState.HOVERED: ft.Colors.with_opacity(0.1, color),
                            ft.ControlState.PRESSED: ft.Colors.with_opacity(0.22, color),
                        }
                    ),
                )

            card = ft.Container(
                content=ft.Column(
                    [
                        # Başlık satırı: rota + işlemler
                        ft.Row(
                            [
                                ft.Row(
                                    [
                                        ft.Checkbox(
                                            value=is_checked,
                                            on_change=lambda e, i=idx: self.toggle_shipment_selection(i, e.control.value),
                                            fill_color=AppColors.SUCCESS
                                        ),
                                        ft.Icon(
                                            ft.Icons.ROUTE_ROUNDED,
                                            color=AppColors.ACCENT,
                                            size=18,
                                        ),
                                        ft.Column(
                                            [
                                                ft.Text(
                                                    route_str,
                                                    weight="bold",
                                                    size=14,
                                                    color=AppColors.TEXT,
                                                ),
                                                ft.Text(
                                                    isim,
                                                    size=11,
                                                    color=AppColors.TEXT_MUTED,
                                                ) if isim else ft.Container(height=0),
                                            ],
                                            spacing=1,
                                        ),
                                    ],
                                    spacing=10,
                                    expand=True,
                                ),
                                ft.Row(
                                    [
                                        ft.Text(
                                            fiyat,
                                            color=AppColors.ACCENT,
                                            weight="bold",
                                            size=15,
                                        ) if fiyat else ft.Container(),
                                        _icon_btn(
                                            ft.Icons.CHECK_CIRCLE_OUTLINE,
                                            AppColors.SUCCESS,
                                            "Onayla",
                                            lambda _, m=mid, i=idx: asyncio.create_task(
                                                self.confirm_shipment(m, i)
                                            ),
                                        ),
                                        _icon_btn(
                                            ft.Icons.EDIT_NOTE_ROUNDED,
                                            AppColors.WARNING,
                                            "Düzenle",
                                            lambda _, m=mid, i=idx: self.open_edit_dialog(m, i),
                                        ),
                                        _icon_btn(
                                            ft.Icons.DELETE_SWEEP_OUTLINED,
                                            AppColors.DANGER,
                                            "Sil",
                                            lambda _, m=mid, i=idx: asyncio.create_task(
                                                self.delete_shipment(m, i)
                                            ),
                                        ),
                                    ],
                                    spacing=0,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        secondary_row,
                        aciklama_row,
                    ],
                    spacing=8,
                ),
                padding=ft.Padding.symmetric(horizontal=18, vertical=14),
                bgcolor=ft.Colors.with_opacity(0.05, "white"),
                border_radius=12,
                border=ft.Border(left=ft.BorderSide(3, AppColors.PRIMARY)),
            )
            new_controls.append(card)

        self.shipments_list.controls = new_controls
        self._safe_update(self.shipments_list)

    def _show_empty_center(self):
        self.shipments_list.controls = [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(
                            ft.Icons.INBOX_OUTLINED, color=AppColors.TEXT_MUTED, size=56
                        ),
                        ft.Text(
                            "Soldaki listeden bir mesaj seçin",
                            color=AppColors.TEXT_MUTED,
                            size=15,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                ),
                alignment=ft.alignment.Alignment(0, 0),
                expand=True,
                padding=60,
            )
        ]
        self._safe_update(self.shipments_list)

    # ------------------------------------------------------------------
    # Düzenleme Dialogu (Tam Formlu)
    # ------------------------------------------------------------------
    def open_edit_dialog(self, mid: str, idx: int):
        msg = self.messages_cache.get(mid)
        if not msg:
            return
        shipment = msg["shipments"][idx]

        # Temel seçenekler
        arac_opts = self._base_options.get("arac_tipleri", [])
        kasa_opts = self._base_options.get("kasa_tipleri", [])
        yuk_opts = self._base_options.get("yuk_tipleri", [])

        def _first_val(key, alt_key=""):
            v = shipment.get(key) or shipment.get(alt_key, "")
            if isinstance(v, list):
                return v[0] if v else ""
            return str(v) if v else ""

        def _make_dropdown(label, opts, key, alt_key=""):
            val = _first_val(key, alt_key)
            return ft.Dropdown(
                label=label,
                value=val if val in opts else None,
                options=[ft.dropdown.Option(o) for o in opts],
                border_radius=10,
            )

        # Form alanları
        isim = ft.TextField(
            label="Firma Adı",
            value=shipment.get("isim", ""),
            border_radius=10,
        )
        nerden_il = ft.TextField(
            label="Nereden İl",
            value=_first_val("nerden_il", "nereden_il"),
            border_radius=10,
        )
        nerden_ilce = ft.TextField(
            label="Nereden İlçe",
            value=_first_val("nerden_ilce", "nereden_ilce"),
            border_radius=10,
        )
        nereye_il = ft.TextField(
            label="Nereye İl",
            value=_first_val("nereye_il"),
            border_radius=10,
        )
        nereye_ilce = ft.TextField(
            label="Nereye İlçe",
            value=_first_val("nereye_ilce"),
            border_radius=10,
        )
        arac_dd = _make_dropdown("Araç Tipi", arac_opts, "arac_tipi")
        kasa_dd = _make_dropdown("Kasa Tipi", kasa_opts, "kasa_tipi")
        yuk_dd = _make_dropdown("Yük Tipi", yuk_opts, "yuk_tipi")
        telefon = ft.TextField(
            label="Telefon",
            value=shipment.get("telefon", ""),
            border_radius=10,
            keyboard_type=ft.KeyboardType.PHONE,
        )
        fiyat = ft.TextField(
            label="Fiyat",
            value=shipment.get("fiyat", ""),
            border_radius=10,
        )
        aciklama = ft.TextField(
            label="Açıklama",
            value=shipment.get("aciklama", ""),
            border_radius=10,
            multiline=True,
            min_lines=2,
            max_lines=4,
        )

        def _section(title):
            return ft.Text(title, size=12, weight="bold", color=AppColors.TEXT_MUTED)

        async def save_edit(e):
            # Konum (büyük harfe normalize)
            nerden_il_val = nerden_il.value.strip().upper()
            shipment["nerden_il"] = nerden_il_val
            shipment["nereden_il"] = nerden_il_val
            nerden_ilce_val = nerden_ilce.value.strip()
            shipment["nerden_ilce"] = nerden_ilce_val
            shipment["nereden_ilce"] = nerden_ilce_val

            nereye_il_val = nereye_il.value.strip().upper()
            shipment["nereye_il"] = nereye_il_val
            nereye_ilce_val = nereye_ilce.value.strip()
            shipment["nereye_ilce"] = nereye_ilce_val

            # Tipler
            if arac_dd.value:
                shipment["arac_tipi"] = [arac_dd.value]
            if kasa_dd.value:
                shipment["kasa_tipi"] = [kasa_dd.value]
            if yuk_dd.value:
                shipment["yuk_tipi"] = [yuk_dd.value]

            # Diğer
            shipment["isim"] = isim.value.strip()
            shipment["telefon"] = telefon.value.strip()
            shipment["fiyat"] = fiyat.value.strip() or "Sorunuz"
            shipment["aciklama"] = aciklama.value.strip()

            await self.data_service.save_unprocessed_messages(self.messages_cache)
            self.page.dialog.open = False
            self._update_shipments_for_message(mid)
            try:
                self.page.update()
            except Exception:
                pass

        def _swap_locations(e):
            old_nerden_il = nerden_il.value
            old_nerden_ilce = nerden_ilce.value
            nerden_il.value = nereye_il.value
            nerden_ilce.value = nereye_ilce.value
            nereye_il.value = old_nerden_il
            nereye_ilce.value = old_nerden_ilce
            self._safe_update(nerden_il)
            self._safe_update(nerden_ilce)
            self._safe_update(nereye_il)
            self._safe_update(nereye_ilce)

        self.page.dialog = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, color=AppColors.WARNING),
                    ft.Text("Sevkiyatı Düzenle", size=18, weight="bold"),
                ],
                spacing=8,
            ),
            content=ft.Column(
                [
                    _section("Firma"),
                    isim,
                    _section("Konum"),
                    ft.Row([nerden_il, nerden_ilce], spacing=10),
                    ft.Container(
                        content=ft.Button(
                            content="⇅ Yer Değiştir",
                            icon=ft.Icons.SWAP_VERT_ROUNDED,
                            bgcolor=ft.Colors.with_opacity(0.1, AppColors.ACCENT),
                            color=AppColors.ACCENT,
                            on_click=_swap_locations,
                            style=ft.ButtonStyle(
                                overlay_color={
                                    ft.ControlState.HOVERED: ft.Colors.with_opacity(
                                        0.15, AppColors.ACCENT
                                    ),
                                }
                            ),
                        )
                    ),
                    ft.Row([nereye_il, nereye_ilce], spacing=10),
                    _section("Taşıma Detayları"),
                    ft.Row([arac_dd, kasa_dd], spacing=10),
                    yuk_dd,
                    _section("İletişim & Fiyat"),
                    ft.Row([telefon, fiyat], spacing=10),
                    _section("Açıklama"),
                    aciklama,
                ],
                tight=True,
                spacing=10,
                scroll=ft.ScrollMode.ADAPTIVE,
                width=520,
            ),
            actions=[
                ft.TextButton(
                    "İptal",
                    on_click=lambda _: setattr(self.page.dialog, "open", False)
                    or self.page.update(),
                ),
                ft.Button(
                    content="KAYDET",
                    icon=ft.Icons.SAVE,
                    bgcolor=AppColors.SUCCESS,
                    color="white",
                    on_click=save_edit,
                    style=ft.ButtonStyle(
                        overlay_color={
                            ft.ControlState.HOVERED: ft.Colors.with_opacity(0.18, "white"),
                            ft.ControlState.PRESSED: ft.Colors.with_opacity(0.35, "white"),
                        }
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog.open = True
        self.page.update()

    def open_bulk_edit_dialog(self):
        """Seçili sevkiyatların konum ve fiyat gibi ortak değerlerini toplu değiştirir"""
        if not self.selected_mid or not self.selected_shipment_indices:
            return
            
        msg = self.messages_cache.get(self.selected_mid)
        if not msg or "shipments" not in msg:
            return

        nerden_il = ft.TextField(label="Nereden İl", border_radius=10, value="", expand=True)
        nerden_ilce = ft.TextField(label="Nereden İlçe", border_radius=10, value="", expand=True)
        nereye_il = ft.TextField(label="Nereye İl", border_radius=10, value="", expand=True)
        nereye_ilce = ft.TextField(label="Nereye İlçe", border_radius=10, value="", expand=True)
        fiyat = ft.TextField(label="Toplu Fiyat (ör. 15000)", border_radius=10, value="")
        aciklama = ft.TextField(label="Toplu Açıklama", border_radius=10, value="")

        async def apply_bulk_edit(e):
            n_il = nerden_il.value.strip().upper()
            n_ilce = nerden_ilce.value.strip()
            ne_il = nereye_il.value.strip().upper()
            ne_ilce = nereye_ilce.value.strip()
            f = fiyat.value.strip()
            a = aciklama.value.strip()

            for idx in self.selected_shipment_indices:
                try:
                    shipment = msg["shipments"][idx]
                except IndexError: 
                    continue
                
                if n_il:
                    shipment["nereden_il"] = n_il
                    shipment["nerden_il"]  = n_il
                if n_ilce:
                    shipment["nereden_ilce"] = n_ilce
                    shipment["nerden_ilce"]  = n_ilce
                if ne_il: shipment["nereye_il"] = ne_il
                if ne_ilce: shipment["nereye_ilce"] = ne_ilce
                if f: shipment["fiyat"] = f
                if a: shipment["aciklama"] = a

            await self.data_service.save_unprocessed_messages({self.selected_mid: msg})
            self.page.dialog.open = False
            self._update_shipments_for_message(self.selected_mid)
            try: self.page.update()
            except: pass

        self.page.dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.EDIT_NOTE, color=AppColors.WARNING), ft.Text("Çoklu Düzenleme")]),
            content=ft.Column([
                ft.Text("Sadece doldurduğunuz alanlar seçili kayıtlara uygulanacaktır.", size=12, color=AppColors.TEXT_MUTED),
                ft.Row([nerden_il, nerden_ilce]),
                ft.Row([nereye_il, nereye_ilce]),
                fiyat,
                aciklama
            ], spacing=10, tight=True),
            actions=[
                ft.TextButton("İptal", on_click=lambda _: setattr(self.page.dialog, "open", False) or self.page.update()),
                ft.Button("Tümüne Uygula", icon=ft.Icons.DONE_ALL, bgcolor=AppColors.WARNING, color="white", on_click=apply_bulk_edit)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog.open = True
        self.page.update()

    # ------------------------------------------------------------------
    # Sevkiyat Aksiyonları
    # ------------------------------------------------------------------
    async def confirm_shipment(self, mid: str, idx: int, force=False):
        try:
            msg = self.messages_cache.get(mid)
            if not msg or "shipments" not in msg:
                return
            if idx >= len(msg["shipments"]):
                return
            shipment = msg["shipments"][idx]

            if not force:
                is_valid, error_msg = self.validate_shipment_data(shipment)
                if not is_valid:
                    self._show_snackbar(f"Doğrulama Hatası:\n{error_msg}", is_error=True)
                    return
                
                is_dup, info = self.check_duplicate_shipment(shipment)
                if is_dup:
                    def _on_dup_yes(e):
                        self.page.dialog.open = False
                        self.page.update()
                        asyncio.create_task(self.confirm_shipment(mid, idx, force=True))
                        
                    def _on_dup_no(e):
                        self.page.dialog.open = False
                        self.page.update()

                    alert = ft.AlertDialog(
                        title=ft.Text("Mükerrer Kayıt Uyarısı!"),
                        content=ft.Text(f"Bu güzergahta benzer bir kayıt var:\nFirma: {info['company']}\nRota: {info['route']}\nTel: {', '.join(info['phone'])}\nYine de onaylamak istiyor musunuz?"),
                        actions=[
                            ft.TextButton("İptal", on_click=_on_dup_no),
                            ft.TextButton("Onayla", on_click=_on_dup_yes, style=ft.ButtonStyle(color=AppColors.DANGER)),
                        ],
                    )
                    self.page.dialog = alert
                    alert.open = True
                    self.page.update()
                    return

            shipment["onay_tarihi"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if self.submission_queue:
                self.submission_queue.add_task(shipment)
            await self.data_service.save_approved_records([shipment])
            # Onaylanan listesin de güncel kalmasını sağla
            self.approved_records.append(shipment)
            
            del msg["shipments"][idx]
            if not msg["shipments"]:
                await self.data_service.delete_unprocessed_message(mid)
            else:
                # Kalan shipmentları da diske yazmamız lazım
                await self.data_service.save_unprocessed_messages({mid: msg})
                
            await self.load_data()
        except Exception as e:
            print(f"confirm_shipment error: {e}")

    async def delete_shipment(self, mid: str, idx: int):
        try:
            msg = self.messages_cache.get(mid)
            if not msg or "shipments" not in msg:
                return
            if idx >= len(msg["shipments"]):
                return
                
            # Geri alma için kaydet
            deleted = msg["shipments"][idx]
            self.deleted_history.append({"type": "shipment", "mid": mid, "idx": idx, "data": deleted})
            
            del msg["shipments"][idx]
            if not msg["shipments"]:
                await self.data_service.delete_unprocessed_message(mid)
            else:
                await self.data_service.save_unprocessed_messages({mid: msg})
                
            await self.load_data()
            
            self._show_snackbar(
                "Sevkiyat silindi", 
                action_text="Geri Al", 
                on_action=lambda e: asyncio.create_task(self.undo_last_deletion())
            )
        except Exception as e:
            print(f"delete_shipment error: {e}")

    def add_new_shipment(self):
        """Mevcut mesaja yeni boş bir sevkiyat ekler"""
        if not self.selected_mid:
            self._show_snackbar("Önce sol taraftan bir mesaj seçmelisiniz.", is_error=True)
            return
            
        msg = self.messages_cache.get(self.selected_mid)
        if not msg:
            return
            
        empty_shipment = {
            "nereden_il": "",
            "nereden_ilce": "",
            "nereye_il": "",
            "nereye_ilce": "",
            "arac_tipi": "",
            "kasa_tipi": "",
            "yuk_tipi": "",
            "telefon": [],
            "fiyat": "",
            "isim": "",
            "aciklama": "Manuel Eklendi",
            "is_valid": False,
            "onay_tarihi": None
        }
        
        if "shipments" not in msg:
            msg["shipments"] = []
            
        msg["shipments"].insert(0, empty_shipment)
        
        # Async kaydet ve callback mantığı çalışmadan view yenilemek için safe run:
        asyncio.create_task(self._safe_add_and_edit_shipment(msg))
        
    async def _safe_add_and_edit_shipment(self, msg):
        await self.data_service.save_unprocessed_messages({self.selected_mid: msg})
        self._update_shipments_for_message(self.selected_mid)
        self.open_edit_dialog(self.selected_mid, 0)
        self.page.update()

    # --- Çoklu Seçim Fonksiyonları ---
    def toggle_shipment_selection(self, idx: int, value: bool):
        if value:
            self.selected_shipment_indices.add(idx)
        else:
            self.selected_shipment_indices.discard(idx)
        self._update_shipments_for_message(self.selected_mid)

    def toggle_select_all(self, value: bool):
        if not self.selected_mid: return
        msg = self.messages_cache.get(self.selected_mid)
        if not msg or "shipments" not in msg: return
        
        if value:
            self.selected_shipment_indices = set(range(len(msg["shipments"])))
        else:
            self.selected_shipment_indices.clear()
        self._update_shipments_for_message(self.selected_mid)

    async def confirm_selected_shipments(self):
        if not self.selected_mid or not self.selected_shipment_indices:
            return
            
        msg = self.messages_cache.get(self.selected_mid)
        if not msg or "shipments" not in msg: return
        
        selected_indices = sorted(list(self.selected_shipment_indices), reverse=True)
        confirmed_count = 0
        error_count = 0
        
        for idx in selected_indices:
            shipment = msg["shipments"][idx]
            is_valid, _ = self.validate_shipment_data(shipment)
            if not is_valid:
                error_count += 1
                continue
                
            is_dup, info = self.check_duplicate_shipment(shipment)
            if is_dup:
                # Toplu onayda mükerrer çıkanı atla, uyarı yığınını önlemek için (veya sayısına göre uyar)
                error_count += 1
                continue
                
            shipment["onay_tarihi"] = datetime.now().isoformat()
            
            payload = {"message_info": msg, "shipments": [shipment]}
            ok = await self.data_service.save_approved(payload)
            if ok:
                # Add to background submission queue
                if self.submission_queue:
                    self.submission_queue.add_task(shipment)
                
                # Remove from message object
                del msg["shipments"][idx]
                confirmed_count += 1
            else:
                error_count += 1
                
        if not msg["shipments"]:
            await self.data_service.delete_unprocessed_message(self.selected_mid)
        else:
            await self.data_service.save_unprocessed_messages({self.selected_mid: msg})
            
        self.selected_shipment_indices.clear()
        
        if confirmed_count > 0:
            self._show_snackbar(f"{confirmed_count} sevkiyat toplu olarak onaylandı!", is_error=False)
            asyncio.create_task(self.load_data())
        if error_count > 0:
            self._show_snackbar(f"{error_count} sevkiyat bilgi eksikliği/mükerrer olduğu için atlandı.", is_error=True)

    # ------------------------------------------------------------------
    # Servis Yönetimi
    # ------------------------------------------------------------------
    async def start_service(self):
        if self.service_process:
            return
        import subprocess, sys

        cmd = [
            sys.executable,
            os.path.join(self.root_dir, "src", "parsers", "veri_cekici_ayristirici.py"),
        ]
        self.service_process = subprocess.Popen(cmd, cwd=self.root_dir)
        self.service_status_icon.color = AppColors.SUCCESS
        self.service_status_text.value = "Servis Çalışıyor"
        self.page.update()

    async def stop_service(self):
        if not self.service_process:
            return
        self.service_process.terminate()
        self.service_process = None
        self.service_status_icon.color = "grey"
        self.service_status_text.value = "Servis Durdu"
        self.page.update()

    # ------------------------------------------------------------------
    # Doğrulama ve Yardımcı Metotlar
    # ------------------------------------------------------------------
    def delete_current_message(self):
        """Mevcut mesajı AlertDialog onayı ile siler"""
        if not self.selected_mid:
            return
            
        def _on_confirm_delete(e):
            self.page.dialog.open = False
            self.page.update()
            asyncio.create_task(self._remove_message_by_id(self.selected_mid))
            
        def _on_cancel(e):
            self.page.dialog.open = False
            self.page.update()

        alert = ft.AlertDialog(
            title=ft.Text("Mesajı Sil"),
            content=ft.Text("Bu mesajı ve içindeki tüm sevkiyatları silmek istediğinize emin misiniz?"),
            actions=[
                ft.TextButton("İptal", on_click=_on_cancel),
                ft.TextButton("Sil", on_click=_on_confirm_delete, style=ft.ButtonStyle(color=AppColors.DANGER)),
            ],
        )
        self.page.dialog = alert
        alert.open = True
        self.page.update()

    def quick_delete_message(self, mid):
        """Onaysız hızlı silme (otomatik akışlar vb. için)"""
        if mid:
            asyncio.create_task(self._remove_message_by_id(mid))

    async def _remove_message_by_id(self, mid: str):
        """Mesajı cache, disk ve UI'dan siler, bir sonraki mesaja geçer"""
        if mid in self.messages_cache:
            del self.messages_cache[mid]
        if mid in self.sorted_message_ids:
            self.sorted_message_ids.remove(mid)
            
        await self.data_service.delete_unprocessed_message(mid)
        self._show_snackbar("Mesaj silindi")
        
        if self.sorted_message_ids:
            if self.current_msg_index >= len(self.sorted_message_ids):
                self.current_msg_index = 0
            # Aynı indeksteki sıradaki öğeye geç (veya ilk elemana)
            next_mid = self.sorted_message_ids[self.current_msg_index]
            self._select_message(next_mid)
        else:
            self.selected_mid = None
            self._show_empty_center()
            self._update_message_display()
            self._refresh_messages_list()
        
        self.msg_count_text.value = str(len(self.messages_cache))
        self._update_nav_text()
        self.page.update()
        
    async def undo_last_deletion(self):
        """Son silinen sevkiyatı veya mesajı geri alır"""
        if not self.deleted_history:
            self._show_snackbar("Geri alınacak bir işlem yok.", is_error=True)
            return
            
        last_action = self.deleted_history.pop()
        
        if last_action["type"] == "shipment":
            mid = last_action["mid"]
            data = last_action["data"]
            
            # Mesaj hala duruyorsa içine geri koyalım
            msg = self.messages_cache.get(mid)
            if msg:
                # İndeksi korumaya çalış (veya sona ekle)
                idx = last_action["idx"]
                if idx <= len(msg["shipments"]):
                    msg["shipments"].insert(idx, data)
                else:
                    msg["shipments"].append(data)
                
                await self.data_service.save_unprocessed_messages({mid: msg})
            else:
                # Mesaj silinmişse, yeni bir mesaj wrapper'ı ile geri mi getirsek? (Oldukça nadir ihtimal, basit tutalım)
                self._show_snackbar("Mesaj artık bulunmadığı için geri alınamadı.", is_error=True)
                return
                
        await self.load_data()
        self._show_snackbar("Silme işlemi geri alındı.")
        
    def validate_shipment_data(self, shipment_dict):
        """Shipment dict validation via validators.py"""
        valid, error_msgs = _validate_shipment_fields(shipment_dict)
        if hasattr(self, 'validate_location'):
            il = shipment_dict.get('nereden_il', '')
            ilce = shipment_dict.get('nereden_ilce', '')
            if il and ilce and not self.validate_location(il, ilce):
                error_msgs.append(f"Geçersiz Nereden İl/İlçe: {il}/{ilce}")
                valid = False
            il2 = shipment_dict.get('nereye_il', '')
            ilce2 = shipment_dict.get('nereye_ilce', '')
            if il2 and ilce2 and not self.validate_location(il2, ilce2):
                error_msgs.append(f"Geçersiz Nereye İl/İlçe: {il2}/{ilce2}")
                valid = False
        return valid, "\n".join(error_msgs) if error_msgs else ""

    def validate_location(self, il, ilce):
        if not self.il_ilceler_data:
            return True 
        try:
            target_il = str(il).strip().upper()
            target_ilce = str(ilce).strip().upper()
            
            # Bazı bilinen kısaltmalar
            if target_ilce == "MERKEZ": return True
            
            for province in self.il_ilceler_data:
                if isinstance(province, dict) and self._normalize_il_name(province.get('il', '')) == self._normalize_il_name(target_il):
                    ilce_list = [self._normalize_il_name(str(i).strip()) for i in province.get('ilceler', [])]
                    return self._normalize_il_name(target_ilce) in ilce_list
            return False
        except Exception:
            return False

    def check_duplicate_shipment(self, shipment_dict):
        # NOTE: is_shipment_duplicate in DataService now checks both approved and unapproved
        # Since the GUI might be in an async flow, we use a sync-friendly wrapper if needed
        # but here we can keep the local cache check for speed and call the service for depth
        
        # 1. Local Cache Check (Fast)
        try:
            phone = shipment_dict.get('telefon', [])
            if isinstance(phone, str):
                phone = [phone]
            from src.utils.phone_utils import normalize_phone
            phones = [normalize_phone(p) for p in phone]
                
            nereden_il = self._normalize_il_name(str(shipment_dict.get('nereden_il', '')).strip())
            nereye_il = self._normalize_il_name(str(shipment_dict.get('nereye_il', '')).strip())

            for existing in self.approved_records:
                existing_phone = existing.get('telefon', [])
                if isinstance(existing_phone, str):
                    existing_phone = [existing_phone]
                existing_phones = [normalize_phone(p) for p in existing_phone]
                    
                existing_nereden = self._normalize_il_name(str(existing.get('nereden_il', '')).strip())
                existing_nereye = self._normalize_il_name(str(existing.get('nereye_il', '')).strip())

                if (phones and existing_phones and set(phones) & set(existing_phones) and 
                    nereden_il == existing_nereden and nereye_il == existing_nereye):
                    return True, {
                        'phone': existing_phones,
                        'route': f"{existing_nereden} → {existing_nereye}",
                        'company': existing.get('isim', 'Bilinmeyen')
                    }
            
            # 2. Deep Check via Service (This will be done in the confirm flow)
            return False, None
        except Exception as e:
            logger.error(f"Error in check_duplicate_shipment: {e}")
            return False, None

    def _normalize_il_name(self, il_name):
        if not il_name: return ""
        return str(il_name).upper().replace('İ', 'I').replace('Ş', 'S').replace('Ğ', 'G').replace('Ü', 'U').replace('Ö', 'O').replace('Ç', 'C')

    def _get_message_datetime(self, msg):
        """Mesajdan datetime çıkarır. 4 farklı format desteği."""
        ts = msg.get('timestamp') or msg.get('time') or msg.get('createdAt')
        if not ts and 'message_info' in msg:
            ts = msg['message_info'].get('timestamp') or msg['message_info'].get('createdAt')
            
        if not ts: return None
        
        try:
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts)
            
            ts_str = str(ts).strip()
            if 'T' in ts_str:
                return datetime.fromisoformat(ts_str.replace('Z', '+00:00')).replace(tzinfo=None)
            if len(ts_str) >= 19 and ts_str[4] == '-':
                return datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
            if len(ts_str) >= 19 and ts_str[4] == '.':
                return datetime.strptime(ts_str[:19], "%Y.%m.%d %H:%M:%S")
            if len(ts_str) >= 19 and ts_str[2] == '.':
                return datetime.strptime(ts_str[:19], "%d.%m.%Y %H:%M:%S")
            return None
        except Exception:
            return None

    def _reset_time_filter(self):
        """Zaman filtresini tümü olarak sıfırlar ve yükler"""
        self.time_filter.value = "all"
        self.page.update()
        asyncio.create_task(self.load_data())

    def _get_ilce_list(self, il_name):
        if not self.il_ilceler_data or not il_name: return []
        nil = self._normalize_il_name(il_name)
        for p in self.il_ilceler_data:
            if self._normalize_il_name(p.get('il', '')) == nil:
                return p.get('ilceler', [])
        return []

    def _show_snackbar(self, msg, is_error=False, action_text=None, on_action=None):
        sb = ft.SnackBar(ft.Text(msg), bgcolor=AppColors.DANGER if is_error else AppColors.SUCCESS)
        if action_text and on_action:
            sb.action = action_text
            sb.on_action = on_action
            # Varsayılan action rengini belirginleştirelim
            sb.action_color = "white"
        self.page.snack_bar = sb
        self.page.snack_bar.open = True
        self.page.update()

    # ------------------------------------------------------------------
    # get_view
    # ------------------------------------------------------------------
    async def get_view(self):
        asyncio.create_task(self.load_data())
        return ft.Row(
            [self.left_pane, self.center_pane, self.right_pane],
            spacing=15,
            expand=True,
        )
