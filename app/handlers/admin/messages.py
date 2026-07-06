from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types import ReplyKeyboardRemove
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database.models import Episode
from app.database.models import Season
from app.database.session import Session
from app.enums import Entity
from app.handlers.admin.helpers import _admin_menu_text
from app.handlers.admin.helpers import _create_anime_from_state
from app.handlers.admin.helpers import _edit_or_answer
from app.handlers.admin.helpers import _edit_prompt
from app.handlers.admin.helpers import _episode_message_id_from_admin_upload
from app.handlers.admin.helpers import _get_entity
from app.handlers.admin.helpers import _guard_message
from app.handlers.admin.helpers import _has_episode_media
from app.handlers.admin.helpers import _mg_collector
from app.handlers.admin.helpers import _parse_edit_value
from app.handlers.admin.helpers import _parse_positive_int
from app.handlers.admin.helpers import _poster_message_id_from_admin_upload
from app.handlers.admin.helpers import _apply_edit
from app.handlers.admin.helpers import _delete_result_text
from app.keyboards.admin import admin_main_keyboard
from app.keyboards.admin import anime_list_keyboard
from app.keyboards.admin import conveyor_finish_keyboard
from app.keyboards.admin import yes_no_keyboard
from app.services.admin_service import next_episode_number
from app.services.catalog_service import search_anime
from app.handlers.admin.helpers import _edit_or_answer
from app.keyboards.admin import yes_no_keyboard
from app.states import AdminStates


router = Router()


@router.message(AdminStates.waiting_anime_search)
async def admin_anime_search(message: Message, state: FSMContext) -> None:
    if not await _guard_message(message):
        return

    query = (message.text or "").strip()
    if not query:
        return

    data = await state.get_data()
    pick_entity = data.get("admin_pick_entity", "anime")
    action_type = data.get("admin_action_type", "edit")

    await state.update_data(last_query=query)
    async with Session() as session:
        page = await search_anime(session, query, 1)

    if page.total == 0:
        await message.answer("Ничего не найдено.")
        return

    keyboard = anime_list_keyboard(page, action_type, pick_entity)
    await message.answer("Результаты поиска:", reply_markup=keyboard)


@router.message(AdminStates.add_anime_title)
async def add_anime_title(message: Message, state: FSMContext) -> None:
    if not await _guard_message(message):
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не должно быть пустым.")
        return
    await state.update_data(anime_title=title)
    await state.set_state(AdminStates.add_anime_poster)
    await message.answer("Фото постера.")


@router.message(AdminStates.add_anime_poster)
async def add_anime_poster(message: Message, state: FSMContext) -> None:
    if not await _guard_message(message):
        return

    try:
        poster_message_id = await _poster_message_id_from_admin_upload(message)
    except TelegramAPIError:
        await message.answer("Не получилось отправить постер в канал. Проверьте, что бот админ канала и может публиковать сообщения.")
        return
    if poster_message_id is None:
        await message.answer("Не понял постер. Пришлите фото.")
        return

    anime = await _create_anime_from_state(state, poster_message_id)

    await state.update_data(anime_id=anime.id)
    await state.set_state(AdminStates.add_anime_add_season)
    await message.answer(
        "Аниме добавлено. Добавить сезон сразу?",
        reply_markup=yes_no_keyboard("anime_add_season_yes", "anime_add_season_no"),
    )


@router.message(AdminStates.add_season_number)
async def add_season_number(message: Message, state: FSMContext) -> None:
    if not await _guard_message(message):
        return

    data = await state.get_data()
    number = _parse_positive_int(message.text)
    if number is None:
        await message.answer("Напишите номер сезона цифрами.")
        return

    async with Session() as session:
        season = Season(anime_id=data["anime_id"], number=number)
        session.add(season)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await message.answer("Такой номер сезона уже есть в этом аниме. Введите другой номер.")
            return
        await session.refresh(season)

    await state.update_data(season_id=season.id)
    await state.set_state(AdminStates.add_season_add_episode)
    await message.answer(
        "Сезон добавлен. Добавить серию сразу?",
        reply_markup=yes_no_keyboard("season_add_episode_yes", "season_add_episode_no"),
    )


@router.message(AdminStates.add_episode_conveyor_video)
async def add_episode_conveyor_video(message: Message, state: FSMContext) -> None:
    if not await _guard_message(message):
        return

    if message.text and message.text.strip() == "Завершить":
        await state.clear()
        await message.answer("Загрузка завершена.", reply_markup=ReplyKeyboardRemove())
        await message.answer(await _admin_menu_text(), reply_markup=admin_main_keyboard())
        return

    if not _has_episode_media(message):
        await message.answer("Пришлите видео.")
        return

    data = await state.get_data()
    season_id = data["season_id"]
    current_number = data["current_number"]

    if message.media_group_id:
        messages = await _mg_collector.collect(message)
        if messages is None:
            return

        last_saved = current_number
        async with Session() as session:
            for msg in messages:
                if not _has_episode_media(msg):
                    continue
                try:
                    msg_id = await _episode_message_id_from_admin_upload(msg)
                except TelegramAPIError:
                    continue
                if msg_id is None:
                    continue
                episode = Episode(season_id=season_id, number=current_number, message_id=msg_id)
                session.add(episode)
                current_number += 1
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                await message.answer("Ошибка: дубликат серии.", reply_markup=conveyor_finish_keyboard())
                return

        await state.update_data(current_number=current_number)
        added = current_number - last_saved
        await message.answer(
            f"Добавлено серий: {added} (с {last_saved} по {current_number - 1}).\n"
            f"Отправьте видео для {current_number} серии или нажмите Завершить.",
            reply_markup=conveyor_finish_keyboard(),
        )
        return

    try:
        message_id = await _episode_message_id_from_admin_upload(message)
    except TelegramAPIError:
        await message.answer("Не получилось отправить серию в канал. Проверьте, что бот админ канала и может публиковать сообщения.")
        return
    if message_id is None:
        await message.answer("Не понял серию. Пришлите видео.")
        return

    async with Session() as session:
        episode = Episode(
            season_id=season_id,
            number=current_number,
            message_id=message_id,
        )
        session.add(episode)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await message.answer(f"Серия {current_number} уже существует.")
            return

    next_number = current_number + 1
    await state.update_data(current_number=next_number)
    await message.answer(
        f"Серия {current_number} добавлена. Отправьте видео для {next_number} серии или нажмите Завершить.",
        reply_markup=conveyor_finish_keyboard(),
    )


@router.message(AdminStates.edit_value)
async def edit_value(message: Message, state: FSMContext) -> None:
    if not await _guard_message(message):
        return

    data = await state.get_data()
    entity = data["edit_entity"]
    item_id = data["edit_item_id"]
    field = data["edit_field"]
    value = await _parse_edit_value(message, entity, field)
    if value is None:
        return

    old_message_id = None
    async with Session() as session:
        item = await _get_entity(session, entity, item_id)
        if item is None:
            await state.clear()
            await message.answer("Запись не найдена.")
            return

        if entity == Entity.ANIME.value and field == "poster":
            old_message_id = item.poster_message_id
        elif entity == Entity.EPISODE.value and field == "message":
            old_message_id = item.message_id

        _apply_edit(item, entity, field, value)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await message.answer("Такой номер уже занят. Попробуйте другой.")
            return

    if old_message_id is not None:
        try:
            await message.bot.delete_message(chat_id=settings.channel_id, message_id=old_message_id)
        except TelegramAPIError:
            pass

    await state.clear()
    await message.answer("Изменения сохранены.", reply_markup=admin_main_keyboard())


@router.message(AdminStates.broadcast_text)
async def broadcast_text(message: Message, state: FSMContext) -> None:
    if not await _guard_message(message):
        return

    if message.text:
        await message.bot.send_message(
            chat_id=message.chat.id,
            text=f"<b>Предпросмотр рассылки:</b>\n\n{message.text}",
            parse_mode="HTML",
        )
    elif message.photo or message.video or message.document or message.animation:
        orig_caption = message.caption or ""
        caption = f"<b>Предпросмотр рассылки</b>"
        if orig_caption:
            caption = f"<b>Предпросмотр рассылки:</b>\n\n{orig_caption}"
        await message.bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            parse_mode="HTML",
        )
    else:
        await message.answer("Пожалуйста, отправьте текст, фото или видео для рассылки.")
        return

    await message.answer(
        "Предпросмотр. Отправить это сообщение всем пользователям?",
        reply_markup=yes_no_keyboard("broadcast_yes", "broadcast_no"),
    )

    await state.update_data(broadcast_message=message)
