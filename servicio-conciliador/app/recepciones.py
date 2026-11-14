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
    try:
        movimientos, _formato = carga.leer(
            nombre, contenido.decode("utf-8", errors="replace"))
    except ValueError as error:
        detalle = "Archivo %s rechazado por formato: %s" % (nombre, error)
        recepcion = db.ejecutar(
            "INSERT INTO recepciones (archivo_id, origen, lote_codigo,"
            " estado_integridad, detalle, verificado_en, verificado_por)"
            " VALUES (%s, %s, NULL, 'rechazado', %s, now(), %s) RETURNING *",
            (archivo["id"], origen, detalle, usuario_id))
        auditoria.registrar(
            usuario_id, "recepcion_rechazada", "recepciones", recepcion["id"],
            {"origen": origen, "archivo": nombre, "estado": "rechazado",
             "sha256": archivo["sha256"], "bytes": archivo["bytes"],
             "motivo": str(error)}, ip)
        alertas.crear(
            "integridad", "alta", "Archivo rechazado: %s de %s" % (nombre, origen),
            "%s SHA-256=%s; ruta=%s" % (detalle, archivo["sha256"], archivo["ruta"]),
            referencia=nombre, usuario_id=usuario_id)
        return recepcion
    estado, lote_codigo, detalle = _verificar(origen, archivo, contenido)

    recepcion = db.ejecutar(
        "INSERT INTO recepciones (archivo_id, origen, lote_codigo,"
        " estado_integridad, detalle, verificado_en, verificado_por)"
        " VALUES (%s, %s, %s, %s, %s, now(), %s) RETURNING *",
        (archivo["id"], origen, lote_codigo, estado, detalle, usuario_id))

    auditoria.registrar(usuario_id, "recepcion_archivo", "recepciones",
                        recepcion["id"],
                        {"origen": origen, "archivo": nombre, "estado": estado,
                         "lote": lote_codigo, "sha256": archivo["sha256"],
                         "bytes": archivo["bytes"], "detalle": detalle}, ip)
    if estado == "alterado":
        alertas.crear("integridad", "alta",
                      "Archivo modificado: %s de %s"
                      % (nombre, origen),
                      "%s Archivo=%s; SHA-256 recibido=%s; ruta=%s; lote=%s"
                      % (detalle, nombre, archivo["sha256"], archivo["ruta"],
                         lote_codigo or "no identificado"),
                      referencia=lote_codigo or nombre,
                      usuario_id=usuario_id)
    elif estado == "sin_sello":
        alertas.crear("integridad", "media",
                      "Archivo %s de %s sin sello disponible"
                      % (nombre, origen),
                      "No hay bloques de ese origen en la copia local; "
                      "sincronice la cadena y vuelva a verificar.",
                      referencia=nombre, usuario_id=usuario_id)
    sin_referencia = sum(not movimiento["referencia"] for movimiento in movimientos)
    if sin_referencia:
        alertas.crear(
            "operativa", "media", "Archivo con movimientos sin referencia",
            "%s de %s contiene %d movimiento(s) sin referencia. El archivo es "
            "válido; la conciliación solo podrá cruzarlos si monto y fecha dan "
            "una coincidencia única, de lo contrario quedarán para revisión."
            % (nombre, origen, sin_referencia),
            referencia=lote_codigo or nombre, usuario_id=usuario_id)
    return recepcion


def listar(limite=100):
    return db.consultar(
        "SELECT r.*, a.nombre AS archivo, a.sha256, a.ruta, a.bytes,"
        " u.email AS subido_por_email"
        " FROM recepciones r JOIN archivos a ON a.id = r.archivo_id"
        " LEFT JOIN usuarios u ON u.id = a.subido_por"
        " ORDER BY r.id DESC LIMIT %s", (limite,))


def eliminar(recepcion_id, usuario_id, ip=None):
    """Elimina una recepción duplicada, sin tocar sellos ni conciliaciones."""
    recepcion = db.consultar_uno(
        "SELECT r.id, r.origen, r.lote_codigo, r.estado_integridad,"
        " a.id AS archivo_id, a.nombre, a.ruta, a.sha256, a.bytes"
        " FROM recepciones r JOIN archivos a ON a.id = r.archivo_id"
        " WHERE r.id = %s", (recepcion_id,))
    if not recepcion:
        raise ValueError("La recepción no existe.")

    with db.conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id FROM recepciones WHERE id = %s FOR UPDATE",
                           (recepcion_id,))
            if not cursor.fetchone():
                raise ValueError("La recepción ya fue eliminada.")
            cursor.execute(
                "SELECT id FROM conciliaciones WHERE recepcion_empresa_id = %s"
                " OR recepcion_banco_id = %s LIMIT 1",
                (recepcion_id, recepcion_id))
            operacion = cursor.fetchone()
            if operacion:
                raise ValueError(
                    "La recepción forma parte de la conciliación #%d y no se "
                    "puede eliminar porque es evidencia de auditoría."
                    % operacion["id"])
            cursor.execute("DELETE FROM recepciones WHERE id = %s",
                           (recepcion_id,))
            cursor.execute("DELETE FROM archivos WHERE id = %s",
                           (recepcion["archivo_id"],))
            cursor.execute("SELECT COUNT(*) AS total FROM archivos WHERE ruta = %s",
                           (recepcion["ruta"],))
            ruta_compartida = cursor.fetchone()["total"] > 0
        conexion.commit()

    ruta = recepcion["ruta"]
    if not ruta_compartida:
        try:
            from pathlib import Path
            Path(ruta).unlink(missing_ok=True)
        except OSError as error:
            raise RuntimeError(
                "La recepción fue eliminada, pero no se pudo borrar el archivo "
                "del almacenamiento: %s" % error) from error

    auditoria.registrar(
        usuario_id, "eliminar_recepcion", "recepciones", recepcion_id,
        {"origen": recepcion["origen"], "archivo": recepcion["nombre"],
         "ruta": ruta, "lote": recepcion["lote_codigo"],
         "estado": recepcion["estado_integridad"],
         "sha256": recepcion["sha256"], "bytes": recepcion["bytes"]}, ip)
    return recepcion


def ultima_intacta(origen):
    """Ultima recepcion intacta de un origen (la que se usa para conciliar)."""
    return db.consultar_uno(
        "SELECT r.*, a.nombre AS archivo, a.ruta, a.sha256, a.contenido"
        " FROM recepciones r JOIN archivos a ON a.id = r.archivo_id"
        " WHERE r.origen = %s AND r.estado_integridad = 'intacto'"
        " ORDER BY r.id DESC LIMIT 1", (origen,))


def _verificar(origen, archivo, contenido):
    """Compara el archivo con los sellos del origen. Devuelve (estado, lote, detalle)."""
    sellos_origen = cadena.sellos_de_origen(origen)
    if not sellos_origen:
        return ("sin_sello", None,
                "No hay sellos del origen %s en la copia local de la cadena. "
                "La carga se conserva; sincronice Cadena y vuelva a verificar."
                % origen)

    # 1) La huella SHA-256 debe coincidir con un sello. Como segunda defensa,
    # se reconstruyen las huellas de cada movimiento del CSV recibido: un
    # bloque inconsistente nunca se marca como integro aunque su hash de
    # archivo haya sido propagado.
    for sello in sellos_origen:
        if sellos.compare_hashes(sello["hash_archivo"], archivo["sha256"]):
            movimientos, _formato = carga.leer(
                archivo["nombre"], contenido.decode("utf-8", errors="replace"))
            problemas = sellos.verificar_movimientos(sello, movimientos)
            if problemas:
                return (
                    "alterado", sello["lote_codigo"],
                    "El SHA-256 del archivo coincide, pero sus movimientos no "
                    "coinciden con las huellas selladas: %s"
                    % "; ".join(problemas[:3]))
            return ("intacto", sello["lote_codigo"],
                    "SHA-256 verificado contra el sello del lote %s emitido el %s."
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
