# -*- coding: utf-8 -*-
"""app/recepciones.py

Recepcion y verificacion de los archivos que llegan de cada parte.

Al recibir un archivo se calcula su huella y se compara con los sellos
que el emisor dejo en la cadena (copia local del conciliador):

  * coincide con el sello de un lote: INTACTO (se identifica el lote);
  * no coincide con ningun sello del origen: ALTERADO, y se compara
    movimiento por movimiento para señalar la posicion exacta que difiere;
  * no hay sellos de ese origen en la copia: SIN SELLO (no se puede
    afirmar nada hasta sincronizar la cadena).

Cada recepcion queda auditada con el usuario que la subio y genera alerta
cuando no esta intacta.
"""
from app import alertas, archivos, auditoria, cadena, carga, db, seguridad
from app.nucleo import sellos


def recibir(origen, nombre, contenido, usuario_id, ip=None):
    """Guarda el archivo recibido, lo verifica contra los sellos y devuelve
    la fila de la recepcion (con su estado de integridad)."""
    origen = origen.upper()
    if origen not in ("EMPRESA", "BANCO"):
        raise ValueError("el origen debe ser EMPRESA o BANCO")
    archivo = archivos.guardar(nombre, contenido, usuario_id)
    estado, lote_codigo, detalle = _verificar(origen, archivo, contenido)

    recepcion = db.ejecutar(
        "INSERT INTO recepciones (archivo_id, origen, lote_codigo,"
        " estado_integridad, detalle, verificado_en, verificado_por)"
        " VALUES (%s, %s, %s, %s, %s, now(), %s) RETURNING *",
        (archivo["id"], origen, lote_codigo, estado, detalle, usuario_id))

    auditoria.registrar(usuario_id, "recepcion_archivo", "recepciones",
                        recepcion["id"],
                        {"origen": origen, "archivo": nombre, "estado": estado,
                         "lote": lote_codigo}, ip)
    if estado == "alterado":
        alertas.crear("integridad", "alta",
                      "Archivo %s de %s no coincide con su sello"
                      % (nombre, origen),
                      detalle, referencia=lote_codigo or nombre,
                      usuario_id=usuario_id)
    elif estado == "sin_sello":
        alertas.crear("integridad", "media",
                      "Archivo %s de %s sin sello disponible"
                      % (nombre, origen),
                      "No hay bloques de ese origen en la copia local; "
                      "sincronice la cadena y vuelva a verificar.",
                      referencia=nombre, usuario_id=usuario_id)
    return recepcion


def listar(limite=100):
    return db.consultar(
        "SELECT r.*, a.nombre AS archivo, a.sha256, a.ruta, a.bytes,"
        " u.email AS subido_por_email"
        " FROM recepciones r JOIN archivos a ON a.id = r.archivo_id"
        " LEFT JOIN usuarios u ON u.id = a.subido_por"
        " ORDER BY r.id DESC LIMIT %s", (limite,))


def ultima_intacta(origen):
    """Ultima recepcion intacta de un origen (la que se usa para conciliar)."""
    return db.consultar_uno(
        "SELECT r.*, a.nombre AS archivo, a.ruta, a.sha256"
        " FROM recepciones r JOIN archivos a ON a.id = r.archivo_id"
        " WHERE r.origen = %s AND r.estado_integridad = 'intacto'"
        " ORDER BY r.id DESC LIMIT 1", (origen,))


def _verificar(origen, archivo, contenido):
    """Compara el archivo con los sellos del origen. Devuelve (estado, lote, detalle)."""
    sellos_origen = cadena.sellos_de_origen(origen)
    if not sellos_origen:
        return ("sin_sello", None,
                "No hay sellos del origen %s en la copia local de la cadena." % origen)

    # 1) Coincidencia exacta con un sello: el archivo llego como se emitio.
    for sello in sellos_origen:
        if sello["hash_archivo"] == archivo["sha256"]:
            return ("intacto", sello["lote_codigo"],
                    "El archivo coincide con el sello del lote %s emitido el %s."
                    % (sello["lote_codigo"], sello["sellado_en"]))

    # 2) No coincide: se usa el sello mas reciente del origen como referencia
    #    y se detalla que movimientos difieren.
    referencia = sellos_origen[0]
    detalle = ("El archivo no coincide con ningun sello del origen %s. "
               "Referencia: lote %s." % (origen, referencia["lote_codigo"]))
    try:
        movimientos, _formato = carga.leer(archivo["nombre"], contenido.decode("utf-8", errors="replace"))
        problemas = sellos.verificar_movimientos(referencia, movimientos)
        if problemas:
            detalle += " Diferencias: " + "; ".join(problemas[:3])
    except ValueError as error:
        detalle += " Ademas no se pudo interpretar el archivo: %s" % error
    return ("alterado", referencia["lote_codigo"], detalle)
