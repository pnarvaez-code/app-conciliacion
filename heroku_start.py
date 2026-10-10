"""Arranque de uno de los servicios del monorepo en Heroku."""
import os
import sys
from pathlib import Path

SERVICIOS = {
    "pyme": "servicio-pyme",
    "banco": "servicio-banco",
    "conciliador": "servicio-conciliador",
}


def main():
    servicio = os.environ.get("SERVICE", "").strip().lower()
    if servicio not in SERVICIOS:
        raise SystemExit(
            "Configura SERVICE con uno de estos valores: pyme, banco o conciliador."
        )

    raiz = Path(__file__).resolve().parent
    directorio = raiz / SERVICIOS[servicio]
    os.chdir(directorio)
    sys.path.insert(0, str(directorio))

    # Heroku solo permite escribir en el espacio temporal del dyno.
    os.environ.setdefault("DIR_DATOS", "/tmp/datos")
    os.makedirs(os.path.join(os.environ["DIR_DATOS"], "archivos"), exist_ok=True)

    from app.inicio import main as inicializar

    inicializar()

    puerto = os.environ.get("PORT")
    if not puerto:
        raise SystemExit("Heroku no asigno PORT al proceso web.")

    os.execv(
        sys.executable,
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", puerto],
    )


if __name__ == "__main__":
    main()
