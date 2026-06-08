import os
import pytest
from src.infrastructure.llm.gemini import GeminiLLM
from src.infrastructure.parsers.llm_parser import LLMParser
from src.domain.entities.shipment import Shipment

@pytest.fixture
def simulated_llm_parser(monkeypatch):
    """Fixture to provide an LLMParser with a simulated Gemini LLM."""
    # Set the environment variable to activate the simulated mode
    monkeypatch.setenv('SIMULATED_GEMINI', '1')
    
    # The API key is not needed for simulated mode, but it's good practice
    # to ensure the environment is clean for the test.
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    
    llm = GeminiLLM()
    parser = LLMParser(llm)
    return parser

def test_llm_parser_with_simulated_gemini(simulated_llm_parser):
    """
    Tests the LLMParser using the simulated GeminiLLM.
    This test ensures that the parser correctly decodes the simulated
    JSON response and creates a valid Shipment object.
    """
    parser = simulated_llm_parser
    test_message = "Bu bir test mesajıdır. İçeriğin bir önemi yok çünkü response mock ediliyor."
    message_id = "test-msg-123"
    
    # Parse the message
    results = parser.parse(test_message, message_id)
    
    # --- Assertions ---
    
    # 1. Check that we got a list with one shipment
    assert isinstance(results, list)
    assert len(results) == 1
    
    # 2. Check the type of the result
    shipment = results[0]
    assert isinstance(shipment, Shipment)
    
    # 3. Check the content of the shipment against the simulated data
    assert shipment.nereden_il == "ANKARA"
    assert shipment.nereye_il == "İSTANBUL"
    assert shipment.nereden_ilce == "MERKEZ"
    assert shipment.arac_tipi == ["1360"]
    assert shipment.fiyat == "SORUNUZ"
    assert shipment.aciklama == "Simulated"
    
    # The simulated response tries to extract the message_id from the prompt.
    # Our prompt builder includes "message_id: {message_id}".
    # Let's check if the parser correctly assigned it.
    # The simulated logic will find "test-msg-123" from the prompt.
    assert shipment.message_id is not None
    # The simulated response will try to find the message_id in the prompt.
    # Let's check the simulated logic in gemini.py... it extracts the first alphanumeric token after 'message_id'.
    # Our prompt is f"Extract shipments from the message. message_id: {message_id}\n...".
    # The simulated response should pick up the message_id.
    assert "test-msg-123" in shipment.message_id
