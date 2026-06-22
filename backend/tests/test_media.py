import io

import pytest
from fastapi import HTTPException, UploadFile

from app.services.media import save_upload


async def test_save_upload_rejects_bad_type(tmp_path, monkeypatch):
    from app.services import media
    monkeypatch.setattr(media.settings, "media_root", str(tmp_path))
    f = UploadFile(filename="x.exe", file=io.BytesIO(b"x"), headers={"content-type": "application/x-msdownload"})
    with pytest.raises(HTTPException):
        await save_upload(f)


async def test_save_upload_writes_png(tmp_path, monkeypatch):
    from app.services import media
    monkeypatch.setattr(media.settings, "media_root", str(tmp_path))
    f = UploadFile(filename="a.png", file=io.BytesIO(b"\x89PNG..."), headers={"content-type": "image/png"})
    url = await save_upload(f)
    assert url.startswith("/media/avatars/") and url.endswith(".png")


async def test_upload_endpoint(client, tmp_path, monkeypatch):
    from app.services import media
    monkeypatch.setattr(media.settings, "media_root", str(tmp_path))
    files = {"file": ("a.png", b"\x89PNG", "image/png")}
    r = await client.post("/media/upload", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("/media/avatars/")
