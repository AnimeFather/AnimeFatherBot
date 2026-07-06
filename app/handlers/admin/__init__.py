from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.config import settings
from app.handlers.admin.actions import router as actions_router
from app.handlers.admin.callbacks import router as callbacks_router
from app.handlers.admin.helpers import AdminMiddleware
from app.handlers.admin.helpers import _admin_menu_text
from app.handlers.admin.helpers import _is_admin
from app.handlers.admin.messages import router as messages_router
from app.keyboards.admin import admin_main_keyboard


router = Router()
router.include_routers(actions_router, callbacks_router, messages_router)
router.callback_query.middleware(AdminMiddleware())


@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer(
            "Админка закрыта.\n\n"
            f"Твой Telegram ID: {message.from_user.id}\n"
        )
        return

    await state.clear()
    await message.answer(await _admin_menu_text(), reply_markup=admin_main_keyboard())
