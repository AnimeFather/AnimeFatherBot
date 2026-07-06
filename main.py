import asyncio
import logging

from app.bot import bot
from app.bot import dp
from app.config import settings
from app.database.session import create_tables
from app.handlers import admin
from app.handlers import search
from app.handlers import start


dp.include_router(admin.router)
dp.include_router(start.router)
dp.include_router(search.router)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if settings.auto_create_tables:
        await create_tables()

    from app.handlers.admin.helpers import resume_incomplete_broadcasts
    asyncio.create_task(resume_incomplete_broadcasts(bot))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
