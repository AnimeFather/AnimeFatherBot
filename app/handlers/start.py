from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.database.session import Session
from app.messages import start_text
from app.services import user_service


router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(start_text())
    async with Session() as session:
        await user_service.register_or_update(
            session,
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
