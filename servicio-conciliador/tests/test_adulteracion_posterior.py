"""No reutilizar recepciones antiguas ni confiar en una validación obsoleta."""
from unittest.mock import patch
from app import conciliacion, recepciones
from app.nucleo import sellos


def main():
    with patch.object(recepciones.db, "consultar_uno",
                      return_value={"estado_integridad": "alterado"}) as consulta:
        assert recepciones.ultima_intacta("EMPRESA") is None
        assert "estado_integridad = 'intacto'" not in consulta.call_args.args[0]
    original = b"fecha;monto;referencia;descripcion\n2026-11-18;100;R-1;VENTA\n"
    cambiado = original.replace(b";100;", b";999;")
    archivo = {"id": 1, "origen": "EMPRESA", "archivo": "prueba.csv",
               "sha256": sellos.huella_archivo(original)}
    # Incluso si la comprobación contra la cadena devuelve intacto, cambiar
    # los bytes desde la recepción original debe bloquear el cruce.
    with patch.object(conciliacion.archivos, "obtener_contenido", return_value=cambiado), \
         patch.object(recepciones, "_verificar", return_value=("intacto", "V-1", "sello")), \
         patch.object(conciliacion.db, "ejecutar") as actualizar, \
         patch.object(conciliacion.alertas, "crear") as alerta, \
         patch.object(conciliacion.auditoria, "registrar") as auditoria:
        try:
            conciliacion._contenido(archivo, 5, "127.0.0.1")
        except ValueError as error:
            assert "bloqueada" in str(error)
        else:
            raise AssertionError("Se permitió contenido modificado")
        assert actualizar.call_args.args[1][0] == "alterado"
        alerta.assert_called_once()
        auditoria.assert_called_once()
    print("Adulteración posterior: bloqueo, alerta y auditoría correctos.")


if __name__ == "__main__":
    main()
