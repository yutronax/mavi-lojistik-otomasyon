#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gemini Model Listesi

Kullanılabilir modelleri listeler
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GEMINI_API_KEY, transport='rest')

print("Kullanilabilir Gemini Modelleri:\n")
print("="*60)

for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"\nModel Adi: {model.name}")
        print(f"Aciklama: {model.display_name}")
        print(f"Desteklenen: {', '.join(model.supported_generation_methods)}")
        print("-"*60)
