from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import media
from app.settings import Settings
from tests.clips import clip, needs_ffmpeg


def image_bytes(format: str = "PNG", size: tuple[int, int] = (40, 30), orientation: int | None = None) -> bytes:
    image = Image.new("RGB", size, (200, 80, 40))
    exif = Image.Exif()
    if orientation is not None:
        exif[media.EXIF_ORIENTATION] = orientation
    buffer = BytesIO()
    image.save(buffer, format=format, exif=exif)
    return buffer.getvalue()


def upload(
    client: TestClient, data: bytes, name: str = "photo.png", content_type: str = "image/png"
) -> dict[str, object]:
    response = client.post("/assets", files={"file": (name, data, content_type)})
    return {"status": response.status_code, **response.json()}


def test_an_uploaded_image_is_stored_and_served(client: TestClient, settings: Settings) -> None:
    data = image_bytes()
    asset = upload(client, data)
    assert asset["status"] == 201
    assert (asset["media_type"], asset["source"], asset["width"], asset["height"]) == ("image", "upload", 40, 30)
    assert asset["url"] == f"/media/uploads/{asset['id']}.png"
    assert (settings.media_dir / "uploads" / f"{asset['id']}.png").read_bytes() == data
    served = client.get(str(asset["url"]))
    assert served.status_code == 200
    assert served.content == data
    assert served.headers["content-type"] == "image/png"


def test_the_file_contents_decide_the_type_not_the_name(client: TestClient) -> None:
    asset = upload(client, image_bytes("JPEG"), name="photo.png", content_type="image/png")
    assert asset["status"] == 201
    assert str(asset["url"]).endswith(".jpg")


def test_a_phone_photo_turned_by_exif_reports_its_shown_size(client: TestClient) -> None:
    # Stored 40 wide and 30 high, but tagged to be shown turned a quarter: 30 wide and 40 high
    asset = upload(client, image_bytes("JPEG", orientation=6), name="portrait.jpg", content_type="image/jpeg")
    assert (asset["width"], asset["height"]) == (30, 40)


@pytest.mark.parametrize(
    "data",
    [b"not an image at all", image_bytes("GIF"), image_bytes()[:-30]],
    ids=["text", "gif", "truncated png"],
)
def test_files_that_are_not_a_supported_image_are_refused(client: TestClient, data: bytes) -> None:
    response = client.post("/assets", files={"file": ("x.png", data, "image/png")})
    assert response.status_code == 415
    assert response.json() == {"detail": "Upload a photo (PNG, JPEG or WebP) or a video clip"}


@needs_ffmpeg
def test_a_clip_is_stored_as_mp4_with_a_poster(client: TestClient, settings: Settings) -> None:
    asset = upload(client, clip(3, size=(640, 360)), name="clip.mov", content_type="video/quicktime")
    assert asset["status"] == 201
    assert (asset["media_type"], asset["width"], asset["height"]) == ("video", 640, 360)
    assert asset["duration_s"] == pytest.approx(3, abs=0.1)
    assert asset["url"] == f"/media/uploads/{asset['id']}.mp4"
    assert asset["thumbnail_url"] == f"/media/uploads/{asset['id']}.jpg"
    assert client.get(str(asset["url"])).headers["content-type"] == "video/mp4"
    with Image.open(settings.media_dir / "uploads" / f"{asset['id']}.jpg") as poster:
        assert poster.size == (640, 360)


@needs_ffmpeg
def test_a_long_tall_clip_is_cut_to_what_the_video_model_uses(client: TestClient) -> None:
    asset = upload(client, clip(17, size=(800, 1600), fps=10), name="tall.mp4", content_type="video/mp4")
    # The first 15 seconds, with the short edge at 768
    assert (asset["width"], asset["height"], asset["duration_s"]) == (768, 1536, 15)


@needs_ffmpeg
def test_a_clip_too_short_to_use_is_refused(client: TestClient) -> None:
    response = client.post("/assets", files={"file": ("blink.mp4", clip(1), "video/mp4")})
    assert response.status_code == 422
    assert response.json() == {"detail": "Clips need to be at least 2 seconds long"}


def test_uploads_over_the_limit_are_refused(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media, "MAX_UPLOAD_BYTES", 100)
    response = client.post("/assets", files={"file": ("x.png", image_bytes(size=(400, 400)), "image/png")})
    assert response.status_code == 413


def test_the_library_lists_uploads_newest_first(client: TestClient) -> None:
    first = upload(client, image_bytes())
    second = upload(client, image_bytes("JPEG"))
    listed = client.get("/assets").json()
    assert [a["id"] for a in listed] == [second["id"], first["id"]]
