import asyncio
import logging
from typing import Callable, List, Union
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat

logger = logging.getLogger(__name__)


class TelegramListener:
    def __init__(
        self,
        session_name: str,
        api_id: int,
        api_hash: str,
        channels: List[Union[str, int]],
        handler_cb: Callable,
    ):
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        self.channels = channels
        self.handler_cb = handler_cb
        self.client = TelegramClient(session_name, api_id, api_hash)

    async def start(self):
        await self.client.start()
        logger.info("Telethon client started")

        @self.client.on(events.NewMessage(chats=self.channels))
        async def on_new_message(event):
            msg = event.message
            if not msg.text:
                return
            try:
                await self.handler_cb(event)
            except Exception as e:
                logger.error(f"Failed to process message {msg.id}: {e}")

        logger.info(f"Listening on {len(self.channels)} channels")
        await self.client.run_until_disconnected()
