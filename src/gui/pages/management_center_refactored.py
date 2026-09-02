"""
Refactored Management Center Page - Uses component-based architecture
Cleaner, more maintainable, and modular design
"""

import flet as ft
import os
import asyncio
from src.gui.styles import AppColors, AppStyles
from src.services.data_service import DataService
from src.services.data_service_async import AsyncDataService
from src.gui.pages.settings_page import SettingsPage
from src.gui.pages.server_control import ServerControlPage
from src.gui.components.yuk_definition_tab import YukDefinitionTab
from src.gui.components.mahalle_management_tab import MahalleManagementTab
from src.gui.components.blacklist_tab import BlacklistTab
from src.gui.components.group_management_tab import GroupManagementTab


class ManagementCenterPage:
    """Refactored Management Center with component-based tabs"""

    def __init__(self, page: ft.Page):
        self.page = page
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        self.data_service = AsyncDataService(DataService(self.root_dir))

        # Initialize sub-pages
        self.settings_page = SettingsPage(page)
        self.server_control = ServerControlPage(page)

        # Initialize tab components
        self.yuk_tab = YukDefinitionTab(page, self.data_service)
        self.mahalle_tab = MahalleManagementTab(page, self.data_service)
        self.blacklist_tab = BlacklistTab(page, self.data_service)
        self.group_tab = GroupManagementTab(page, self.data_service)

        self.layout = None

    async def get_view(self):
        """Build and return the management center view"""
        if self.layout:
            # Refresh data in background if view already exists
            asyncio.create_task(self._load_all_data())
            return self.layout

        # Create tab structure
        self.tab_bar = ft.TabBar(
            tabs=[
                ft.Tab(label="Yük Tanımlama", icon=ft.Icons.INVENTORY_2_ROUNDED),
                ft.Tab(label="Mahalle Yönetimi", icon=ft.Icons.LOCATION_ON_ROUNDED),
                ft.Tab(label="Grup Ayarları", icon=ft.Icons.GROUPS_ROUNDED),
                ft.Tab(label="Kara Liste", icon=ft.Icons.BLOCK_ROUNDED),
                ft.Tab(label="VPS Kontrolü", icon=ft.Icons.DNS_ROUNDED),
                ft.Tab(label="Sistem Ayarları", icon=ft.Icons.SETTINGS_ROUNDED),
            ],
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_MUTED,
        )

        self.tab_view = ft.TabBarView(
            controls=[
                self.yuk_tab.build(),
                self.mahalle_tab.build(),
                self.group_tab.build(),
                self.blacklist_tab.build(),
                ft.Container(content=await self.server_control.get_view(), expand=True),
                ft.Container(content=await self.settings_page.get_view(), expand=True),
            ],
            expand=True
        )

        # Main layout
        self.layout = ft.Column(
            [
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, color=AppColors.PRIMARY, size=18),
                        ft.Text("Yönetim Merkezi", size=24, weight="bold", color=AppColors.TEXT),
                    ]),
                    ft.IconButton(
                        icon=ft.Icons.SYNC,
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda _: asyncio.create_task(self._load_all_data()),
                        tooltip="Verileri Yenile",
                        style=ft.ButtonStyle(
                            overlay_color={
                                ft.ControlState.HOVERED: ft.Colors.with_opacity(0.12, AppColors.PRIMARY),
                                ft.ControlState.PRESSED: ft.Colors.with_opacity(0.25, AppColors.PRIMARY),
                            }
                        )
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(color="white10", height=30),
                ft.Tabs(
                    length=6,
                    content=ft.Column([
                        ft.Container(
                            content=self.tab_bar,
                            bgcolor=AppColors.SURFACE,
                            padding=ft.Padding.symmetric(vertical=0, horizontal=10),
                            border=ft.Border(bottom=ft.BorderSide(1, "white10"))
                        ),
                        ft.Container(self.tab_view, expand=True, padding=ft.Padding.only(top=10))
                    ], expand=True),
                    expand=True
                )
            ],
            expand=True,
        )

        # Load data in background
        asyncio.create_task(self._load_all_data())

        return self.layout

    async def _load_all_data(self):
        """Load data for all tabs"""
        try:
            await asyncio.gather(
                self.yuk_tab.load_data(),
                self.mahalle_tab.load_data(),
                self.blacklist_tab.load_data(),
                self.group_tab.load_data()
            )
        except Exception as e:
            print(f"Data loading error: {e}")
