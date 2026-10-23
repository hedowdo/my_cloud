from sqlalchemy import Engine, create_engine

from app.config import Settings

SCHEMA_REVISION = "0005_media_cleanup"


def make_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )
