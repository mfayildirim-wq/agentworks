"""Gemeinsame Klartext-Extraktion aus hochgeladenen Dateien.

Genutzt sowohl beim Profil-Parsen (`profile_extract`) als auch beim Anhängen von
Dateien im Instanz-Chat (`artifact_files.attachments_context`). Bewusst tolerant:
unbekannte Endung oder leerer Inhalt → "" (der Aufrufer entscheidet, was das heißt).
"""

from __future__ import annotations

import io


def extract_text(filename: str, data: bytes) -> str:
    """Extrahiert Klartext aus PDF/DOCX/TXT/MD/CSV anhand der Dateiendung.

    Gibt "" zurück, wenn der Typ unbekannt ist oder kein Text gewonnen werden kann.
    Wirft NICHT bei unbekannter Endung.
    """
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if name.endswith(".docx"):
        import docx

        doc = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    if name.endswith((".txt", ".md", ".csv")):
        return data.decode("utf-8", errors="ignore")
    return ""
