from aiogram import Bot
from aiogram import Dispatcher

from app.config import settings


bot = Bot(settings.bot_token)
dp = Dispatcher()
