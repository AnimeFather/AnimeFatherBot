from aiogram.filters.callback_data import CallbackData


class SearchPageCallback(CallbackData, prefix="sp"):
    page: int


class AnimeCallback(CallbackData, prefix="an"):
    anime_id: int


class SeasonPageCallback(CallbackData, prefix="sg"):
    anime_id: int
    page: int


class SeasonCallback(CallbackData, prefix="sn"):
    season_id: int
    page: int = 1
    highlight: int = 0


class EpisodeCallback(CallbackData, prefix="ep"):
    episode_id: int


class EpisodePageCallback(CallbackData, prefix="eg"):
    season_id: int
    page: int
    highlight: int = 0


class EpisodeSearchCallback(CallbackData, prefix="ef"):
    season_id: int


class BackToSearchCallback(CallbackData, prefix="bs"):
    pass


class BackToSeasonsCallback(CallbackData, prefix="bt"):
    anime_id: int
    page: int = 1


class BackToEpisodesCallback(CallbackData, prefix="be"):
    season_id: int
    page: int = 1
    highlight: int = 0


class EpisodeNavCallback(CallbackData, prefix="en"):
    season_id: int
    episode_number: int


class AdminActionCallback(CallbackData, prefix="aa"):
    action: str


class AdminListCallback(CallbackData, prefix="al"):
    entity: str
    action: str
    page: int = 1
    parent_id: int = 0


class AdminPickCallback(CallbackData, prefix="ap"):
    entity: str
    action: str
    item_id: int


class AdminFieldCallback(CallbackData, prefix="af"):
    entity: str
    item_id: int
    field: str


class AdminConfirmCallback(CallbackData, prefix="ac"):
    entity: str
    item_id: int
    action: str


class BroadcastCancelCallback(CallbackData, prefix="bcc"):
    broadcast_id: int
