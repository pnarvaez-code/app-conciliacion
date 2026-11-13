"""Regresión: un fallo de sellado revierte el cierre completo."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import cierre


class CursorFalso:
    def __init__(self):
        self.resultado = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sentencia, parametros=()):
        if "WHERE estado = 'pendiente'" in sentencia:
            self.resultado = [{"id": 1, "fecha": "2026-11-13", "monto": 1000,
                               "referencia": "FV-1", "descripcion": "VENTA"}]
        elif "COUNT(*) AS total FROM lotes" in sentencia:
            self.resultado = {"total": 0}
        elif "COUNT(*) AS total FROM bloques" in sentencia:
            self.resultado = {"total": 0}
        elif "INSERT INTO lotes" in sentencia:
            self.resultado = {"id": 1, "codigo": "V-2026-11-13-01"}
        else:
            self.resultado = None

    def fetchone(self):
        return self.resultado

    def fetchall(self):
        return self.resultado


class ConexionFalsa:
    def __init__(self):
        self.cursor_falso = CursorFalso()
        self.confirmada = False
        self.revertida = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cursor_falso

    def commit(self):
        self.confirmada = True

    def rollback(self):
        self.revertida = True


def main():
    conexion = ConexionFalsa()
    with TemporaryDirectory() as temporal:
        ruta = Path(temporal) / "lote.csv"
        ruta.write_text("contenido", encoding="utf-8")
        archivo = {"id": 1, "ruta": str(ruta)}
        with patch.object(cierre.db, "conectar", return_value=conexion), \
             patch.object(cierre.archivos, "guardar", return_value=archivo), \
             patch.object(cierre.cadena, "sellar_lote",
                          side_effect=RuntimeError("fallo simulado")):
            try:
                cierre.cerrar_dia(1)
            except RuntimeError:
                pass
            else:
                raise AssertionError("el fallo del sello debía propagarse")
        assert conexion.revertida and not conexion.confirmada
        assert not ruta.exists(), "el archivo huérfano debe eliminarse"
    print("Fallo de sellado: cierre revertido sin archivo huérfano.")


if __name__ == "__main__":
    main()
