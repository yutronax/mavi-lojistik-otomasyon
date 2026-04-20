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
        # Eğer zaten çalışıyorsa yeni bir tane başlatma
        if getattr(self, "_active_task", False):
            return
        
        self._active_task = True
        self.is_watching = True
        
        # Dosya yoksa oluştur
        if not os.path.exists(self.log_path):
            try:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                with open(self.log_path, 'a') as f:
                    pass
            except:
                pass

        # ILK YÜKLEME OPTİMİZASYONU
        try:
            current_size = os.path.getsize(self.log_path)
            if current_size > 20480: # 20KB
                last_size = current_size - 20480
                first_read = True
            else:
                last_size = 0
                first_read = False
        except:
            last_size = 0
            first_read = False

        while self.is_watching:
            try:
                # Kontrolün sayfada olup olmadığını kontrol et
                if not self.log_content.page:
                    await asyncio.sleep(2)
                    continue

                if not os.path.exists(self.log_path):
                    await asyncio.sleep(2)
                    continue

                current_size = os.path.getsize(self.log_path)
                
                if current_size < last_size:
                    self.log_content.controls.clear()
                    last_size = 0
                    first_read = False
                
                if current_size > last_size:
                    with open(self.log_path, 'r', encoding='utf-8', errors='replace') as f:
                        f.seek(last_size)
                        lines = f.readlines()
                        
                        if first_read:
                            lines = lines[1:] if len(lines) > 1 else []
                            first_read = False

                        if lines:
                            for line in lines:
                                line_text = line.strip()
                                if not line_text: continue
                                
                                color = "white"
                                if "ERROR" in line or "CRITICAL" in line or "[FAIL]" in line:
                                    color = AppColors.DANGER
                                elif "WARNING" in line or "[WARN]" in line:
                                    color = AppColors.WARNING
                                elif "SUCCESS" in line or "[OK]" in line:
                                    color = AppColors.SUCCESS
                                elif "INFO" in line or "[INFO]" in line:
                                    color = "#64b5f6"
                                
                                self.log_content.controls.append(
                                    ft.Text(line_text, color=color, size=11, font_family="Consolas")
                                )
                            
                            if len(self.log_content.controls) > 500:
                                self.log_content.controls = self.log_content.controls[-500:]
                            
                            last_size = current_size
                            
                            # Sayfaya hala bağlıysa güncelle
                            if self.log_content.page:
                                self.log_content.update()
                
            except Exception as e:
                # Terminal log kirliliğini önlemek için sadece kritik hataları bas
                if "Control must be added to the page first" not in str(e):
                    print(f"Log watch error: {e}")
            
            await asyncio.sleep(2)
        
        self._active_task = False

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
