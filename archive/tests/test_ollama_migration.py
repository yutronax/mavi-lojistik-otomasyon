"""
Ollama Migration Integration Test
Tests import chain, OllamaClient init, adapter proxy, and config save/load.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  [PASS] {name}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        failed += 1

print("=" * 60)
print("OLLAMA MIGRATION TEST SUITE")
print("=" * 60)

# --- Test 1: OllamaClient import ---
def test_ollama_client_import():
    from src.utils.ollama_client import OllamaClient
    client = OllamaClient(host="http://test-server:11434", default_model="llama3.1")
    assert client.host == "http://test-server:11434"
    assert client.default_model == "llama3.1"

test("OllamaClient import & init", test_ollama_client_import)

# --- Test 2: Adapter routes to OllamaClient ---
def test_adapter_uses_ollama():
    from src.utils.gemini_adapter import get_client
    client = get_client()
    assert "OllamaClient" in type(client).__name__, f"Expected OllamaClient, got {type(client).__name__}"

test("Adapter routes to OllamaClient", test_adapter_uses_ollama)

# --- Test 3: DataService save_config / load_config ---
def test_config_save_load():
    from src.services.data_service import DataService
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ds = DataService(root)
    config_path = os.path.join(str(ds.user_data_dir), 'app_config.json')
    print(f"    [DEBUG] config path: {config_path}")
    
    test_config = {"ollama_url": "http://192.168.1.5:11434", "ollama_model": "llama3.1"}
    ds.save_config("test_ollama", test_config)
    
    # Verify file was actually written
    assert os.path.exists(config_path), f"Config file not created at {config_path}"
    
    loaded = ds.load_config("test_ollama")
    assert loaded is not None, f"Config returned None. File content: {open(config_path).read()}"
    assert loaded["ollama_url"] == "http://192.168.1.5:11434"
    assert loaded["ollama_model"] == "llama3.1"

test("DataService save_config / load_config", test_config_save_load)

# --- Test 4: AsyncDataService has load_config ---
def test_async_has_load_config():
    from src.services.data_service_async import AsyncDataService
    assert hasattr(AsyncDataService, 'load_config'), "AsyncDataService missing load_config"
    assert hasattr(AsyncDataService, 'save_config'), "AsyncDataService missing save_config"

test("AsyncDataService has load_config", test_async_has_load_config)

# --- Test 5: mavi_whap still importable ---
def test_mavi_whap_import():
    from src.fetchers.mavi_whap import extract_shipments_with_openai
    assert callable(extract_shipments_with_openai)

test("mavi_whap importable", test_mavi_whap_import)

# --- Test 6: location_research_agent uses adapter ---
def test_location_agent():
    from src.parsers.location_research_agent import LocationResearchAgent
    agent = LocationResearchAgent()
    assert hasattr(agent, '_adapter_available')
    assert agent.default_model == os.getenv('OLLAMA_MODEL', 'llama3.1')

test("LocationResearchAgent uses Ollama adapter", test_location_agent)

# --- Test 7: OllamaClient connection error is graceful ---
def test_ollama_graceful_failure():
    from src.utils.ollama_client import OllamaClient
    client = OllamaClient(host="http://localhost:99999")  # unreachable
    result = client.generate_content("test", response_mime_type="application/json")
    assert isinstance(result, dict), f"Expected dict on failure, got {type(result)}"

test("OllamaClient graceful failure on connection error", test_ollama_graceful_failure)

# --- Test 8: Settings page fields exist ---
def test_settings_fields():
    try:
        import flet as ft
    except ImportError:
        # Read file directly if flet not installed in this env
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      'src', 'gui', 'pages', 'settings_page.py')
        source = open(settings_path, encoding='utf-8').read()
        assert 'ollama_url_field' in source
        assert 'ollama_model_field' in source
        assert 'gemini_key_field' not in source, "Gemini key field should be removed"
        return
    import inspect
    from src.gui.pages.settings_page import SettingsPage
    source = inspect.getsource(SettingsPage.__init__)
    assert "ollama_url_field" in source
    assert "ollama_model_field" in source
    assert "gemini_key_field" not in source, "Gemini key field should be removed"

test("Settings page has Ollama fields, no Gemini", test_settings_fields)

print()
print("=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
print("=" * 60)

if failed > 0:
    sys.exit(1)
