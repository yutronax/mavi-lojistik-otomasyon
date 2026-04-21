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
        self.llm_url_field = ft.TextField(
            label="LLM Sunucu URL (Groq/Ollama)",
            value="https://api.groq.com/openai/v1",
            border_radius=10,
            expand=True
        )
        self.llm_model_field = ft.TextField(
            label="LLM Model Adı",
            value="llama-3.1-8b-instant",
            border_radius=10,
            expand=True
        )
        self.llm_keys_field = ft.TextField(
            label="LLM API Anahtarları (Virgülle ayırın)",
            placeholder="gsk_..., gsk_...",
            border_radius=10,
            expand=True,
            multiline=True,
            min_lines=2
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
            config = await self.data_service.load_config("app_settings") or {}
            
            self.llm_url_field.value = config.get("llm_url", "https://api.groq.com/openai/v1")
            self.llm_model_field.value = config.get("llm_model", "llama-3.1-8b-instant")
            self.llm_keys_field.value = config.get("llm_keys", "")
            self.whapi_token_field.value = config.get("whapi_token", "")
            self.whapi_url_field.value = config.get("whapi_url", "https://gate.whapi.cloud")
            self.refresh_interval_field.value = str(config.get("refresh_interval", "60"))
            
            self.page.update()
        except Exception as e:
            self._show_error(f"Ayarlar yüklenemedi: {e}")

    async def save_settings(self, e):
        """Ayarları kaydeder"""
        try:
            config = {
                "llm_url": self.llm_url_field.value,
                "llm_model": self.llm_model_field.value,
                "llm_keys": self.llm_keys_field.value,
                "whapi_token": self.whapi_token_field.value,
                "whapi_url": self.whapi_url_field.value,
                "refresh_interval": int(self.refresh_interval_field.value or 60)
            }
            await self.data_service.save_config("app_settings", config)
            
            # Update env for underlying scripts expecting OS Env vars immediately
            os.environ["LLM_BASE_URL"] = self.llm_url_field.value
            os.environ["LLM_MODEL"] = self.llm_model_field.value
            os.environ["GROQ_API_KEYS"] = self.llm_keys_field.value
            
            # Reload keys in manager
            self.api_manager.load_keys(reason='settings_update')
            
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
        # Header (Yönetim Merkezi ile aynı stil)
        header = ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.SETTINGS_SUGGEST_ROUNDED, color=AppColors.PRIMARY, size=18),
                ft.Text("Sistem Ayarları", size=24, weight="bold", color=AppColors.TEXT),
            ]),
            ft.IconButton(
                icon=ft.Icons.SYNC,
                icon_color=AppColors.PRIMARY,
                on_click=lambda _: asyncio.create_task(self.load_settings()),
                tooltip="Ayarları Yenile"
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # Form Kartı
        form_content = ft.Container(
            content=ft.Column([
                ft.Text("Yapay Zeka (LLM) Yapılandırması", size=18, weight="bold", color=AppColors.TEXT),
                ft.Text("Mesaj ayrıştırma için Groq veya Ollama bilgileri", size=12, color=AppColors.TEXT_MUTED),
                ft.Divider(color="white10"),
                
                self.llm_url_field,
                self.llm_model_field,
                self.llm_keys_field,
                
                ft.Divider(height=20, color="transparent"),
                
                ft.Text("WhatsApp API Yapılandırması", size=18, weight="bold", color=AppColors.TEXT),
                ft.Divider(color="white10"),
                self.whapi_token_field,
                self.whapi_url_field,
                
                ft.Divider(height=20, color="transparent"),
                
                ft.Text("Uygulama Tercihleri", size=18, weight="bold", color=AppColors.TEXT),
                ft.Divider(color="white10"),
                self.refresh_interval_field,
                
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
            ], scroll=ft.ScrollMode.ADAPTIVE, spacing=15),
            padding=30,
            bgcolor=AppColors.SURFACE,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW],
            expand=True
        )

        content = ft.Column(
            [
                header,
                ft.Divider(color="white10", height=30),
                form_content
            ],
            expand=True,
            spacing=0
        )

        # İlk yükleme
        asyncio.create_task(self.load_settings())
        
        return content
