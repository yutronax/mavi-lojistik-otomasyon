#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GUI Test - Sadece Tanıdık Yerler Panelini Aç
"""

import tkinter as tk
import os
import sys

# Proje kök dizinini ekle
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, 'src'))

from src.gui.tanidk_yerler_panel import TanidikYerlerManager
from src.services.data_service import DataService

class SimpleGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Test - Tanidik Yerler")
        self.root.geometry("400x200")
        
        # COLORS dictionary (TanidikYerlerManager için gerekli)
        self.COLORS = {
            'primary': '#1a56db',
            'success': '#059669',
            'danger': '#dc2626',
            'info': '#0ea5e9',
            'bg': '#f1f5f9',
            'text': '#111827',
            'surface': '#ffffff',
            'border': '#e5e7eb'
        }
        
        # DataService
        self.data_service = DataService(current_dir)
        
        # TanidikYerlerManager
        self.tanidk_yerler_manager = TanidikYerlerManager(self)
        
        # Buton
        tk.Button(
            self.root,
            text="Tanidik Yerler Panelini Ac",
            command=self.tanidk_yerler_manager.open_window,
            font=("Arial", 12),
            bg=self.COLORS['info'],
            fg='white',
            padx=20,
            pady=10
        ).pack(expand=True)
        
        self.root.mainloop()

if __name__ == "__main__":
    app = SimpleGUI()
