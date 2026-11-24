"""
Convierte las pantallas capturadas con scripts/capturar_partido.sh en el jugada a jugada de cada partido.

Lo llama scripts/actualizar_datos.py; también se puede ejecutar solo:
    python3 scripts/jugadas.py

Lee jugadas/capturas/<carpeta>/*.xml y guarda un archivo por partido en data/jugadas/.
Cada partido se compara con su Excel para avisar si falta alguna jugada.
"""
import glob, json, os, re, unicodedata, xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from statistics import median

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPT = os.path.join(ROOT, "jugadas", "capturas")
OUTD = os.path.join(ROOT, "data", "jugadas")

RX_T = re.compile(r"P\s*(\d)\s*,\s*(\d{1,2}):(\d\d)")
RX_D = re.compile(r"#\s*(\w{1,3})")


def plain(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s).upper()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


# Acciones de la app (en español y en inglés, según el idioma de BlueStacks) -> código
def classify(act):
    a = plain(act)
    has = lambda *ws: any(w in a for w in ws)
    if has("LIBRES PARA", "LIBRE PARA", "FREE THROWS FOR", "FREE THROW FOR"): return "award"
    if has("REBOTE OFENSIVO", "OFFENSIVE REBOUND"): return "ro"
    if has("REBOTE DEFENSIVO", "DEFENSIVE REBOUND"): return "rd"
    if has("TIEMPO MUERTO", "TIMEOUT"): return "to"
    if has("ENTRA", "ENTERS"): return "in"
    if has("SALE ", "SALE", "ABANDONA", "LEAVES"): return "out"
    if has("ASISTENCIA", "ASSIST"): return "as"
    if has("RECUPERA", "ROBO", "STEAL"): return "rec"
    if has("PERDIDA", "TURNOVER"): return "per"
    if has("TAPON", "BLOCK"): return "tr" if has("RECIB", "RECEIV") else "tap"
    if has("FALTA", "FOUL"): return "fr" if has("RECIB", "RECEIV") else "fc"
    if has("DISRUPTIVA", "FLAGRANTE", "FLAGRANT", "ANTIDEPORTIVA", "TECNICA", "DESCALIFICANTE", "UNSPORTSMANLIKE", "TECHNICAL"): return "fc"
    miss = has("FALL", "MISS", "ERRAD")
    if has("LIBRE", "FREE THROW"): return "1x" if miss else "1m"
    if has("TRIPLE", "THREE", "3P", "DE 3", "3 PUNTOS"): return "3x" if miss else "3m"
    if has("2P", "2-POINT", "DE 2", "2 PUNTOS", "CANASTA", "BASKET", "TIRO", "SHOT"): return "2x" if miss else "2m"
    return "?"


def nodes_of(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    out = []
    for n in root.iter("node"):
        t = (n.get("text") or "").strip()
        if not t:
            continue
        x1, y1, x2, y2 = map(int, re.findall(r"-?\d+", n.get("bounds", "[0,0][0,0]")))
        out.append(dict(t=t, x1=x1, y1=y1, x2=x2, y2=y2, cx=(x1 + x2) / 2))
    return out


RX_SC = re.compile(r"^\s*(\d{1,3})\s*-\s*(\d{1,3})\s*$")
LIST_TOP = 725  # por encima están la cabecera, el botón de jugadores y el buscador


def parse_screen(path):
    N = nodes_of(path)
    # cabecera: nombres de los equipos y marcador
    head = sorted([n for n in N if 240 < n["y1"] < 440], key=lambda n: (n["y1"], n["x1"]))
    teams = [n["t"] for n in head if n["x1"] > 150 and n["x1"] < 800 and not n["t"].isdigit()]
    scores = [int(n["t"]) for n in head if n["t"].isdigit() and n["x1"] > 800]
    W = max([n["x2"] for n in N] + [1080])
    # pantalla leída a mitad de un movimiento: textos montados unos encima de otros -> se quitan esos textos
    # (esas jugadas salen bien en la pantalla siguiente; el resto de la pantalla sirve para enlazar)
    L = [n for n in N if n["y1"] >= LIST_TOP]
    bad = set()
    for i, a in enumerate(L):
        for b in L[i + 1:]:
            if min(a["x2"], b["x2"]) - max(a["x1"], b["x1"]) > 20 and min(a["y2"], b["y2"]) - max(a["y1"], b["y1"]) > 8:
                bad.add(id(a)); bad.add(id(b))
    if bad:
        ys = [n["y1"] for n in L if id(n) in bad]
        lo, hi = min(ys) - 110, max(ys) + 110   # la jugada entera alrededor también
        N = [n for n in N if not (n["y1"] >= LIST_TOP and lo <= n["y1"] <= hi)]
    full = lambda o, h=25: o["y2"] - o["y1"] >= h
    special = lambda o: RX_T.search(o["t"]) or RX_D.fullmatch(o["t"].strip(" ,")) or RX_SC.match(o["t"])
    ev = []
    for n in N:
        m = RX_T.search(n["t"])
        if not m or not full(n) or n["y1"] < LIST_TOP:
            continue  # jugada cortada: saldrá entera en otra pantalla
        line = [o for o in N if abs(o["y1"] - n["y1"]) < 8 or abs(o["y2"] - n["y2"]) < 8]
        dors = next((RX_D.search(o["t"]).group(1) for o in line if RX_D.search(o["t"]) and not RX_T.search(o["t"])), None)
        if dors is None and RX_D.search(n["t"]):   # en inglés dorsal y minuto van juntos: "#13, P4, 06:49"
            dors = RX_D.search(n["t"]).group(1)
        score = next((RX_SC.match(o["t"]).group(1) + "-" + RX_SC.match(o["t"]).group(2) for o in N
                      if RX_SC.match(o["t"]) and abs((o["y1"] + o["y2"]) / 2 - (n["y1"] + n["y2"]) / 2) < 12), "")
        left = n["cx"] < W / 2
        col = [o for o in N if (o["cx"] < W / 2) == left and 0 < n["y1"] - o["y1"] < 120
               and o["y1"] >= LIST_TOP and full(o) and not special(o)]
        col.sort(key=lambda o: o["y1"], reverse=True)
        if len(col) < 2:
            continue
        name, act = col[0]["t"], col[1]["t"]
        ev.append(dict(side=0 if left else 1, y=col[1]["y1"], act=act, name=name, num=dors or "",
                       per=int(m.group(1)), clock=int(m.group(2)) * 60 + int(m.group(3)), score=score))
    ends = any("INICIO DEL PARTIDO" in plain(n["t"]) or "START OF MATCH" in plain(n["t"]) for n in N)
    return dict(teams=teams[:2], scores=scores[:2], ev=ev, start=ends)


def stitch(screens):
    """Une las pantallas solapadas en una lista única, de la más reciente a la más antigua."""
    cum, prev, rows, gaps, hist = 0.0, None, [], 0, []
    for sc in screens:
        ev = sc["ev"]
        for e in ev:
            e["key"] = (e["side"], e["num"], e["per"], e["clock"], plain(e["act"]), plain(e["name"]), e.get("score", ""))
        if prev is not None and ev:
            # cada pareja de jugadas iguales propone un desplazamiento; gana el que más coincidencias explica
            # (la lista puede saltar hacia atrás cuando la app carga más jugadas, así que vale cualquier sentido)
            cand = [p["y"] - e["y"] for p in prev for e in ev if p["key"] == e["key"]]
            best, votes = None, 0
            for c in cand:
                v = sum(1 for x in cand if abs(x - c) <= 6)
                if v > votes or (v == votes and best is not None and c < best):
                    best, votes = c, v
            if best is not None:
                dy = median(x for x in cand if abs(x - best) <= 6)
                hist.append(dy)
                cum += dy
            else:
                gaps += 1
                cum += (median(hist) if hist else 600) + 150
        for e in ev:
            rows.append(dict(e, ay=e["y"] + cum))
        if ev:
            prev = ev
    rows.sort(key=lambda e: e["ay"])
    groups = []
    for e in rows:
        g = next((g for g in groups[-6:] if g[0]["key"] == e["key"] and abs(median(x["ay"] for x in g) - e["ay"]) < 40), None)
        if g:
            g.append(e)
        else:
            groups.append([e])
    out = [dict(g[0], ay=median(x["ay"] for x in g), seen=len(g)) for g in groups]
    out.sort(key=lambda e: e["ay"])
    return out, gaps


def team_id(name, liga):
    k = lambda s: re.sub(r"[^A-Z0-9]", "", plain(s))
    n = k(name)
    for i, t in enumerate(liga["teams"]):
        if n in (k(t[0]), k(t[1])):
            return i
    for i, t in enumerate(liga["teams"]):
        if k(t[0]) and (k(t[0]) in n or n in k(t[1])):
            return i
    return None


def game_index(home, away, liga):
    th, ta = team_id(home, liga), team_id(away, liga)
    return next((i for i, g in enumerate(liga["games"]) if g[2] == th and g[3] == ta), None)


def load_for_web(liga):
    """Jugadas de cada partido en formato compacto para la web: {índice del partido: [[cuarto, segundos que quedan, lado, jugador, código], ...]}.
    lado: 0 local, 1 visitante. jugador: índice en liga["players"], o "#dorsal" si no está entre los jugadores del Excel."""
    out, okd = {}, {}
    for f in sorted(glob.glob(os.path.join(OUTD, "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        gi = game_index(d["home"], d["away"], liga)
        if gi is None:
            continue
        g = liga["games"][gi]
        who = {}
        for r in liga["pg"]:
            if r[0] == gi:
                who[(0 if liga["players"][r[1]][1] == g[2] else 1, str(r[2]))] = r[1]
        out[str(gi)] = [[e[0], e[1], e[2], who.get((e[2], str(e[3])), "#" + str(e[3])), e[4]] for e in d["ev"] if e[4] != "?"]
        okd[str(gi)] = bool(d.get("ok"))
    return out, okd


def tally(events):
    st = defaultdict(Counter)
    for e in events:
        st[(e["side"], e["num"])][e["code"]] += 1
    return st


def process_folder(folder, liga):
    files = sorted(glob.glob(os.path.join(folder, "*.xml")))
    screens = [parse_screen(f) for f in files]
    screens = [s for s in screens if s["ev"]]
    if not screens:
        return None, f"{os.path.basename(folder)}: no hay jugadas en las pantallas."
    teams = Counter(tuple(s["teams"]) for s in screens if len(s["teams"]) == 2).most_common(1)
    if not teams:
        return None, f"{os.path.basename(folder)}: no se leen los equipos de la cabecera."
    home, away = teams[0][0]
    # solo las pantallas de este partido (por si se coló otra pantalla de la app o un anuncio)
    screens = [s for s in screens if tuple(s["teams"]) == (home, away)]
    scores = Counter(tuple(s["scores"]) for s in screens if len(s["scores"]) == 2).most_common(1)
    events, gaps = stitch(screens)
    for e in events:
        e["code"] = classify(e["act"])
    events.reverse()  # de la más antigua a la más reciente
    rep = [f"{home} - {away}: {len(files)} pantallas, {len(events)} jugadas"]
    if gaps:
        rep.append(f"  AVISO: {gaps} saltos sin solape entre pantallas; puede faltar alguna jugada.")
    unk = Counter(e["act"] for e in events if e["code"] == "?")
    if unk:
        rep.append("  Acciones sin reconocer (avísame para añadirlas): " + ", ".join(f"{a} ({n})" for a, n in unk.most_common()))
    # comparar con el Excel del partido
    gi = game_index(home, away, liga) if liga else None
    ok = None
    if gi is not None:
        C = liga["cols"]
        box = {}
        for r in liga["pg"]:
            if r[0] == gi:
                s = dict(zip(C, r[3:]))
                box[(0 if liga["players"][r[1]][1] == liga["games"][gi][2] else 1, r[2])] = s
        T = tally(events)
        pts = lambda c: 2 * c["2m"] + 3 * c["3m"] + c["1m"]
        bad, small, big = [], 0, 0
        for k, s in box.items():
            c = T.get(k, Counter())
            mine = dict(pts=pts(c), t2a=c["2m"] + c["2x"], t3a=c["3m"] + c["3x"], tla=c["1m"] + c["1x"], reb=c["rd"] + c["ro"], per=c["per"], fc=c["fc"])
            ref = dict(pts=s["pts"], t2a=s["t2a"], t3a=s["t3a"], tla=s["tla"], reb=s["rd"] + s["ro"], per=s["per"], fc=s["fc"])
            d = {x: (mine[x], ref[x]) for x in mine if mine[x] != ref[x]}
            if d:
                bad.append(f"#{k[1]} " + ", ".join(f"{x} {a} en vez de {b}" for x, (a, b) in d.items()))
                small += sum(1 for x, (a, b) in d.items() if x != "pts" and abs(a - b) == 1)
                big += sum(1 for x, (a, b) in d.items() if x == "pts" or abs(a - b) > 1)
        sh = sum(pts(c) for (sd, _), c in T.items() if sd == 0)
        sa = sum(pts(c) for (sd, _), c in T.items() if sd == 1)
        g = liga["games"][gi]
        rep.append(f"  Puntos leídos {sh}-{sa}; resultado del Excel {g[4]}-{g[5]}. Jugadores que cuadran: {len(box) - len(bad)} de {len(box)}.")
        for b in bad[:8]:
            rep.append("    · " + b)
        # correcto si cuadran todos los puntos y como mucho hay 2 detalles de una unidad (un rebote, una falta...):
        # esas pequeñas diferencias suelen venir de la propia app, no de la captura
        exact = not bad and sh == g[4] and sa == g[5]
        ok = sh == g[4] and sa == g[5] and big == 0 and small <= 2
        if ok and not exact:
            rep.append("  Se da por buena: los puntos cuadran y solo difiere algún detalle de una unidad.")
    else:
        rep.append("  AVISO: no encuentro este partido entre los Excel; se guarda igualmente.")
    data = dict(home=home, away=away, score=list(scores[0][0]) if scores else None, game=gi, ok=ok,
                source=os.path.basename(folder),
                ev=[[e["per"], e["clock"], e["side"], e["num"], e["code"], e["name"], e["act"]] for e in events if e["code"] not in ("award",)])
    return data, "\n".join(rep)


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", plain(s)).strip("_")


def main(liga=None, quiet=False):
    if liga is None:
        p = os.path.join(ROOT, "data", "liga.json")
        liga = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    os.makedirs(OUTD, exist_ok=True)
    folders = sorted(d for d in glob.glob(os.path.join(CAPT, "*")) if os.path.isdir(d))
    best = {}   # por partido: la última captura correcta o, si no hay ninguna, la última
    for f in folders:
        data, rep = process_folder(f, liga)
        if not data:
            continue
        k = f"{slug(data['home'])}__{slug(data['away'])}"
        if k not in best or data.get("ok") or not best[k][0].get("ok"):
            best[k] = (data, rep)
    for k, (data, rep) in best.items():
        with open(os.path.join(OUTD, k + ".json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    msgs = [rep for data, rep in best.values() if not data.get("ok") or "·" in rep or "AVISO" in rep]
    if best and not quiet:
        n_ok = sum(1 for d, _ in best.values() if d.get("ok"))
        print(f"Jugada a jugada: {len(best)} partidos capturados, {n_ok} cuadran con su Excel.")
        for m in msgs:
            print(m)
    return msgs


if __name__ == "__main__":
    main()
