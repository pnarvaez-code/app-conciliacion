"""Una falla al guardar el detalle no puede confirmar una conciliación parcial."""
from unittest.mock import patch

from app import conciliacion


class CursorFalso:
    def __init__(self):
        self.resultado = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, consulta, parametros=()):
        if consulta.startswith("SELECT id FROM conciliaciones"):
            self.resultado = None
        elif consulta.startswith("INSERT INTO conciliaciones"):
            self.resultado = {"id": 91, "conciliados": 1,
                              "total_empresa": 1, "porcentaje": 100}
        elif consulta.startswith("INSERT INTO conciliacion_pares"):
            raise RuntimeError("fallo simulado al guardar el par")

    def fetchone(self):
        resultado, self.resultado = self.resultado, None
        return resultado


class ConexionFalsa:
    def __init__(self):
        self.cursor_falso = CursorFalso()
        self.confirmada = False
        self.error_al_salir = None

    def __enter__(self):
        return self

    def __exit__(self, tipo, *_):
        self.error_al_salir = tipo
        return False

    def cursor(self):
        return self.cursor_falso

    def commit(self):
        self.confirmada = True


def main():
    empresa = {"id": 11, "archivo": "empresa.csv"}
    banco = {"id": 22, "archivo": "banco.csv"}
    movimiento = {"fecha": "2026-09-01", "monto": 100,
                  "referencia": "R-1", "descripcion": "VENTA"}
    conexion = ConexionFalsa()
    with patch.object(conciliacion.recepciones, "ultima_intacta",
                      side_effect=[empresa, banco]), \
            patch.object(conciliacion, "conciliacion_existente",
                         return_value=None), \
            patch.object(conciliacion, "_contenido", return_value="contenido"), \
            patch.object(conciliacion.carga, "leer",
                         side_effect=[([movimiento], "csv"),
                                      ([movimiento], "csv")]), \
            patch.object(conciliacion.db, "conectar", return_value=conexion):
        try:
            conciliacion.ejecutar(usuario_id=1)
        except RuntimeError as error:
            assert "fallo simulado" in str(error)
        else:
            raise AssertionError("la falla simulada debió propagarse")
    assert not conexion.confirmada
    assert conexion.error_al_salir is RuntimeError
    print("Atomicidad: una falla de detalle no confirma la operación parcial.")


if __name__ == "__main__":
    main()
