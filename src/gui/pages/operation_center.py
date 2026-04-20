import flet as ft
import asyncio
import os
from datetime import datetime
from src.gui.styles import AppColors, AppStyles
from src.services.data_service import DataService
from src.services.data_service_async import AsyncDataService
from src.services.submission_queue import SubmissionQueue


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
                                ]
                            ),
                            ft.Row(
                                [
                                    self.time_filter,
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
            ts = msg.get("timestamp") or msg.get("time", "")
            time_str = ""
            if ts:
                try:
                    if isinstance(ts, (int, float)):
                        dt = datetime.fromtimestamp(ts)
                    else:
                        dt = datetime.strptime(str(ts).replace("T", " ")[:19], "%Y-%m-%d %H:%M:%S")
                    time_str = dt.strftime("%H:%M")
                except Exception:
                    pass

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

        new_controls = []
        for idx, s in enumerate(shipments):
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

    # ------------------------------------------------------------------
    # Sevkiyat Aksiyonları
    # ------------------------------------------------------------------
    async def confirm_shipment(self, mid: str, idx: int):
        try:
            msg = self.messages_cache.get(mid)
            if not msg:
                return
            shipment = msg["shipments"][idx]
            shipment["onay_tarihi"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if self.submission_queue:
                self.submission_queue.add_task(shipment)
            await self.data_service.save_approved_records([shipment])
            del msg["shipments"][idx]
            if not msg["shipments"]:
                await self.data_service.delete_unprocessed_message(mid)
            await self.load_data()
        except Exception as e:
            print(f"confirm_shipment error: {e}")

    async def delete_shipment(self, mid: str, idx: int):
        try:
            msg = self.messages_cache.get(mid)
            if not msg:
                return
            del msg["shipments"][idx]
            if not msg["shipments"]:
                await self.data_service.delete_unprocessed_message(mid)
            await self.load_data()
        except Exception as e:
            print(f"delete_shipment error: {e}")

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
    # get_view
    # ------------------------------------------------------------------
    async def get_view(self):
        asyncio.create_task(self.load_data())
        return ft.Row(
            [self.left_pane, self.center_pane, self.right_pane],
            spacing=15,
            expand=True,
        )
