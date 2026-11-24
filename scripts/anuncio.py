"""
Detecta el botón para cerrar un anuncio en una pantalla leída con uiautomator.

    python3 scripts/anuncio.py pantalla.xml   -> imprime "x y" del botón de cerrar, o nada si no hay
"""
import re, sys, unicodedata, xml.etree.ElementTree as ET

WORDS = ("CERRAR", "CLOSE", "SALTAR", "SKIP", "OMITIR", "DISMISS", "NO, GRACIAS", "NO GRACIAS")
MARKS = ("X", "×", "✕", "✖", "⨯")


def plain(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s).upper()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def close_point(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    best = None
    for n in root.iter("node"):
        t, d, r = plain(n.get("text")), plain(n.get("content-desc")), (n.get("resource-id") or "").lower()
        b = list(map(int, re.findall(r"-?\d+", n.get("bounds", ""))))
        if len(b) != 4 or b[2] <= b[0] or b[3] <= b[1]:
            continue
        hit = (any(w in t or w in d for w in WORDS) or t in MARKS or d in MARKS
               or any(k in r for k in ("close", "dismiss", "skip")))
        if not hit or "VOLVER" in d:
            continue
        area = (b[2] - b[0]) * (b[3] - b[1])
        # preferir botones pequeños y arriba a la derecha, que es donde suelen estar
        score = area / 1000 - b[0] / 50 + b[1] / 50
        if best is None or score < best[0]:
            best = (score, (b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
    return best[1:] if best else None


if __name__ == "__main__":
    try:
        txt = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
    except Exception:
        sys.exit(0)
    p = close_point(txt)
    if p:
        print(p[0], p[1])
