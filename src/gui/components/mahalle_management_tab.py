"""
Mahalle Yönetimi (Neighborhood Management) Tab Component
Manages provinces, districts, and neighborhoods
"""

import flet as ft
import asyncio
from src.gui.styles import AppColors, AppStyles
from src.services.data_service_async import AsyncDataService


class MahalleManagementTab:
    """Neighborhood/district/province management tab"""

    def __init__(self, page: ft.Page, data_service: AsyncDataService):
        self.page = page
        self.data_service = data_service
        self.il_data = []

        # UI Components
        self.il_dropdown = ft.Dropdown(label="İl Seçin", expand=True)
        self.il_dropdown.on_select = self._on_il_change

        self.ilce_dropdown = ft.Dropdown(label="İlçe Seçin", expand=True)
        self.ilce_dropdown.on_select = self._on_ilce_change

        self.mahalle_list_view = ft.ListView(expand=True, spacing=5)
        self.new_mahalle_field = ft.TextField(label="Yeni Mahalle Adı", expand=True)

    async def load_data(self):
        """Load province and district data"""
        try:
            self.il_data = await self.data_service.load_il_ilceler()
            self.il_dropdown.options = [ft.dropdown.Option(item['il']) for item in self.il_data]
            self.il_dropdown.update()
        except Exception as e:
            self._show_error(f"İl verisi yükleme hatası: {e}")

    def _on_il_change(self, e):
        """Handle province selection"""
        il_name = self.il_dropdown.value
        ilceler = next((item['ilceler'] for item in self.il_data if item['il'] == il_name), [])
        self.ilce_dropdown.options = [ft.dropdown.Option(item['ilce']) for item in ilceler]
        self.ilce_dropdown.value = None
        self.mahalle_list_view.controls = []
        self.page.update()

    def _on_ilce_change(self, e):
        """Handle district selection"""
        asyncio.create_task(self._refresh_mahalle_list())

    async def _refresh_mahalle_list(self):
        """Refresh neighborhood list for selected district"""
        il_name = self.il_dropdown.value
        ilce_name = self.ilce_dropdown.value
        if not il_name or not ilce_name:
            return

        il_item = next((item for item in self.il_data if item['il'] == il_name), None)
        if not il_item:
            return

        ilce_item = next((item for item in il_item['ilceler'] if item['ilce'] == ilce_name), None)
        if not ilce_item:
            return

        items = []
        for m in ilce_item.get('mahalleler', []):
            items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(m, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=AppColors.DANGER,
                            on_click=lambda e, mname=m: asyncio.create_task(self._delete_mahalle(mname))
                        )
                    ]),
                    padding=10,
                    bgcolor=AppColors.BG_DEEP,
                    border_radius=8
                )
            )

        self.mahalle_list_view.controls = items
        self.page.update()

    async def _add_mahalle(self):
        """Add new neighborhood"""
        il_name = self.il_dropdown.value
        ilce_name = self.ilce_dropdown.value
        mahalle_name = self.new_mahalle_field.value.strip()

        if not all([il_name, ilce_name, mahalle_name]):
            self._show_error("Tüm alanları doldurun!")
            return

        try:
            il_item = next((item for item in self.il_data if item['il'] == il_name), None)
            ilce_item = next((item for item in il_item['ilceler'] if item['ilce'] == ilce_name), None)

            if mahalle_name not in ilce_item.get('mahalleler', []):
                ilce_item.setdefault('mahalleler', []).append(mahalle_name)
                await self.data_service.save_il_ilceler(self.il_data)
                self.new_mahalle_field.value = ""
                await self._refresh_mahalle_list()
                self._show_success(f"'{mahalle_name}' eklendi")
            else:
                self._show_error("Bu mahalle zaten kayıtlı!")
        except Exception as e:
            self._show_error(f"Ekleme hatası: {e}")

    async def _delete_mahalle(self, mname):
        """Delete neighborhood"""
        il_name = self.il_dropdown.value
        ilce_name = self.ilce_dropdown.value

        try:
            il_item = next((item for item in self.il_data if item['il'] == il_name), None)
            ilce_item = next((item for item in il_item['ilceler'] if item['ilce'] == ilce_name), None)

            if mname in ilce_item.get('mahalleler', []):
                ilce_item['mahalleler'].remove(mname)
                await self.data_service.save_il_ilceler(self.il_data)
                await self._refresh_mahalle_list()
                self._show_success("Mahalle silindi")
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

    def build(self) -> ft.Container:
        """Build the UI"""
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
                        tooltip="Mahalle Ekle",
                        style=ft.ButtonStyle(
                            overlay_color={
                                ft.ControlState.HOVERED: ft.Colors.with_opacity(0.2, "white"),
                                ft.ControlState.PRESSED: ft.Colors.with_opacity(0.4, "white"),
                            }
                        )
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
