from dataclasses import dataclass
from math import ceil

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Episode
from app.database.models import Season
from app.database.models import Anime
from app.services.catalog_service import Page
from app.services.catalog_service import clamp_page


@dataclass(frozen=True)
class CatalogStats:
    anime: int
    seasons: int
    episodes: int


async def get_stats(session: AsyncSession) -> CatalogStats:
    anime = await session.scalar(select(func.count(Anime.id)))
    seasons = await session.scalar(select(func.count(Season.id)))
    episodes = await session.scalar(select(func.count(Episode.id)))
    return CatalogStats(anime or 0, seasons or 0, episodes or 0)


async def list_anime(session: AsyncSession, page: int, per_page: int = 8) -> Page:
    total = await session.scalar(select(func.count(Anime.id)))
    pages = max(1, ceil((total or 0) / per_page))
    page = clamp_page(page, pages)
    result = await session.scalars(
        select(Anime)
        .order_by(Anime.title.asc(), Anime.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return Page(list(result), total or 0, page, per_page)


async def get_episode_for_admin(session: AsyncSession, episode_id: int) -> Episode | None:
    return await session.scalar(
        select(Episode)
        .options(selectinload(Episode.season).selectinload(Season.anime))
        .where(Episode.id == episode_id)
    )


async def next_season_number(session: AsyncSession, anime_id: int) -> int:
    number = await session.scalar(
        select(func.max(Season.number)).where(Season.anime_id == anime_id)
    )
    return (number or 0) + 1


async def next_episode_number(session: AsyncSession, season_id: int) -> int:
    number = await session.scalar(select(func.max(Episode.number)).where(Episode.season_id == season_id))
    return (number or 0) + 1
