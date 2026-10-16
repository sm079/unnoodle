"""Makes previews for pictures stored before every picture got one (app.media.write_preview).

    uv run python -m app.previews

Safe to run again: pictures that have a preview are skipped.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import make_engine
from app.media import MediaStore, write_preview
from app.models import Asset, MediaType
from app.settings import Settings


def main() -> None:
    settings = Settings()
    store = MediaStore(settings.media_dir)
    with Session(make_engine(settings.database_url)) as session:
        pictures = session.scalars(
            select(Asset).where(Asset.media_type == MediaType.IMAGE, Asset.poster_key.is_(None))
        ).all()
        for n, asset in enumerate(pictures, 1):
            # uploads/<id>.png -> uploads/<id>.preview.webp
            preview_key = f"{asset.storage_key.rsplit('.', 1)[0]}.preview.webp"
            write_preview(store, asset.storage_key, preview_key)
            asset.poster_key = preview_key
            session.commit()
            print(f"{n}/{len(pictures)} {preview_key}")
    print(f"Made {len(pictures)} previews")


if __name__ == "__main__":
    main()
