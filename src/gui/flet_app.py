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
from src.gui.components.log_viewer import LogPage

def main(page: ft.Page):
    print("DEBUG: Modular flet_app baslatildi.")
    page.title = "Mavi Lojistik - Yönetim Sistemi"
    apply_app_theme(page)
    
    # Sayfa nesnelerini hazirla
    op_center = OperationCenterPage(page)
    mgmt_center = ManagementCenterPage(page)
    log_page = LogPage(page)

    # Ana içerik alanı
    main_content = ft.Container(
        expand=True,
        padding=20,
    )

    async def change_page(page_name):
        print(f"DEBUG: Sayfa degistiliyor -> {page_name}")
        main_content.content = ft.ProgressRing()
        page.update()
        
        if page_name == "Operasyon":
            main_content.content = await op_center.get_view()
        elif page_name == "Yönetim":
            main_content.content = await mgmt_center.get_view()
        elif page_name == "Loglar":
            main_content.content = await log_page.get_view()
        elif page_name == "Ayarlar":
            main_content.content = ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.SETTINGS_SUGGEST_ROUNDED, color=AppColors.PRIMARY, size=28),
                    ft.Text("Sistem Ayarları", size=24, weight="bold", color=AppColors.TEXT),
                ]),
                ft.Divider(color="white10", height=20),
                ft.Container(
                    content=ft.Column([
                        ft.Text("API & Servis Yapılandırması", size=18, weight="bold", color=AppColors.TEXT),
                        ft.Text("WhatsApp ve Veritabanı bağlantı ayarlarını buradan yönetebilirsiniz.", size=12, color=AppColors.TEXT_MUTED),
                        ft.Divider(color="white10"),
                        
                        ft.TextField(
                            label="WhatsApp API Token (Whapi.cloud)", 
                            password=True, 
                            can_reveal_password=True,
                            border_color="white24",
                            focused_border_color=AppColors.PRIMARY
                        ),
                        ft.TextField(
                            label="Veritabanı Saklama Yolu", 
                            value="data/storage/",
                            border_color="white24",
                            focused_border_color=AppColors.PRIMARY
                        ),
                        
                        ft.Row([
                            ft.ElevatedButton(
                                "AYARLARI KAYDET", 
                                icon=ft.Icons.SAVE,
                                bgcolor=AppColors.PRIMARY, 
                                color="white",
                                width=200,
                                height=45
                            ),
                            ft.TextButton("Varsayılana Dön", icon=ft.Icons.RESTORE_ROUNDED)
                        ], spacing=10)
                    ], spacing=15),
                    padding=30,
                    bgcolor=AppColors.SURFACE,
                    border_radius=15,
                    shadow=[AppStyles.CARD_SHADOW]
                )
            ], expand=True, spacing=10)
        
        page.update()

    # --- SIDEBAR (Premium Navigation) ---
    def create_nav_item(text, icon, page_name):
        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=20, color=AppColors.TEXT_MUTED),
                ft.Text(text, size=14, weight="w500", color=AppColors.TEXT_MUTED),
            ], spacing=12),
            padding=ft.padding.symmetric(15, 20),
            border_radius=10,
            on_click=lambda _: asyncio.create_task(change_page(page_name)),
            on_hover=lambda e: self_hover(e),
        )

    def self_hover(e):
        e.control.bgcolor = "white10" if e.data == "true" else None
        e.control.content.controls[0].color = AppColors.PRIMARY if e.data == "true" else AppColors.TEXT_MUTED
        e.control.content.controls[1].color = "white" if e.data == "true" else AppColors.TEXT_MUTED
        e.control.update()

    sidebar = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.LOCAL_SHIPPING, color=AppColors.PRIMARY, size=30),
                    ft.Text("MAVİ LOJİSTİK", size=18, weight="bold", color="white"),
                ], alignment=ft.MainAxisAlignment.CENTER),
                padding=ft.padding.only(top=20, bottom=40)
            ),
            create_nav_item("Operasyon Merkezi", ft.Icons.DASHBOARD_ROUNDED, "Operasyon"),
            create_nav_item("Yönetim Paneli", ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED, "Yönetim"),
            create_nav_item("Sistem Logları", ft.Icons.TERMINAL_ROUNDED, "Loglar"),
            create_nav_item("Ayarlar", ft.Icons.SETTINGS_ROUNDED, "Ayarlar"),
            
            ft.Container(expand=True), # Spacer
            
            ft.Container(
                content=ft.Text("v2.1.0 Premium", size=10, color=AppColors.TEXT_MUTED),
                padding=ft.padding.only(left=20, bottom=20)
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
        padding=ft.padding.symmetric(10, 20),
        bgcolor=AppColors.BG_DEEP,
        border=ft.border.only(bottom=ft.border.BorderSide(1, "white10"))
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
    asyncio.create_task(change_page("Operasyon"))
    page.update()

if __name__ == "__main__":
    ft.run(main)
