import threading
import queue
import time
import logging
import os
from pathlib import Path
from src.utils.file_operations import save_json_safe

logger = logging.getLogger('PersistenceManager')

class PersistenceManager:
    """
    Manages background file writing to ensure zero-wait for the main application
    and prevents simultaneous writes to the same file.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(PersistenceManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.write_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        self._initialized = True
        self.start()

    def start(self):
        """Starts the background writer thread."""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logger.info("File persistence background worker started")

    def stop(self):
        """Stops the background worker thread gracefully."""
        self.running = False
        if self.worker_thread:
            self.write_queue.put(None) # Sentinel to stop
            self.worker_thread.join(timeout=2.0)
            logger.info("File persistence background worker stopped")

    def queue_write(self, filepath, data, **kwargs):
        """
        Queues a JSON write operation. Returns immediately.
        """
        self.write_queue.put({
            'path': filepath,
            'data': data,
            'kwargs': kwargs,
            'timestamp': time.time()
        })
        # logger.debug(f"Write queued for {os.path.basename(filepath)}")

    def _worker_loop(self):
        while self.running:
            try:
                task = self.write_queue.get(timeout=1.0)
                if task is None:
                    break
                
                # Execute the write
                try:
                    save_json_safe(
                        task['path'], 
                        task['data'], 
                        **task['kwargs']
                    )
                except Exception as e:
                    logger.error(f"Background write failed for {task['path']}: {e}")
                
                self.write_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in writer loop: {e}")
                time.sleep(0.5)

# Global instances
persistence_manager = PersistenceManager()
