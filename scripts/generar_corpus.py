"""Genera el corpus sintético de F2 en fixtures/corpus/ a partir del manifiesto.

Solo desarrollo (Pillow + reportlab, requirements-dev.txt). Cinco documentos
"desordenados": licencia fotografiada borrosa (la vigencia, ilegible a propósito),
verificación vencida escaneada, permiso SICT escaneado, póliza PDF de 12
páginas, hoja de 17 puntos "manuscrita". Ningún dato real.

Uso: .venv/bin/python scripts/generar_corpus.py
"""

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "corpus"
FUENTES = Path("/usr/share/fonts/truetype")
SERIF = FUENTES / "dejavu" / "DejaVuSerif.ttf"
MONO = FUENTES / "dejavu" / "DejaVuSansMono.ttf"
rng = random.Random(57)  # reproducible


def _fuente(ruta: Path, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ruta), tam)


def _pagina(lineas: list[str], *, tam=26, ancho=1240, alto=1754, jitter=0) -> Image.Image:
    img = Image.new("RGB", (ancho, alto), (250, 248, 242))
    d = ImageDraw.Draw(img)
    f = _fuente(SERIF, tam)
    y = 120
    for linea in lineas:
        if jitter:  # "manuscrito": cada carácter se desplaza un poco
            x = 100
            for ch in linea:
                d.text((x + rng.randint(-jitter, jitter), y + rng.randint(-jitter, jitter)), ch, font=f, fill=(30, 40, 90))
                x += d.textlength(ch, font=f) + rng.randint(0, 3)
        else:
            d.text((100, y), linea, font=f, fill=(20, 20, 20))
        y += int(tam * 1.7)
    return img


def _escaneo(img: Image.Image) -> Image.Image:
    """Ruido + leve inclinación, como escáner de oficina."""
    img = img.rotate(rng.uniform(-1.2, 1.2), fillcolor=(235, 232, 225), expand=False)
    ruido = Image.effect_noise(img.size, 18).convert("RGB")
    return Image.blend(img, ruido, 0.08).filter(ImageFilter.GaussianBlur(0.6))


def licencia(doc: dict) -> None:
    lineas = doc["transcripcion"].replace("[ILEGIBLE]", "2027-03-15").split("\n")
    img = _pagina(lineas, tam=34, ancho=1400, alto=900)
    d = ImageDraw.Draw(img)
    # La línea de VIGENCIA se emborrona aparte: el extractor NO debe inventarla.
    idx = next(i for i, l in enumerate(lineas) if l.startswith("VIGENCIA"))
    y = 120 + idx * int(34 * 1.7)
    caja = img.crop((90, y - 8, 700, y + 48)).filter(ImageFilter.GaussianBlur(7))
    img.paste(caja, (90, y - 8))
    d.rectangle((0, 0, 1399, 899), outline=(90, 90, 90), width=6)
    img = img.rotate(rng.uniform(-4, 4), fillcolor=(60, 55, 50), expand=True).filter(ImageFilter.GaussianBlur(1.4))
    img.save(CORPUS / doc["archivo"], quality=55)


def escaneado(doc: dict) -> None:
    _escaneo(_pagina(doc["transcripcion"].split("\n"))).save(CORPUS / doc["archivo"], quality=72)


def manuscrita(doc: dict) -> None:
    lineas = doc["transcripcion"].split("\n")
    puntos = lineas[5].split(" OK ")
    lineas = lineas[:5] + [p.strip() + (" OK" if i < len(puntos) - 1 else "") for i, p in enumerate(puntos)] + lineas[6:]
    _escaneo(_pagina(lineas, tam=30, jitter=3)).save(CORPUS / doc["archivo"], quality=72)


def poliza_pdf(doc: dict) -> None:
    c = canvas.Canvas(str(CORPUS / doc["archivo"]), pagesize=letter)
    relleno = [
        "CONDICIONES GENERALES (TEXTO SINTETICO DE RELLENO)",
        "Clausula %d. El presente texto no corresponde a ninguna poliza real y existe",
        "unicamente para que el documento tenga doce paginas y el extractor deba",
        "localizar la vigencia entre contenido irrelevante.",
    ]
    for pagina in range(1, 13):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(72, 740, f"ASEGURADORA SINTETICA SA — Pagina {pagina} de 12")
        c.setFont("Helvetica", 11)
        y = 700
        lineas = doc["transcripcion"].split("\n") if pagina in (1, 7) else []
        for l in lineas:
            c.drawString(72, y, l)
            y -= 18
        y -= 20
        for i in range(18):
            for l in relleno:
                c.drawString(72, y, l % (pagina * 10 + i) if "%d" in l else l)
                y -= 14
            y -= 8
            if y < 90:
                break
        c.showPage()
    c.save()


GENERADORES = {
    "licencia_federal": licencia,
    "verificacion_fisico_mecanica": escaneado,
    "permiso_sict": escaneado,
    "poliza_responsabilidad_civil": poliza_pdf,
    "inspeccion_17_puntos": manuscrita,
}

if __name__ == "__main__":
    manifiesto = json.loads((CORPUS / "manifiesto.json").read_text(encoding="utf-8"))
    for doc in manifiesto["documentos"]:
        GENERADORES[doc["tipo"]](doc)
        print("ok", doc["archivo"], (CORPUS / doc["archivo"]).stat().st_size, "bytes")
