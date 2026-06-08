"""
Kara Liste (Blacklist) Tab Component
Manages blocked phone numbers
"""

import flet as ft
import asyncio
from src.gui.styles import AppColors, AppStyles
from src.services.data_service_async import AsyncDataService


class BlacklistTab:
    """Blacklist management tab"""

    def __init__(self, page: ft.Page, data_service: AsyncDataService):
        self.page = page
        self.data_service = data_service
        self.blacklist = []

        # UI Components
        self.phone_input = ft.TextField(
            label="Telefon Numarası",
            hint_text="+90 5XX XXX XXXX",
            expand=True,
            border_radius=10
        )
        self.reason_input = ft.TextField(
            label="Neden (Opsiyonel)",
            hint_text="Spam, Hatalı veri, vb.",
            expand=True,
            border_radius=10
        )
        self.blacklist_view = ft.ListView(expand=True, spacing=5, padding=10)

    async def load_data(self):
        """Load blacklist"""
        try:
            self.blacklist = await self.data_service.load_blacklist()
            await self._refresh_list()
        except Exception as e:
            print(f"Blacklist yükleme hatası: {e}")

    async def _refresh_list(self):
        """Refresh blacklist display"""
        items = []

        for entry in self.blacklist:
            if isinstance(entry, dict):
                phone = entry.get('phone', entry)
                reason = entry.get('reason', '')
            else:
                phone = entry
                reason = ''

            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.BLOCK, color=AppColors.DANGER),
                    title=ft.Text(phone, weight="bold"),
                    subtitle=ft.Text(reason, size=11) if reason else None,
                    trailing=ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=AppColors.DANGER,
                        on_click=lambda e, p=phone: asyncio.create_task(self._delete_blacklist(p))
                    ),
                    bgcolor=AppColors.SURFACE,
                )
            )

        self.blacklist_view.controls = items
        self.page.update()

    async def _add_blacklist(self):
        """Add phone to blacklist"""
        phone = self.phone_input.value.strip()
        reason = self.reason_input.value.strip()

        if not phone:
            self._show_error("Telefon numarası gerekli!")
            return

        try:
            entry = {"phone": phone, "reason": reason} if reason else phone
            self.blacklist.append(entry)
            await self.data_service.save_blacklist(self.blacklist)

            self.phone_input.value = ""
            self.reason_input.value = ""
            await self._refresh_list()
            self._show_success(f"'{phone}' kara listeye eklendi")

        except Exception as e:
            self._show_error(f"Ekleme hatası: {e}")

    async def _delete_blacklist(self, phone):
        """Remove phone from blacklist"""
        try:
            self.blacklist = [
                e for e in self.blacklist
                if (e if isinstance(e, str) else e.get('phone')) != phone
            ]
            await self.data_service.save_blacklist(self.blacklist)
            await self._refresh_list()
            self._show_success("Telefon kara listeden çıkarıldı")

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
                    ft.Icon(ft.Icons.BLOCK_ROUNDED, color=AppColors.DANGER, size=18),
                    ft.Text("Kara Liste Yönetimi", size=18, weight="bold", color=AppColors.TEXT),
                ]),
                ft.Divider(color="white10"),

                # Input Section
                ft.Container(
                    content=ft.Column([
                        ft.Text("Yeni Numara Ekle", size=14, weight="bold", color=AppColors.TEXT),
                        self.phone_input,
                        self.reason_input,
                        ft.ElevatedButton(
                            "EKLE",
                            icon=ft.Icons.ADD,
                            bgcolor=AppColors.DANGER,
                            color="white",
                            on_click=lambda _: asyncio.create_task(self._add_blacklist()),
                            width=float("inf"),
                            height=45,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                        )
                    ], spacing=10),
                    padding=15,
                    bgcolor=AppColors.SURFACE,
                    border_radius=12,
                ),

                # List Section
                ft.Container(height=10),
                ft.Text("Kara Listedeki Numaralar", size=14, weight="bold", color=AppColors.TEXT),
                ft.Container(
                    content=self.blacklist_view,
                    expand=True,
                    bgcolor=AppColors.BG_DEEP,
                    border_radius=12,
                )
            ], spacing=10),
            padding=20,
            bgcolor=AppColors.SURFACE,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW],
        )
