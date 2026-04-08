# styles.py - Flet Arayüz Stilleri

import flet as ft

class AppColors:
    # Deep Oceanic Palette
    BG_DEEP = "#0a0f1e"      # Ana Arka Plan
    SURFACE = "#161c2e"      # Panel/Kart Yüzeyi
    SURFACE_LIGHT = "#1e293b" # Hover/Alternatif Yüzey
    
    PRIMARY = "#3b82f6"      # Electric Blue
    ACCENT = "#00d2ff"       # Cyan Vurgu
    
    TEXT = "#f8fafc"         # Ana Metin
    TEXT_MUTED = "#94a3b8"   # Soluk Metin
    
    SUCCESS = "#10b981"      # Emerald
    DANGER = "#f43f5e"       # Rose
    WARNING = "#f59e0b"      # Amber

class AppGradients:
    PRIMARY = ft.LinearGradient(
        begin=ft.alignment.Alignment(-1, -1),
        end=ft.alignment.Alignment(1, 1),
        colors=[AppColors.PRIMARY, "#1d4ed8"]
    )
    ACCENT = ft.LinearGradient(
        begin=ft.alignment.Alignment(-1, -1),
        end=ft.alignment.Alignment(1, 1),
        colors=[AppColors.ACCENT, AppColors.PRIMARY]
    )
    SURFACE = ft.LinearGradient(
        begin=ft.alignment.Alignment(0, -1),
        end=ft.alignment.Alignment(0, 1),
        colors=[AppColors.SURFACE, "#111827"]
    )

class AppStyles:
    CARD_SHADOW = ft.BoxShadow(
        blur_radius=15,
        spread_radius=1,
        color="black26",
        offset=ft.Offset(0, 5)
    )
    
    HEADER_TITLE = ft.TextStyle(
        size=24,
        weight="bold",
        color=AppColors.TEXT,
        font_family="Segoe UI Semibold"
    )

def apply_app_theme(page: ft.Page):
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = AppColors.BG_DEEP
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=AppColors.PRIMARY,
            secondary=AppColors.ACCENT,
            surface=AppColors.SURFACE,
            on_surface=AppColors.TEXT,
        ),
        visual_density=ft.VisualDensity.COMFORTABLE,
        font_family="Segoe UI"
    )
