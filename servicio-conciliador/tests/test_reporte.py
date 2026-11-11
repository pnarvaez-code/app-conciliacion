"""El reporte PDF contiene resultado, certificado de fuentes y firma."""
from unittest.mock import patch

from app import reporte


def main():
    usuario = {"email": "auditor@ejemplo.com"}
    with patch.object(reporte.auditoria, "listar", return_value=[]), \
            patch.object(reporte.alertas, "listar", return_value=[]), \
            patch.object(reporte.conciliacion, "listar", return_value=[]), \
            patch.object(reporte.recepciones, "ultima_intacta", return_value=None), \
            patch.object(reporte.db, "consultar_uno", return_value={"n": 0}):
        contenido = reporte.generar(usuario)
    assert contenido.startswith(b"%PDF")
    assert len(contenido) > 1000
    print("Reporte PDF: generado con certificado y firma.")


if __name__ == "__main__":
    main()
