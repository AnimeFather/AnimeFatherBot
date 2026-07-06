from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import select

from app.callbacks import AdminConfirmCallback
from app.callbacks import AdminFieldCallback
from app.callbacks import AdminListCallback
from app.callbacks import AdminPickCallback
from app.database.models import Episode
from app.database.models import Season
from app.database.session import Session
from app.enums import Entity
from app.handlers.admin.helpers import _ask_delete
from app.handlers.admin.helpers import _create_season
from app.handlers.admin.helpers import _edit_or_answer
from app.handlers.admin.helpers import _edit_prompt
from app.handlers.admin.helpers import _delete_result_text
from app.handlers.admin.helpers import _hard_delete
from app.handlers.admin.helpers import _show_anime_editor
from app.handlers.admin.helpers import _show_anime_list
from app.handlers.admin.helpers import _show_episode_editor
from app.handlers.admin.helpers import _show_episode_list
from app.handlers.admin.helpers import _show_season_editor
from app.handlers.admin.helpers import _show_season_list
from app.keyboards.admin import admin_main_keyboard
from app.keyboards.admin import conveyor_finish_keyboard
from app.keyboards.admin import yes_no_keyboard
from app.services.admin_service import next_episode_number
from app.states import AdminStates


router = Router()


@router.callback_query(AdminListCallback.filter())
async def admin_list(callback: CallbackQuery, callback_data: AdminListCallback, state: FSMContext) -> None:
    query = None
    if callback_data.entity in (Entity.ANIME.value, "anime_for_season", "anime_for_episode"):
        data = await state.get_data()
        query = data.get("last_query")

    if callback_data.entity == Entity.ANIME.value:
        await _show_anime_list(callback, callback_data.action, callback_data.page, Entity.ANIME.value, query=query)
    elif callback_data.entity == "anime_for_season":
        await _show_anime_list(callback, callback_data.action, callback_data.page, "anime_for_season", query=query)
    elif callback_data.entity == "anime_for_episode":
        await _show_anime_list(callback, callback_data.action, callback_data.page, "anime_for_episode", query=query)
    elif callback_data.entity == Entity.SEASON.value:
        if callback_data.action in ("edit", "edit_episode"):
            await state.update_data(back_anime_id=callback_data.parent_id)
        await _show_season_list(callback, callback_data.action, callback_data.parent_id, callback_data.page)
    elif callback_data.entity == Entity.EPISODE.value:
        async with Session() as session:
            season = await session.scalar(select(Season).where(Season.id == callback_data.parent_id))
        await state.update_data(back_anime_id=season.anime_id if season else 0, back_season_id=callback_data.parent_id, back_action=callback_data.action)
        await _show_episode_list(callback, callback_data.action, callback_data.parent_id, callback_data.page)

    await callback.answer()


@router.callback_query(AdminPickCallback.filter())
async def admin_pick(callback: CallbackQuery, callback_data: AdminPickCallback, state: FSMContext) -> None:
    entity = callback_data.entity
    action = callback_data.action
    item_id = callback_data.item_id

    if entity == Entity.ANIME.value and action == "add_season":
        await state.update_data(anime_id=item_id)
        result = await _create_season(item_id)
        if result is None:
            await callback.message.edit_text("Ошибка: такой сезон уже существует.")
            return
        number, season = result
        await state.update_data(season_id=season.id)
        await state.set_state(AdminStates.add_season_add_episode)
        await callback.message.edit_text(
            f"Сезон {number} добавлен. Добавить серию?",
            reply_markup=yes_no_keyboard("season_add_episode_yes", "season_add_episode_no"),
        )
        await callback.answer()
        return
    elif entity == Entity.ANIME.value and action == "add_episode":
        await state.update_data(anime_id=item_id)
        await _show_season_list(callback, "add_episode", item_id, 1)
    elif entity == "anime_for_episode":
        next_action = "add_episode" if action == "add_episode" else f"{action}_episode"
        await state.update_data(anime_id=item_id)
        await _show_season_list(callback, next_action, item_id, 1)
    elif entity == "anime_for_season":
        await state.update_data(back_anime_id=item_id)
        await _show_season_list(callback, action, item_id, 1)
    elif entity == Entity.ANIME.value and action == "edit":
        await state.update_data(back_anime_id=item_id)
        await _show_anime_editor(callback, item_id)
    elif entity == Entity.SEASON.value and action == "add_episode":
        await state.update_data(season_id=item_id)
        await state.set_state(AdminStates.add_episode_conveyor_video)
        async with Session() as session:
            next_num = await next_episode_number(session, item_id)
        await state.update_data(current_number=next_num)
        await callback.message.edit_text(
            f"Отправьте видео (или несколько) для {next_num} серии.",
        )
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text="Нажмите Завершить, когда закончите.",
            reply_markup=conveyor_finish_keyboard(),
        )
    elif entity == Entity.SEASON.value and action == "edit_episode":
        async with Session() as session:
            season = await session.scalar(select(Season).where(Season.id == item_id))
        await state.update_data(back_anime_id=season.anime_id if season else 0, back_season_id=item_id, back_action="edit_episode")
        await _show_episode_list(callback, "edit", item_id, 1)
    elif entity == Entity.SEASON.value and action == "delete_episode":
        await _show_episode_list(callback, "delete", item_id, 1)
    elif entity == Entity.SEASON.value and action == "edit":
        async with Session() as session:
            season = await session.scalar(select(Season).where(Season.id == item_id))
        await state.update_data(back_anime_id=season.anime_id if season else 0, back_season_id=item_id, back_action="edit")
        await _show_season_editor(callback, item_id)
    elif entity == Entity.EPISODE.value and action == "edit":
        async with Session() as session:
            episode = await session.scalar(select(Episode).where(Episode.id == item_id))
        await state.update_data(back_season_id=episode.season_id if episode else 0, back_action="edit")
        await _show_episode_editor(callback, item_id)

    await callback.answer()


@router.callback_query(AdminFieldCallback.filter())
async def admin_field(callback: CallbackQuery, callback_data: AdminFieldCallback, state: FSMContext) -> None:
    await state.set_state(AdminStates.edit_value)
    await state.update_data(
        edit_entity=callback_data.entity,
        edit_item_id=callback_data.item_id,
        edit_field=callback_data.field,
    )
    await callback.message.answer(_edit_prompt(callback_data.entity, callback_data.field))
    await callback.answer()


@router.callback_query(AdminConfirmCallback.filter())
async def admin_confirm(callback: CallbackQuery, callback_data: AdminConfirmCallback, state: FSMContext) -> None:
    if callback_data.action == "delete":
        await _ask_delete(callback, callback_data.entity, callback_data.item_id)
    elif callback_data.action == "delete_no":
        if callback_data.entity == Entity.ANIME.value:
            await _show_anime_editor(callback, callback_data.item_id)
        elif callback_data.entity == Entity.SEASON.value:
            await _show_season_editor(callback, callback_data.item_id)
        elif callback_data.entity == Entity.EPISODE.value:
            await _show_episode_editor(callback, callback_data.item_id)
        else:
            await _edit_or_answer(callback, "Удаление отменено.", admin_main_keyboard())
    elif callback_data.action == "delete_yes":
        data = await state.get_data()
        result = await _hard_delete(callback.bot, callback_data.entity, callback_data.item_id)
        if callback_data.entity == Entity.ANIME.value:
            await _edit_or_answer(callback, _delete_result_text(result), admin_main_keyboard())
        elif callback_data.entity == Entity.SEASON.value:
            anime_id = data.get("back_anime_id")
            if anime_id:
                await _show_season_list(callback, "edit", anime_id, 1)
            else:
                await _edit_or_answer(callback, _delete_result_text(result), admin_main_keyboard())
        elif callback_data.entity == Entity.EPISODE.value:
            season_id = data.get("back_season_id")
            if season_id:
                await _show_episode_list(callback, "edit", season_id, 1)
            else:
                await _edit_or_answer(callback, _delete_result_text(result), admin_main_keyboard())
        else:
            await _edit_or_answer(callback, _delete_result_text(result), admin_main_keyboard())

    await callback.answer()
