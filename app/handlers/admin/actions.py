from collections.abc import Awaitable
from collections.abc import Callable

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.callbacks import AdminActionCallback
from app.callbacks import BroadcastCancelCallback
from app.enums import Entity
from app.handlers.admin.helpers import _admin_menu_text
from app.handlers.admin.helpers import _create_season
from app.handlers.admin.helpers import _edit_or_answer
from app.handlers.admin.helpers import _show_anime_editor
from app.handlers.admin.helpers import _show_anime_list
from app.handlers.admin.helpers import _show_episode_list
from app.handlers.admin.helpers import _show_season_list
from app.keyboards.admin import admin_main_keyboard
from app.keyboards.admin import conveyor_finish_keyboard
from app.keyboards.admin import yes_no_keyboard
from app.services.admin_service import next_episode_number
from app.database.session import Session
from app.states import AdminStates


router = Router()


async def _action_menu(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    await state.clear()
    await _edit_or_answer(callback, await _admin_menu_text(), admin_main_keyboard())


async def _action_add_anime(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    await state.set_state(AdminStates.add_anime_title)
    await callback.message.answer("Название аниме:")


async def _action_add_season(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    await _show_anime_list(callback, "add_season", 1, Entity.ANIME)


async def _action_create_season(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    data = await state.get_data()
    anime_id = data.get("anime_id")
    if not anime_id:
        await callback.answer("Сначала выберите аниме.", show_alert=True)
        return
    result = await _create_season(anime_id)
    if result is None:
        await callback.message.edit_text("Ошибка: такой сезон уже существует.")
        await callback.answer()
        return
    number, season = result
    await state.update_data(season_id=season.id)
    await state.set_state(AdminStates.add_season_add_episode)
    await callback.message.edit_text(
        f"Сезон {number} добавлен. Добавить серию?",
        reply_markup=yes_no_keyboard("season_add_episode_yes", "season_add_episode_no"),
    )


async def _action_add_episode(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    await state.update_data(admin_pick_entity=Entity.ANIME.value, admin_action_type="add_episode")
    await state.set_state(AdminStates.waiting_anime_search)
    await callback.message.answer("Напишите название аниме:")


async def _action_edit(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    await state.update_data(admin_pick_entity=Entity.ANIME.value, admin_action_type="edit")
    await state.set_state(AdminStates.waiting_anime_search)
    await callback.message.answer("Напишите название аниме:")


async def _action_back_to_anime_list(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    data = await state.get_data()
    pick_entity = data.get("admin_pick_entity", Entity.ANIME.value)
    action_type = data.get("admin_action_type", "edit")
    query = data.get("last_query")
    await _show_anime_list(callback, action_type, 1, pick_entity, query=query)


async def _action_back_to_anime_editor(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    data = await state.get_data()
    anime_id = data.get("back_anime_id")
    if anime_id:
        await _show_anime_editor(callback, anime_id)
    else:
        await _edit_or_answer(callback, "Не удалось вернуться.", admin_main_keyboard())


async def _action_back_to_season_list(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    data = await state.get_data()
    anime_id = data.get("back_anime_id")
    back_action = data.get("back_action", "edit")
    if anime_id:
        await _show_season_list(callback, back_action, anime_id, 1)
    else:
        await _edit_or_answer(callback, "Не удалось вернуться.", admin_main_keyboard())


async def _action_back_to_episode_list(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    data = await state.get_data()
    season_id = data.get("back_season_id")
    back_action = data.get("back_action", "edit")
    if season_id:
        await _show_episode_list(callback, back_action, season_id, 1)
    else:
        await _edit_or_answer(callback, "Не удалось вернуться.", admin_main_keyboard())


async def _action_anime_add_season_yes(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    data = await state.get_data()
    anime_id = data.get("anime_id")
    if not anime_id:
        await callback.answer("Ошибка: аниме не выбрано.", show_alert=True)
        return
    result = await _create_season(anime_id)
    if result is None:
        await callback.message.edit_text("Ошибка: такой сезон уже существует.")
        await callback.answer()
        return
    number, season = result
    await state.update_data(season_id=season.id)
    await state.set_state(AdminStates.add_season_add_episode)
    await callback.message.edit_text(
        f"Сезон {number} добавлен. Добавить серию?",
        reply_markup=yes_no_keyboard("season_add_episode_yes", "season_add_episode_no"),
    )


async def _action_anime_add_season_no(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Готово. Аниме добавлено.", reply_markup=admin_main_keyboard())


async def _action_season_add_episode_yes(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    data = await state.get_data()
    season_id = data.get("season_id")
    if season_id is None:
        await callback.message.edit_text("Сначала выберите сезон.")
        await callback.answer()
        return
    await state.set_state(AdminStates.add_episode_conveyor_video)
    async with Session() as session:
        next_num = await next_episode_number(session, season_id)
    await state.update_data(current_number=next_num)
    await callback.message.edit_text(
        f"Отправьте видео (или несколько) для {next_num} серии.",
    )
    await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text="Нажмите Завершить, когда закончите.",
        reply_markup=conveyor_finish_keyboard(),
    )


async def _action_season_add_episode_no(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    data = await state.get_data()
    anime_id = data.get("anime_id")
    if anime_id:
        await _show_season_list(callback, "add_episode", anime_id, 1)
    else:
        await state.clear()
        await callback.message.edit_text("Готово. Сезон добавлен.", reply_markup=admin_main_keyboard())


async def _action_broadcast(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    await state.set_state(AdminStates.broadcast_text)
    await callback.message.answer("Отправьте сообщение для рассылки. Можно использовать фото, видео, текст.")


async def _action_broadcast_yes(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    import asyncio

    data = await state.get_data()
    message = data.get("broadcast_message")
    if message is None:
        await callback.message.edit_text("Сообщение не найдено. Начните заново.")
        await state.clear()
        return
    await callback.message.edit_text("Рассылка запущена в фоне. Следите за прогрессом.")
    await state.clear()
    from app.handlers.admin.helpers import send_broadcast
    asyncio.create_task(send_broadcast(callback.bot, callback.message.chat.id, message))


async def _action_broadcast_no(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Рассылка отменена.", reply_markup=admin_main_keyboard())


async def _action_clear_broadcasts(callback: CallbackQuery, _callback_data: AdminActionCallback, state: FSMContext) -> None:
    from app.services.user_service import delete_old_broadcasts
    async with Session() as session:
        deleted = await delete_old_broadcasts(session)
    text = f"Удалено завершённых и отменённых рассылок: {deleted}." if deleted else "Нет завершённых или отменённых рассылок."
    await callback.message.answer(text)


_admin_actions: dict[str, Callable[[CallbackQuery, AdminActionCallback, FSMContext], Awaitable[None]]] = {
    "menu": _action_menu,
    "add_anime": _action_add_anime,
    "add_season": _action_add_season,
    "create_season": _action_create_season,
    "add_episode": _action_add_episode,
    "edit": _action_edit,
    "back_to_anime_list": _action_back_to_anime_list,
    "back_to_anime_editor": _action_back_to_anime_editor,
    "back_to_season_list": _action_back_to_season_list,
    "back_to_episode_list": _action_back_to_episode_list,
    "anime_add_season_yes": _action_anime_add_season_yes,
    "anime_add_season_no": _action_anime_add_season_no,
    "season_add_episode_yes": _action_season_add_episode_yes,
    "season_add_episode_no": _action_season_add_episode_no,
    "broadcast": _action_broadcast,
    "broadcast_yes": _action_broadcast_yes,
    "broadcast_no": _action_broadcast_no,
    "clear_broadcasts": _action_clear_broadcasts,
}


@router.callback_query(BroadcastCancelCallback.filter())
async def broadcast_cancel(callback: CallbackQuery, callback_data: BroadcastCancelCallback) -> None:
    from app.database.session import Session
    from app.services.user_service import cancel_broadcast
    async with Session() as session:
        await cancel_broadcast(session, callback_data.broadcast_id)
    try:
        await callback.message.edit_text(f"Рассылка #{callback_data.broadcast_id} отменена.")
    except Exception:
        await callback.message.answer(f"Рассылка #{callback_data.broadcast_id} отменена.")
    await callback.answer()


@router.callback_query(AdminActionCallback.filter())
async def admin_action(callback: CallbackQuery, callback_data: AdminActionCallback, state: FSMContext) -> None:
    handler = _admin_actions.get(callback_data.action)
    if handler:
        await handler(callback, callback_data, state)
    await callback.answer()
