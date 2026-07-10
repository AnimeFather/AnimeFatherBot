from aiogram import F
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.types import Message

from app.callbacks import AnimeCallback
from app.callbacks import BackToEpisodesCallback
from app.callbacks import BackToSearchCallback
from app.callbacks import BackToSeasonsCallback
from app.callbacks import EpisodeCallback
from app.callbacks import EpisodeNavCallback
from app.callbacks import EpisodePageCallback
from app.callbacks import EpisodeSearchCallback
from app.callbacks import SearchPageCallback
from app.callbacks import SeasonCallback
from app.callbacks import SeasonPageCallback
from app.config import settings
from app.database.session import Session
from app.handlers.search.helpers import _edit_text_or_caption
from app.handlers.search.helpers import _send_anime_card
from app.handlers.search.helpers import _show_episode_page
from app.keyboards.catalog import episodes_keyboard
from app.keyboards.catalog import episode_video_keyboard
from app.keyboards.catalog import search_results_keyboard
from app.keyboards.catalog import seasons_keyboard
from app.messages import anime_card_text
from app.messages import episodes_text
from app.messages import nothing_found_text
from app.messages import search_results_text
from app.services.catalog_service import find_episode_by_number
from app.services import user_service
from app.services.catalog_service import get_anime
from app.services.catalog_service import get_episode
from app.services.catalog_service import get_episode_page
from app.services.catalog_service import get_episodes
from app.services.catalog_service import get_season
from app.services.catalog_service import get_seasons
from app.services.catalog_service import has_next_episode
from app.services.catalog_service import search_anime
from app.states import CatalogStates


router = Router()


@router.message(CatalogStates.waiting_episode_number)
async def process_episode_search(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    season_id = data.get("episode_search_season_id")
    if season_id is None:
        await state.clear()
        await message.answer("Не понял, в каком сезоне искать. Выберите сезон заново.")
        return

    try:
        episode_number = int((message.text or "").strip())
    except ValueError:
        await message.answer("Напишите номер серии цифрами, например 99.")
        return

    async with Session() as session:
        episode, page = await find_episode_by_number(session, season_id, episode_number)
        season = await get_season(session, season_id)
        if season is None:
            await state.clear()
            await message.answer("Сезон не найден.")
            return
        if episode is None:
            await message.answer("Такой серии в этом сезоне нет.")
            return
        episodes_page = await get_episodes(session, season_id, page)
        anime = season.anime

    last_query = data.get("last_query")
    await state.clear()
    if last_query is not None:
        await state.update_data(last_query=last_query)
    anime_id = anime.id
    if anime.poster_message_id:
        await message.bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=settings.channel_id,
            message_id=anime.poster_message_id,
            caption=episodes_text(season, episodes_page),
            parse_mode="HTML",
            reply_markup=episodes_keyboard(episodes_page, season_id, highlight=episode.number, anime_id=anime_id),
        )
    else:
        await message.answer(
            episodes_text(season, episodes_page),
            parse_mode="HTML",
            reply_markup=episodes_keyboard(episodes_page, season_id, highlight=episode.number, anime_id=anime_id),
        )


@router.message(F.text)
async def process_search(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    if not query:
        return

    async with Session() as session:
        await user_service.register_or_update(
            session,
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

        if query.isdigit():
            anime = await get_anime(session, int(query))
            if anime is not None:
                await _send_anime_card(message, session, anime)
                return

        page = await search_anime(session, query, page=1)

    if page.total == 0:
        await message.answer(nothing_found_text(query))
        return

    await state.update_data(last_query=query)
    await message.answer(
        search_results_text(query, page),
        reply_markup=search_results_keyboard(page),
    )


@router.callback_query(SearchPageCallback.filter())
async def paginate_search(
    callback: CallbackQuery,
    callback_data: SearchPageCallback,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    query = data.get("last_query")
    if not query:
        await callback.answer("Напишите название аниме еще раз.", show_alert=True)
        return

    async with Session() as session:
        page = await search_anime(session, query, page=callback_data.page)

    await _edit_text_or_caption(
        callback,
        search_results_text(query, page),
        search_results_keyboard(page),
    )
    await callback.answer()


@router.callback_query(AnimeCallback.filter())
async def show_anime(callback: CallbackQuery, callback_data: AnimeCallback) -> None:
    async with Session() as session:
        anime = await get_anime(session, callback_data.anime_id)
        if anime is None:
            await callback.answer("Аниме не найдено.", show_alert=True)
            return
        seasons_page = await get_seasons(session, anime.id, page=1)

    text = anime_card_text(anime)
    keyboard = seasons_keyboard(anime.id, seasons_page)
    if anime.poster_message_id:
        await callback.message.delete()
        await callback.bot.copy_message(
            chat_id=callback.message.chat.id,
            from_chat_id=settings.channel_id,
            message_id=anime.poster_message_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(SeasonPageCallback.filter())
async def paginate_seasons(callback: CallbackQuery, callback_data: SeasonPageCallback) -> None:
    async with Session() as session:
        anime = await get_anime(session, callback_data.anime_id)
        if anime is None:
            await callback.answer("Аниме не найдено.", show_alert=True)
            return
        seasons_page = await get_seasons(session, anime.id, page=callback_data.page)

    await _edit_text_or_caption(
        callback,
        anime_card_text(anime),
        seasons_keyboard(anime.id, seasons_page),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(SeasonCallback.filter())
async def show_season(callback: CallbackQuery, callback_data: SeasonCallback) -> None:
    await _show_episode_page(
        callback,
        season_id=callback_data.season_id,
        page=callback_data.page,
        highlight=callback_data.highlight,
    )


@router.callback_query(EpisodePageCallback.filter())
async def paginate_episodes(callback: CallbackQuery, callback_data: EpisodePageCallback) -> None:
    await _show_episode_page(
        callback,
        season_id=callback_data.season_id,
        page=callback_data.page,
        highlight=callback_data.highlight,
    )


@router.callback_query(EpisodeSearchCallback.filter())
async def ask_episode_number(
    callback: CallbackQuery,
    callback_data: EpisodeSearchCallback,
    state: FSMContext,
) -> None:
    await state.set_state(CatalogStates.waiting_episode_number)
    await state.update_data(episode_search_season_id=callback_data.season_id)
    await callback.message.answer("Введите номер серии, которую нужно найти.")
    await callback.answer()


@router.callback_query(EpisodeCallback.filter())
async def send_episode(callback: CallbackQuery, callback_data: EpisodeCallback) -> None:
    async with Session() as session:
        episode = await get_episode(session, callback_data.episode_id)
        if episode is None:
            await callback.answer("Серия не найдена.", show_alert=True)
            return

        page = await get_episode_page(session, episode.season_id, episode.number)
        has_next = await has_next_episode(session, episode.season_id, episode.number)
        has_prev = episode.number > 1

    await callback.message.delete()
    keyboard = episode_video_keyboard(episode.season_id, episode.number, page, has_next=has_next, has_prev=has_prev)
    await callback.bot.copy_message(
        chat_id=callback.message.chat.id,
        from_chat_id=settings.channel_id,
        message_id=episode.message_id,
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(EpisodeNavCallback.filter())
async def send_next_episode(callback: CallbackQuery, callback_data: EpisodeNavCallback) -> None:
    next_number = callback_data.episode_number + 1
    async with Session() as session:
        episode, page = await find_episode_by_number(session, callback_data.season_id, next_number)
        if episode is None:
            await callback.answer("Такой серии нет.", show_alert=True)
            return

        has_next = await has_next_episode(session, callback_data.season_id, episode.number)
        has_prev = episode.number > 1

    await callback.message.delete()
    keyboard = episode_video_keyboard(callback_data.season_id, episode.number, page, has_next=has_next, has_prev=has_prev)
    await callback.bot.copy_message(
        chat_id=callback.message.chat.id,
        from_chat_id=settings.channel_id,
        message_id=episode.message_id,
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(BackToEpisodesCallback.filter())
async def back_to_episodes(callback: CallbackQuery, callback_data: BackToEpisodesCallback) -> None:
    async with Session() as session:
        season = await get_season(session, callback_data.season_id)
        if season is None:
            await callback.answer("Сезон не найден.", show_alert=True)
            return
        episodes_page = await get_episodes(session, callback_data.season_id, callback_data.page)
        anime = season.anime

    await callback.message.delete()
    text = episodes_text(season, episodes_page)
    keyboard = episodes_keyboard(episodes_page, callback_data.season_id, highlight=callback_data.highlight, anime_id=anime.id)
    if anime.poster_message_id:
        await callback.bot.copy_message(
            chat_id=callback.message.chat.id,
            from_chat_id=settings.channel_id,
            message_id=anime.poster_message_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(BackToSeasonsCallback.filter())
async def back_to_seasons(callback: CallbackQuery, callback_data: BackToSeasonsCallback) -> None:
    async with Session() as session:
        anime = await get_anime(session, callback_data.anime_id)
        if anime is None:
            await callback.answer("Аниме не найдено.", show_alert=True)
            return
        seasons_page = await get_seasons(session, anime.id, page=callback_data.page)

    text = anime_card_text(anime)
    keyboard = seasons_keyboard(anime.id, seasons_page)

    await callback.message.delete()
    if anime.poster_message_id:
        await callback.bot.copy_message(
            chat_id=callback.message.chat.id,
            from_chat_id=settings.channel_id,
            message_id=anime.poster_message_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(BackToSearchCallback.filter())
async def back_to_search(callback: CallbackQuery, callback_data: BackToSearchCallback, state: FSMContext) -> None:
    data = await state.get_data()
    query = data.get("last_query")
    if not query:
        await callback.answer("Начните поиск заново.", show_alert=True)
        return

    async with Session() as session:
        page = await search_anime(session, query, page=1)

    await callback.message.delete()
    await callback.message.answer(
        search_results_text(query, page),
        reply_markup=search_results_keyboard(page),
    )
    await callback.answer()
