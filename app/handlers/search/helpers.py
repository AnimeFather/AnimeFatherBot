from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from aiogram.types import Message

from app.config import settings
from app.database.models import Anime
from app.database.session import Session
from app.keyboards.catalog import episodes_keyboard
from app.keyboards.catalog import seasons_keyboard
from app.messages import anime_card_text
from app.messages import episodes_text
from app.services.catalog_service import get_episodes
from app.services.catalog_service import get_season
from app.services.catalog_service import get_seasons


async def _send_anime_card(message: Message, session, anime: Anime) -> None:
    seasons_page = await get_seasons(session, anime.id, page=1)
    text = anime_card_text(anime)
    keyboard = seasons_keyboard(anime.id, seasons_page)
    if anime.poster_message_id:
        await message.bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=settings.channel_id,
            message_id=anime.poster_message_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


async def _show_episode_page(
    callback: CallbackQuery,
    season_id: int,
    page: int,
    highlight: int = 0,
) -> None:
    async with Session() as session:
        season = await get_season(session, season_id)
        if season is None:
            await callback.answer("Сезон не найден.", show_alert=True)
            return
        episodes_page = await get_episodes(session, season_id, page)

    await _edit_text_or_caption(
        callback,
        episodes_text(season, episodes_page),
        episodes_keyboard(episodes_page, season_id, highlight=highlight, anime_id=season.anime_id),
        parse_mode="HTML",
    )
    await callback.answer()


async def _edit_text_or_caption(callback: CallbackQuery, text: str, reply_markup, parse_mode: str | None = None) -> None:
    try:
        await callback.message.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except TelegramBadRequest as text_error:
        if _is_not_modified(text_error):
            return
        try:
            await callback.message.edit_caption(caption=text, parse_mode=parse_mode, reply_markup=reply_markup)
        except TelegramBadRequest as caption_error:
            if _is_not_modified(caption_error):
                return
            raise


def _is_not_modified(error: TelegramBadRequest) -> bool:
    return "message is not modified" in str(error).lower()
