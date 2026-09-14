#!/bin/bash
# Read-mostly experiment: can root build a cgroup jail that uid 1000 cannot escape?
# Everything it creates is removed at the end.
set -uo pipefail
JAIL=/sys/fs/cgroup/nightguard-experiment
OWNER=${SUDO_USER:-$(id -un)}

cleanup() {
    [[ -d $JAIL ]] && rmdir "$JAIL" 2>/dev/null
    echo "-- limpieza: $( [[ -d $JAIL ]] && echo 'QUEDA el cgroup' || echo 'cgroup eliminado' )"
}
trap cleanup EXIT

echo "== 1. crear la jaula, propiedad de root, fuera del subarbol delegado =="
mkdir -p "$JAIL" || { echo "   FALLO al crear"; exit 1; }
ls -ld "$JAIL"
ls -l "$JAIL/cgroup.procs" "$JAIL/cgroup.kill" 2>/dev/null

echo
echo "== 2. lanzar un proceso inofensivo COMO EL USUARIO =="
runuser -u "$OWNER" -- sleep 300 &
VICTIM=$!
sleep 0.5
echo "   pid $VICTIM, cgroup original: $(cat /proc/$VICTIM/cgroup 2>/dev/null)"

echo
echo "== 3. root lo mete en la jaula =="
if echo "$VICTIM" > "$JAIL/cgroup.procs" 2>/dev/null; then
    echo "   movido. cgroup ahora: $(cat /proc/$VICTIM/cgroup 2>/dev/null)"
else
    echo "   FALLO al mover"; kill $VICTIM 2>/dev/null; exit 1
fi

echo
echo "== 4. ¿puede el usuario sacarlo? (esta es la pregunta) =="
runuser -u "$OWNER" -- bash -c "echo $VICTIM > /sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/cgroup.procs" 2>&1 \
  | sed 's/^/   /' || true
echo "   cgroup tras el intento: $(cat /proc/$VICTIM/cgroup 2>/dev/null)"
runuser -u "$OWNER" -- bash -c "echo 0 > $JAIL/cgroup.freeze" 2>&1 | sed 's/^/   descongelar: /' || true
runuser -u "$OWNER" -- bash -c "rmdir $JAIL" 2>&1 | sed 's/^/   borrar jaula: /' || true

echo
echo "== 5. cgroup.kill: matar el arbol entero de una =="
if echo 1 > "$JAIL/cgroup.kill" 2>/dev/null; then
    sleep 0.5
    if kill -0 $VICTIM 2>/dev/null; then echo "   el proceso SIGUE VIVO"; else echo "   proceso muerto por cgroup.kill"; fi
else
    echo "   cgroup.kill no disponible"
fi
kill -9 $VICTIM 2>/dev/null
wait $VICTIM 2>/dev/null
