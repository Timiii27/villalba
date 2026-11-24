#!/bin/bash
# Captura el jugada a jugada de un partido desde la app Afición FBM abierta en BlueStacks.
#
# Uso (desde la carpeta del repositorio):
#   1. En BlueStacks, entra en el partido y abre la pestaña EN VIVO (la lista empieza arriba).
#   2. Ejecuta:  bash scripts/capturar_partido.sh
#   3. No toques BlueStacks hasta que termine (unos minutos por partido).
#
# Deja las pantallas leídas en jugadas/capturas/<fecha_hora>/. Después, ejecuta
#   python3 scripts/actualizar_datos.py
# y las jugadas se incorporan a la web.

set -u
cd "$(dirname "$0")/.." || exit 1

TS=$(date +%Y%m%d_%H%M%S)
OUT="jugadas/capturas/$TS"
LOG="jugadas/ultimo_log.txt"
mkdir -p "$OUT"
echo "Captura $TS" > "$LOG"

DEV=""
# Busca BlueStacks. "emulator-5554" aguanta aunque adb se reinicie; 127.0.0.1:5555 hay que reconectarlo.
find_dev() {
  if ! adb start-server >>"$LOG" 2>&1; then
    killall adb >/dev/null 2>&1; sleep 1
    adb start-server >>"$LOG" 2>&1
  fi
  local list
  list=$(adb devices 2>>"$LOG" | awk 'NR>1 && $2=="device" {print $1}')
  if [ -z "$list" ]; then
    adb connect 127.0.0.1:5555 >>"$LOG" 2>&1; sleep 1
    list=$(adb devices 2>>"$LOG" | awk 'NR>1 && $2=="device" {print $1}')
  fi
  DEV=$(echo "$list" | grep -m1 '^emulator-' || true)
  [ -z "$DEV" ] && DEV=$(echo "$list" | head -n1)
  [ -n "$DEV" ]
}
ok_dev() { [ -n "$DEV" ] && [ "$(adb -s "$DEV" get-state 2>/dev/null)" = "device" ]; }
ensure() { ok_dev || find_dev; }
A() { ensure && adb -s "$DEV" "$@"; }

if ! find_dev; then
  echo "No encuentro BlueStacks. Comprueba que está abierto y que 'Android Debug Bridge' está activado en Ajustes > Avanzado."
  exit 1
fi
echo "Usando $DEV" >> "$LOG"

dump() {  # $1 = archivo de salida. Reintenta: Android no lee la pantalla si algo se está moviendo
  local n
  for n in 1 2 3 4 5 6; do
    A exec-out uiautomator dump /dev/tty 2>>"$LOG" | sed 's/UI hierc*h*ary dumped to.*//' > "$1"
    grep -q '</hierarchy>' "$1" && return 0
    # plan B: borrar antes el archivo del móvil para no recoger nunca una pantalla vieja
    A shell rm -f /sdcard/fbm_tmp.xml >>"$LOG" 2>&1
    if A shell uiautomator dump /sdcard/fbm_tmp.xml 2>&1 | tee -a "$LOG" | grep -q "dumped to"; then
      A pull /sdcard/fbm_tmp.xml "$1" >>"$LOG" 2>&1
      grep -q '</hierarchy>' "$1" && return 0
    fi
    sleep 1
  done
  rm -f "$1"
  return 1
}
fingerprint() { grep -o 'text="[^"]*"' "$1" | cksum; }
# Si la pantalla no tiene jugadas, puede ser un anuncio: intenta cerrarlo (botón de cerrar o, si no hay, atrás una vez)
# Hay jugadas, o los avisos de inicio/final (algunos partidos empiezan con el "FINAL DEL PARTIDO" repetido varias veces)
is_live() { grep -q 'P[1-9], [0-9][0-9]:[0-9][0-9]\|FINAL DEL PARTIDO\|FINAL DEL PERIODO\|INICIO DEL PERIODO\|END OF MATCH\|END OF PERIOD\|START OF PERIOD' "$1"; }
close_ad() {  # $1 = pantalla leída
  local p; p=$(python3 scripts/anuncio.py "$1" 2>/dev/null)
  if [ -n "$p" ]; then
    echo "Anuncio: toco $p" >> "$LOG"; A shell input tap $p >>"$LOG" 2>&1; sleep 2.5; return 0
  fi
  if ! grep -q 'text="EN VIVO"\|text="LIVE"' "$1"; then
    # algunos anuncios tienen la X abajo: bajar buscándola antes de pulsar atrás
    local k t="$OUT/anuncio_tmp.xml"
    sleep 4
    for k in 1 2 3 4 5; do
      A shell input swipe 540 1500 540 600 400 >>"$LOG" 2>&1; sleep 1.5
      dump "$t" || continue
      p=$(python3 scripts/anuncio.py "$t" 2>/dev/null)
      if [ -n "$p" ]; then echo "Anuncio (abajo): toco $p" >> "$LOG"; A shell input tap $p >>"$LOG" 2>&1; rm -f "$t"; sleep 2.5; return 0; fi
      grep -q 'text="EN VIVO"\|text="LIVE"' "$t" && { rm -f "$t"; return 0; }
    done
    rm -f "$t"
    echo "Pantalla sin jugadas ni pestaña EN VIVO: pulso atrás" >> "$LOG"; sleep 1
    A shell input keyevent 4 >>"$LOG" 2>&1; sleep 2.5; return 0
  fi
  sleep 3; return 1
}
dump_live() {  # como dump, pero quitando anuncios que tapen la lista
  local k
  for k in 1 2 3 4; do
    dump "$1" || return 1
    is_live "$1" && return 0
    close_ad "$1"
  done
  return 0
}

sleep 1
if ! dump_live "$OUT/000.xml" || ! is_live "$OUT/000.xml"; then
  mkdir -p jugadas/errores
  cp "$OUT/000.xml" "jugadas/errores/$TS.xml" 2>/dev/null
  rm -rf "$OUT"
  echo "No veo jugadas en la pantalla."
  echo "Entra otra vez en el partido, en la pestaña EN VIVO, y vuelve a ejecutar el script."
  echo "Detalle en $LOG"
  exit 1
fi

# Bajar poco a poco leyendo cada pantalla, hasta que la lista deje de moverse
prev=$(fingerprint "$OUT/000.xml"); last="$OUT/000.xml"
same=0; fails=0; i=1; MODE=motion
while [ $i -le 500 ]; do
  if [ "$MODE" = motion ]; then
    # Arrastre lento con pausa antes de soltar: así la lista no sigue deslizando sola
    A shell "input motionevent DOWN 540 1650; input motionevent MOVE 540 1500; input motionevent MOVE 540 1350; input motionevent MOVE 540 1200; input motionevent MOVE 540 1050; sleep 0.25; input motionevent UP 540 1050" >>"$LOG" 2>&1
  else
    A shell input swipe 540 1650 540 1050 1500 >>"$LOG" 2>&1
  fi
  f=$(printf "%s/%03d.xml" "$OUT" "$i")
  if ! dump_live "$f"; then
    fails=$((fails+1))
    if [ $fails -ge 4 ]; then
      echo; echo "Se ha perdido la conexión con BlueStacks varias veces seguidas. Lo leído hasta ahora queda guardado; vuelve a capturar este partido."
      break
    fi
    continue
  fi
  fails=0
  cur=$(fingerprint "$f")
  if [ "$cur" = "$prev" ]; then
    same=$((same+1))
    rm -f "$f"
    if [ $i -eq 1 ] && [ "$MODE" = motion ]; then MODE=swipe; same=0; continue; fi
    # ¿Final de verdad? Solo si ya se ve el inicio del partido; si no, la app está cargando más jugadas
    if grep -q 'INICIO DEL PARTIDO\|START OF MATCH' "$last"; then
      [ $same -ge 2 ] && break
    else
      [ $same -ge 8 ] && { echo; echo "La lista no avanza y no veo el inicio del partido: puede que falte el principio."; break; }
      sleep $same
    fi
  else
    same=0
    prev="$cur"
    last="$f"
    i=$((i+1))
  fi
  printf "\rPantallas leídas: %d" "$i"
done
echo
echo "Hecho: $i pantallas en $OUT"
