"""Arranque de uno de los servicios del monorepo en Heroku."""
import os
import sys
from pathlib import Path

SERVICIOS = {
    "pyme": "servicio-pyme",
    "servicio-pyme": "servicio-pyme",
    "banco": "servicio-banco",
    "servicio-banco": "servicio-banco",
    "conciliador": "servicio-conciliador",
    "servicio-conciliador": "servicio-conciliador",
}


def main():
    servicio = (os.environ.get("SERVICIO")
                or os.environ.get("APP_SERVICE")
                or os.environ.get("SERVICE", "")).strip().lower()
    if servicio not in SERVICIOS:
        raise SystemExit(
            "Configura SERVICIO, APP_SERVICE o SERVICE con pyme, banco, "
            "conciliador o el nombre servicio-* correspondiente."
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

    puerto = os.environ.get("PORT", "8000")

    os.execv(
        sys.executable,
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", puerto,
         "--proxy-headers", "--forwarded-allow-ips", "*"],
    )


if __name__ == "__main__":
    main()
