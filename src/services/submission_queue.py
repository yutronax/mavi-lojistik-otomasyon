import threading
import queue
import time
import logging
import json
import os
from datetime import datetime
from src.utils.file_operations import save_json_safe, load_json_safe
from src.services.persistence_manager import persistence_manager

logger = logging.getLogger('SubmissionQueue')

class SubmissionQueue:
    def __init__(self, submitter, on_success=None, on_failure=None):
        """
        Initialize the submission queue.
        
        Args:
            submitter: Instance of Submitter class (for API calls)
            on_success: Callback function (record) -> void
            on_failure: Callback function (record, error) -> void
        """
        self.queue = queue.Queue()
        self.submitter = submitter
        self.on_success = on_success
        self.on_failure = on_failure
        self.running = False
        self.worker_thread = None
        self.failed_file = 'basarisiz_gonderimler.json'

    def start(self):
        """Start the background worker thread."""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logger.info("Submission queue worker started")

    def stop(self):
        """Stop the background worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
            logger.info("Submission queue worker stopped")

    def add_task(self, shipment_record):
        """Add a shipment record to the processing queue."""
        self.queue.put(shipment_record)
        logger.info(f"Task added to queue. Current size: {self.queue.qsize()}")

    def _worker_loop(self):
        while self.running:
            try:
                # Wait for a task (blocking with timeout to allow checking self.running)
                try:
                    record = self.queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if record is None:
                    break

                self._process_record(record)
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in submission queue worker: {e}", exc_info=True)
                time.sleep(1) # Prevent tight loop on error

    def _process_record(self, record):
        """Process a single record: Auth -> Submit -> Handle Result"""
        try:
            # 1. Get phone
            tel_list = record.get("telefon_numarasi", [])
            if tel_list:
                tel = tel_list[0] if isinstance(tel_list, list) else str(tel_list)
            else:
                tel = record.get("telefon", "")
            
            if not tel or not str(tel).strip():
                self._handle_failure(record, "No phone number")
                return

            # 2. Auth & Submit
            # Ensure calling ensure_auth_for_phone on the submitter
            # Note: submitter method signature might vary, assuming it matches masaustu_uygulama logic
            token, owner_user_id = self.submitter.ensure_auth_for_phone(tel)
            
            if not token or not owner_user_id:
                self._handle_failure(record, f"Auth failed for {tel}")
                return

            payload = self.submitter.transform_record_to_payload(record)
            payload['ownerUserId'] = owner_user_id
            
            # Update headers safely (assuming submitter has a session)
            if hasattr(self.submitter, 'session'):
                self.submitter.session.headers.update({'Authorization': f'Bearer {token}'})
            
            result = self.submitter.submit_single_load(payload)
            
            if result.get('success'):
                logger.info(f"Successfully submitted record for {tel}")
                if self.on_success:
                    self.on_success(record)
            else:
                error_msg = result.get('error', 'Unknown Error')
                self._handle_failure(record, error_msg)

        except Exception as e:
            logger.error(f"Exception processing record: {e}", exc_info=True)
            self._handle_failure(record, str(e))

    def _handle_failure(self, record, error_message):
        """Log failure and save to disk."""
        logger.warning(f"Submission failed: {error_message}")
        
        failed_entry = {
            'record': record,
            'error': error_message,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Save to file immediately
        # Save to file via background queue
        try:
            existing_failed = load_json_safe(self.failed_file, default=[])
            existing_failed.append(failed_entry)
            persistence_manager.queue_write(self.failed_file, existing_failed)
        except Exception as e:
            logger.error(f"Failed to queue to basarisiz_gonderimler.json: {e}")

        if self.on_failure:
            self.on_failure(record, error_message)
