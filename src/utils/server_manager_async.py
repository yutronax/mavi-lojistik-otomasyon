# server_manager_async.py - Async Wrapper for ServerManager

import asyncio
from concurrent.futures import ThreadPoolExecutor
from src.utils.server_manager import ServerManager

class AsyncServerManager:
    """
    Purpose:      Provides non-blocking access to ServerManager (PM2 commands)
    Inputs:       service_name (str)
    Outputs:      Async methods returning command results
    Dependencies: ServerManager, asyncio, ThreadPoolExecutor
    Usage:        Used by ServerControlPage to keep GUI responsive
    """
    def __init__(self, service_name="mavi-lojistik-server"):
        self.manager = ServerManager(service_name)
        self.executor = ThreadPoolExecutor(max_workers=3)

    async def get_status_summary(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.manager.get_status_summary)

    async def restart(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.manager.restart)

    async def stop(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.manager.stop)

    async def start(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.manager.start)

    async def get_logs(self, lines=50):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.manager.get_logs, lines)

    async def git_pull(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.manager.git_pull)
