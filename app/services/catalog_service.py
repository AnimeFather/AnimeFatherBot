from dataclasses import dataclass
from math import ceil
from typing import Generic
from typing import TypeVar

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Episode
from app.database.models import Season
from app.database.models import Anime

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int

    @property
    def pages(self) -> int:
        return max(1, ceil(self.total / self.per_page))


def clamp_page(page: int, pages: int) -> int:
    return max(1, min(page, max(1, pages)))


async def search_anime(
    session: AsyncSession,
    query: str,
    page: int,
    per_page: int = 10,
) -> Page:
    query = query.strip()
    pattern = f"%{query}%"

    total = await session.scalar(select(func.count(Anime.id)).where(Anime.title.ilike(pattern)))
    pages = max(1, ceil((total or 0) / per_page))
    page = clamp_page(page, pages)

    result = await session.scalars(
        select(Anime)
        .where(Anime.title.ilike(pattern))
        .order_by(
            (func.lower(Anime.title) == query.lower()).desc(),
            Anime.title.asc(),
            Anime.id.asc(),
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return Page(list(result), total or 0, page, per_page)


async def get_anime(session: AsyncSession, anime_id: int) -> Anime | None:
    return await session.scalar(
        select(Anime)
        .options(selectinload(Anime.seasons))
        .where(Anime.id == anime_id)
    )


async def get_seasons(session: AsyncSession, anime_id: int, page: int, per_page: int = 3) -> Page:
    total = await session.scalar(select(func.count(Season.id)).where(Season.anime_id == anime_id))
    pages = max(1, ceil((total or 0) / per_page))
    page = clamp_page(page, pages)

    result = await session.scalars(
        select(Season)
        .where(Season.anime_id == anime_id)
        .order_by(Season.number.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return Page(list(result), total or 0, page, per_page)


async def get_season(session: AsyncSession, season_id: int) -> Season | None:
    return await session.scalar(
        select(Season)
        .options(selectinload(Season.anime))
        .where(Season.id == season_id)
    )


async def get_episodes(session: AsyncSession, season_id: int, page: int, per_page: int = 12) -> Page:
    total = await session.scalar(select(func.count(Episode.id)).where(Episode.season_id == season_id))
    pages = max(1, ceil((total or 0) / per_page))
    page = clamp_page(page, pages)

    result = await session.scalars(
        select(Episode)
        .where(Episode.season_id == season_id)
        .order_by(Episode.number.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return Page(list(result), total or 0, page, per_page)


async def get_episode(session: AsyncSession, episode_id: int) -> Episode | None:
    return await session.scalar(select(Episode).where(Episode.id == episode_id))


async def has_next_episode(session: AsyncSession, season_id: int, episode_number: int) -> bool:
    episode = await session.scalar(
        select(Episode.id).where(
            Episode.season_id == season_id,
            Episode.number > episode_number,
        ).limit(1)
    )
    return episode is not None


async def get_episode_page(session: AsyncSession, season_id: int, episode_number: int, per_page: int = 12) -> int:
    before_count = await session.scalar(
        select(func.count(Episode.id)).where(
            Episode.season_id == season_id,
            Episode.number <= episode_number,
        )
    )
    return ceil((before_count or 1) / per_page)


async def find_episode_by_number(
    session: AsyncSession,
    season_id: int,
    number: int,
    per_page: int = 12,
) -> tuple[Episode | None, int]:
    episode = await session.scalar(
        select(Episode).where(
            Episode.season_id == season_id,
            Episode.number == number,
        )
    )
    if episode is None:
        return None, 1

    before_count = await session.scalar(
        select(func.count(Episode.id)).where(
            Episode.season_id == season_id,
            Episode.number <= episode.number,
        )
    )
    return episode, ceil((before_count or 1) / per_page)
