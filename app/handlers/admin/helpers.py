import logging
from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aiogram import BaseMiddleware
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup
from aiogram.types import Message
from aiogram.types import ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.models import Anime
from app.database.models import Episode
from app.database.models import Season
from app.database.session import Session
from app.enums import Entity
from app.keyboards.admin import admin_main_keyboard
from app.keyboards.admin import anime_edit_keyboard
from app.keyboards.admin import anime_list_keyboard
from app.keyboards.admin import conveyor_finish_keyboard
from app.keyboards.admin import delete_confirm_keyboard
from app.keyboards.admin import episode_edit_keyboard
from app.keyboards.admin import episode_list_keyboard
from app.keyboards.admin import season_edit_keyboard
from app.keyboards.admin import season_list_keyboard
from app.keyboards.admin import yes_no_keyboard
from app.services.admin_service import get_episode_for_admin
from app.services.admin_service import get_stats
from app.services.admin_service import list_anime
from app.services.admin_service import next_episode_number
from app.services.admin_service import next_season_number
from app.services.catalog_service import get_anime
from app.services.catalog_service import get_episodes
from app.services.catalog_service import get_season
from app.services.catalog_service import get_seasons
from app.services.catalog_service import search_anime
from app.callbacks import BroadcastCancelCallback
from app.database.models import Broadcast
from app.database.models import BroadcastRecipient
from app.services.channel_service import ChannelService
from app.services.media_group_collector import MediaGroupCollector


_mg_collector = MediaGroupCollector()


class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        if not _is_admin(event.from_user.id):
            await event.answer("Нет доступа.", show_alert=True)
            return
        return await handler(event, data)


@dataclass(frozen=True)
class DeleteResult:
    found: bool
    db_deleted: bool
    telegram_deleted: int
    telegram_failed: int


def _is_admin(user_id: int | None) -> bool:
    return bool(user_id and user_id in settings.admin_ids)


async def _guard_message(message: Message) -> bool:
    if _is_admin(message.from_user.id):
        return True
    await message.answer("Нет доступа.")
    return False


async def _admin_menu_text() -> str:
    async with Session() as session:
        stats = await get_stats(session)
        from app.services.user_service import count_users
        user_count = await count_users(session)
    return (
        "Админ-панель\n\n"
        f"Аниме: {stats.anime}\n"
        f"Сезонов: {stats.seasons}\n"
        f"Серий: {stats.episodes}\n"
        f"Пользователей: {user_count}"
    )


async def _edit_or_answer(callback: CallbackQuery, text: str, reply_markup) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        await callback.message.answer(text, reply_markup=reply_markup)


async def _create_anime_from_state(state, poster_message_id: int | None) -> Anime:
    data = await state.get_data()
    async with Session() as session:
        anime = Anime(
            title=data["anime_title"],
            poster_message_id=poster_message_id,
        )
        session.add(anime)
        await session.commit()
        await session.refresh(anime)
        return anime


async def _show_anime_list(callback: CallbackQuery, action: str, page: int, pick_entity: str, query: str | None = None) -> None:
    async with Session() as session:
        if query:
            anime_page = await search_anime(session, query, page)
        else:
            anime_page = await list_anime(session, page)
    keyboard = anime_list_keyboard(anime_page, action, pick_entity)
    await _edit_or_answer(callback, "Выберите аниме:", keyboard)


async def _show_season_list(callback: CallbackQuery, action: str, anime_id: int, page: int) -> None:
    async with Session() as session:
        seasons_page = await get_seasons(session, anime_id, page)
    show_create = action == "add_episode"
    await _edit_or_answer(callback, "Выберите сезон:", season_list_keyboard(seasons_page, action, anime_id, show_create))


async def _show_episode_list(callback: CallbackQuery, action: str, season_id: int, page: int) -> None:
    async with Session() as session:
        episodes_page = await get_episodes(session, season_id, page)
    await _edit_or_answer(callback, "Выберите серию:", episode_list_keyboard(episodes_page, action, season_id))


async def _show_anime_editor(callback: CallbackQuery, anime_id: int) -> None:
    async with Session() as session:
        anime = await get_anime(session, anime_id)
    if anime is None:
        await callback.answer("Аниме не найдено.", show_alert=True)
        return
    await _edit_or_answer(callback, f"Аниме: {anime.title}\n\nЧто изменить?", anime_edit_keyboard(anime.id))


async def _show_season_editor(callback: CallbackQuery, season_id: int) -> None:
    async with Session() as session:
        season = await get_season(session, season_id)
    if season is None:
        await callback.answer("Сезон не найден.", show_alert=True)
        return
    text = f"{season.anime.title}\nСезон {season.number}\n\nЧто изменить?"
    await _edit_or_answer(callback, text, season_edit_keyboard(season.id))


async def _show_episode_editor(callback: CallbackQuery, episode_id: int) -> None:
    async with Session() as session:
        episode = await get_episode_for_admin(session, episode_id)
    if episode is None:
        await callback.answer("Серия не найдена.", show_alert=True)
        return
    text = (
        f"{episode.season.anime.title}\n"
        f"Сезон {episode.season.number}, серия {episode.number}\n"
        f"message_id: {episode.message_id}\n\n"
        "Что изменить?"
    )
    await _edit_or_answer(callback, text, episode_edit_keyboard(episode.id))


async def _ask_delete(callback: CallbackQuery, entity: str, item_id: int) -> None:
    await _edit_or_answer(callback, "Вы уверены?", delete_confirm_keyboard(entity, item_id))


async def _create_season(anime_id: int) -> tuple[int, Season] | None:
    async with Session() as session:
        number = await next_season_number(session, anime_id)
        season = Season(anime_id=anime_id, number=number)
        session.add(season)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return None
        await session.refresh(season)
    return number, season


async def _hard_delete(bot: Bot, entity: str, item_id: int) -> DeleteResult:
    channel = ChannelService(bot)
    async with Session() as session:
        item = await _get_entity_for_delete(session, entity, item_id)
        if item is None:
            return DeleteResult(found=False, db_deleted=False, telegram_deleted=0, telegram_failed=0)

        message_ids = _collect_channel_message_ids(entity, item)
        telegram_deleted, telegram_failed = await channel.delete_messages(message_ids)
        await session.delete(item)
        await session.commit()
        return DeleteResult(
            found=True,
            db_deleted=True,
            telegram_deleted=telegram_deleted,
            telegram_failed=telegram_failed,
        )


async def _get_entity_for_delete(session, entity: str, item_id: int):
    if entity == Entity.ANIME.value:
        return await session.scalar(
            select(Anime)
            .options(selectinload(Anime.seasons).selectinload(Season.episodes))
            .where(Anime.id == item_id)
        )
    if entity == Entity.SEASON.value:
        return await session.scalar(
            select(Season)
            .options(selectinload(Season.episodes))
            .where(Season.id == item_id)
        )
    if entity == Entity.EPISODE.value:
        return await session.scalar(select(Episode).where(Episode.id == item_id))
    return None


def _collect_channel_message_ids(entity: str, item) -> list[int]:
    message_ids: list[int] = []
    if entity == Entity.ANIME.value:
        if item.poster_message_id is not None:
            message_ids.append(item.poster_message_id)
        for season in item.seasons:
            message_ids.extend(episode.message_id for episode in season.episodes)
    elif entity == Entity.SEASON.value:
        message_ids.extend(episode.message_id for episode in item.episodes)
    elif entity == Entity.EPISODE.value:
        message_ids.append(item.message_id)
    return list(dict.fromkeys(message_ids))


def _delete_result_text(result: DeleteResult) -> str:
    if not result.found:
        return "Запись не найдена."
    if result.telegram_failed:
        return (
            "Удалено из базы. "
            f"Из канала удалено сообщений: {result.telegram_deleted}. "
            f"Не удалось удалить: {result.telegram_failed}."
        )
    return f"Удалено из базы и канала. Сообщений в канале удалено: {result.telegram_deleted}."


async def _get_entity(session, entity: str, item_id: int):
    if entity == Entity.ANIME.value:
        return await get_anime(session, item_id)
    if entity == Entity.SEASON.value:
        return await get_season(session, item_id)
    if entity == Entity.EPISODE.value:
        return await get_episode_for_admin(session, item_id)
    return None


def _apply_edit(item, entity: str, field: str, value) -> None:
    if entity == Entity.ANIME.value and field == "title":
        item.title = value
    elif entity == Entity.ANIME.value and field == "poster":
        item.poster_message_id = value["poster_message_id"]
    elif field == "number":
        item.number = value
    elif entity == Entity.EPISODE.value and field == "message":
        item.message_id = value


async def _parse_edit_value(message: Message, entity: str, field: str):
    if entity == Entity.ANIME.value and field == "title":
        value = (message.text or "").strip()
        if not value:
            await message.answer("Пустое название не подойдет.")
            return None
        return value
    if field == "number":
        number = _parse_positive_int(message.text)
        if number is None:
            await message.answer("Нужен положительный номер цифрами.")
            return None
        return number
    if entity == Entity.ANIME.value and field == "poster":
        try:
            poster_message_id = await _poster_message_id_from_admin_upload(message)
        except TelegramAPIError:
            await message.answer("Не получилось отправить постер в канал. Проверьте права бота в канале.")
            return None
        if poster_message_id is None:
            await message.answer("Пришлите фото.")
            return None
        return {"poster_message_id": poster_message_id}
    if entity == Entity.EPISODE.value and field == "message":
        try:
            message_id = await _episode_message_id_from_admin_upload(message)
        except TelegramAPIError:
            await message.answer("Не получилось отправить серию в канал. Проверьте права бота в канале.")
            return None
        if message_id is None:
            await message.answer("Пришлите видео.")
            return None
        return message_id
    return None


def _edit_prompt(entity: str, field: str) -> str:
    if entity == Entity.ANIME.value and field == "poster":
        return "Фото нового постера:"
    if entity == Entity.EPISODE.value and field == "message":
        return "Фото новой серии:"
    if field == "number":
        return "Новый номер:"
    return "Новое название:"


def _parse_positive_int(value: str | None) -> int | None:
    try:
        number = int((value or "").strip())
    except ValueError:
        return None
    return number if number > 0 else None


async def _poster_message_id_from_admin_upload(message: Message) -> int | None:
    if not message.photo:
        return None
    channel = ChannelService(message.bot)
    return await channel.copy_message(message)


async def _episode_message_id_from_admin_upload(message: Message) -> int | None:
    if not _has_episode_media(message):
        return None
    channel = ChannelService(message.bot)
    return await channel.copy_message(message)


def broadcast_progress_keyboard(broadcast_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Отменить рассылку",
                callback_data=BroadcastCancelCallback(broadcast_id=broadcast_id).pack(),
            )],
        ]
    )


async def send_broadcast(bot: Bot, admin_chat_id: int, message: Message) -> None:
    from app.services.user_service import create_broadcast
    from app.services.user_service import get_all_user_ids

    async with Session() as session:
        user_ids = await get_all_user_ids(session)
        if not user_ids:
            await bot.send_message(chat_id=admin_chat_id, text="Нет пользователей для рассылки.")
            return
        broadcast_id = await create_broadcast(
            session,
            admin_user_id=admin_chat_id,
            from_chat_id=message.chat.id,
            from_message_id=message.message_id,
            user_ids=user_ids,
        )

    await _run_broadcast(bot, admin_chat_id, broadcast_id, message.chat.id, message.message_id)


async def _run_broadcast(
    bot: Bot,
    admin_chat_id: int,
    broadcast_id: int,
    from_chat_id: int,
    from_message_id: int,
) -> None:
    import asyncio

    from app.services.user_service import complete_broadcast
    from app.services.user_service import flush_recipient_statuses
    from app.services.user_service import get_broadcast
    from app.services.user_service import get_pending_recipients_batch
    from app.services.user_service import mark_blocked
    from app.services.user_service import set_broadcast_progress_message

    total = 0
    async with Session() as session:
        b = await get_broadcast(session, broadcast_id)
        if not b or b.status == "cancelled":
            return
        total = b.total_count

    progress = await bot.send_message(
        chat_id=admin_chat_id,
        text=f"Рассылка #{broadcast_id}: 0/{total}",
        reply_markup=broadcast_progress_keyboard(broadcast_id),
    )

    async with Session() as session:
        await set_broadcast_progress_message(session, broadcast_id, progress.chat.id, progress.message_id)

    sent = blocked = failed = 0
    blocked_user_ids: list[int] = []
    batch_updates: list[tuple[int, str]] = []

    while True:
        async with Session() as session:
            b = await get_broadcast(session, broadcast_id)
            if b and b.status == "cancelled":
                await progress.edit_text(
                    f"Рассылка #{broadcast_id} отменена.\n"
                    f"Отправлено: {sent}, заблокировано: {blocked}",
                )
                return

            pending = await get_pending_recipients_batch(session, broadcast_id, 50)

        if not pending:
            break

        for recipient in pending:
            try:
                await bot.copy_message(
                    chat_id=recipient.user_id,
                    from_chat_id=from_chat_id,
                    message_id=from_message_id,
                )
                batch_updates.append((recipient.user_id, "sent"))
                sent += 1
            except TelegramAPIError:
                batch_updates.append((recipient.user_id, "blocked"))
                blocked_user_ids.append(recipient.user_id)
                blocked += 1
            except Exception:
                batch_updates.append((recipient.user_id, "failed"))
                failed += 1

            if len(batch_updates) >= 100:
                async with Session() as session:
                    await flush_recipient_statuses(session, broadcast_id, batch_updates)
                batch_updates.clear()

            await asyncio.sleep(0.03)

        if batch_updates:
            async with Session() as session:
                await flush_recipient_statuses(session, broadcast_id, batch_updates)
            batch_updates.clear()

        done = sent + blocked + failed
        await progress.edit_text(
            f"Рассылка #{broadcast_id}: {done}/{total}\n"
            f"Отправлено: {sent}\n"
            f"Заблокировано: {blocked}",
            reply_markup=broadcast_progress_keyboard(broadcast_id),
        )

    if batch_updates:
        async with Session() as session:
            await flush_recipient_statuses(session, broadcast_id, batch_updates)

    async with Session() as session:
        for uid in blocked_user_ids:
            await mark_blocked(session, uid)
        await complete_broadcast(session, broadcast_id, sent, blocked, failed)

    await progress.edit_text(
        f"Рассылка #{broadcast_id} завершена.\n"
        f"Отправлено: {sent}\n"
        f"Заблокировали бота: {blocked}\n"
        f"Ошибок: {failed}\n"
        f"Всего: {total}",
    )


async def resume_incomplete_broadcasts(bot: Bot) -> None:
    import asyncio

    from app.services.user_service import get_running_broadcasts

    async with Session() as session:
        broadcasts = await get_running_broadcasts(session)

    if not broadcasts:
        return

    for b in broadcasts:
        logging.warning(
            "Resuming broadcast #%d from chat %d message %d",
            b.id, b.from_chat_id, b.from_message_id,
        )
        asyncio.create_task(
            _run_broadcast(bot, b.admin_user_id, b.id, b.from_chat_id, b.from_message_id)
        )


def _has_episode_media(message: Message) -> bool:
    return any(
        (
            message.video,
            message.document,
            message.animation,
            message.video_note,
        )
    )
