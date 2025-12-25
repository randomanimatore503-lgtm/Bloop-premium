import asyncio

_json_lock = asyncio.Lock()

async def queued_write(func):
    async with _json_lock:
        return func()