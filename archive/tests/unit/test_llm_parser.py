import os
import json
from src.infrastructure.llm.gemini import GeminiLLM
from src.infrastructure.parsers.llm_parser import LLMParser


def test_llm_parser_simulated(monkeypatch, tmp_path):
    # Ensure simulated mode
    monkeypatch.setenv('SIMULATED_GEMINI', '1')
    # reload module to pick up env change (ensure module uses env at import)
    import importlib
    importlib.reload(__import__('src.infrastructure.llm.gemini', fromlist=['*']))

    llm = GeminiLLM()
    parser = LLMParser(llm)

    message = "KAYSERİ -> İSTANBUL 1 TIR"
    message_id = 'u1'
    results = parser.parse(message, message_id)
    assert isinstance(results, list)
    assert len(results) == 1
    sh = results[0]
    assert sh.nereden_il
    assert sh.nereye_il
    assert sh.message_id in (message_id, 'sim-msg-1')
