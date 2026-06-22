import io

from app.services import profile_extract as pe


def test_extract_text_from_txt():
    assert "Java" in pe._extract_text("cv.txt", b"Senior Java Entwickler")


async def test_extract_profile_uses_ollama(monkeypatch):
    from fastapi import UploadFile

    def fake_call(text: str) -> dict:
        return {"role": "Softwareentwickler", "domain": "software",
                "skills": ["java", "spring"], "summary": "Senior.", "name": "Max"}

    monkeypatch.setattr(pe, "_call_ollama", fake_call)
    f = UploadFile(filename="cv.txt", file=io.BytesIO(b"Java Spring Entwickler"))
    out = await pe.extract_profile(f)
    assert out.role == "Softwareentwickler"
    assert out.skills == ["java", "spring"]
