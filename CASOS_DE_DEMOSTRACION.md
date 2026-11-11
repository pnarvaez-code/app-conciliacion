# Casos para la demostración

Los archivos de esta carpeta son datos de entrada para PYME y Banco. No se
suben directamente al Conciliador: primero cada emisor debe importarlos y
emitir su lote o extracto. Esa emisión genera el CSV definitivo, su SHA-256 y
el bloque encadenado que el Conciliador usará al validar la recepción.

## Caso 1: conciliación exitosa

1. En PYME, importe
   `servicio-pyme/ejemplos/caso1_pyme_coincidencia_exacta.csv`, luego emita
   el cierre.
2. En Banco, importe
   `servicio-banco/ejemplos/caso1_banco_coincidencia_exacta.csv`, luego
   emita el extracto en CSV.
3. En Conciliador, ejecute **Cadena → Sincronizar**.
4. Descargue los dos CSV emitidos y súbalos en **Recepciones** con el origen
   correcto. Ambos deben quedar como **intacto**, con SHA-256 verificado.
5. Ejecute la conciliación: se esperan 3 pares y 100 %. El efectivo no tiene
   referencia, por lo que demuestra el cruce por monto y fecha.

## Caso 2: diferencias operativas y reemisión

1. Repita el flujo anterior usando los dos archivos `caso2_*.csv`.
2. La venta POS de 1.500.000 y el abono de 1.470.000 producen una diferencia
   por referencia; la comisión de 30.000 queda como movimiento solo bancario.
   El efectivo cruza correctamente.
3. En Banco, use **Reemitir extracto** para generar una versión nueva,
   encadenada y auditada del mismo lote. La versión anterior permanece en la
   cadena; el bloque y el archivo conservan sus SHA-256 respectivos.

Para resolver una diferencia contable real, registre el ajuste como un nuevo
movimiento documentado y emita un nuevo lote o extracto. No se modifica un
lote sellado: así se conserva la evidencia y la trazabilidad.
