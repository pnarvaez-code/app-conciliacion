"""La misma pareja de recepciones no se puede conciliar dos veces."""
from unittest.mock import patch

from app import conciliacion


def main():
    empresa = {"id": 11}
    banco = {"id": 22}
    with patch.object(conciliacion.recepciones, "ultima_intacta",
                      side_effect=[empresa, banco]), \
            patch.object(conciliacion, "conciliacion_existente",
                         return_value={"id": 7}):
        try:
            conciliacion.ejecutar(usuario_id=1)
        except ValueError as error:
            assert "ya fueron conciliados" in str(error)
            assert "#7" in str(error)
        else:
            raise AssertionError("la pareja repetida debio rechazarse")
    print("Conciliacion repetida: rechazada correctamente.")


if __name__ == "__main__":
    main()
