import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, List, Union, Optional
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, ChannelPrivateError
from telethon.tl.types import Channel, Chat

logger = logging.getLogger(__name__)


class TelegramListener:
    """Wraps Telethon client to resolve target channels and stream incoming text signals."""

    def __init__(
        self,
        session_name: str,
        api_id: int,
        api_hash: str,
        channels: List[Union[str, int]],
        on_signal_coro: Callable,
        phone: Optional[str] = None,
    ):
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        self.target_channels = channels
        self.on_signal_coro = on_signal_coro
        self.phone = phone
        self.client = TelegramClient(session_name, api_id, api_hash)
        self._resolved_ids: List[int] = []
        self._running = False

    async def _resolve_entities(self):
        self._resolved_ids.clear()
        for target in self.target_channels:
            try:
                entity = await self.client.get_entity(target)
                # print(f"Resolved target: {target} -> {entity.id}")
                self._resolved_ids.append(entity.id)
                title = getattr(entity, "title", str(entity.id))
                logger.info(f"Resolved channel '{title}' (id={entity.id})")
            except ChannelPrivateError:
                logger.warning(f"Cannot access private channel: {target}")
            except FloodWaitError as e:
                logger.warning(f"Flood wait during resolve ({e.seconds}s), sleeping...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Failed to resolve entity {target}: {e}")

        if not self._resolved_ids:
            logger.warning("No channel entities could be resolved. Will still try raw inputs.")

    async def start(self):
        self._running = True
        await self.client.start(phone=self.phone)
        logger.info("Telegram client connected")

        await self._resolve_entities()
        watch_targets = self._resolved_ids if self._resolved_ids else self.target_channels

        @self.client.on(events.NewMessage(chats=watch_targets))
        async def _message_handler(event):
            msg = event.message
            if not msg.raw_text:
                return

            # Telegram datetime is UTC
            msg_date = msg.date
            if msg_date and msg_date.tzinfo is None:
                msg_date = msg_date.replace(tzinfo=timezone.utc)

            # FIXME: grouped media (albums) fire multiple events with identical text
            channel_id = event.chat_id
            try:
                await self.on_signal_coro(
                    channel_id=channel_id,
                    message_id=msg.id,
                    text=msg.raw_text,
                    msg_timestamp=msg_date.timestamp() if msg_date else None,
                )
            except Exception as err:
                logger.exception(f"Unhandled error in signal handler: {err}")

        retry_delay = 5
        while self._running:
            try:
                await self.client.run_until_disconnected()
                break
            except (ConnectionError, asyncio.TimeoutError) as err:
                if not self._running:
                    break
                logger.warning(f"Connection dropped ({err}), reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
            except Exception as err:
                logger.error(f"Unexpected error in client loop: {err}")
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        if self.client.is_connected():
            await self.client.disconnect()
            logger.info("Telegram client disconnected")
