from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from app.database.session import Session
from app.keyboards.catalog import episodes_keyboard
from app.messages import episodes_text
from app.services.catalog_service import get_episodes
from app.services.catalog_service import get_season


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
