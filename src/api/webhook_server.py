import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
import os
import threading
import time

# Fix paths for imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.parsers.veri_cekici_ayristirici import OrchestratorSDK

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("WebhookServer")

# Singleton Orchestrator
orchestrator = OrchestratorSDK()
_server_instance = None
_server_thread = None
_loop_thread = None # Track the periodic loop thread

class WhapiWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            
            # DEBUG DUMP
            logger.info("--- INCOMING WEBHOOK ---")
            
            # Send 200 OK immediately to prevent webhook timeout drops
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'received'}).encode('utf-8'))
            
            # Handle the event via orchestrator ASYNCHRONOUSLY
            threading.Thread(target=orchestrator.handle_webhook_event, args=(data,), daemon=True).start()
            
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            try:
                self.send_response(500)
                self.end_headers()
            except:
                pass

    def do_GET(self):
        """Health check for external monitors or ngrok"""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Mavi Lojistik Webhook Server is Running")

    def log_message(self, format, *args):
        # Suppress default logging to keep console clean, or redirect to our logger
        logger.debug(format%args)

def run_server(port=8080, use_ngrok=None):
    global _server_instance
    
    # 0. Check USE_NGROK from .env if not explicitly passed
    if use_ngrok is None:
        use_ngrok_env = os.getenv("USE_NGROK", "1")
        use_ngrok = use_ngrok_env.strip() in ("1", "true", "True")
    
    # 0. Cleanup orphaned processes on target port
    try:
        import subprocess
        logger.info(f"[CLEAN] Port {port} üzerindeki olası zombi süreçler temizleniyor...")
        if sys.platform == 'win32':
             # Windows specific port cleanup
             cmd = f"FOR /F \"tokens=5\" %a IN ('netstat -aon ^| find \":{port}\" ^| find \"LISTENING\"') DO taskkill /F /PID %a"
             subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
    except Exception as e:
        logger.warning(f"Port temizleme başarısız: {e}")

    # 1. Start Ngrok Tunnel (Optional)
    public_url = None
    if use_ngrok:
        try:
            import site
            user_site = site.getusersitepackages()
            if user_site not in sys.path:
                sys.path.append(user_site)
                
            from pyngrok import ngrok, conf
            from src.fetchers.whapi_fetcher import setup_webhook
            
            # 1.1 Configure pyngrok for basic stability and try different regions
            # Common regions: 'us', 'eu', 'au', 'ap', 'sa', 'jp', 'in'
            regions = ['eu', 'us', 'ap']
            success = False
            
            for region in regions:
                try:
                    logger.info(f"[POLL] Ngrok tüneli başlatılıyor (Bölge: {region})...")
                    ngrok_config = conf.PyngrokConfig(
                        monitor_thread=True,
                        region=region
                    )
                    
                    # Cleanup existing tunnels robustly
                    try:
                        tunnels = ngrok.get_tunnels()
                        for t in tunnels:
                            ngrok.disconnect(t.public_url)
                        ngrok.kill()
                        time.sleep(1)
                    except: pass
                    
                    public_url = ngrok.connect(port, pyngrok_config=ngrok_config).public_url
                    logger.info(f"[OK] Ngrok Tüneli Aktif ({region}): {public_url}")
                    success = True
                    break
                except Exception as e:
                    logger.warning(f"[FAIL] Ngrok {region} bölgesinde başarısız oldu: {e}")
                    if "verify certificate" not in str(e).lower():
                        # If it's not a cert error, maybe don't loop all regions
                        pass
            
            if not success:
                 raise Exception("Tüm Ngrok bölgeleri denendi ancak bağlantı kurulamadı.")
            
            # 2. Register Webhook with Whapi automatically
            if setup_webhook(public_url):
                logger.info("[OK] Whapi Tetikleyici (Webhook) OTOMATİK ADRESLENDİ!")
            else:
                logger.warning("[FAIL] Whapi Webhook ayarlanamadı.")

        except ImportError:
            logger.warning("[FAIL] pyngrok yüklü değil, tünel başlatılamadı.")
        except Exception as e:
            logger.error(f"[ERROR] Ngrok hatası: {e}")
            logger.error("💡 ÇÖZÜM ÖNERİLERİ:")
            logger.error("1. Antivirüs veya Güvenlik Duvarınızı (Firewall) geçici olarak kapatıp tekrar deneyin.")
            logger.error("2. Eğer VPN kullanıyorsanız kapatın.")
            logger.error("3. Whapi panelinden Webhook URL'sini manuel güncelleyebilirsiniz.")
            logger.info("ℹ️ Sunucu yerel modda devam ediyor. Webhook adresini manuel girebilirsiniz.")

    # 4. Start Orchestrator Periodic Loop (5-min scan) in its own thread
    global _loop_thread
    if not _loop_thread or not _loop_thread.is_alive():
        logger.info("[POLL] Orchestrator periyodik tarama döngüsü başlatılıyor (5 dk)...")
        # Ensure keep_only_today is True by default for performance
        _loop_thread = threading.Thread(target=orchestrator.run_loop, daemon=True)
        _loop_thread.start()

    # 5. Start HTTP Server
    # Sunucu adresi: 0.0.0.0 (Tüm ağ arayüzlerini dinler)
    server_address = ('0.0.0.0', port)
    _server_instance = HTTPServer(server_address, WhapiWebhookHandler)
    logger.info(f"[START] Webhook Sunucusu {server_address[0]}:{port} adresinde dinliyor...")
    
    try:
        _server_instance.serve_forever()
    except Exception as e:
        if _server_instance:
            logger.info(f"Server stopped: {e}")
    finally:
        if _server_instance:
             _server_instance.server_close()

def stop_server():
    global _server_instance
    if _server_instance:
        logger.info("Stopping Webhook Server & Orchestrator Loop...")
        _server_instance.shutdown()
        _server_instance = None
    
    # Sign orchestrator to stop if it has a stop event (Need to add this to OrchestratorSDK)
    if hasattr(orchestrator, 'stop_event'):
        orchestrator.stop_event.set()

if __name__ == "__main__":
    # If run directly as a script
    run_server(port=8080)
