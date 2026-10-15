from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    AssetSource,
    Capability,
    Generation,
    GenerationInput,
    GenerationStatus,
    InputRole,
    MediaType,
    Quality,
)


def upload(key: str = "uploads/a.png") -> Asset:
    return Asset(
        media_type=MediaType.IMAGE,
        source=AssetSource.UPLOAD,
        storage_key=key,
        mime_type="image/png",
        size_bytes=100,
        width=64,
        height=64,
    )


def generation(**changes: object) -> Generation:
    fields: dict[str, object] = {
        "capability": Capability.VIDEO_REFERENCE,
        "workflow_id": "minimax-h3",
        "prompt": "she turns towards the camera",
        "quality": Quality.MEDIUM,
        "aspect_ratio": "16:9",
        "duration_s": 5.0,
        "count": 1,
        "seed": 42,
    }
    return Generation(**(fields | changes))


def test_a_generation_keeps_its_inputs_in_order_and_its_outputs(engine: Engine) -> None:
    with Session(engine) as session:
        first, second = upload("uploads/1.png"), upload("uploads/2.png")
        g = generation(capability=Capability.IMAGE_EDIT, aspect_ratio=None, duration_s=None)
        g.inputs = [
            GenerationInput(position=1, role=InputRole.REFERENCE, asset=second),
            GenerationInput(position=0, role=InputRole.EDIT_TARGET, asset=first),
        ]
        session.add(g)
        session.flush()
        session.add(
            Asset(
                media_type=MediaType.VIDEO,
                source=AssetSource.GENERATION,
                storage_key=f"outputs/{g.id}/0.mp4",
                mime_type="video/mp4",
                size_bytes=1000,
                width=1280,
                height=720,
                duration_s=5.0,
                poster_key=f"outputs/{g.id}/0.jpg",
                generation_id=g.id,
            )
        )
        session.commit()
        generation_id = g.id

    with Session(engine) as session:
        loaded = session.get_one(Generation, generation_id)
        assert loaded.status is GenerationStatus.QUEUED
        assert [i.role for i in loaded.inputs] == [InputRole.EDIT_TARGET, InputRole.REFERENCE]
        assert [i.asset.storage_key for i in loaded.inputs] == ["uploads/1.png", "uploads/2.png"]
        assert [o.media_type for o in loaded.outputs] == [MediaType.VIDEO]


def test_ids_sort_by_creation(engine: Engine) -> None:
    with Session(engine) as session:
        session.add_all([generation(prompt=str(n)) for n in range(5)])
        session.commit()
        prompts = session.scalars(select(Generation.prompt).order_by(Generation.id)).all()
    assert prompts == ["0", "1", "2", "3", "4"]


def failed_without_error(session: Session) -> None:
    session.add(generation(status=GenerationStatus.FAILED, finished_at=datetime.now(UTC)))


def done_without_finish_time(session: Session) -> None:
    session.add(generation(status=GenerationStatus.DONE))


def unknown_quality(session: Session) -> None:
    session.add(generation(quality="2K"))


def output_without_generation(session: Session) -> None:
    asset = upload()
    asset.source = AssetSource.GENERATION
    session.add(asset)


def video_without_duration(session: Session) -> None:
    asset = upload()
    asset.media_type, asset.poster_key = MediaType.VIDEO, "uploads/a.jpg"
    session.add(asset)


def video_without_poster(session: Session) -> None:
    asset = upload()
    asset.media_type, asset.duration_s = MediaType.VIDEO, 3.0
    session.add(asset)


@pytest.mark.parametrize(
    "break_a_rule",
    [
        failed_without_error,
        done_without_finish_time,
        unknown_quality,
        output_without_generation,
        video_without_duration,
        video_without_poster,
    ],
)
def test_the_database_rejects_rows_that_break_the_rules(
    engine: Engine, break_a_rule: Callable[[Session], None]
) -> None:
    with Session(engine) as session:
        break_a_rule(session)
        with pytest.raises(IntegrityError):
            session.commit()
