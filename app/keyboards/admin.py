from aiogram.types import InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup
from aiogram.types import KeyboardButton
from aiogram.types import ReplyKeyboardMarkup

from app.callbacks import AdminActionCallback
from app.callbacks import AdminConfirmCallback
from app.callbacks import AdminFieldCallback
from app.callbacks import AdminListCallback
from app.callbacks import AdminPickCallback
from app.services.catalog_service import Page


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_action("Добавить аниме", "add_anime")],
            [_action("Добавить серию", "add_episode")],
            [_action("Редактировать", "edit")],
            [_action("Сделать рассылку", "broadcast")],
            [_action("Очистить историю рассылок", "clear_broadcasts")],
        ]
    )


def yes_no_keyboard(yes_action: str, no_action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_action("Да", yes_action), _action("Нет", no_action)]])


def anime_list_keyboard(page: Page, action: str, pick_entity: str = "anime") -> InlineKeyboardMarkup:
    rows = [[_pick(anime.title, pick_entity, action, anime.id)] for anime in page.items]
    rows.append(_pager(pick_entity, action, page.page, page.pages))
    rows.append([_action("Назад", "menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def season_list_keyboard(page: Page, action: str, anime_id: int, show_create: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [_pick(f"Сезон {season.number}", "season", action, season.id)]
        for season in page.items
    ]
    rows.append(_pager("season", action, page.page, page.pages, parent_id=anime_id))
    if show_create:
        rows.append([_action("Создать сезон", "create_season")])
    back_action = "back_to_anime_list" if action == "add_episode" else "back_to_anime_editor"
    rows.append([_action("Назад", back_action)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def episode_list_keyboard(page: Page, action: str, season_id: int) -> InlineKeyboardMarkup:
    rows = [
        [_pick(str(episode.number), "episode", action, episode.id)]
        for episode in page.items
    ]
    rows.append(_pager("episode", action, page.page, page.pages, parent_id=season_id))
    rows.append([_action("Назад", "back_to_season_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def anime_edit_keyboard(anime_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_field("Название", "anime", anime_id, "title")],
            [_field("Постер", "anime", anime_id, "poster")],
            [_list("Сезон", "season", "edit", 1, anime_id)],
            [_list("Серия", "season", "edit_episode", 1, anime_id)],
            [_confirm("Удалить", "anime", anime_id, "delete")],
            [_action("Назад", "back_to_anime_list")],
        ]
    )


def season_edit_keyboard(season_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_field("Номер", "season", season_id, "number")],
            [_confirm("Удалить", "season", season_id, "delete")],
            [_action("Назад", "back_to_season_list")],
        ]
    )


def episode_edit_keyboard(episode_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_field("Номер", "episode", episode_id, "number")],
            [_field("Заменить", "episode", episode_id, "message")],
            [_confirm("Удалить", "episode", episode_id, "delete")],
            [_action("Назад", "back_to_episode_list")],
        ]
    )


def delete_confirm_keyboard(entity: str, item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _confirm("Удалить", entity, item_id, "delete_yes"),
                _confirm("Отмена", entity, item_id, "delete_no"),
            ]
        ]
    )


def _action(text: str, action: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=AdminActionCallback(action=action).pack())


def _list(text: str, entity: str, action: str, page: int = 1, parent_id: int = 0) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=AdminListCallback(entity=entity, action=action, page=page, parent_id=parent_id).pack(),
    )


def _pick(text: str, entity: str, action: str, item_id: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=AdminPickCallback(entity=entity, action=action, item_id=item_id).pack(),
    )


def _field(text: str, entity: str, item_id: int, field: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=AdminFieldCallback(entity=entity, item_id=item_id, field=field).pack(),
    )


def _confirm(text: str, entity: str, item_id: int, action: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=AdminConfirmCallback(entity=entity, item_id=item_id, action=action).pack(),
    )


def conveyor_finish_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Завершить")]],
        resize_keyboard=True,
    )


def _pager(entity: str, action: str, page: int, pages: int, parent_id: int = 0) -> list[InlineKeyboardButton]:
    left = _list("◀️", entity, action, page - 1, parent_id) if page > 1 else InlineKeyboardButton(text="⏺️", callback_data="noop")
    right = _list("▶️", entity, action, page + 1, parent_id) if page < pages else InlineKeyboardButton(text="⏺️", callback_data="noop")
    return [
        left,
        _list(f"{page}/{pages}", entity, action, page, parent_id),
        right,
    ]
