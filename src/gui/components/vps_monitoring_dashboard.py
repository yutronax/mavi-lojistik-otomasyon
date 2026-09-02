"""
VPS Monitoring Dashboard Component
Real-time server metrics and alerts visualization
"""

import flet as ft
import asyncio
from datetime import datetime
from src.gui.styles import AppColors, AppStyles
from src.utils.server_manager_async import AsyncServerManager
from src.utils.access_control import get_access_control, Permission


class VPSMonitoringDashboard:
    """Real-time VPS monitoring with metrics visualization"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.manager = AsyncServerManager()
        self.update_interval = 10  # seconds
        self.is_monitoring = False

        # Metric displays
        self.cpu_gauge = self._create_gauge("CPU", "0%", AppColors.PRIMARY)
        self.memory_gauge = self._create_gauge("RAM", "0 MB", AppColors.ACCENT)
        self.disk_gauge = self._create_gauge("DISK", "0%", AppColors.DANGER)

        # Status indicators
        self.service_status = ft.Chip(
            label=ft.Text("OFFLINE", size=12, weight="bold"),
            leading=ft.Icon(ft.Icons.CIRCLE, size=12, color=AppColors.DANGER),
            bgcolor=ft.Colors.with_opacity(0.1, AppColors.DANGER),
        )

        self.uptime_text = ft.Text("0d 0h 0m", size=14, weight="bold", color=AppColors.TEXT)
        self.load_avg_text = ft.Text("1m: 0.0 | 5m: 0.0 | 15m: 0.0", size=11, color=AppColors.TEXT_MUTED)

        # Alerts section
        self.alerts_list = ft.ListView(expand=True, spacing=5, padding=10)
        self.alerts = []
        self.max_alerts = 20

        # Last update time
        self.last_update_text = ft.Text("Hiçbir zaman", size=10, color=AppColors.TEXT_MUTED)

    def _create_gauge(self, label: str, value: str, color: str) -> ft.Column:
        """Create a metric gauge display"""
        return ft.Column(
            [
                ft.Text(label, size=12, weight="bold", color=AppColors.TEXT_MUTED),
                ft.Text(value, size=24, weight="bold", color=color),
                ft.ProgressBar(value=0, width=120, color=color),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5,
        )

    async def start_monitoring(self):
        """Start continuous monitoring"""
        self.is_monitoring = True
        while self.is_monitoring:
            try:
                await self._update_metrics()
            except Exception as e:
                print(f"Monitoring error: {e}")
            await asyncio.sleep(self.update_interval)

    async def _update_metrics(self):
        """Fetch and update metrics"""
        try:
            stats = await self.manager.get_status_summary()

            # Update service status
            status = stats.get("status", "offline")
            if status in ["online", "running", "connected"]:
                self.service_status.label.value = "ÇALIŞIYOR"
                self.service_status.leading.color = AppColors.SUCCESS
                self.service_status.bgcolor = ft.Colors.with_opacity(0.1, AppColors.SUCCESS)
            else:
                self.service_status.label.value = status.upper()
                self.service_status.leading.color = AppColors.DANGER
                self.service_status.bgcolor = ft.Colors.with_opacity(0.1, AppColors.DANGER)

            # Update CPU
            cpu = stats.get("cpu", 0)
            self.cpu_gauge.controls[1].value = f"{int(cpu)}%"
            self.cpu_gauge.controls[2].value = min(cpu / 100, 1.0)

            # Update Memory
            memory = stats.get("memory", 0)
            self.memory_gauge.controls[1].value = f"{int(memory)} MB"
            self.memory_gauge.controls[2].value = min(memory / 8192, 1.0)  # Assume 8GB

            # Update Disk
            disk = stats.get("disk", 0)
            self.disk_gauge.controls[1].value = f"{disk}%"
            self.disk_gauge.controls[2].value = disk / 100

            # Update Uptime
            uptime_ms = stats.get("uptime", 0)
            if uptime_ms > 0:
                total_seconds = uptime_ms // 1000
                days = total_seconds // 86400
                hours = (total_seconds % 86400) // 3600
                minutes = (total_seconds % 3600) // 60
                self.uptime_text.value = f"{days}d {hours}h {minutes}m"

            # Update Load Average
            system = stats.get("system", {})
            load_avg = system.get("load_average", {})
            if load_avg:
                load_str = f"1m: {load_avg.get('1min', 0):.1f} | 5m: {load_avg.get('5min', 0):.1f} | 15m: {load_avg.get('15min', 0):.1f}"
                self.load_avg_text.value = load_str

            # Check for alerts
            self._check_alerts(cpu, memory, disk)

            # Update last check time
            self.last_update_text.value = f"Son güncelleme: {datetime.now().strftime('%H:%M:%S')}"

            self.page.update()

        except Exception as e:
            print(f"Metric update error: {e}")

    def _check_alerts(self, cpu: float, memory: float, disk: int):
        """Check metrics and generate alerts"""
        new_alerts = []

        if cpu > 80:
            new_alerts.append(("🔴 Yüksek CPU", f"{int(cpu)}% - Processler kontrol edin", AppColors.DANGER))

        if memory > 7000:  # 7GB
            new_alerts.append(("🔴 Yüksek Bellek", f"{int(memory)}MB - Temizleme gerekli", AppColors.DANGER))

        if disk > 90:
            new_alerts.append(("🔴 Disk Dolu", f"{disk}% - Acil temizleme!", AppColors.DANGER))

        # Add new alerts that aren't already in the list
        for title, msg, color in new_alerts:
            if not any(a[0] == title for a in self.alerts):
                self.alerts.insert(0, (title, msg, color))
                self._update_alerts_display()

        # Keep only last N alerts
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[:self.max_alerts]
            self._update_alerts_display()

    def _update_alerts_display(self):
        """Update alerts list display"""
        items = []

        for title, msg, color in self.alerts[:20]:
            items.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(title, size=12, weight="bold", color=color),
                        ft.Text(msg, size=11, color=AppColors.TEXT_MUTED),
                        ft.Text(datetime.now().strftime("%H:%M:%S"), size=9, color=AppColors.TEXT_MUTED),
                    ], spacing=3),
                    padding=10,
                    bgcolor=ft.Colors.with_opacity(0.05, color),
                    border_radius=8,
                    border=ft.Border(left=ft.BorderSide(3, color))
                )
            )

        self.alerts_list.controls = items
        self.page.update()

    def stop_monitoring(self):
        """Stop monitoring"""
        self.is_monitoring = False

    def build(self) -> ft.Container:
        """Build the dashboard"""
        # Access control check
        access = get_access_control()
        if not access.has_permission(Permission.VIEW_METRICS):
            return ft.Container(
                content=ft.Column([
                    ft.Text("Yetkiniz yok", color=AppColors.DANGER)
                ]),
                padding=20,
            )

        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.Column([
                        ft.Text("VPS Monitoring", size=20, weight="bold", color=AppColors.TEXT),
                        self.last_update_text,
                    ], spacing=3),
                    self.service_status,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Divider(color="white10", height=30),

                # Metrics Grid
                ft.Row([
                    ft.Container(
                        content=self.cpu_gauge,
                        padding=15,
                        bgcolor=AppColors.SURFACE,
                        border_radius=12,
                        expand=True,
                        shadow=[AppStyles.CARD_SHADOW],
                    ),
                    ft.Container(
                        content=self.memory_gauge,
                        padding=15,
                        bgcolor=AppColors.SURFACE,
                        border_radius=12,
                        expand=True,
                        shadow=[AppStyles.CARD_SHADOW],
                    ),
                    ft.Container(
                        content=self.disk_gauge,
                        padding=15,
                        bgcolor=AppColors.SURFACE,
                        border_radius=12,
                        expand=True,
                        shadow=[AppStyles.CARD_SHADOW],
                    ),
                ], spacing=10),

                # System Info
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Column([
                                ft.Text("Çalışma Süresi", size=11, weight="bold", color=AppColors.TEXT_MUTED),
                                self.uptime_text,
                            ]),
                            ft.Column([
                                ft.Text("Ortalama Yük", size=11, weight="bold", color=AppColors.TEXT_MUTED),
                                self.load_avg_text,
                            ], expand=True),
                        ]),
                    ], spacing=5),
                    padding=15,
                    bgcolor=AppColors.SURFACE,
                    border_radius=12,
                    shadow=[AppStyles.CARD_SHADOW],
                ),

                # Alerts Section
                ft.Container(height=15),
                ft.Text("Son Uyarılar", size=14, weight="bold", color=AppColors.TEXT),
                ft.Container(
                    content=self.alerts_list,
                    expand=True,
                    bgcolor=AppColors.BG_DEEP,
                    border_radius=12,
                    height=250,
                ),
            ], spacing=15, expand=True),
            padding=20,
            bgcolor=AppColors.SURFACE,
            border_radius=15,
            shadow=[AppStyles.CARD_SHADOW],
        )
