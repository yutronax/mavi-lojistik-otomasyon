#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OPTIMIZED TEXT GENERATION PARSER
Asynchronous and Parallel implementation.
"""

import sys
import os
import json
import asyncio
from typing import List, Dict, Any

sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

class TextGenParserOptimized(TextGenParser):
    """Optimized variant of the async parser."""
    def __init__(self, api_key=None):
        super().__init__(api_key)

    async def parse_async(self, message: str) -> list:
        # Optimized version can use even more aggressive skipping or smaller models
        # For now, it inherits the smart routing of the main parser
        return await super().parse_async(message)

if __name__ == "__main__":
    parser = TextGenParserOptimized()
    test_msg = "İZMİR - İSTANBUL"
    results = asyncio.run(parser.parse_async(test_msg))
    print(json.dumps(results, ensure_ascii=False, indent=2))
