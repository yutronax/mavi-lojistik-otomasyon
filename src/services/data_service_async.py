# data_service_async.py - Async Wrapper for DataService

import asyncio
from concurrent.futures import ThreadPoolExecutor
from src.services.data_service import DataService

class AsyncDataService:
    def __init__(self, data_service: DataService):
        self.ds = data_service
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def load_unprocessed_messages(self, filter_today: bool = True, hours_back: float = None):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.load_unprocessed_messages, filter_today, hours_back)

    async def save_approved_records(self, new_records):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.save_approved_records, new_records)

    async def save_approved(self, payload):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.save_approved, payload)

    async def load_arac_kasa_tipleri(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.load_arac_kasa_tipleri)

    async def load_il_ilceler(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.load_il_ilceler)

    async def mark_content_as_processed(self, content):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.mark_content_as_processed, content)

    async def delete_unprocessed_message(self, message_id):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.delete_unprocessed_message, message_id)

    async def save_unprocessed_messages(self, data):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.save_unprocessed_messages, data)

    async def load_blacklist(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.load_blacklist)

    async def load_yuk_tipleri(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.load_yuk_tipleri)

    async def save_yuk_tipleri(self, data):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.save_yuk_tipleri, data)

    async def save_blacklist(self, blacklist):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.save_blacklist, blacklist)

    async def load_saved_groups(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.load_saved_groups)

    async def save_groups(self, groups_list):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.save_groups, groups_list)

    async def load_approved_records(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.load_approved_records)

    async def save_config(self, key, value):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.save_config, key, value)

    async def load_config(self, key):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.load_config, key)

    async def is_shipment_duplicate(self, shipment):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.ds.is_shipment_duplicate, shipment)
