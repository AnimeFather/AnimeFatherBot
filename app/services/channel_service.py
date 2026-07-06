from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message

from app.config import settings


class ChannelService:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._channel_id = settings.channel_id

    async def copy_message(self, message: Message) -> int | None:
        copied = await self._bot.copy_message(
            chat_id=self._channel_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        return getattr(copied, "message_id", None)

    async def copy_to_user(
        self,
        chat_id: int,
        from_message_id: int,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup=None,
    ) -> Message | None:
        try:
            return await self._bot.copy_message(
                chat_id=chat_id,
                from_chat_id=self._channel_id,
                message_id=from_message_id,
                caption=caption,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        except TelegramAPIError:
            return None

    async def delete_messages(self, message_ids: list[int]) -> tuple[int, int]:
        deleted = 0
        failed = 0
        for message_id in message_ids:
            try:
                await self._bot.delete_message(chat_id=self._channel_id, message_id=message_id)
            except TelegramAPIError:
                failed += 1
            else:
                deleted += 1
        return deleted, failed

    async def delete_message(self, message_id: int) -> bool:
        try:
            await self._bot.delete_message(chat_id=self._channel_id, message_id=message_id)
            return True
        except TelegramAPIError:
            return False
