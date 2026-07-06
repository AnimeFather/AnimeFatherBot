from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    channel_id: int
    admin_ids: frozenset[int]
    auto_create_tables: bool = True


def _parse_admin_ids(value: str | None) -> frozenset[int]:
    if not value:
        return frozenset()
    return frozenset(int(item.strip()) for item in value.split(",") if item.strip())


settings = Settings(
    bot_token=_required("BOT_TOKEN"),
    database_url=_required("DATABASE_URL"),
    channel_id=int(_required("CHANNEL_ID")),
    admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS")),
    auto_create_tables=os.getenv("AUTO_CREATE_TABLES", "1").lower() in {"1", "true", "yes"},
)
