import os
import json
import logging
import requests
from typing import Dict, Any, Optional
from src.utils.api_key_manager import get_default_manager

logger = logging.getLogger(__name__)

class OllamaClient:
    """
    Universal LLM Client supporting Ollama and OpenAI-compatible APIs (Groq, Together, etc.)
    Acts as a drop-in replacement for GeminiClient.
    """
    
    def __init__(self, host: str = None, default_model: str = None):
        self.host = host or os.getenv("LLM_BASE_URL") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.default_model = default_model or os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL", "llama3.1")
        
        # Ensure host doesn't have a trailing slash
        if self.host.endswith('/'):
            self.host = self.host[:-1]
            
        self.is_openai_style = "openai" in self.host.lower() or "groq" in self.host.lower()
        self.api_manager = get_default_manager()
            
        logger.info(f"LLMClient initialized. Host: {self.host}, Model: {self.default_model}, Type: {'OpenAI-Style' if self.is_openai_style else 'Ollama'}")

    def generate_content(self, 
                         contents: str, 
                         model: str = None, 
                         system_instruction: str = None, 
                         temperature: float = 0.1, 
                         response_mime_type: str = "text/plain",
                         response_schema: Any = None) -> Any:
        """
        Generic content generation method compatible with Gemini logic.
        """
        target_model = model or self.default_model
        
        if self.is_openai_style:
            return self._generate_openai_style(contents, target_model, system_instruction, temperature, response_mime_type)
        else:
            return self._generate_ollama_style(contents, target_model, system_instruction, temperature, response_mime_type, response_schema)

    def _generate_openai_style(self, contents, model, system, temp, mime_type):
        url = f"{self.host}/chat/completions" if not self.host.endswith('/chat/completions') else self.host
        
        active_key = self.api_manager.get_active_key()
        if not active_key:
            self.api_manager.load_keys(reason='llm_client_init')
            active_key = self.api_manager.get_active_key()

        headers = {
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": contents})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temp
        }
        
        if mime_type == "application/json":
            payload["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            
            # Handle rate limit
            if response.status_code == 429:
                logger.warning("[LLMClient] Rate limit hit! Rotating key...")
                if self.api_manager.switch_to_next(reason='rate_limit_429'):
                    return self._generate_openai_style(contents, model, system, temp, mime_type)
            
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            if mime_type == "application/json":
                try:
                    return json.loads(content)
                except:
                    return {}
            return content
        except Exception as e:
            logger.error(f"[LLMClient] OpenAI-style request failed: {e}")
            return {} if mime_type == "application/json" else ""

    def _generate_ollama_style(self, contents, model, system, temp, mime_type, schema):
        url = f"{self.host}/api/chat"
        payload = {
            "model": model,
            "messages": [],
            "stream": False,
            "options": {"temperature": temp}
        }
        
        if system:
            payload["messages"].append({"role": "system", "content": system})
        payload["messages"].append({"role": "user", "content": contents})
        
        if mime_type == "application/json" or schema:
            payload["format"] = "json"
            
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            
            if payload.get("format") == "json":
                try:
                    return json.loads(content)
                except:
                    return {}
            return content
        except Exception as e:
            logger.error(f"[LLMClient] Ollama request failed: {e}")
            return {} if mime_type == "application/json" else ""

    def generate_text_only(self, user_prompt: str, system_instruction: str = None, 
                           model: str = None, temperature: float = 0.1) -> str:
        return self.generate_content(user_prompt, model, system_instruction, temperature, "text/plain")

