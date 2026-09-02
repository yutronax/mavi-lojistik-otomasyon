"""
Yük Tanımlama (Load Type Definition) Tab Component
Handles load type definitions and keywords
"""

import flet as ft
import asyncio
from src.gui.styles import AppColors, AppStyles
from src.services.data_service_async import AsyncDataService
from src.utils.text_utils import generate_keyword_variants


class YukDefinitionTab:
    """Load/Cargo type definition management tab"""

    def __init__(self, page: ft.Page, data_service: AsyncDataService):
        self.page = page
        self.data_service = data_service
        self.yuk_rules = []
        self._is_loading = False

        # UI Components
        self.search_entry = ft.TextField(
            label="Yük Ara",
            prefix_icon="search",
            on_change=lambda e: asyncio.create_task(self._filter_yuk(e)),
            border_radius=10
        )
        self.yuk_list_view = ft.ListView(expand=True, spacing=10, padding=10)

        # Form Fields
        self.keyword_field = ft.TextField(label="Orijinal Mesajdaki Kelime", border_radius=10)
        self.priority_field = ft.TextField(label="Öncelik (1000)", border_radius=10, value="1000")
        self.yuk_type_dropdown = ft.Dropdown(label="Yük Tipi", border_radius=10)
        self.arac_type_dropdown = ft.Dropdown(label="Araç Tipi", border_radius=10)
        self.kasa_type_dropdown = ft.Dropdown(label="Kasa Tipi", border_radius=10)

    async def load_data(self):
        """Load yük definitions and dropdown options"""
        if self._is_loading:
            return
        self._is_loading = True

        try:
            base_options = await self.data_service.load_arac_kasa_tipleri()
            self.yuk_type_dropdown.options = [ft.dropdown.Option(opt) for opt in base_options.get('yuk_tipleri', [])]
            self.arac_type_dropdown.options = [ft.dropdown.Option(opt) for opt in base_options.get('arac_tipleri', [])]
            self.kasa_type_dropdown.options = [ft.dropdown.Option(opt) for opt in base_options.get('kasa_tipleri', [])]

            self.yuk_rules = await self.data_service.load_yuk_tipleri()
            await self._refresh_yuk_list()
            self._safe_update(self.page)
        except Exception as e:
            if "session" not in str(e).lower():
                print(f"Yük verisi yükleme hatası: {e}")
        finally:
            self._is_loading = False

    def _safe_update(self, control):
        if not control:
            return
        try:
            control.update()
        except:
            pass

    async def _refresh_yuk_list(self, filter_text=""):
        items = []
        filter_text = filter_text.lower()
        limit = 100
        count = 0

        for idx, rule in enumerate(self.yuk_rules):
            if count >= limit:
                break

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
                )
            )
            count += 1

        self.yuk_list_view.controls = items
        self._safe_update(self.yuk_list_view)

    async def _filter_yuk(self, e):
        await self._refresh_yuk_list(e.control.value)

    async def _save_yuk_tanimi(self, e):
        try:
            keyword = self.keyword_field.value.strip().upper()
            if not keyword:
                self._show_error("Anahtar kelime boş olamaz!")
                return

            variants = generate_keyword_variants(keyword)

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

            self.keyword_field.value = ""
            await self._refresh_yuk_list()
            self._show_success(f"'{keyword}' ve {len(variants)} varyasyonu kaydedildi.")

        except Exception as e:
            self._show_error(f"Kaydetme hatası: {e}")

    async def _delete_yuk_tanimi(self, index):
        try:
            if 0 <= index < len(self.yuk_rules):
                del self.yuk_rules[index]
                await self.data_service.save_yuk_tipleri(self.yuk_rules)
                await self._refresh_yuk_list()
                self._show_success("Tanım silindi.")
            else:
                self._show_error("Hata: Geçersiz Tanım İndeksi")
        except Exception as ex:
            self._show_error(f"Silme hatası: {str(ex)}")

    def _show_error(self, msg):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=AppColors.DANGER)
        self.page.snack_bar.open = True
        self.page.update()

    def _show_success(self, msg):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=AppColors.SUCCESS)
        self.page.snack_bar.open = True
        self.page.update()

    def build(self) -> ft.Container:
        """Build the UI"""
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
                        height=50,
                        style=ft.ButtonStyle(
                            overlay_color={
                                ft.ControlState.HOVERED: ft.Colors.with_opacity(0.18, "white"),
                                ft.ControlState.PRESSED: ft.Colors.with_opacity(0.35, "white"),
                            },
                            elevation={
                                ft.ControlState.DEFAULT: 2,
                                ft.ControlState.HOVERED: 6,
                                ft.ControlState.PRESSED: 0,
                            }
                        )
                    ),
                ], scroll=ft.ScrollMode.ADAPTIVE, spacing=15),
                expand=1,
                padding=20,
                bgcolor=AppColors.SURFACE,
                border_radius=15,
                shadow=[AppStyles.CARD_SHADOW],
            )
        ], expand=True, spacing=20)
