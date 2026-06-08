
import flet as ft
import asyncio
import datetime
import os
from src.gui.styles import AppColors, AppStyles
from src.utils.server_manager_async import AsyncServerManager
from src.services.data_service import DataService
from src.services.data_service_async import AsyncDataService
from src.utils.command_rate_limiter import get_rate_limiter
from src.utils.health_monitor import get_health_monitor
from src.utils.access_control import get_access_control, Permission
from src.gui.components.vps_monitoring_dashboard import VPSMonitoringDashboard


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
        
        # Data Service for config sync
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        self.data_service = AsyncDataService(DataService(root_dir))

        
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
        
        # Autonomous Settings
        self.auto_onay_switch = ft.Switch(
            label="Otomatik Onay (AUTO_SUBMIT)",
            value=False,
            active_color=AppColors.SUCCESS,
            on_change=lambda e: asyncio.create_task(self._toggle_auto_onay(e))
        )
        
        self.auto_onay_status = ft.Text(
            "Yükleri otomatik olarak YukBurada'ya gönderir",
            size=12,
            color=AppColors.TEXT_MUTED
        )
        
        # Performance/Safe Threading
        self.status_update_active = False

        # Health monitoring
        self.health_monitor = get_health_monitor()
        self.health_monitor.register_alert_callback(self._show_health_alert)

        # VPS Monitoring Dashboard
        self.monitoring_dashboard = VPSMonitoringDashboard(page)


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
                    delta = datetime.timedelta(milliseconds=uptime_ms)
                    self.uptime_text.value = str(delta).split('.')[0]
                else:
                    self.uptime_text.value = "0s"
                
                self.page.update()
            except Exception as e:
                print(f"Status update error: {e}")
            
            await asyncio.sleep(5)

    async def _load_settings(self):
        """MongoDB'den güncel otonom ayarlarını yükler"""
        try:
            auto_onay = await self.data_service.load_config('vps_auto_onay')
            # Eğer config yoksa None dönebilir, varsayılan False
            if auto_onay is None: auto_onay = False

            self.auto_onay_switch.value = bool(auto_onay)
            self._update_auto_onay_text(bool(auto_onay))
            self.page.update()
        except Exception as e:
            print(f"Error loading VPS settings: {e}")

    def _show_health_alert(self, message: str):
        """Show health alert in UI"""
        self.page.snack_bar = ft.SnackBar(
            ft.Text(message),
            bgcolor=AppColors.DANGER if "🔴" in message else AppColors.DANGER,
            duration=5000
        )
        self.page.snack_bar.open = True
        try:
            self.page.update()
        except:
            pass

    def _update_auto_onay_text(self, is_active):
        if is_active:
            self.auto_onay_status.value = "AKTİF: Puanı yüksek yükler otomatik onaylanır."
            self.auto_onay_status.color = AppColors.SUCCESS
        else:
            self.auto_onay_status.value = "PASİF: Yükler sadece manuel onay ile gönderilir."
            self.auto_onay_status.color = AppColors.TEXT_MUTED

    async def _toggle_auto_onay(self, e):
        new_state = e.control.value
        self._update_auto_onay_text(new_state)
        self.page.update()
        
        success = await self.data_service.save_config('vps_auto_onay', new_state)
        
        if success:
            self.page.snack_bar = ft.SnackBar(
                ft.Text(f"Otomatik Onay {'Açıldı' if new_state else 'Kapatıldı'} (Bulut Senkronize Edildi)"),
                bgcolor=AppColors.SUCCESS if new_state else AppColors.PRIMARY
            )
        else:
            self.page.snack_bar = ft.SnackBar(ft.Text("Ayarlar senkronize edilemedi!"), bgcolor=AppColors.DANGER)
            # Geri al
            e.control.value = not new_state
            self._update_auto_onay_text(not new_state)
            
        self.page.snack_bar.open = True
        self.page.update()

    async def _refresh_logs(self, e=None):
        self.log_display.value = "Yükleniyor..."
        self.page.update()
        logs = await self.manager.get_logs(lines=50)
        self.log_display.value = logs
        self.page.update()


    async def _run_command(self, cmd_type):
        # Permission check
        access_ctrl = get_access_control()
        permission_map = {
            "restart": Permission.RESTART_SERVICE,
            "stop": Permission.STOP_SERVICE,
            "start": Permission.START_SERVICE,
            "pull": Permission.GIT_PULL
        }

        required_permission = permission_map.get(cmd_type)
        if required_permission and not access_ctrl.has_permission(required_permission):
            self.page.snack_bar = ft.SnackBar(
                ft.Text(f"Yetkiniz yok: {required_permission.value}"),
                bgcolor=AppColors.DANGER
            )
            self.page.snack_bar.open = True
            self.page.update()
            return

        # Rate limiting check
        limiter = get_rate_limiter()
        allowed, message = limiter.is_allowed(cmd_type)

        if not allowed:
            self.page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=AppColors.DANGER)
            self.page.snack_bar.open = True
            self.page.update()
            return

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

        # Record the operation
        limiter.record_operation(cmd_type)

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
                ft.Text("Sunucu Operasyonları", size=16, weight="bold", color=AppColors.TEXT),
                ft.Row([
                    ft.ElevatedButton(
                        content=ft.Row([ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED), ft.Text("Başlat")], spacing=10),
                        bgcolor=AppColors.SUCCESS,
                        color="white",
                        on_click=lambda _: asyncio.create_task(self._run_command("start")),
                        expand=True,
                        height=50,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                    ),
                    ft.ElevatedButton(
                        content=ft.Row([ft.Icon(ft.Icons.STOP_CIRCLE_ROUNDED), ft.Text("Durdur")], spacing=10),
                        bgcolor=AppColors.DANGER,
                        color="white",
                        on_click=lambda _: asyncio.create_task(self._run_command("stop")),
                        expand=True,
                        height=50,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                    ),
                ], spacing=15),
            ], spacing=15),
            padding=20,
            bgcolor=AppColors.SURFACE,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW]
        )

        # Autonomous Settings Container
        auto_settings = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=AppColors.PRIMARY, size=18),
                    ft.Text("Otonom Modu Ayarları", size=16, weight="bold", color=AppColors.TEXT),
                ]),
                ft.Divider(color="white10"),
                ft.Row([
                    ft.Column([
                        self.auto_onay_switch,
                        self.auto_onay_status,
                    ], expand=True),
                    ft.Icon(
                        ft.Icons.BOLT_ROUNDED, 
                        color=AppColors.SUCCESS if self.auto_onay_switch.value else AppColors.TEXT_MUTED,
                        size=30
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=10),
            padding=20,
            bgcolor=AppColors.SURFACE,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW]
        )

        content = ft.Column([
            # VPS Monitoring Dashboard
            self.monitoring_dashboard.build(),

            ft.Container(height=15),

            ft.Row([
                ft.Column([
                    ft.Text("VPS Kontrol Merkezi", size=24, weight="bold", color=AppColors.TEXT),
                    ft.Text("Sunucu durumunu ve loglarını buradan yönetebilirsiniz", size=12, color=AppColors.TEXT_MUTED),
                ]),
                self.status_chip
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(color="white10", height=30),

            # Metrics
            ft.Row([
                self._create_stat_card("CPU", ft.Icons.MEMORY, self.cpu_text),
                self._create_stat_card("RAM", ft.Icons.STORAGE, self.mem_text),
                self._create_stat_card("ÇALIŞMA SÜRESİ", ft.Icons.TIMER_OUTLINED, self.uptime_text),
            ], spacing=10),
            
            ft.Container(height=10),
            
            # Controls
            controls,
            
            ft.Container(height=5),
            
            # Auto Settings
            auto_settings,
            
            ft.Container(height=5),
            
            # Terminal
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=AppColors.PRIMARY, size=18),
                            ft.Text("Terminal & Sistem Logları (Son 50)", size=16, weight="bold", color=AppColors.TEXT),
                        ], spacing=10),
                        ft.ElevatedButton(
                            "Terminali Çek",
                            icon=ft.Icons.REFRESH_ROUNDED,
                            on_click=self._refresh_logs,
                            bgcolor=AppColors.PRIMARY,
                            color="white",
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=5),
                    self.terminal_box
                ], spacing=10),
                padding=20,
                bgcolor=AppColors.SURFACE,
                border_radius=15,
                shadow=[AppStyles.CARD_SHADOW]
            )
            
        ], expand=True, spacing=15, scroll=ft.ScrollMode.ADAPTIVE)

        # Background update task - Only starts once
        if not self.status_update_active:
            self.status_update_active = True
            asyncio.create_task(self._update_status())
            asyncio.create_task(self._refresh_logs())
            asyncio.create_task(self._load_settings())
            asyncio.create_task(self.health_monitor.monitor_health(self.manager.get_status_summary))
            asyncio.create_task(self.monitoring_dashboard.start_monitoring())

        return content
