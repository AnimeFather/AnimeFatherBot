import html

from app.database.models import Season
from app.database.models import Anime
from app.services.catalog_service import Page


def start_text() -> str:
    return (
        "<b>AnimeFather</b> — твой бесплатный доступ к аниме.\n\n"
        "⚡️ Смотри и скачивай любимые серии без ограничений.\n"
        "🔍 Чтобы найти аниме, отправь боту его название или код.\n\n"
        "📢 Следи за новинками и обновлениями в нашем канале: @AnimeFathNews\n"
        "✉️ По всем вопросам и предложениям пиши сюда: @AnimeFathSupport\n\n"
        "Приятного просмотра! 🍿"
    )


def search_results_text(query: str, page: Page) -> str:
    return (
        f"Поиск: {query}\n"
        f"Найдено: {page.total}\n"
    )


def nothing_found_text(query: str) -> str:
    return (
        f"По запросу «{query}» ничего не найдено.\n\n"
    )


def anime_card_text(anime: Anime) -> str:
    return (
        f"<b>{html.escape(anime.title)}</b>\n\n"
        "Выберите сезон:"
    )


def episodes_text(season: Season, page: Page) -> str:
    anime_title = f"<b>{html.escape(season.anime.title)}</b>" if season.anime else "Аниме"
    return (
        f"{anime_title}\n\n"
        f"Сезон {season.number}\n"
        f"Кол-во серий: {page.total}\n\n"
        "Выберите серию:"
    )
