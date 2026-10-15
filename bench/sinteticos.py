"""Medios sintéticos para comparar con los grabados por el equipo.

- Audio: Amazon Polly (voces neuronales es-US/es-MX) en MP3 → bench/medios/sint/audio/Cxx.mp3
- Post-it: guion renderizado con fuentes manuscritas (Google Fonts, OFL) sobre fondo amarillo,
  con rotación, ruido y desenfoque leve → bench/medios/sint/postit/Cxx.jpg

    python -m bench.sinteticos
"""
from __future__ import annotations

import io
import json
import random
import textwrap
import urllib.request
from pathlib import Path

import boto3
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src import config

AQUI = Path(__file__).parent
OUT = AQUI / "medios" / "sint"
CACHE = AQUI / ".cache"
VOCES = [("Lupe", "es-US"), ("Pedro", "es-US"), ("Mia", "es-MX"), ("Andres", "es-MX")]
FUENTES = {
    "Caveat": "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf",
    "IndieFlower": "https://github.com/google/fonts/raw/main/ofl/indieflower/IndieFlower-Regular.ttf",
    "PatrickHand": "https://github.com/google/fonts/raw/main/ofl/patrickhand/PatrickHand-Regular.ttf",
}


def _fuente(nombre: str) -> Path:
    CACHE.mkdir(exist_ok=True)
    p = CACHE / f"{nombre}.ttf"
    if not p.exists():
        urllib.request.urlretrieve(FUENTES[nombre], p)
    return p


def audio(caso: dict, i: int) -> Path:
    voz, lang = VOCES[i % len(VOCES)]
    r = boto3.client("polly", region_name=config.AWS_REGION).synthesize_speech(
        Text=caso["guion"], OutputFormat="mp3", VoiceId=voz, Engine="neural", LanguageCode=lang)
    p = OUT / "audio" / f"{caso['caso']}.mp3"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r["AudioStream"].read())
    return p


def postit(caso: dict, i: int, rnd: random.Random) -> Path:
    nombre = list(FUENTES)[i % len(FUENTES)]
    f = ImageFont.truetype(str(_fuente(nombre)), rnd.randint(40, 50))
    fondo = (255, rnd.randint(225, 245), rnd.randint(100, 150))
    im = Image.new("RGB", (900, 900), fondo)
    d = ImageDraw.Draw(im)
    y = 50
    for linea in textwrap.wrap(caso["guion"], width=30)[:13]:
        d.text((50 + rnd.randint(-6, 6), y), linea, fill=(rnd.randint(10, 60), 30, rnd.randint(60, 120)), font=f)
        y += f.size + rnd.randint(8, 16)
    im = im.rotate(rnd.uniform(-6, 6), expand=True, fillcolor=(200, 200, 200)).filter(ImageFilter.GaussianBlur(0.8))
    p = OUT / "postit" / f"{caso['caso']}.jpg"
    p.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=70); p.write_bytes(buf.getvalue())
    return p


def main() -> None:
    rnd = random.Random(7)
    casos = [json.loads(l) for l in open(AQUI / "casos.jsonl", encoding="utf-8")]
    for i, c in enumerate(casos):
        audio(c, i); postit(c, i, rnd)
        print(c["caso"], "ok")


if __name__ == "__main__":
    main()
