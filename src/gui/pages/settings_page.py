import flet as ft
import os
import asyncio
from src.gui.styles import AppColors
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
            label="LLM Sunucu URL (DeepSeek/Ollama)",
            value="https://api.deepseek.com/v1",
            border_radius=12,
            expand=True,
            filled=True,
            bgcolor=AppColors.SURFACE_LIGHT,
            focused_border_color=AppColors.ACCENT
        )
        self.llm_model_field = ft.TextField(
            label="LLM Model Adı",
            value="deepseek-chat",
            border_radius=12,
            expand=True,
            filled=True,
            bgcolor=AppColors.SURFACE_LIGHT,
            focused_border_color=AppColors.ACCENT
        )
        self.llm_keys_field = ft.TextField(
            label="LLM API Anahtarları (Virgülle ayırın)",
            placeholder="sk_..., sk_...",
            border_radius=12,
            expand=True,
            multiline=True,
            min_lines=2,
            password=True,
            can_reveal_password=True,
            filled=True,
            bgcolor=AppColors.SURFACE_LIGHT,
            focused_border_color=AppColors.ACCENT
        )
        
    async def load_settings(self):
        """Mevcut ayarları yükler"""
        try:
            config = await self.data_service.load_config("app_settings") or {}

            self.llm_url_field.value = config.get("llm_url", "https://api.deepseek.com/v1")
            self.llm_model_field.value = config.get("llm_model", "deepseek-chat")
            self.llm_keys_field.value = config.get("llm_keys", "")

            self.page.update()
        except Exception as e:
            self._show_error(f"Ayarlar yüklenemedi: {e}")

    async def save_settings(self, e):
        """Ayarları kaydeder"""
        try:
            config = {
                "llm_url": self.llm_url_field.value,
                "llm_model": self.llm_model_field.value,
                "llm_keys": self.llm_keys_field.value
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

        # Form Kartı — Modernize tasarım
        llm_header = ft.Row([
            ft.Icon(ft.Icons.SMART_TOY, color=AppColors.ACCENT, size=24),
            ft.Text("Yapay Zeka (LLM) Yapılandırması", size=20, weight="bold", color=AppColors.TEXT),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        form_content = ft.Container(
            content=ft.Column([
                llm_header,
                ft.Text("Mesaj ayrıştırma için Groq veya Ollama bilgileri", size=12, color=AppColors.TEXT_MUTED),
                ft.Divider(color=AppColors.PRIMARY, height=2),

                ft.Divider(height=20, color="transparent"),

                self.llm_url_field,
                ft.Divider(height=12, color="transparent"),
                self.llm_model_field,
                ft.Divider(height=12, color="transparent"),
                self.llm_keys_field,

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
            border_radius=20,
            shadow=[ft.BoxShadow(
                blur_radius=25,
                spread_radius=2,
                color="black40",
                offset=ft.Offset(0, 8)
            )],
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
