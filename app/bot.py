from aiogram import Bot
from aiogram import Dispatcher
from aiogram.types import BotCommand
from aiogram.types import BotCommandScopeChat
from aiogram.types import BotCommandScopeDefault
from aiogram.types import MenuButtonCommands

from app.config import settings


bot = Bot(settings.bot_token)
dp = Dispatcher()


async def setup_bot_commands() -> None:
    default_commands = [
        BotCommand(command="start", description="Перезапустить бота"),
    ]
    admin_commands = [
        BotCommand(command="start", description="Перезапустить бота"),
        BotCommand(command="admin", description="Админ-панель"),
    ]

    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

    for admin_id in settings.admin_ids:
        await bot.set_my_commands(
            admin_commands,
            scope=BotCommandScopeChat(chat_id=admin_id),
        )

    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())