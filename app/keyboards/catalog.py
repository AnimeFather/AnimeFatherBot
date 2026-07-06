from aiogram.types import InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup

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
from app.callbacks import AnimeCallback
from app.database.models import Episode
from app.services.catalog_service import Page


def search_results_keyboard(page: Page) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=anime.title, callback_data=AnimeCallback(anime_id=anime.id).pack())]
        for anime in page.items
    ]
    rows.append(_pager_row(page.page, page.pages, SearchPageCallback))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def seasons_keyboard(anime_id: int, page: Page) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=f"Сезон {season.number}",
            callback_data=SeasonCallback(season_id=season.id).pack(),
        )
        for season in page.items
    ]
    rows = _chunk(buttons, 4)
    rows.append(_pager_row(page.page, page.pages, SeasonPageCallback, anime_id=anime_id))
    rows.append([InlineKeyboardButton(text="Назад", callback_data=BackToSearchCallback().pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def episodes_keyboard(page: Page, season_id: int, highlight: int = 0, anime_id: int = 0) -> InlineKeyboardMarkup:
    episodes: list[Episode] = page.items
    rows: list[list[InlineKeyboardButton]] = []
    rows_count = 4

    for row_index in range(rows_count):
        row = []
        for episode in episodes[row_index::rows_count]:
            text = f"[{episode.number}]" if episode.number == highlight else str(episode.number)
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=EpisodeCallback(episode_id=episode.id).pack(),
                )
            )
        if row:
            rows.append(row)

    rows.append(
        _pager_row(
            page.page,
            page.pages,
            EpisodePageCallback,
            season_id=season_id,
            highlight=highlight,
        )
    )
    rows.append(
        [
            InlineKeyboardButton(text="Назад", callback_data=BackToSeasonsCallback(anime_id=anime_id).pack()),
            InlineKeyboardButton(
                text="Поиск",
                callback_data=EpisodeSearchCallback(season_id=season_id).pack(),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def episode_video_keyboard(season_id: int, episode_number: int, page: int, has_next: bool = True, has_prev: bool = False) -> InlineKeyboardMarkup:
    nav_row = [
        InlineKeyboardButton(
            text="◀️",
            callback_data=EpisodeNavCallback(season_id=season_id, episode_number=episode_number - 2).pack(),
        ) if has_prev else InlineKeyboardButton(text="⏺️", callback_data="noop"),
        InlineKeyboardButton(
            text=f"Серия {episode_number}",
            callback_data="noop",
        ),
        InlineKeyboardButton(
            text="▶️",
            callback_data=EpisodeNavCallback(season_id=season_id, episode_number=episode_number).pack(),
        ) if has_next else InlineKeyboardButton(text="⏺️", callback_data="noop"),
    ]
    back_row = [
        InlineKeyboardButton(
            text="Назад",
            callback_data=BackToEpisodesCallback(season_id=season_id, page=page, highlight=0).pack(),
        ),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[nav_row, back_row])


def _pager_row(page: int, pages: int, callback_cls, **kwargs) -> list[InlineKeyboardButton]:
    left = InlineKeyboardButton(text="◀️", callback_data=callback_cls(page=page - 1, **kwargs).pack()) if page > 1 else InlineKeyboardButton(text="⏺️", callback_data="noop")
    right = InlineKeyboardButton(text="▶️", callback_data=callback_cls(page=page + 1, **kwargs).pack()) if page < pages else InlineKeyboardButton(text="⏺️", callback_data="noop")
    return [
        left,
        InlineKeyboardButton(text=f"{page}/{pages}", callback_data=callback_cls(page=page, **kwargs).pack()),
        right,
    ]


def _chunk(items: list[InlineKeyboardButton], size: int) -> list[list[InlineKeyboardButton]]:
    return [items[index : index + size] for index in range(0, len(items), size)]
