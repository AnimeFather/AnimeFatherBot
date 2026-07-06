from aiogram.fsm.state import State
from aiogram.fsm.state import StatesGroup


class CatalogStates(StatesGroup):
    waiting_episode_number = State()


class AdminStates(StatesGroup):
    add_anime_title = State()
    add_anime_poster = State()
    add_anime_add_season = State()
    add_season_number = State()
    add_season_add_episode = State()
    edit_value = State()
    add_episode_conveyor_video = State()
    waiting_anime_search = State()
    broadcast_text = State()
