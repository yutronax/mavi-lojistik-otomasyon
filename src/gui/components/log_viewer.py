import flet as ft
import os
import asyncio
from src.gui.styles import AppColors, AppStyles

class LogViewer(ft.Container):
    def __init__(self, log_path: str, height: int = 400):
        super().__init__()
        self.log_path = log_path
        self.height = height
        self.is_watching = False
        
        self.log_content = ft.ListView(
            expand=True,
            spacing=2,
            padding=ft.Padding.all(10),
            auto_scroll=True
        )
        
        # Container properties
        self.content = self.log_content
        self.bgcolor = AppColors.BG_DEEP
        self.border_radius = 12
        self.border = ft.Border.all(width=1, color="white10")
        self.padding = ft.Padding.all(5)

    async def start_watch(self):
        self.is_watching = True
        last_size = 0
        
        # Dosya yoksa oluştur (veya hata verme)
        if not os.path.exists(self.log_path):
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, 'a') as f:
                pass

        while self.is_watching:
            try:
                current_size = os.path.getsize(self.log_path)
                if current_size < last_size: # Dosya temizlenmiş olabilir
                    self.log_content.controls.clear()
                    last_size = 0
                
                if current_size > last_size:
                    with open(self.log_path, 'r', encoding='utf-8', errors='replace') as f:
                        f.seek(last_size)
                        new_lines = f.readlines()
                        
                        for line in new_lines:
                            color = "white"
                            if "ERROR" in line or "CRITICAL" in line:
                                color = AppColors.DANGER
                            elif "WARNING" in line:
                                color = AppColors.WARNING
                            elif "SUCCESS" in line or "✅" in line:
                                color = AppColors.SUCCESS
                            elif "INFO" in line:
                                color = "#64b5f6" # Light blue
                            
                            self.log_content.controls.append(
                                ft.Text(
                                    line.strip(),
                                    color=color,
                                    size=12,
                                    font_family="Consolas"
                                )
                            )
                        
                        last_size = current_size
                        self.update()
                
            except Exception as e:
                print(f"Log watch error: {e}")
            
            await asyncio.sleep(2) # 2 saniyede bir kontrol et

    def stop_watch(self):
        self.is_watching = False

class LogPage:
    def __init__(self, page: ft.Page):
        self.page = page
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        
        # Farklı log dosyaları için izleyiciler
        self.orchestrator_log = LogViewer(os.path.join(self.root_dir, "tools", "orchestrator.log"), height=300)
        self.system_log = LogViewer(os.path.join(self.root_dir, "logs", f"MaviLojistikGUI_{os.getpid()}.log"), height=300)

    async def get_view(self):
        content = ft.Column(
            [
                ft.Row([
                    ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=AppColors.PRIMARY, size=28),
                    ft.Text("Sistem Logları", size=24, weight="bold", color=AppColors.TEXT),
                ]),
                ft.Divider(color="white10", height=20),
                
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.MANAGE_SEARCH_ROUNDED, color=AppColors.ACCENT, size=18),
                            ft.Text("Orchestrator (Canlı Veri Akışı)", weight="bold", color=AppColors.TEXT),
                        ]),
                        self.orchestrator_log,
                    ], spacing=10),
                    padding=20,
                    bgcolor=AppColors.SURFACE,
                    border_radius=15,
                    shadow=[AppStyles.CARD_SHADOW]
                ),
                
                ft.Divider(height=20, color="transparent"),
                
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.BUG_REPORT_ROUNDED, color=AppColors.WARNING, size=18),
                            ft.Text("Uygulama Logları", weight="bold", color=AppColors.TEXT),
                        ]),
                        self.system_log,
                    ], spacing=10),
                    padding=20,
                    bgcolor=AppColors.SURFACE,
                    border_radius=15,
                    shadow=[AppStyles.CARD_SHADOW]
                ),
            ],
            expand=True,
            scroll=ft.ScrollMode.ADAPTIVE,
            spacing=10
        )

        # İzlemeyi başlat
        asyncio.create_task(self.orchestrator_log.start_watch())
        asyncio.create_task(self.system_log.start_watch())
        
        return content
