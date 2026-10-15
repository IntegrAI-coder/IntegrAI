"""Genera los medios de las 50 pruebas en datos_sinteticos/pruebas50/ (+ manifiesto SHA-256).

    python -m bench.pruebas50.generar

- texto  : la nota tal cual (casos.jsonl)
- imagen : post-it manuscrito (PIL + fuentes OFL de bench/.cache), rotado/desenfocado/desordenado;
           paisaje o figuras para fuera de tema; archivo FALSO (texto con extensión de imagen)
- audio  : Amazon Polly (es-US/es-MX), opcionalmente con volumen muy bajo (ffmpeg)
- video  : figura animada (PIL + imageio-ffmpeg) con cartel opcional y la voz Polly mezclada
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import subprocess
from pathlib import Path

import boto3
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bench.pruebas50.casos import CASOS
from bench.sinteticos import _fuente

RAIZ = Path(__file__).resolve().parents[2]
OUT = RAIZ / "datos_sinteticos" / "pruebas50"
MEDIOS = OUT / "medios"
VOCES = [("Lupe", "es-US"), ("Mia", "es-MX"), ("Pedro", "es-US"), ("Andres", "es-MX")]
rnd = random.Random(20261015)


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _voz(texto: str, ruta: Path, i: int) -> None:
    voz, lang = VOCES[i % len(VOCES)]
    r = boto3.client("polly", region_name="us-east-1").synthesize_speech(
        Text=texto, OutputFormat="mp3", VoiceId=voz, Engine="neural", LanguageCode=lang)
    ruta.write_bytes(r["AudioStream"].read())


def _postit(texto: str, ruta: Path, extra: dict, i: int) -> None:
    fuente = ImageFont.truetype(str(_fuente(["Caveat", "IndieFlower", "PatrickHand"][i % 3])), 64)
    im = Image.new("RGB", (900, 900), (255, 238, 130))
    d = ImageDraw.Draw(im)
    y = 120
    for linea in texto.split("\n"):
        x = 70 + (rnd.randint(-40, 40) if extra.get("desordenado") else rnd.randint(-6, 6))
        d.text((x, y + (rnd.randint(-15, 15) if extra.get("desordenado") else 0)), linea, fill=(25, 35, 110), font=fuente)
        y += 120
    im = im.rotate(extra.get("rotacion", rnd.uniform(-5, 5)), expand=True, fillcolor=(210, 210, 210))
    if extra.get("blur"):
        im = im.filter(ImageFilter.GaussianBlur(extra["blur"]))
    im.save(ruta, "JPEG", quality=75)


def _escena(tipo: str, ruta: Path) -> None:
    im = Image.new("RGB", (900, 600), (140, 190, 235))
    d = ImageDraw.Draw(im)
    if tipo == "paisaje":
        d.rectangle([0, 380, 900, 600], fill=(80, 150, 70))
        d.polygon([(100, 380), (300, 150), (500, 380)], fill=(110, 110, 120))
        d.polygon([(400, 380), (620, 120), (840, 380)], fill=(95, 95, 110))
        d.ellipse([720, 40, 820, 140], fill=(250, 220, 90))
    else:
        for _ in range(12):
            x, y = rnd.randint(0, 800), rnd.randint(0, 500)
            d.rectangle([x, y, x + rnd.randint(40, 120), y + rnd.randint(40, 120)],
                        fill=(rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255)))
    im.save(ruta, "JPEG", quality=85)


def _video(texto: str, ruta: Path, extra: dict, i: int) -> None:
    import imageio.v2 as iio
    segundos = extra.get("segundos", 4)
    n = 24 * segundos
    fuente = ImageFont.truetype(str(_fuente("PatrickHand")), 30)
    frames = []
    for k in range(n):
        t = k / max(n - 1, 1)
        im = Image.new("RGB", (640, 368), (235, 230, 220))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 300, 640, 368], fill=(150, 120, 90))
        fig = extra.get("figura", "quieta")
        if fig == "figuras":
            for j in range(5):
                x = (int(t * 500) + j * 130) % 640
                d.ellipse([x, 120 + j * 25, x + 50, 170 + j * 25], fill=(60 + j * 40, 90, 160))
        else:
            if fig == "pararse":
                d.rectangle([420, 200, 480, 300], outline=(80, 50, 30), width=6)  # silla
                h = min(1, t * 1.6); x = 330 if t < 0.7 else 330 - (t - 0.7) * 260
            elif fig == "guardar":
                d.rectangle([450, 240, 540, 300], outline=(90, 60, 30), width=5)    # caja
                h, x = 1, 300 + 100 * abs(np.sin(t * 6))
                d.rectangle([x + 30, 225, x + 50, 245], fill=(200, 60, 60))       # bloque
            else:
                h, x = 0.2, 330
            hip = 300 - 30 - 90 * h; head = hip - 100
            d.ellipse([x - 20, head - 20, x + 20, head + 20], fill=(240, 190, 150))
            d.line([x, head + 20, x, hip], fill=(60, 90, 160), width=12)
            d.line([x, hip, x - 14, 300], fill=(40, 40, 60), width=10); d.line([x, hip, x + 14, 300], fill=(40, 40, 60), width=10)
        if extra.get("cartel"):
            d.rectangle([20, 15, 620, 75], fill=(255, 255, 255), outline=(0, 0, 0), width=3)
            d.text((35, 25), extra["cartel"], fill=(180, 0, 0), font=fuente)
        frames.append(np.array(im))
    mudo = ruta.with_suffix(".mudo.mp4")
    iio.mimwrite(mudo, frames, fps=24, codec="libx264", quality=6)
    if texto:
        voz = ruta.with_suffix(".mp3")
        _voz(texto, voz, i)
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(mudo), "-i", str(voz),
                        "-c:v", "copy", "-c:a", "aac"] + (["-shortest"] if segundos < 3 else []) + [str(ruta)], check=True)
        voz.unlink()
        mudo.unlink()
    else:
        mudo.rename(ruta)


def main() -> None:
    MEDIOS.mkdir(parents=True, exist_ok=True)
    filas, manifiesto = [], []
    for i, (cid, cat, mod, contenido, edad, nivel, controles, extra) in enumerate(CASOS):
        ruta = None
        if mod == "imagen":
            if extra.get("falso"):
                ruta = MEDIOS / f"{cid}{extra.get('extension', '.jpg')}"
                ruta.write_text("#!/bin/sh\necho " + contenido + "\n", encoding="utf-8")   # no es una imagen
            elif extra.get("escena"):
                ruta = MEDIOS / f"{cid}.jpg"; _escena(extra["escena"], ruta)
            else:
                ruta = MEDIOS / f"{cid}.jpg"; _postit(contenido, ruta, extra, i)
        elif mod == "audio":
            ruta = MEDIOS / f"{cid}.mp3"
            _voz(contenido, ruta, i)
            if extra.get("volumen"):
                bajo = ruta.with_suffix(".bajo.mp3")
                subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(ruta), "-filter:a",
                                f"volume={extra['volumen']}", str(bajo)], check=True)
                bajo.replace(ruta)
        elif mod == "video":
            ruta = MEDIOS / f"{cid}.mp4"; _video(contenido, ruta, extra, i)
        filas.append({"id": cid, "categoria": cat, "modalidad": mod, "contenido": contenido, "edad_meses": edad,
                      "nivel_esperado": nivel, "controles": controles, "extra": extra,
                      "medio": ruta.relative_to(OUT).as_posix() if ruta else None})
        if ruta:
            manifiesto.append({"archivo": ruta.relative_to(OUT).as_posix(), "bytes": ruta.stat().st_size,
                               "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest(), "caso": cid,
                               "generador": "bench/pruebas50/generar.py",
                               "modelo": {"audio": "Amazon Polly", "video": "PIL + imageio-ffmpeg + Polly",
                                          "imagen": "PIL + fuentes OFL"}[mod]})
        print(cid, mod, "ok")
    (OUT / "casos.jsonl").write_text("\n".join(json.dumps(f, ensure_ascii=False) for f in filas) + "\n", encoding="utf-8")
    with open(OUT / "MANIFEST.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(manifiesto[0])); w.writeheader(); w.writerows(manifiesto)
    print(f"{len(filas)} casos, {len(manifiesto)} medios -> {OUT}")


if __name__ == "__main__":
    main()
