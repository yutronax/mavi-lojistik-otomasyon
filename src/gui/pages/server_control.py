
import flet as ft
import asyncio
import datetime
from src.gui.styles import AppColors, AppStyles
from src.utils.server_manager_async import AsyncServerManager


class ServerControlPage:
    """
    Purpose:      Mobile-friendly Remote Server Control Interface
    Inputs:       Flet Page object
    Outputs:      Interactive server management UI
    Dependencies: ServerManager, flet
    Usage:        Integrated into sidebar of flet_app.py
    """
    def __init__(self, page: ft.Page):
        self.page = page
        self.manager = AsyncServerManager()

        
        # UI Components
        self.status_chip = ft.Chip(
            label=ft.Text("OFFLINE", size=12, weight="bold"),
            leading=ft.Icon(ft.Icons.CIRCLE, size=12, color=AppColors.DANGER),
            bgcolor=ft.Colors.with_opacity(0.1, AppColors.DANGER),
        )
        
        self.cpu_text = ft.Text("0%", size=14, weight="bold", color=AppColors.TEXT)
        self.mem_text = ft.Text("0 MB", size=14, weight="bold", color=AppColors.TEXT)
        self.uptime_text = ft.Text("0s", size=14, weight="bold", color=AppColors.TEXT)
        
        self.log_display = ft.Text(
            value="Loglar bekleniyor...",
            size=11,
            color=AppColors.TEXT_MUTED,
            font_family="monospace",
            selectable=True
        )
        
        self.terminal_box = ft.Container(
            content=ft.Column([self.log_display], scroll=ft.ScrollMode.ALWAYS, expand=True),
            bgcolor="#050a18",
            padding=ft.Padding.all(15),
            border_radius=15,
            border=ft.Border.all(width=1, color="white10"),
            expand=True,
            height=300
        )
        
        # Performance/Safe Threading
        self.status_update_active = False


    async def _update_status(self):
        while True:
            try:
                stats = await self.manager.get_status_summary()
                status = stats.get("status", "offline")

                
                # Update Status Chip
                if status == "online":
                    self.status_chip.label.value = "ÇALIŞIYOR"
                    self.status_chip.leading.color = AppColors.SUCCESS
                    self.status_chip.bgcolor = ft.Colors.with_opacity(0.1, AppColors.SUCCESS)
                else:
                    self.status_chip.label.value = status.upper()
                    self.status_chip.leading.color = AppColors.DANGER
                    self.status_chip.bgcolor = ft.Colors.with_opacity(0.1, AppColors.DANGER)
                
                self.cpu_text.value = f"{stats.get('cpu', 0)}%"
                self.mem_text.value = f"{int(stats.get('memory', 0))} MB"
                
                uptime_ms = stats.get('uptime', 0)
                if uptime_ms > 0:
                    delta = datetime.timedelta(milliseconds=datetime.datetime.now().timestamp()*1000 - uptime_ms)
                    self.uptime_text.value = str(delta).split('.')[0]
                else:
                    self.uptime_text.value = "0s"
                
                self.page.update()
            except Exception as e:
                print(f"Status update error: {e}")
            
            await asyncio.sleep(5)

    async def _refresh_logs(self, e=None):
        self.log_display.value = "Yükleniyor..."
        self.page.update()
        logs = await self.manager.get_logs(lines=50)
        self.log_display.value = logs
        self.page.update()


    async def _run_command(self, cmd_type):
        self.page.snack_bar = ft.SnackBar(ft.Text("Komut gönderildi..."), bgcolor=AppColors.PRIMARY)
        self.page.snack_bar.open = True
        self.page.update()
        
        success, output = (False, "Unknown")
        if cmd_type == "restart":
            success, output = await self.manager.restart()
        elif cmd_type == "stop":
            success, output = await self.manager.stop()
        elif cmd_type == "start":
            success, output = await self.manager.start()
        elif cmd_type == "pull":
            success, output = await self.manager.git_pull()

            
        self.page.snack_bar = ft.SnackBar(
            ft.Text("Başarılı" if success else f"Hata: {output}"),
            bgcolor=AppColors.SUCCESS if success else AppColors.DANGER,
            duration=3000
        )
        self.page.snack_bar.open = True
        await self._refresh_logs()
        self.page.update()

    def _create_stat_card(self, title, icon, value_ref):
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(icon, size=16, color=AppColors.PRIMARY), ft.Text(title, size=12, color=AppColors.TEXT_MUTED)]),
                value_ref
            ], spacing=5),
            padding=15,
            bgcolor=AppColors.SURFACE,
            border_radius=12,
            expand=True,
            shadow=[AppStyles.CARD_SHADOW]
        )

    async def get_view(self):
        # Action Buttons
        controls = ft.Container(
            content=ft.Column([
                ft.Text("Sistem Kontrolleri", size=16, weight="bold", color=AppColors.TEXT),
                ft.ResponsiveRow([
                    ft.Button(
                        content="Yeniden Başlat", 
                        icon=ft.Icons.RESTART_ALT, 
                        bgcolor=AppColors.PRIMARY, 
                        color="white",
                        on_click=lambda _: asyncio.create_task(self._run_command("restart")),
                        col={"xs": 6, "sm": 3}
                    ),
                    ft.Button(
                        content="Durdur", 
                        icon=ft.Icons.STOP_CIRCLE_ROUNDED, 
                        bgcolor=AppColors.DANGER, 
                        color="white",
                        on_click=lambda _: asyncio.create_task(self._run_command("stop")),
                        col={"xs": 6, "sm": 3}
                    ),
                    ft.Button(
                        content="Başlat", 
                        icon=ft.Icons.PLAY_ARROW_ROUNDED, 
                        bgcolor=AppColors.SUCCESS, 
                        color="white",
                        on_click=lambda _: asyncio.create_task(self._run_command("start")),
                        col={"xs": 6, "sm": 3}
                    ),
                    ft.Button(
                        content="Kod Güncelle", 
                        icon=ft.Icons.DOWNLOAD_ROUNDED, 
                        bgcolor=AppColors.WARNING, 
                        color="white",
                        on_click=lambda _: asyncio.create_task(self._run_command("pull")),
                        col={"xs": 6, "sm": 3}
                    ),
                ], spacing=10),
            ], spacing=10),
            padding=20,
            bgcolor=AppColors.SURFACE,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW]
        )

        content = ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("Sunucu Yönetimi", size=24, weight="bold", color=AppColors.TEXT),
                    ft.Text("Mavi Lojistik Otonom Motor Kontrolü", size=12, color=AppColors.TEXT_MUTED),
                ]),
                self.status_chip
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(color="white10", height=30),
            
            # Metrics
            ft.Row([
                self._create_stat_card("CPU", ft.Icons.MEMORY, self.cpu_text),
                self._create_stat_card("RAM", ft.Icons.STORAGE, self.mem_text),
                self._create_stat_card("UPTIME", ft.Icons.TIMER_OUTLINED, self.uptime_text),
            ], spacing=10),
            
            ft.Container(height=10),
            
            # Controls
            controls,
            
            ft.Container(height=10),
            
            # Terminal
            ft.Row([
                ft.Text("Terminal & Log Geçmişi", size=16, weight="bold", color=AppColors.TEXT),
                ft.IconButton(ft.Icons.REFRESH_ROUNDED, on_click=self._refresh_logs, icon_color=AppColors.PRIMARY)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.terminal_box
            
        ], expand=True, spacing=15, scroll=ft.ScrollMode.ADAPTIVE)

        # Background update task - Only starts once
        if not self.status_update_active:
            self.status_update_active = True
            asyncio.create_task(self._update_status())
            asyncio.create_task(self._refresh_logs())

        
        return content
