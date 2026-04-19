import flet as ft
import os
import asyncio
from src.gui.styles import AppColors, AppStyles
from src.services.data_service import DataService
from src.services.data_service_async import AsyncDataService
from src.utils.api_key_manager import APIKeyManager

class SettingsPage:
    def __init__(self, page: ft.Page):
        self.page = page
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        self.data_service = AsyncDataService(DataService(self.root_dir))
        self.api_manager = APIKeyManager(self.root_dir)
        
        # UI Bileşenleri
        self.gemini_key_field = ft.TextField(
            label="Gemini API Key",
            password=True,
            can_reveal_password=True,
            border_radius=10,
            expand=True
        )
        self.whapi_token_field = ft.TextField(
            label="Whapi Token",
            password=True,
            can_reveal_password=True,
            border_radius=10,
            expand=True
        )
        self.whapi_url_field = ft.TextField(
            label="Whapi API URL",
            value="https://gate.whapi.cloud",
            border_radius=10,
            expand=True
        )
        self.refresh_interval_field = ft.TextField(
            label="Otomatik Yenileme (Saniye)",
            value="60",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=10,
            expand=True
        )
        
    async def load_settings(self):
        """Mevcut ayarları yükler"""
        try:
            keys = self.api_manager.get_all_keys()
            self.gemini_key_field.value = keys.get("GEMINI_API_KEY", "")
            self.whapi_token_field.value = keys.get("WHATSAPP_TOKEN", "") or keys.get("WHAPI_TOKEN", "")
            
            # config.json'dan ek ayarları oku
            # Gelecekte eklenecek...
            
            self.page.update()
        except Exception as e:
            self._show_error(f"Ayarlar yüklenemedi: {e}")

    async def save_settings(self, e):
        """Ayarları kaydeder"""
        try:
            # API Anahtarlarını kaydet (.env)
            self.api_manager.set_key("GEMINI_API_KEY", self.gemini_key_field.value)
            self.api_manager.set_key("WHAPI_TOKEN", self.whapi_token_field.value)
            
            # Diğer ayarları config.json'a kaydet
            config = {
                "whapi_url": self.whapi_url_field.value,
                "refresh_interval": int(self.refresh_interval_field.value or 60)
            }
            await self.data_service.save_config("app_settings", config)
            
            self._show_success("Ayarlar başarıyla kaydedildi.")
        except Exception as e:
            self._show_error(f"Kaydetme hatası: {e}")

    def _show_error(self, msg):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=AppColors.DANGER)
        self.page.snack_bar.open = True
        self.page.update()

    def _show_success(self, msg):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=AppColors.SUCCESS)
        self.page.snack_bar.open = True
        self.page.update()

    async def get_view(self):
        content = ft.Column(
            [
                ft.Row([
                    ft.Text("Ayarlar", style=AppStyles.HEADER_TITLE),
                    ft.IconButton(icon=ft.Icon(icon="sync"), on_click=lambda _: asyncio.create_task(self.load_settings()))
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Divider(),
                
                ft.Container(
                    content=ft.Column([
                        ft.Text("API Yapılandırması", size=18, weight="bold"),
                        ft.Row([self.gemini_key_field]),
                        ft.Row([self.whapi_token_field]),
                        ft.Row([self.whapi_url_field]),
                        
                        ft.Divider(height=20, color="transparent"),
                        
                        ft.Text("Uygulama Ayarları", size=18, weight="bold"),
                        ft.Row([self.refresh_interval_field]),
                        
                        ft.Divider(height=40, color="transparent"),
                        
                        ft.Button(
                            content="AYARLARI KAYDET",
                            icon=ft.Icons.SAVE,
                            bgcolor=AppColors.PRIMARY,
                            color="white",
                            on_click=lambda e: asyncio.create_task(self.save_settings(e)),
                            height=50,
                            width=float("inf")
                        ),
                    ], scroll=ft.ScrollMode.ADAPTIVE),
                    padding=20,
                    bgcolor=AppColors.SURFACE,
                    border_radius=12,
                    expand=True
                )
            ],
            expand=True,
            spacing=20
        )

        # İlk yükleme
        asyncio.create_task(self.load_settings())
        
        return content
