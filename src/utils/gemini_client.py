""" 
Gemini Native Client
Uses google-genai SDK for structured JSON output
"""

import os
import time
import logging
import json
from typing import Any, Dict, Optional

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    types = None
from src.utils.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Wrapper for Google Gemini generative AI.
    Uses native google-genai SDK with structured output.
    """
    
    def __init__(self, api_key: str = None, default_model: str = "gemini-2.0-flash"):
        self.api_key = api_key or GEMINI_API_KEY
        self.default_model = default_model
        self.client = None
        
        if not self.api_key:
            logger.warning("No Gemini API key found")
            return
        
        if not GENAI_AVAILABLE:
            logger.warning("google-genai SDK not available")
            return
        
        try:
            self.client = genai.Client(api_key=self.api_key)
            logger.info("Gemini client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
    
    def generate_shipments(self, 
                          user_prompt: str, 
                          model: str = None, 
                          system_instruction: str = None, 
                          temperature: float = 0.1) -> Dict:
        """
        Generate shipment routes using response_schema.
        Returns dict with 'routes' key.
        """
        if not self.client:
            return {"routes": []}
        
        from src.utils.gemini_models import ShipmentsResponse
        
        target_model = model or self.default_model
        
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=ShipmentsResponse,
            system_instruction=system_instruction
        )
        
        try:
            start = time.time()
            response = self.client.models.generate_content(
                model=target_model,
                contents=user_prompt,
                config=config
            )
            duration = time.time() - start
            logger.debug(f"Gemini generation took {duration:.2f}s")
            
            if response.text:
                return json.loads(response.text)
            return {"routes": []}
        
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return {"routes": []}
    
    def generate_content(self, 
                         contents: str, 
                         model: str = None, 
                         system_instruction: str = None, 
                         temperature: float = 0.1, 
                         response_schema: Any = None, 
                         response_mime_type: str = "text/plain") -> Any:
        """
        Generic content generation method using native SDK.
        Returns text (if text/plain) or deserialized JSON (if application/json).
        """
        if not self.client:
            logger.warning("Google GenAI SDK not initialized.")
            return ""
        
        target_model = model or self.default_model
        
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type=response_mime_type,
            response_schema=response_schema,
            system_instruction=system_instruction
        )
        
        try:
            response = self.client.models.generate_content(
                model=target_model,
                contents=contents,
                config=config
            )
            
            if response_mime_type == "application/json":
                if response.text:
                    return json.loads(response.text)
                return {}
            
            return response.text or ""
            
        except Exception as e:
            logger.error(f"Gemini generic generation failed: {e}")
            return ""
    
    def generate_text_only(self, user_prompt: str, system_instruction: str = None, 
                           model: str = None, temperature: float = 0.1) -> str:
        """
        Generate plain text response WITHOUT schema constraints.
        Allows Gemini to follow prompt instructions more closely.
        """
        if not self.client:
            logger.warning("Gemini client not initialized, cannot generate text.")
            return ""
        
        target_model = model or self.default_model
        
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="text/plain",
            system_instruction=system_instruction
        )
        
        try:
            logger.info(f"Generating AI text for prompt: {user_prompt[:50]}...")
            response = self.client.models.generate_content(
                model=target_model,
                contents=user_prompt,
                config=config
            )
            
            result = response.text or ""
            logger.info(f"AI response received: {result[:50]}...")
            return result
        except Exception as e:
            logger.error(f"Gemini text generation failed: {e}")
            return "" # Return empty instead of raising to keep GUI stable
