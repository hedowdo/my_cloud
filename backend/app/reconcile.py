"""Resume only abandoned unpublished uploads and explicitly approved deletion jobs."""

from app.config import Settings
from app.database import make_engine
from app.file_service import Files
from app.identity_service import Identity


def main():
    settings = Settings()
    engine = make_engine(settings)
    try:
        Files(engine, Identity(engine, settings), settings).reconcile()
        print("File lifecycle reconciliation completed; recycle-bin items were not auto-purged")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
