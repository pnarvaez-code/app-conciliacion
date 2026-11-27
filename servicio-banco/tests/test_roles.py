"""Verifica permisos efectivos y controles visibles para cada perfil."""
from unittest.mock import patch
from fastapi.testclient import TestClient
from starlette.requests import Request
from fastapi import HTTPException
from app import main, usuarios


def request(path, method='GET'):
    return Request({'type': 'http', 'method': method, 'path': path,
                    'query_string': b'', 'headers': []})


def permitido(path, method, rol):
    try:
        usuarios.verificar(request(path, method), {'rol': rol})
        return True
    except HTTPException as exc:
        assert exc.status_code == 403
        return False


def main_test():
    for rol in ('administrador', 'operador', 'consulta'):
        assert permitido('/', 'GET', rol)
        assert permitido('/sesion/actividad', 'POST', rol)
        assert permitido('/usuarios', 'GET', rol) == (rol == 'administrador')
        assert permitido('/usuarios/9/eliminar', 'POST', rol) == (rol == 'administrador')
        assert permitido('/auditoria/reset', 'POST', rol) == (rol == 'administrador')
        for ruta in ('/movimientos', '/lotes/cerrar', '/ingresos', '/conciliacion', '/cadena/sincronizar', '/alertas/1/estado'):
            assert permitido(ruta, 'POST', rol) == (rol != 'consulta')
        assert permitido('/movimientos/1/editar', 'GET', rol) == (rol != 'consulta')
    assert not permitido('/', 'GET', 'desconocido')

    cliente = TestClient(main.app)
    for rol in ('consulta', 'operador'):
        with patch.object(main.seguridad, 'usuario_actual', return_value={'id': 1, 'rol': rol, 'email': 'test@example.com'}), \
             patch.object(main.reset, 'ejecutar') as reset:
            respuesta = cliente.post('/auditoria/reset', data={'email': 'a@a.com', 'clave': 'x'})
            assert respuesta.status_code == 403
            reset.assert_not_called()
            assert cliente.get('/usuarios').status_code == 403
    with patch.object(main.seguridad, 'usuario_actual', return_value={'id': 1, 'rol': 'administrador', 'email': 'test@example.com'}), \
         patch.object(main.reset, 'ejecutar', return_value=True) as reset:
        respuesta = cliente.post('/auditoria/reset', data={'email': 'a@a.com', 'clave': 'x'}, follow_redirects=False)
        assert respuesta.status_code == 303
        reset.assert_called_once()

    with patch.object(main.seguridad, 'usuario_actual', return_value={'id': 1, 'rol': 'consulta', 'email': 'test@example.com'}):
        if hasattr(main, 'movimientos'):
            assert cliente.post('/movimientos', data={'monto': '1'}).status_code == 403
            assert cliente.get('/movimientos/1/editar').status_code == 403
        else:
            assert cliente.post('/conciliacion').status_code == 403
            assert cliente.post('/cadena/sincronizar').status_code == 403

    # Compila cada plantilla y comprueba que los formularios operativos no sean visibles.
    env = main.plantillas.env
    for nombre in env.list_templates():
        env.get_template(nombre)
    for nombre in ('alertas.html', 'conexion.html'):
        for rol in ('administrador', 'operador', 'consulta'):
            html = env.get_template(nombre).render(request=request('/'), usuario={'rol':rol, 'email':'a'}, servicio='BANCO', alertas=[{'id':1,'estado':'nueva','tipo':'otro','severidad':'baja'}], resultados=[], conexion_establecida=False)
            assert ('method="post"' in html) == (rol != 'consulta'), (nombre, rol)
    if hasattr(main, 'movimientos'):
        context = dict(request=request('/'), usuario={'rol':'consulta','email':'a'}, servicio='PYME',
                       resumen={'total':0,'monto_total':0,'pendientes':0,'en_lote':0},
                       lote_activo='todos', lotes_filtro=[], movimientos=[], alertas_nuevas=0)
        html = env.get_template('panel.html').render(**context)
        assert 'Registrar venta' not in html and 'Carga masiva' not in html
    else:
        html = env.get_template('recepciones.html').render(request=request('/ingresos'),
            usuario={'rol':'consulta','email':'a'}, servicio='CONCILIADOR', recepciones=[], alertas_nuevas=0)
        assert 'Recibir archivo' not in html and 'Obtener último lote' not in html
    print('Permisos por rol, reset y plantillas: OK')

if __name__ == '__main__':
    main_test()
