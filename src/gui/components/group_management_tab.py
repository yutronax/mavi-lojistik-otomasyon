"""
Grup Ayarları (Group Management) Tab Component
Manages WhatsApp groups and chat settings
"""

import flet as ft
import asyncio
from src.gui.styles import AppColors, AppStyles
from src.services.data_service_async import AsyncDataService


class GroupManagementTab:
    """Group/chat management tab"""

    def __init__(self, page: ft.Page, data_service: AsyncDataService):
        self.page = page
        self.data_service = data_service
        self.groups = []
        self.saved_groups = set()

        # UI Components
        self.saved_groups_view = ft.ListView(expand=True, spacing=5, padding=10)
        self.available_groups_view = ft.ListView(expand=True, spacing=5, padding=10)

    async def load_data(self):
        """Load group data"""
        try:
            groups_data = await self.data_service.load_chat_groups()
            self.saved_groups = set(groups_data.keys()) if isinstance(groups_data, dict) else set()
            await self._refresh_saved_groups()
        except Exception as e:
            print(f"Grup verisi yükleme hatası: {e}")

    async def _refresh_saved_groups(self):
        """Refresh saved groups display"""
        items = []

        for group_name in sorted(self.saved_groups):
            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.GROUPS, color=AppColors.SUCCESS),
                    title=ft.Text(group_name, weight="bold"),
                    subtitle=ft.Text("Kaydedilmiş", size=11, color=AppColors.TEXT_MUTED),
                    trailing=ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=AppColors.DANGER,
                        on_click=lambda e, gname=group_name: asyncio.create_task(self._remove_group(gname))
                    ),
                    bgcolor=AppColors.SURFACE,
                )
            )

        self.saved_groups_view.controls = items
        self.page.update()

    async def _remove_group(self, group_name):
        """Remove group from saved list"""
        try:
            self.saved_groups.discard(group_name)
            groups_dict = {g: {} for g in self.saved_groups}
            await self.data_service.save_chat_groups(groups_dict)
            await self._refresh_saved_groups()
            self._show_success(f"'{group_name}' çıkarıldı")

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
                    ft.Icon(ft.Icons.GROUPS_ROUNDED, color=AppColors.PRIMARY, size=18),
                    ft.Text("Grup Ayarları", size=18, weight="bold", color=AppColors.TEXT),
                ]),
                ft.Divider(color="white10"),

                # Saved Groups
                ft.Text("Kaydedilmiş Gruplar", size=14, weight="bold", color=AppColors.TEXT),
                ft.Container(
                    content=self.saved_groups_view,
                    expand=True,
                    bgcolor=AppColors.BG_DEEP,
                    border_radius=12,
                    height=200
                ),

                ft.Container(height=10),

                # Info Box
                ft.Container(
                    content=ft.Column([
                        ft.Text("💡 Bilgi", size=12, weight="bold", color=AppColors.PRIMARY),
                        ft.Text(
                            "Grupları buradan yönetebilirsiniz. Yeni gruplar otomatik olarak WhatsApp taramasında bulunup listelenecektir.",
                            size=11,
                            color=AppColors.TEXT_MUTED
                        )
                    ], spacing=5),
                    padding=12,
                    bgcolor=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
                    border_radius=10,
                )
            ], spacing=10),
            padding=20,
            bgcolor=AppColors.SURFACE,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW],
        )
