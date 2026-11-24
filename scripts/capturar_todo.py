#!/usr/bin/env python3
"""
Captura de noche: entra en cada partido jugado de la liga, captura su jugada a jugada y pasa al siguiente.

Uso (desde la carpeta del repositorio, con BlueStacks abierto):
    1. En la app Afición FBM, deja abierta la pantalla con la lista de partidos de una jornada.
    2. Ejecuta:  caffeinate -dims python3 -u scripts/capturar_todo.py
       (caffeinate impide que el Mac se duerma mientras dura; deja el Mac enchufado y con la tapa abierta)

- Se salta los partidos que ya estén capturados y cuadren con su Excel; se puede parar (Ctrl+C) y relanzar.
- Si un partido no cuadra, lo repite una vez.
- Todo lo que hace queda en jugadas/noche_log.txt; si se pierde en alguna pantalla, la guarda en jugadas/errores/.
- Opcional: solo algunas jornadas:  python3 -u scripts/capturar_todo.py 8 7 6
"""
import glob, json, os, re, subprocess, sys, time, unicodedata, xml.etree.ElementTree as ET
from statistics import median

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import jugadas as J  # noqa: E402
import anuncio  # noqa: E402

os.chdir(ROOT)
LOG = os.path.join("jugadas", "noche_log.txt")
ERR = os.path.join("jugadas", "errores")
os.makedirs(ERR, exist_ok=True)


def log(*a):
    msg = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


# ---------------- adb ----------------
DEV = None


def sh(args, timeout=60):
    try:
        return subprocess.run(args, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, b"", b"timeout")


def ensure():
    global DEV
    if DEV and sh(["adb", "-s", DEV, "get-state"], 15).stdout.strip() == b"device":
        return True
    if sh(["adb", "start-server"], 30).returncode != 0:
        sh(["killall", "adb"]); time.sleep(1); sh(["adb", "start-server"], 30)
    def devs():
        out = sh(["adb", "devices"], 15).stdout.decode(errors="ignore").splitlines()[1:]
        return [l.split()[0] for l in out if l.strip().endswith("device")]
    d = devs()
    if not d:
        sh(["adb", "connect", "127.0.0.1:5555"], 15); time.sleep(1); d = devs()
    DEV = next((x for x in d if x.startswith("emulator-")), d[0] if d else None)
    return DEV is not None


def adb(*args, timeout=60):
    if not ensure():
        return subprocess.CompletedProcess(args, 1, b"", b"sin dispositivo")
    return sh(["adb", "-s", DEV] + [str(a) for a in args], timeout)


def tap(x, y):
    adb("shell", "input", "tap", int(x), int(y))


def back():
    adb("shell", "input", "keyevent", "4")


def swipe(x1, y1, x2, y2, ms=400):
    adb("shell", "input", "swipe", int(x1), int(y1), int(x2), int(y2), int(ms))


def dump_raw():
    for _ in range(6):
        out = adb("exec-out", "uiautomator", "dump", "/dev/tty", timeout=40).stdout.decode("utf-8", errors="ignore")
        out = re.sub(r"UI hierc*h*ary dumped to.*", "", out)
        if "</hierarchy>" in out:
            return out[out.find("<?xml") if "<?xml" in out else 0:]
        adb("shell", "rm", "-f", "/sdcard/fbm_nav.xml")   # nunca leer una pantalla vieja
        r = adb("shell", "uiautomator", "dump", "/sdcard/fbm_nav.xml", timeout=40)
        if b"dumped to" in (r.stdout + r.stderr):
            out = adb("exec-out", "cat", "/sdcard/fbm_nav.xml").stdout.decode("utf-8", errors="ignore")
            if "</hierarchy>" in out:
                return out
        time.sleep(1.5)
    return ""


def screen():
    raw = dump_raw()
    nodes = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return [], raw
    for n in root.iter("node"):
        b = list(map(int, re.findall(r"-?\d+", n.get("bounds", "[0,0][0,0]"))))
        if len(b) != 4:
            continue
        nodes.append(dict(t=(n.get("text") or "").strip(), d=(n.get("content-desc") or "").strip(),
                          x1=b[0], y1=b[1], x2=b[2], y2=b[3], cx=(b[0] + b[2]) / 2, cy=(b[1] + b[3]) / 2,
                          click=n.get("clickable") == "true", scroll=n.get("scrollable") == "true"))
    return nodes, raw


def save_err(raw, name):
    p = os.path.join(ERR, time.strftime("%Y%m%d_%H%M%S_") + re.sub(r"[^A-Za-z0-9]+", "_", name) + ".xml")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(raw)
    return p


# ---------------- liga y equipos ----------------
LIGA = json.load(open(os.path.join("data", "liga.json"), encoding="utf-8"))
key = lambda s: re.sub(r"[^A-Z0-9]", "", J.plain(s))
TEAMK = [(key(t[0]), key(t[1])) for t in LIGA["teams"]]


def team_of(text):
    n = key(text)
    if len(n) < 4:
        return None
    for i, (s, f) in enumerate(TEAMK):
        if n == f or n == s or (len(f) >= 6 and f in n):
            return i
    return None


def team_nodes(nodes):
    out = []
    for n in nodes:
        t = team_of(n["t"]) if n["t"] else None
        if t is not None:
            out.append((t, n))
    return out


def find_game(nodes, h, a):
    """Busca en pantalla la fila del partido h-a; devuelve el punto donde tocar o None."""
    tn = team_nodes(nodes)
    hs = [n for t, n in tn if t == h and n["y1"] > 300]
    as_ = [n for t, n in tn if t == a and n["y1"] > 300]
    best = None
    for x in hs:
        for y in as_:
            d = abs(x["cy"] - y["cy"]) + abs(x["cx"] - y["cx"]) / 3
            if d < 260 and (best is None or d < best[0]):
                best = (d, x, y)
    if not best:
        return None
    _, x, y = best
    return ((min(x["x1"], y["x1"]) + max(x["x2"], y["x2"])) / 2, (x["cy"] + y["cy"]) / 2)


def in_game(nodes, h, a):
    head = [n for n in nodes if 230 < n["y1"] < 450]
    ids = {team_of(n["t"]) for n in head if n["t"]}
    return h in ids and a in ids


def has_live(nodes):
    """Lista de jugadas a la vista (o los avisos de final/inicio, que a veces se repiten varias veces arriba)."""
    banners = ("FINAL DEL PARTIDO", "FINAL DEL PERIODO", "INICIO DEL PERIODO", "END OF MATCH", "END OF PERIOD", "START OF PERIOD")
    return any(J.RX_T.search(n["t"]) or any(b in J.plain(n["t"]) for b in banners) for n in nodes)


def tab_live(nodes):
    return next((n for n in nodes if J.plain(n["t"]) in ("EN VIVO", "LIVE", "EN DIRECTO")), None)


def on_list(nodes):
    """Lista de partidos de la app (Equipo > PARTIDOS > Por jornadas): no tiene la pestaña EN VIVO."""
    if tab_live(nodes):
        return False
    txt = {J.plain(n["t"]) for n in nodes if n["t"]}
    return (bool(jornada_labels(nodes)) or bool(txt & {"TERMINADO", "FINISHED", "POR JORNADAS", "BY ROUNDS"})
            or len(team_nodes(nodes)) >= 2)


def jornada_labels(nodes):
    out = []
    for n in nodes:
        m = re.search(r"\b(?:JORNADA|ROUND|J)\.?\s*(\d{1,2})\b", J.plain(n["t"] or n["d"]))
        if m:
            out.append((int(m.group(1)), n))
    return out


# ---------------- anuncios ----------------
def clear_ads(max_wait=30):
    """Si hay un anuncio delante (ni lista ni partido), lo cierra. Devuelve la pantalla ya limpia."""
    t0, backed, seen, scrolls = time.time(), False, False, 0
    while True:
        nodes, raw = screen()
        if tab_live(nodes) or on_list(nodes):
            if seen:
                log("  Anuncio cerrado.")
            return nodes, raw
        seen = True
        p = anuncio.close_point(raw)
        if p:
            tap(*p); time.sleep(2.5)
            continue
        if time.time() - t0 > 6 and scrolls < 5:
            swipe(540, 1500, 540, 600, 400); scrolls += 1; time.sleep(1.5)   # algunos anuncios tienen la X abajo
            continue
        if time.time() - t0 > 12 and not backed:
            back(); backed = True; time.sleep(2.5)   # sin botón visible: atrás una vez
            continue
        if time.time() - t0 > max_wait:
            log("  Hay algo delante que no sé cerrar. Pantalla guardada en", save_err(raw, "anuncio"))
            return nodes, raw
        time.sleep(3)   # cuenta atrás del anuncio


# ---------------- navegación ----------------
def back_to_list():
    """Vuelve atrás solo mientras esté dentro de un partido (para no salirse nunca de la lista)."""
    for _ in range(4):
        nodes, raw = clear_ads()
        if on_list(nodes):
            return nodes
        if tab_live(nodes) or any(J.plain(n["t"]) in ("MAPA DE TIRO", "ESTADISTICAS", "SHOT CHART", "STATISTICS", "COMPARATIVA", "COMPARISON") for n in nodes):
            back(); time.sleep(2.5)
            continue
        log("  Pantalla desconocida; la guardo y pulso atrás una vez:", save_err(raw, "pantalla_desconocida"))
        back(); time.sleep(2.5)
    nodes, raw = screen()
    if not on_list(nodes):
        log("  No consigo volver a la lista de partidos. Pantalla guardada en", save_err(raw, "no_vuelvo_a_la_lista"))
    return nodes


def scroll_page_top():
    for _ in range(6):
        nodes, _ = clear_ads()
        if jornada_labels(nodes):
            return nodes
        swipe(540, 700, 540, 1600, 300); time.sleep(1.2)
    return screen()[0]


def goto_jornada(j, games_j):
    """Pulsa la pestaña JORNADA j (desliza la fila de jornadas si no se ve)."""
    for attempt in range(12):
        nodes = scroll_page_top()
        labels = jornada_labels(nodes)
        if not labels:
            break
        exact = [n for num, n in labels if num == j]
        if exact:
            n = exact[0]
            x = min(max(n["cx"], 60), 1020)
            tap(x, n["cy"]); time.sleep(3)
            return True
        nums = [num for num, _ in labels]
        yrow = median(n["cy"] for _, n in labels)
        if min(nums) > j:
            swipe(200, yrow, 900, yrow, 350)   # ver jornadas anteriores
        else:
            swipe(900, yrow, 200, yrow, 350)   # ver jornadas posteriores
        time.sleep(1.5)
    nodes, raw = screen()
    log(f"  No encuentro la pestaña de la jornada {j}. Pantalla guardada en", save_err(raw, f"jornada_{j}"))
    return False


def open_game(g):
    """Busca la tarjeta del partido bajando por la lista de la jornada, entra y abre EN VIVO."""
    h, a = g[2], g[3]
    for attempt in range(18):
        nodes, raw = clear_ads()
        pt = find_game(nodes, h, a)
        if pt:
            tap(*pt); time.sleep(4)
            nodes, raw = clear_ads()
            t = tab_live(nodes)
            if t and not has_live(nodes):
                tap(t["cx"], t["cy"]); time.sleep(3)
                nodes, raw = screen()
            if in_game(nodes, h, a) and has_live(nodes):
                return True
            if tab_live(nodes):
                log("  He entrado pero no veo el jugada a jugada. Pantalla guardada en", save_err(raw, "sin_en_vivo"))
                back_to_list()
                return False
            back_to_list()
            continue
        # no está a la vista: bajar por la lista; si llega abajo, volver arriba
        if attempt < 9:
            swipe(540, 1550, 540, 1050, 450)
        else:
            swipe(540, 1050, 540, 1550, 450)
        time.sleep(1.3)
    nodes, raw = screen()
    save_err(raw, f"no_encuentro_{h}_{a}")
    return False


def capture():
    try:
        p = subprocess.run(["bash", "scripts/capturar_partido.sh"], capture_output=True, timeout=45 * 60)
        out = p.stdout.decode("utf-8", errors="ignore")
    except subprocess.TimeoutExpired:
        return None, "la captura ha tardado demasiado"
    m = re.search(r"Hecho: (\d+) pantallas en (\S+)", out)
    if not m:
        return None, out.strip().splitlines()[-1] if out.strip() else "sin salida"
    return m.group(2), f"{m.group(1)} pantallas"


def done_games():
    ok = set()
    for f in glob.glob(os.path.join("data", "jugadas", "*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        gi = J.game_index(d["home"], d["away"], LIGA)
        if gi is not None and d.get("ok"):
            ok.add(gi)
    return ok


def main():
    only = {int(x) for x in sys.argv[1:] if x.isdigit()}
    J.main(liga=LIGA, quiet=True)  # procesa capturas anteriores
    done = done_games()
    games = [(i, g) for i, g in enumerate(LIGA["games"]) if (not only or g[0] in only)]
    pend = [(i, g) for i, g in games if i not in done]
    log(f"=== Captura de noche: {len(pend)} partidos pendientes de {len(games)} ({len(done)} ya capturados y correctos) ===")
    if not ensure():
        log("No encuentro BlueStacks. ¿Está abierto y con Android Debug Bridge activado?")
        return
    nodes, raw = clear_ads()
    save_err(raw, "pantalla_inicial")
    if not team_nodes(nodes):
        log("No veo equipos en la pantalla. Deja abierta en la app la lista de partidos de una jornada y vuelve a lanzarlo.")
        return
    stats = dict(ok=0, dif=0, fallo=0)
    for j in sorted({g[0] for _, g in pend}, reverse=True):
        gj = [(i, g) for i, g in pend if g[0] == j]
        log(f"--- Jornada {j}: {len(gj)} partidos ---")
        back_to_list()
        if not goto_jornada(j, [g for _, g in gj]):
            stats["fallo"] += len(gj)
            continue
        for i, g in gj:
            name = f"{LIGA['teams'][g[2]][0]} - {LIGA['teams'][g[3]][0]}"
            result = None
            for intento in (1, 2):
                back_to_list()
                if not open_game(g):
                    if not goto_jornada(j, [g]) or not open_game(g):
                        log(f"  {name}: no lo encuentro en la lista.")
                        break
                t0 = time.time()
                folder, info = capture()
                back_to_list()
                if not folder:
                    log(f"  {name}: la captura ha fallado ({info}).")
                    continue
                data, rep = J.process_folder(folder, LIGA)
                mins = (time.time() - t0) / 60
                result = data.get("ok") if data else False
                log(f"  {name}: {info} en {mins:.1f} min. " + ("Cuadra con el Excel." if result else "NO cuadra del todo:"))
                if not result:
                    for line in rep.splitlines()[1:]:
                        log("    " + line.strip())
                if result:
                    break
                if intento == 1:
                    log("  Lo repito una vez.")
                    goto_jornada(j, [g])
            stats["ok" if result else ("dif" if result is False else "fallo")] += 1
    J.main(liga=LIGA, quiet=True)
    log(f"=== Fin: {stats['ok']} partidos correctos, {stats['dif']} con alguna diferencia, {stats['fallo']} sin capturar ===")
    log("Mañana dile a Claude que mire jugadas/noche_log.txt")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Parado a mano. Al relanzarlo seguirá por donde iba.")
