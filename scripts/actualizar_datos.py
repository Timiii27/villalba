"""
Convierte los Excel de estadísticas de partido (app Afición FBM) en data/liga.json.

Uso (desde la raíz del repositorio):
    pip install -r scripts/requirements.txt
    python scripts/actualizar_datos.py

- Mete los Excel nuevos en la carpeta excels/ (da igual el nombre; los repetidos se ignoran).
- Si la FBM mueve un partido de fecha, cambia la fecha en data/calendario.csv.
- Puesto y altura salen de data/plantillas.csv (sacado de la guía de la liga). Si ficha alguien nuevo,
  añádelo ahí con su equipo tal y como sale en los Excel.
"""
import glob, json, os, re, sys, unicodedata
from datetime import date
from difflib import SequenceMatcher
from openpyxl import load_workbook

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCELS = os.path.join(ROOT, "excels")
CAL = os.path.join(ROOT, "data", "calendario.csv")
PLANT = os.path.join(ROOT, "data", "plantillas.csv")
OUT = os.path.join(ROOT, "data", "liga.json")
MI_EQUIPO = "VILLALBA GILMAR"

SHORT = {"MAJADAHONDA": "Majadahonda", "SANJORGE MADRID": "San Jorge", "ADC BOADILLA": "Boadilla",
         "SALTIUM ALCORCÓN BASKET": "Alcorcón", "C.B. GETAFE": "Getafe", "BASKET TORREJON": "Torrejón",
         "SAN VIATOR": "San Viator", "C.D. TAJAMAR": "Tajamar", "VILLALBA GILMAR": "Villalba",
         "BALONCESTO ALCALA": "Alcalá", "JANSEN BT": "Jansen", "UROS DE RIVAS": "Uros de Rivas"}
FULL = {"MAJADAHONDA": "Majadahonda", "SANJORGE MADRID": "San Jorge Madrid", "ADC BOADILLA": "ADC Boadilla",
        "SALTIUM ALCORCÓN BASKET": "Saltium Alcorcón Basket", "C.B. GETAFE": "C.B. Getafe",
        "BASKET TORREJON": "Basket Torrejón", "SAN VIATOR": "San Viator", "C.D. TAJAMAR": "C.D. Tajamar",
        "VILLALBA GILMAR": "Villalba Gilmar", "BALONCESTO ALCALA": "Baloncesto Alcalá", "JANSEN BT": "Jansen BT",
        "UROS DE RIVAS": "Uros de Rivas"}
TEAMS = list(SHORT)
TID = {t: i for i, t in enumerate(TEAMS)}
COLS = ["min", "pts", "t2m", "t2a", "t3m", "t3a", "tlm", "tla", "rd", "ro", "as", "rec", "per", "tap", "tr", "fc", "fr", "val"]
LOW = {"de", "del", "la", "las", "los", "y", "da", "di", "van", "von"}


def mmss(s):
    m, sec = str(s or "0:00").split(":")
    return round(int(m) + int(sec) / 60, 2)


def ai(s):
    a, i = str(s or "0/0").split("/")
    return int(a), int(i)


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def title(s):
    s = re.sub(r"\s+", " ", str(s).strip()).lower()
    words = ["-".join(p if p in LOW else p[:1].upper() + p[1:] for p in w.split("-")) for w in s.split(" ")]
    return re.sub(r",\s*", ", ", " ".join(words))


def _toks(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")
    return {w for w in re.findall(r"[a-z]+", s) if len(w) > 1 and w not in LOW}


def _score(a, b):
    """Palabras del nombre que coinciden (admite pequeñas erratas, p. ej. Tejeda/Tejada)."""
    tb = _toks(b)
    return sum(1 for x in _toks(a) if any(x == y or SequenceMatcher(None, x, y).ratio() >= 0.8 for y in tb))


def load_plantillas():
    """Devuelve {equipo: [(dorsal, nombre, altura, puesto), ...]} desde data/plantillas.csv."""
    out = {}
    if not os.path.exists(PLANT):
        return out
    with open(PLANT, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            if line.strip():
                eq, d, n, h, p = [x.strip() for x in line.strip().split(";")]
                out.setdefault(eq, []).append((d, n, float(h.replace(",", ".")) if h else None, p))
    return out


def find_ficha(plant, team, name, dorsal):
    best, bs = None, 0
    for f in plant.get(team, []):
        s = _score(name, f[1])
        if s > bs or (s == bs and best and f[0] == dorsal and best[0] != dorsal):
            best, bs = f, s
    if best and (bs >= 2 or (bs >= 1 and best[0] == dorsal)):
        return best
    return None


def parse_excel(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    rows = [list(r) for r in wb.active.iter_rows(values_only=True)]
    title_row = next(str(r[0]) for r in rows if r and r[0] and str(r[0]).startswith("Estadísticas"))
    m = re.match(r"Estadísticas - (.+?) vs (.+?) - ", title_row)
    home, away = m.group(1).strip(), m.group(2).strip()
    cur, players, totals = None, [], {}
    for i, r in enumerate(rows):
        r = (r + [None] * 25)[:25]
        filled = [v for v in r if v not in (None, "")]
        nxt = [str(v) for v in (rows[i + 1] if i + 1 < len(rows) else []) if v]
        if len(filled) == 1 and r[0] and "TC 2P" in nxt:
            cur = str(r[0]).strip()
            continue
        if cur is None or r[1] in (None, "", "Nombre"):
            continue
        rec = {"team": cur, "num": str(r[0] or "").strip(), "name": str(r[1]).strip(), "min": mmss(r[2]), "pts": num(r[3])}
        rec["t2m"], rec["t2a"] = ai(r[4]); rec["t3m"], rec["t3a"] = ai(r[6]); rec["tlm"], rec["tla"] = ai(r[8])
        for k, c in [("rd", 10), ("ro", 11), ("as", 13), ("rec", 14), ("per", 15), ("tap", 16), ("tr", 17), ("fc", 18), ("fr", 19), ("val", 20), ("pm", 21)]:
            rec[k] = num(r[c])
        if rec["name"] == "TOTALES":
            totals[cur] = rec
        else:
            players.append(rec)
    return home, away, players, totals


def main():
    cal = {}
    with open(CAL, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            if line.strip():
                j, h, a, f = line.strip().split(";")
                cal[(h, a)] = (int(j), f)
    games, tg, names, nidx, pg, seen, avisos = [], [], [], {}, [], set(), []
    parsed = []
    for f in sorted(glob.glob(os.path.join(EXCELS, "*.xlsx"))):
        home, away, players, totals = parse_excel(f)
        for t in (home, away):
            if t not in TID:
                sys.exit(f"Equipo desconocido '{t}' en {os.path.basename(f)}. Añádelo a SHORT y FULL.")
        sig = (home, away)
        if sig in seen:
            continue
        seen.add(sig)
        if sig not in cal:
            avisos.append(f"{home} - {away} ({os.path.basename(f)}) no está en el calendario: se ignora.")
            continue
        parsed.append((home, away, players, totals))
    to_date = lambda s: tuple(int(x) for x in reversed(s.split("/")))
    parsed.sort(key=lambda x: (to_date(cal[(x[0], x[1])][1]), cal[(x[0], x[1])][0]))
    for gi, (home, away, players, totals) in enumerate(parsed):
        j, fecha = cal[(home, away)]
        games.append([j, fecha, TID[home], TID[away], totals[home]["pts"], totals[away]["pts"]])
        for t in (home, away):
            tg.append([gi, TID[t]] + [totals[t][c] for c in COLS])
        for p in players:
            if p["name"] == "NOMBRE":
                continue
            if p["min"] == 0 and not any(p[c] for c in ("pts", "rd", "ro", "as", "fc")):
                continue
            key = (p["team"], p["name"])
            if key not in nidx:
                nidx[key] = len(names)
                names.append([title(p["name"]), TID[p["team"]]])
            pg.append([gi, nidx[key], p["num"]] + [p[c] for c in COLS] + [p["pm"]])
    # puesto y altura desde la guía (se emparejan por nombre; el dorsal ayuda a desempatar)
    plant, sin_ficha = load_plantillas(), []
    dors = {}
    for r in pg:
        dors.setdefault(r[1], {}).setdefault(r[2], 0)
        dors[r[1]][r[2]] += 1
    raw = {v: k for k, v in nidx.items()}
    for i, n in enumerate(names):
        team, rawname = raw[i]
        dorsal = max(dors[i].items(), key=lambda x: x[1])[0]
        f = find_ficha(plant, team, rawname, dorsal)
        n += [f[3], f[2]] if f else ["", None]
        if not f and plant:
            sin_ficha.append(f"{SHORT[team]} {dorsal} {n[0]}")
    played = {(TEAMS[g[2]], TEAMS[g[3]]) for g in games}
    fut = [[j, TID[h], TID[a], f] for (h, a), (j, f) in cal.items() if (h, a) not in played]
    hoy = date.today()
    pendientes_pasados = [f"J{j} {SHORT[h]} - {SHORT[a]} ({f})" for (h, a), (j, f) in cal.items()
                          if (h, a) not in played and to_date(f) < (hoy.year, hoy.month, hoy.day)]
    last = max(games, key=lambda g: to_date(g[1]))[1] if games else hoy.strftime("%d/%m/%Y")
    data = dict(updated=last, teams=[[SHORT[t], FULL[t]] for t in TEAMS], me=TID[MI_EQUIPO], games=games,
                tg=tg, players=names, pg=pg, fut=fut, cols=COLS)
    # jugada a jugada (capturas de scripts/capturar_partido.sh), si las hay
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import jugadas
    jugadas.main(liga=data)
    pbp, pbp_ok = jugadas.load_for_web(data)
    if pbp:
        data["pbp"], data["pbp_ok"] = pbp, pbp_ok
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {len(games)} partidos, {len(names)} jugadores, {len(fut)} partidos pendientes. Datos hasta el {last}."
          + (f" Jugada a jugada de {len(pbp)} partidos." if pbp else ""))
    for a in avisos:
        print("AVISO:", a)
    if sin_ficha:
        print(f"{len(sin_ficha)} jugadores sin puesto en data/plantillas.csv (la web lo estima por sus números):")
        print("  " + ", ".join(sin_ficha))
    if pendientes_pasados:
        print("Partidos con fecha ya pasada sin Excel (¿aplazados o te falta el archivo?):")
        for p in pendientes_pasados:
            print("  -", p)


if __name__ == "__main__":
    main()
