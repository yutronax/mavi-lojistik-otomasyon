# flet_app.py - Özel Sidebar Geri Yükleme Modu

import flet as ft
import asyncio
import sys
import os

# Proje kök dizinini ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.gui.styles import AppColors, AppStyles, apply_app_theme
from src.gui.pages.operation_center import OperationCenterPage
from src.gui.pages.management_center import ManagementCenterPage
from src.gui.pages.server_control import ServerControlPage
from src.gui.components.log_viewer import LogPage
from src.gui.pages.settings_page import SettingsPage

def main(page: ft.Page):
    print("DEBUG: Modular flet_app baslatildi.")
    page.title = "Mavi Lojistik - Yönetim Sistemi"
    apply_app_theme(page)
    
    # Sayfa nesnelerini hazirla
    op_center = OperationCenterPage(page)
    mgmt_center = ManagementCenterPage(page)
    srv_control = ServerControlPage(page)
    log_page = LogPage(page)
    settings_page = SettingsPage(page)

    # Aktif sayfa ve nav referans takibi
    _current_page = {"name": "Yönetim"}
    _nav_refs: dict = {}

    # Ana içerik alanı
    main_content = ft.Container(
        expand=True,
        padding=20,
    )

    def _update_active_nav(page_name: str):
        """Aktif nav öğesini görsel olarak vurgular."""
        for pname, container in _nav_refs.items():
            is_active = pname == page_name
            container.bgcolor = ft.Colors.with_opacity(0.1, AppColors.PRIMARY) if is_active else None
            container.border = ft.Border(left=ft.BorderSide(3, AppColors.PRIMARY if is_active else "transparent"))
            container.content.controls[0].color = AppColors.PRIMARY if is_active else AppColors.TEXT_MUTED
            if len(container.content.controls) > 1:
                container.content.controls[1].color = "white" if is_active else AppColors.TEXT_MUTED
            try:
                container.update()
            except Exception:
                pass
        _current_page["name"] = page_name

    async def change_page(page_name):
        try:
            print(f"DEBUG: Sayfa degistiliyor -> {page_name}")
            main_content.content = ft.ProgressRing(color=AppColors.PRIMARY)
            page.update()
            _update_active_nav(page_name)

            if page_name == "Operasyon":
                content = await op_center.get_view()
            elif page_name == "Yönetim":
                content = await mgmt_center.get_view()
            elif page_name == "Sunucu":
                content = await srv_control.get_view()
            elif page_name == "Loglar":
                content = await log_page.get_view()
            elif page_name == "Ayarlar":
                # Ayarlar tıklandığında Yönetim Merkezi'ne git ve 5. sekmeye (index 4) seç
                content = await mgmt_center.get_view()
                if hasattr(mgmt_center, "tabs_wrapper") and mgmt_center.tabs_wrapper:
                    mgmt_center.tabs_wrapper.selected_index = 4
                page_name = "Ayarlar" # Sidebar'da Ayarlar'ı işaretle
            
            main_content.content = content
            page.update()
            print(f"DEBUG: Sayfa degistirildi -> {page_name} (Tamamlandi)")
        except Exception as ex:
            print(f"ERROR: change_page hatasi ({page_name}): {ex}")
            main_content.content = ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=AppColors.DANGER, size=48),
                    ft.Text(f"Sayfa yüklenirken hata oluştu: {page_name}", size=18, weight="bold"),
                    ft.Text(str(ex), color=AppColors.TEXT_MUTED, size=12),
                    ft.Button("TEKRAR DENE", on_click=lambda _: asyncio.create_task(change_page(page_name)))
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                alignment=ft.alignment.center,
                expand=True
            )
            page.update()
            page.snack_bar = ft.SnackBar(ft.Text(f"Sayfa yüklenirken hata oluştu: {ex}"), bgcolor=AppColors.DANGER)
            page.snack_bar.open = True
            page.update()


    # --- SIDEBAR (Premium Navigation) ---
    def create_nav_item(text, icon, page_name):
        container = ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=20, color=AppColors.TEXT_MUTED),
                ft.Text(text, size=14, weight="w500", color=AppColors.TEXT_MUTED),
            ], spacing=12),
            padding=ft.Padding.symmetric(vertical=13, horizontal=20),
            border_radius=10,
            border=ft.Border(left=ft.BorderSide(3, "transparent")),
            ink=True,
            on_click=lambda e, pn=page_name: asyncio.create_task(change_page(pn)),
            on_hover=lambda e: self_hover(e),
        )
        _nav_refs[page_name] = container
        return container

    def self_hover(e):
        # Aktif sayfanın hover stilini değiştirme
        for pname, c in _nav_refs.items():
            if c is e.control and pname == _current_page["name"]:
                return
        is_hover = e.data == "true"
        e.control.bgcolor = AppColors.SURFACE_LIGHT if is_hover else None
        e.control.border = ft.Border(left=ft.BorderSide(3, AppColors.PRIMARY if is_hover else "transparent"))
        if len(e.control.content.controls) > 0:
            e.control.content.controls[0].color = AppColors.PRIMARY if is_hover else AppColors.TEXT_MUTED
        if len(e.control.content.controls) > 1:
            e.control.content.controls[1].color = "white" if is_hover else AppColors.TEXT_MUTED
        e.control.update()

    sidebar = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.LOCAL_SHIPPING, color=AppColors.PRIMARY, size=30),
                    ft.Text("MAVİ LOJİSTİK", size=18, weight="bold", color="white"),
                ], alignment=ft.MainAxisAlignment.CENTER),
                padding=ft.Padding.only(top=20, bottom=40)
            ),
            create_nav_item("Operasyon Merkezi", ft.Icons.DASHBOARD_ROUNDED, "Operasyon"),
            create_nav_item("Yönetim Paneli", ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED, "Yönetim"),
            create_nav_item("Sunucu Kontrolü", ft.Icons.DNS_OUTLINED, "Sunucu"),
            create_nav_item("Sistem Logları", ft.Icons.TERMINAL_ROUNDED, "Loglar"),
            create_nav_item("Ayarlar", ft.Icons.SETTINGS_ROUNDED, "Ayarlar"),
            
            ft.Container(expand=True), # Spacer
            
            ft.Container(
                content=ft.Text("v2.1.0 Premium", size=10, color=AppColors.TEXT_MUTED),
                padding=ft.Padding.only(left=20, bottom=20)
            )
        ], spacing=5),
        width=250,
        bgcolor=AppColors.SURFACE,
        padding=10,
    )

    # --- TOP HEADER ---
    header = ft.Container(
        content=ft.Row([
            ft.Text("Hoş Geldiniz, Yönetici", size=14, color=AppColors.TEXT_MUTED),
            ft.Row([
                ft.IconButton(icon=ft.Icons.NOTIFICATIONS_NONE, icon_color=AppColors.TEXT_MUTED),
                ft.CircleAvatar(content=ft.Text("Y"), bgcolor=AppColors.PRIMARY, radius=15),
            ], spacing=10)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.Padding.symmetric(vertical=10, horizontal=20),
        bgcolor=AppColors.BG_DEEP,
        border=ft.Border(bottom=ft.BorderSide(width=1, color="white10"))
    )

    layout = ft.Row(
        [
            sidebar,
            ft.Column([
                header,
                main_content
            ], expand=True, spacing=0)
        ],
        expand=True,
        spacing=0,
    )

    page.add(layout)
    asyncio.create_task(change_page("Yönetim"))
    page.update()

if __name__ == "__main__":
    ft.run(main)
