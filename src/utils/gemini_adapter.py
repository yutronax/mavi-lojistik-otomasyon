
import logging
import json
from typing import Optional, Any
from src.utils.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

# Global client instance (lazy init)
_CLIENT = None

def get_client(api_key: str = None):
    global _CLIENT
    if not _CLIENT:
        _CLIENT = GeminiClient(api_key=api_key)
    return _CLIENT

def generate_content_text(api_key: str, model: str, contents: str, response_mime_type: Optional[str] = None, response_schema: Optional[object] = None, **kwargs) -> str:
    """
    Adapter function bridging legacy calls to Native GeminiClient.
    Wraps 'generate_content' and ensures string output for backward compatibility.
    """
    try:
        client = get_client(api_key)
        
        # Log bridge usage
        logger.debug(f"CombinedBridge: generate_content_text called for model={model} mime={response_mime_type}")

        # Map kwargs if needed (e.g. temperature)
        temperature = kwargs.get('temperature', 0.1)
        system_instructions = kwargs.get('system_instruction')

        result = client.generate_content(
            contents=contents,
            model=model,
            system_instruction=system_instructions,
            temperature=temperature,
            response_mime_type=response_mime_type or "text/plain",
            response_schema=response_schema
        )
        
        # Adaptation: Callers of this function expect a string (JSON string or plain text)
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        
        return str(result)
        
    except Exception as e:
        logger.error(f"GeminiAdapter Bridge Error: {e}")
        # Return empty string to mimic failure behavior of original adapter
        return ""
