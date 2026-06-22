"""Registry auswählbarer Avatar-Stile.

Jeder Stil hat eine deutsche `label`-Bezeichnung (Dropdown), eine `group` (Gruppierung
im Dropdown) und ein englisches `prompt`-Fragment, das beim Generieren an die
Bildbeschreibung angehängt wird und den Look bestimmt (Fotorealismus, Anime, Pixar …).

Die Liste ist gegenüber der Nutzer-Vorlage **dedupliziert** (jeder Stil genau einmal,
in seiner ersten Gruppe). Default ist `fotorealistisch`.
"""

from __future__ import annotations

_DEFAULT_ID = "fotorealistisch"

# (id, label, group, prompt-fragment)
_RAW: list[tuple[str, str, str, str]] = [
    # --- Realistische Stile ---
    ("fotorealistisch", "Fotorealistisch", "Realistische Stile",
     "photorealistic, ultra-detailed, realistic skin and textures, natural lighting, 50mm photo"),
    ("hyperrealistisch", "Hyperrealistisch", "Realistische Stile",
     "hyperrealistic, extreme detail, lifelike, razor-sharp focus, high dynamic range"),
    ("cinematic-movie-shot", "Cinematic Movie Shot", "Realistische Stile",
     "cinematic movie shot, dramatic lighting, shallow depth of field, film grain, anamorphic"),
    ("hollywood-blockbuster", "Hollywood Blockbuster", "Realistische Stile",
     "Hollywood blockbuster poster style, epic dramatic lighting, high production value"),
    ("national-geographic", "National Geographic Fotografie", "Realistische Stile",
     "National Geographic photography, candid realism, natural light, documentary feel"),
    ("studio-portrait", "Studio Portrait", "Realistische Stile",
     "professional studio portrait, soft key light, seamless backdrop, sharp focus"),
    ("fashion-photography", "Fashion Photography", "Realistische Stile",
     "high-fashion editorial photography, stylish, glossy magazine lighting"),
    ("cyberpunk-realismus", "Cyberpunk Realismus", "Realistische Stile",
     "cyberpunk realism, neon-lit, gritty futuristic city, photoreal"),
    ("post-apocalyptic-realismus", "Post-Apocalyptic Realismus", "Realistische Stile",
     "post-apocalyptic realism, weathered, gritty, dramatic, photoreal"),
    ("fantasy-realismus", "Fantasy Realismus", "Realistische Stile",
     "fantasy realism, painterly photoreal, epic, richly detailed costume"),
    # --- Zeichentrick & Animation ---
    ("disney-stil", "Disney-Stil", "Zeichentrick & Animation",
     "classic Disney animation style, expressive, polished, vibrant"),
    ("pixar-stil", "Pixar-Stil", "Zeichentrick & Animation",
     "Pixar 3D animation style, soft rounded shapes, big expressive eyes, warm lighting"),
    ("dreamworks-stil", "DreamWorks-Stil", "Zeichentrick & Animation",
     "DreamWorks animation style, stylized, characterful, cinematic"),
    ("cartoon-network-stil", "Cartoon Network Stil", "Zeichentrick & Animation",
     "Cartoon Network style, bold flat colors, playful, simple shapes"),
    ("nickelodeon-stil", "Nickelodeon Stil", "Zeichentrick & Animation",
     "Nickelodeon cartoon style, zany, colorful, exaggerated"),
    ("saturday-morning-cartoon", "Saturday Morning Cartoon", "Zeichentrick & Animation",
     "retro Saturday-morning cartoon style, clean lines, bright colors"),
    ("chibi", "Chibi", "Zeichentrick & Animation",
     "chibi style, super-cute, big head small body, kawaii"),
    ("anime", "Anime", "Zeichentrick & Animation",
     "anime style, clean cel shading, expressive eyes, detailed"),
    ("manga", "Manga", "Zeichentrick & Animation",
     "black-and-white manga style, ink lines, screentones"),
    ("super-deformed", "Super Deformed (SD)", "Zeichentrick & Animation",
     "super deformed SD style, tiny cute proportions, comedic"),
    # --- Comics ---
    ("marvel-comic-stil", "Marvel Comic Stil", "Comics",
     "Marvel comic book style, dynamic, bold inking, vivid colors"),
    ("dc-comic-stil", "DC Comic Stil", "Comics",
     "DC comic book style, dramatic, detailed inking, cinematic"),
    ("graphic-novel", "Graphic Novel", "Comics",
     "graphic novel style, painterly, moody, mature illustration"),
    ("franco-belgischer-comic", "Franco-Belgischer Comic", "Comics",
     "Franco-Belgian ligne claire comic style, clean lines, flat colors"),
    ("manga-cover", "Manga Cover", "Comics",
     "manga cover art style, polished color illustration, dynamic"),
    ("cell-shading", "Cell Shading", "Comics",
     "cel-shaded style, flat shading, bold outlines"),
    ("comic-ink-drawing", "Comic Ink Drawing", "Comics",
     "comic ink drawing, black ink linework, cross-hatching"),
    ("noir-comic", "Noir Comic", "Comics",
     "noir comic style, high-contrast black and white, dramatic shadows"),
    # --- Videospiel-Stile ---
    ("rpg-concept-art", "RPG Character Concept Art", "Videospiel-Stile",
     "RPG character concept art, detailed costume design, painterly"),
    ("mmorpg-held", "MMORPG Held", "Videospiel-Stile",
     "MMORPG hero style, ornate armor, epic fantasy game art"),
    ("moba-champion", "MOBA Champion", "Videospiel-Stile",
     "MOBA champion splash art, dynamic pose, stylized rendering"),
    ("fighting-game-charakter", "Fighting Game Charakter", "Videospiel-Stile",
     "fighting game character art, muscular, dynamic, stylized"),
    ("retro-pixel-art", "Retro Pixel Art", "Videospiel-Stile",
     "retro pixel art, limited palette, crisp pixels"),
    ("16-bit-sprite", "16-Bit Sprite", "Videospiel-Stile",
     "16-bit sprite art, SNES-era pixel style"),
    ("8-bit-pixel-art", "8-Bit Pixel Art", "Videospiel-Stile",
     "8-bit pixel art, NES-era, blocky, limited colors"),
    ("unreal-engine-5", "Unreal Engine 5 Character", "Videospiel-Stile",
     "Unreal Engine 5 render, ultra-realistic real-time, ray-traced"),
    ("playstation-game-character", "PlayStation Game Character", "Videospiel-Stile",
     "modern PlayStation game character render, high detail, cinematic"),
    ("nintendo-charakter", "Nintendo-artiger Charakter", "Videospiel-Stile",
     "Nintendo-style character, friendly, rounded, colorful"),
    # --- Fantasy ---
    ("high-fantasy", "High Fantasy", "Fantasy",
     "high fantasy art, epic, detailed, painterly"),
    ("dark-fantasy", "Dark Fantasy", "Fantasy",
     "dark fantasy art, grim, moody, atmospheric"),
    ("epic-fantasy", "Epic Fantasy", "Fantasy",
     "epic fantasy illustration, grand, dramatic lighting"),
    ("elfen-stil", "Elfen-Stil", "Fantasy",
     "elf fantasy style, elegant, ethereal, detailed"),
    ("drachenreiter", "Drachenreiter", "Fantasy",
     "dragon rider fantasy art, epic, dynamic"),
    ("magischer-zauberer", "Magischer Zauberer", "Fantasy",
     "powerful wizard fantasy art, magical glow, detailed robes"),
    ("fantasy-ritter", "Fantasy Ritter", "Fantasy",
     "fantasy knight art, detailed armor, heroic"),
    ("mythologische-kreatur", "Mythologische Kreatur", "Fantasy",
     "mythological creature art, majestic, detailed"),
    ("dnd-charakter", "Dungeons & Dragons Charakter", "Fantasy",
     "Dungeons & Dragons character art, detailed fantasy portrait"),
    # --- Sci-Fi ---
    ("cyberpunk", "Cyberpunk", "Sci-Fi",
     "cyberpunk style, neon, high-tech, futuristic, gritty"),
    ("steampunk", "Steampunk", "Sci-Fi",
     "steampunk style, brass gears, Victorian retro-futurism"),
    ("biopunk", "Biopunk", "Sci-Fi",
     "biopunk style, organic tech, bioluminescent, unsettling"),
    ("space-opera", "Space Opera", "Sci-Fi",
     "space opera style, grand sci-fi, dramatic cosmic backdrop"),
    ("alien-civilization", "Alien Civilization", "Sci-Fi",
     "alien civilization concept art, otherworldly, detailed"),
    ("android-roboter", "Android / Roboter", "Sci-Fi",
     "android robot concept art, sleek mechanical detail"),
    ("mecha-pilot", "Mecha Pilot", "Sci-Fi",
     "mecha pilot style, futuristic suit, anime-mecha vibe"),
    ("futuristischer-soldat", "Futuristischer Soldat", "Sci-Fi",
     "futuristic soldier concept art, high-tech armor"),
    ("galactic-explorer", "Galactic Explorer", "Sci-Fi",
     "galactic explorer sci-fi art, adventurous, detailed suit"),
    # --- Kunststile ---
    ("oelgemaelde", "Ölgemälde", "Kunststile",
     "oil painting style, visible brushstrokes, rich texture"),
    ("aquarell", "Aquarell", "Kunststile",
     "watercolor painting style, soft washes, bleeding colors"),
    ("acrylmalerei", "Acrylmalerei", "Kunststile",
     "acrylic painting style, bold colors, textured"),
    ("kohlezeichnung", "Kohlezeichnung", "Kunststile",
     "charcoal drawing, soft smudges, monochrome"),
    ("bleistiftskizze", "Bleistiftskizze", "Kunststile",
     "pencil sketch, graphite linework, hand-drawn"),
    ("impressionismus", "Impressionismus", "Kunststile",
     "Impressionist painting style, loose brushwork, light-focused"),
    ("expressionismus", "Expressionismus", "Kunststile",
     "Expressionist painting style, bold colors, emotional distortion"),
    ("surrealismus", "Surrealismus", "Kunststile",
     "surrealist art style, dreamlike, imaginative"),
    ("pop-art", "Pop Art", "Kunststile",
     "pop art style, bold flat colors, halftone dots, Warhol-esque"),
    ("art-nouveau", "Art Nouveau", "Kunststile",
     "Art Nouveau style, ornate flowing lines, decorative"),
    ("art-deco", "Art Deco", "Kunststile",
     "Art Deco style, geometric, elegant, gold accents"),
    # --- Japanische Stile ---
    ("studio-ghibli", "Studio Ghibli inspiriert", "Japanische Stile",
     "Studio Ghibli inspired style, soft painterly backgrounds, warm and whimsical"),
    ("samurai-illustration", "Samurai Illustration", "Japanische Stile",
     "samurai illustration, traditional Japanese, detailed armor"),
    ("ukiyo-e", "Ukiyo-e Holzschnitt", "Japanische Stile",
     "ukiyo-e woodblock print style, traditional Japanese, flat bold colors"),
    ("visual-novel", "Visual Novel Charakter", "Japanische Stile",
     "visual novel character art, soft anime, detailed"),
    ("jrpg-charakterdesign", "JRPG Charakterdesign", "Japanische Stile",
     "JRPG character design, stylized anime, detailed costume"),
    # --- Niedliche Stile ---
    ("kawaii", "Kawaii", "Niedliche Stile",
     "kawaii style, adorable, pastel colors, cute"),
    ("plush-toy", "Plush Toy Style", "Niedliche Stile",
     "plush toy style, soft fabric texture, stuffed-animal look"),
    ("sticker-style", "Sticker Style", "Niedliche Stile",
     "die-cut sticker style, bold outline, flat colors, glossy"),
    ("kinderbuch-illustration", "Kinderbuch Illustration", "Niedliche Stile",
     "children's book illustration, warm, friendly, hand-drawn"),
    ("3d-toy-character", "3D Toy Character", "Niedliche Stile",
     "3D toy character render, glossy plastic, collectible figure"),
    ("funko-pop", "Funko-Pop-artig", "Niedliche Stile",
     "Funko Pop style, big head small body, vinyl figure, black dot eyes"),
]

STYLES: list[dict] = [
    {"id": i, "label": label, "group": group, "prompt": prompt}
    for (i, label, group, prompt) in _RAW
]

_BY_ID: dict[str, dict] = {s["id"]: s for s in STYLES}


def list_styles() -> list[dict]:
    """Alle Stile (id, label, group, prompt) in Anzeige-Reihenfolge."""
    return list(STYLES)


def fragment(style_id: str) -> str:
    """Englisches Prompt-Fragment für `style_id`; unbekannt/leer → Default-Stil."""
    return _BY_ID.get(style_id, _BY_ID[_DEFAULT_ID])["prompt"]
