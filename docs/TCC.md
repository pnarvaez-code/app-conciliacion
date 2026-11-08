# UNIVERSIDAD COLUMBIA DEL PARAGUAY

## CARRERA DE INGENIERÍA EN INFORMÁTICA

### Sistema de Conciliación Financiera Automatizada para PYMES mediante Tecnología Blockchain Permisionada

**Línea de investigación:** Tecnología e Innovación  
**Trabajo de Conclusión de Carrera**

**Autores**

- Pedro Pablo Narváez Benítez
- Ariel Torres Romero

**Tutor:** Msc. Roberto Sánchez  
**Asunción, Paraguay — Octubre de 2026**

> **Documento académico del proyecto.** Este archivo reúne la memoria técnica
> y la descripción de la solución implementada en este repositorio. La
> diagramación institucional, paginación, firmas, fotografías y capturas
> definitivas deben completarse en la versión final presentada ante la
> Universidad.

## Ficha catalográfica

Narváez Benítez, Pedro Pablo; Torres Romero, Ariel. *Sistema de
Conciliación Financiera Automatizada para PYMES mediante Tecnología
Blockchain Permisionada* / Pedro Pablo Narváez Benítez; Ariel Torres Romero.
— Asunción, 2026.

Trabajo de Conclusión de Carrera (Ingeniero en Informática) — Carrera de
Ingeniería en Informática, Universidad Columbia del Paraguay, 2026.

**Palabras clave:** conciliación financiera; blockchain permisionada;
integridad de datos; PYMES; SHA-256.

## Acta de aprobación TCC

En la ciudad de Asunción, a los ____ días del mes de __________ del año
2026, el Tribunal Evaluador designado por la Carrera de Ingeniería en
Informática se reúne para evaluar el trabajo titulado *Sistema de
Conciliación Financiera Automatizada para PYMES mediante Tecnología
Blockchain Permisionada*, presentado por Pedro Pablo Narváez Benítez y Ariel
Torres Romero para la obtención del título de Ingeniero en Informática.

| Estudiante | Calificación |
|---|---|
| Pedro Pablo Narváez Benítez | ____ (________) |
| Ariel Torres Romero | ____ (________) |

El trabajo queda: **aprobado / aprobado con observaciones / no aprobado**.

| Tribunal | Nombre y apellido | Firma |
|---|---|---|
| Presidente |  |  |
| Miembro 1 |  |  |
| Miembro 2 |  |  |

## Dedicatoria

A nuestras familias, por su apoyo incondicional a lo largo de esta carrera; y
a nuestro tutor, por su guía y exigencia en la construcción de este trabajo.

## Agradecimientos

Expresamos nuestro sincero agradecimiento al tutor, Profesor Roberto Sánchez,
por su orientación rigurosa, sus comentarios constructivos y su exigencia
académica. A la Universidad Columbia del Paraguay y a la Carrera de
Ingeniería en Informática, por la formación y el espacio institucional para
desarrollar este trabajo. A los docentes, familias y personas que
contribuyeron al proyecto mediante sus conocimientos, apoyo y confianza.

## Resumen

Este Trabajo de Conclusión de Carrera aborda la conciliación financiera en
pequeñas y medianas empresas paraguayas, proceso que suele depender de
planillas, archivos CSV/XML y verificaciones manuales. Esta situación genera
costos operativos, errores humanos y una dependencia excesiva de la confianza
entre las partes que intercambian información.

Se desarrolló un sistema de conciliación financiera automatizada que utiliza
una blockchain permisionada como mecanismo de notariado digital. El sistema
no almacena importes ni descripciones sensibles en la cadena: registra
huellas SHA-256 de los movimientos, archivos y bloques, junto con el
encadenamiento temporal y el origen del sello. La solución productiva está
compuesta por tres servicios FastAPI independientes: `servicio-pyme`,
`servicio-banco` y `servicio-conciliador`. Cada servicio posee usuarios,
sesiones, auditoría, almacenamiento y base PostgreSQL aislados.

El motor de conciliación aplica tres niveles deterministas: referencia
exacta; monto exacto con fecha cercana; y descripción similar con monto
aproximado. La verificación previa se ejecuta en tres frentes: cadena,
archivo físico y movimientos individuales. La arquitectura se despliega
mediante Docker Compose, PostgreSQL y, opcionalmente, Heroku o Coolify.

La validación funcional incluyó pruebas de sellos, arranque, importación,
conciliación y sincronización. También se verificaron archivos alterados,
registros modificados y divergencias de cadena. Los resultados muestran que
la solución permite detectar cambios posteriores al sellado, conservar
trazabilidad y automatizar el cruce sin requerir criptomonedas ni una red
blockchain pública.

**Palabras clave:** conciliación financiera; blockchain permisionada;
integridad de datos; PYMES; SHA-256.

## Abstract

This Final Degree Project addresses financial reconciliation for Paraguayan
small and medium-sized enterprises, a process frequently based on spreadsheets,
CSV/XML files and manual verification. This approach creates operational
costs, human errors and excessive reliance on trust among the parties
exchanging information.

An automated financial reconciliation system was developed using a
permissioned blockchain as a digital notarization mechanism. Sensitive
amounts and descriptions are not stored on-chain. Instead, the system stores
SHA-256 fingerprints of movements, files and blocks, together with temporal
chaining and origin metadata. The production solution consists of three
independent FastAPI services: `servicio-pyme`, `servicio-banco` and
`servicio-conciliador`. Each service has isolated users, sessions, auditing,
storage and PostgreSQL data.

The reconciliation engine applies three deterministic levels: exact
reference; exact amount within a date window; and similar description with an
approximate amount. Integrity is checked through three independent fronts:
chain, physical file and individual movements. The architecture is deployable
with Docker Compose, PostgreSQL and, optionally, Heroku or Coolify.

**Keywords:** financial reconciliation; permissioned blockchain; data
integrity; SMEs; SHA-256.

## Índice general

1. Introducción  
2. Presentación de la investigación  
3. Marco teórico y antecedentes  
4. Marco metodológico  
5. Especificación, desarrollo y validación de la solución  
6. Conclusiones y recomendaciones  
7. Referencias bibliográficas  
8. Declaración de uso de Inteligencia Artificial  
9. Anexos

## Lista de abreviaturas

| Sigla | Significado |
|---|---|
| API | Application Programming Interface |
| CSV | Comma-Separated Values |
| DER | Diagrama/Modelo Entidad-Relación |
| HTTP/HTTPS | Hypertext Transfer Protocol / Secure |
| JSON | JavaScript Object Notation |
| MIPYMES | Micro, pequeñas y medianas empresas |
| PostgreSQL | Sistema gestor relacional utilizado en producción |
| PYME/PYMES | Pequeña y mediana empresa / empresas |
| SHA-256 | Secure Hash Algorithm de 256 bits |
| SQL | Structured Query Language |
| STRIDE | Modelo de análisis de amenazas |
| TCC | Trabajo de Conclusión de Carrera |
| XML | Extensible Markup Language |

# 1. Introducción

La conciliación bancaria compara los registros internos de una empresa con
los movimientos informados por su entidad financiera. En muchas PYMES este
proceso se realiza manualmente mediante archivos electrónicos y planillas,
sin una prueba matemática de que el archivo recibido sea idéntico al emitido.

El proyecto propone una solución que separa dos responsabilidades. La base
de datos privada conserva los datos operativos; la cadena permisionada conserva
evidencia criptográfica verificable. De esta forma, la solución no pretende
demostrar que un hecho económico ocurrió antes de ingresar al sistema, sino
garantizar que el dato no fue modificado silenciosamente después de su
emisión y sellado.

El documento presenta el problema, fundamentos, metodología, arquitectura,
implementación, validación, resultados, limitaciones y recomendaciones.

# 2. Presentación de la investigación

## 2.1 Planteamiento del problema

Las PYMES intercambian ventas y extractos mediante archivos CSV o XML. Los
archivos pueden modificarse accidentalmente al abrirlos con una hoja de
cálculo, sustituirse por copias antiguas o alterarse mediante acceso directo
a una base de datos. Una comparación tradicional no identifica de manera
independiente el origen, el contenido original ni el registro exacto que
cambió.

El problema se resume en tres riesgos:

1. **Alteración en tránsito:** cambios de formato, fechas o montos.
2. **Modificación interna:** cambios directos en archivos o registros.
3. **Asimetría probatoria:** ausencia de un historial compartido y verificable.

## 2.2 Pregunta general

¿De qué manera una blockchain permisionada, limitada a la función de notario
digital, puede automatizar la conciliación financiera y fortalecer la
integridad de los archivos intercambiados entre una PYME, un banco y un
conciliador?

## 2.3 Preguntas específicas

1. ¿Qué limitaciones tienen los métodos tradicionales de integridad?
2. ¿Cómo diseñar servicios independientes sin almacenar datos sensibles en la
   cadena?
3. ¿Qué efectividad alcanza un motor determinista de tres niveles?
4. ¿Puede detectar modificaciones en archivos, registros y copias de cadena?

## 2.4 Objetivo general

Desarrollar un sistema de conciliación financiera automatizada para PYMES que
integre blockchain permisionada como notario digital y detecte modificaciones
posteriores al sellado de archivos y registros.

## 2.5 Objetivos específicos

1. Diferenciar técnicamente hashing, encadenamiento y cifrado.
2. Implementar los servicios PYME, Banco y Conciliador.
3. Desarrollar un motor determinista de tres niveles.
4. Validar integridad mediante archivos, bases de datos y copias de cadena.
5. Documentar despliegue, contratos internos, auditoría y operación.

## 2.6 Hipótesis y variables

**Hipótesis:** una cadena permisionada de anclaje SHA-256, replicada entre las
partes autorizadas y combinada con un motor determinista, permite automatizar
la conciliación y detectar alteraciones posteriores al sellado sin utilizar
criptomonedas.

**Variables operacionalizadas:**

- Integridad criptográfica: huellas de movimientos, archivo, raíz y bloque.
- Automatización: porcentaje conciliado por cada nivel.
- Trazabilidad: auditoría, usuario emisor, fecha, IP y re-emisiones.

## 2.7 Justificación

La propuesta aporta una alternativa de bajo costo para PYMES, basada en
software libre y desplegable en infraestructura pequeña. Su valor práctico
consiste en reducir tareas manuales y aportar evidencia compartida. Su valor
teórico consiste en aplicar blockchain únicamente donde agrega valor:
encadenamiento, replicación y verificación entre organizaciones autorizadas.

# 3. Marco teórico y antecedentes

## 3.1 Conceptos fundamentales

Una función hash transforma una entrada en una huella de longitud fija.
SHA-256 genera 256 bits, representados normalmente como 64 caracteres
hexadecimales. Un hash detecta cambios, pero por sí solo no conserva un
historial. La blockchain agrega bloques encadenados y copias replicadas.
El cifrado, en cambio, protege la confidencialidad y no reemplaza al hash.

| Concepto | Uso en el proyecto |
|---|---|
| SHA-256 | Huellas de movimientos, archivos, raíces y bloques |
| Blockchain permisionada | Historial encadenado replicado entre servicios |
| Cifrado/hash de credenciales | Sesiones y contraseñas; no reemplaza la integridad |

## 3.2 Blockchain pública y permisionada

El sistema no utiliza minería, prueba de trabajo ni criptomonedas. La
participación está restringida a servicios identificados. PYME y Banco
mantienen sus cadenas de origen y propagan sus bloques al Conciliador. La
separación evita mezclar índices de cadenas independientes y permite
identificar el origen esperado.

## 3.3 Conciliación financiera

La conciliación compara ventas y movimientos bancarios. La solución usa una
regla de honestidad: cada movimiento puede emparejarse como máximo una vez y
no se fuerzan coincidencias.

| Nivel | Regla |
|---|---|
| 1 | Referencia normalizada idéntica |
| 2 | Monto idéntico y fecha dentro de una ventana |
| 3 | Descripción similar y monto dentro de tolerancia |

Los resultados se clasifican como `conciliado`,
`en_banco_no_empresa`, `en_empresa_no_banco`, `monto_distinto`,
`fuera_de_ventana` o `referencia_distinta`.

# 4. Marco metodológico

La investigación es aplicada, tecnológica, propositiva y experimental. El
desarrollo se ejecutó iterativamente en las siguientes fases:

1. Revisión del problema y delimitación de garantías.
2. Diseño de sellos, API, base de datos y modelo de conciliación.
3. Implementación de los tres servicios.
4. Integración con PostgreSQL, Docker y despliegue.
5. Pruebas funcionales, de integridad y sincronización.
6. Documentación de resultados y recomendaciones.

La muestra técnica está compuesta por movimientos de ventas y extractos
bancarios de prueba, archivos CSV/XML, bases PostgreSQL y cadenas replicadas.
La recolección se realizó mediante pruebas automatizadas, observación de
logs, auditoría y escenarios de modificación controlada.

# 5. Especificación, desarrollo y validación

## 5.1 Arquitectura

| Servicio | Puerto local | Responsabilidad |
|---|---:|---|
| `servicio-pyme` | 8001 | Ventas, lotes, CSV, sellado y auditoría |
| `servicio-banco` | 8002 | Movimientos, extractos CSV/XML y sellado |
| `servicio-conciliador` | 8080 → 8000 | Recepciones, verificación y conciliación |

Cada servicio usa FastAPI, Uvicorn, Jinja2, PostgreSQL y psycopg 3. La
comunicación interna utiliza `X-Servicio-Token`. Docker Compose crea
PostgreSQL y espera healthchecks antes de iniciar los servicios dependientes.

## 5.2 Ciclo de vida

1. Se registra o importa un movimiento.
2. Se cierra un lote y se genera el archivo.
3. Se calculan las huellas SHA-256 y se crea el bloque.
4. El bloque se propaga al Conciliador.
5. El auditor carga el archivo y se verifican tres frentes.
6. Solo los lotes intactos ingresan a conciliación.

## 5.3 Estructura criptográfica

Los campos sellados son:

`indice`, `origen`, `lote_codigo`, `archivo`, `n_movimientos`,
`hashes_movimientos`, `hash_raiz`, `hash_archivo`, `hash_anterior`,
`emitido_por`, `sellado_en` y `hash_bloque`.

Las columnas internas como `id` y `created_at` no forman parte del hash del
bloque. `sellado_en` se conserva en formato ISO exacto para evitar cambios de
representación al releer PostgreSQL.

## 5.4 Verificación en tres frentes

1. **Cadena:** continuidad de `hash_anterior`, recomputación de bloques y
   comparación entre copias.
2. **Archivo:** hash binario del archivo físico contra `hash_archivo`.
3. **Datos:** comparación posición por posición contra
   `hashes_movimientos`.

Una alteración impide continuar con la conciliación y genera una alerta de
integridad.

## 5.5 Seguridad y auditoría

- Contraseñas con bcrypt.
- Sesiones firmadas y revocables.
- API interna protegida por token.
- Consultas parametrizadas.
- Auditoría de accesos, emisiones, recepciones y alertas.
- Separación de secretos y bases por servicio.
- Validación de nombres de esquema mediante expresión segura.
- Datos financieros fuera de la cadena.

## 5.6 Reportes

Cada servicio incorpora **Reporte PDF**, protegido por sesión. El informe
incluye usuario, fecha, métricas, bloques, alertas y operaciones auditadas.
La descarga se registra con la acción `generar_reporte` y el PDF se genera
en memoria para no depender de almacenamiento temporal permanente.

## 5.7 Requisitos funcionales

| Código | Requisito |
|---|---|
| RF-01 | Autenticar y administrar usuarios |
| RF-02 | Registrar e importar movimientos |
| RF-03 | Cerrar lotes y emitir archivos |
| RF-04 | Sellar y propagar bloques |
| RF-05 | Recibir y verificar archivos |
| RF-06 | Conciliar por tres niveles |
| RF-07 | Administrar alertas y auditoría |
| RF-08 | Generar reportes PDF |

## 5.8 Validación

Se ejecutaron:

- pruebas de arranque y rutas protegidas;
- pruebas de sellos y hash;
- pruebas de importación;
- pruebas del motor de conciliación;
- pruebas de sincronización;
- compilación Python;
- validación de YAML de Compose;
- verificación de migraciones idempotentes;
- pruebas de detección de archivos y bloques alterados.

La integración completa con Docker Compose debe ejecutarse en un entorno que
disponga del subcomando `docker compose`. Los resultados de cada ejecución
deben conservarse junto con fecha, versión del commit y logs.

# 6. Conclusiones y recomendaciones

## 6.1 Conclusiones

1. Una blockchain permisionada de anclaje aporta evidencia encadenada y
   replicada sin exigir criptomonedas.
2. La separación entre datos operativos y huellas protege la privacidad por
   diseño.
3. Los tres frentes de verificación detectan cambios en cadena, archivos y
   movimientos.
4. El motor multinivel permite conciliar coincidencias exactas y diferencias
   operativas sin inventar pares.
5. Docker Compose, PostgreSQL y FastAPI permiten desplegar la solución en
   infraestructura accesible para una PYME.
6. La auditoría y los reportes PDF mejoran la trazabilidad del trabajo del
   operador y del auditor.

## 6.2 Limitaciones

- El sellado no demuestra la veracidad de un dato anterior a su ingreso.
- La cadena de aplicación no reemplaza una red blockchain empresarial con
  consenso formal.
- Heroku utiliza almacenamiento efímero para archivos; la producción real
  requiere almacenamiento de objetos y copias de seguridad.
- Las métricas de efectividad deben validarse con datos de PYMES reales antes
  de generalizar resultados.

## 6.3 Recomendaciones

1. Incorporar firmas asimétricas ECDSA/PKI por bloque.
2. Automatizar respaldos de PostgreSQL y archivos.
3. Integrar SMTP para alertas críticas.
4. Agregar formatos bancarios ISO 20022/CAMT.053 y MT940.
5. Ejecutar pilotos con PYMES y sistemas SIFEN.
6. Comparar el anclaje ligero con Hyperledger Fabric en rendimiento y costo.

# 7. Referencias bibliográficas

- Catalini, C., & Gans, J. S. (2016). *Some simple economics of the
  blockchain*. NBER Working Paper No. 22952.
- Hernández Sampieri, R., Fernández Collado, C., & Baptista Lucio, P. (2014).
  *Metodología de la investigación* (6.ª ed.). McGraw-Hill.
- Nakamoto, S. (2008). *Bitcoin: A peer-to-peer electronic cash system*.
- National Institute of Standards and Technology. (2015). *FIPS 180-4:
  Secure Hash Standard*.
- Schneier, B. (1996). *Applied Cryptography* (2.ª ed.).
- Yaga, D., Mell, P., Roby, N., & Scarfone, K. (2019). *Blockchain Technology
  Overview*. NIST IR 8202.
- Universidad Columbia del Paraguay. (2025). *Manual de Orientación General
  para Trabajo de Conclusión de Carrera*.

> Las referencias legales, institucionales y estadísticas deben cotejarse con
> las fuentes oficiales y el formato bibliográfico exigido por la Universidad
> antes de la entrega final.

# 8. Declaración de uso de Inteligencia Artificial

Los autores declaran que utilizaron asistentes de IA generativa como apoyo
para explorar ideas, organizar contenido y revisar redacción. El contenido,
las decisiones técnicas, los resultados y las fuentes deben ser revisados y
validados personalmente por los autores conforme a las normas institucionales.

**Estudiante:** Pedro Pablo Narváez Benítez  
**Firma:** ____________________  **Fecha:** ____ / ____ / ______

**Estudiante:** Ariel Torres Romero  
**Firma:** ____________________  **Fecha:** ____ / ____ / ______

# 9. Anexos

## Anexo A. Cronograma

| Fase | Periodo | Resultado |
|---|---|---|
| Problema y objetivos | Agosto 2026 | Alcance y preguntas |
| Marco teórico y legal | Agosto–septiembre | Fundamentos |
| Arquitectura y modelo de datos | Septiembre | Diseño técnico |
| Implementación de servicios | Septiembre–octubre | Plataforma funcional |
| Pruebas e integración | Octubre | Validación |
| Documentación y defensa | Octubre–noviembre | TCC final |

## Anexo B. Presupuesto referencial

El software utilizado es de código abierto. El costo principal corresponde al
VPS, dominio, almacenamiento externo y respaldos. Los valores deben
actualizarse con cotizaciones y tipo de cambio vigentes al momento de la
presentación.

## Anexo C. Glosario

- **Bloque:** registro sellado que contiene huellas y referencia al bloque
  anterior.
- **Hash:** resumen criptográfico determinista.
- **Lote:** conjunto de movimientos cerrado y emitido.
- **Re-emisión:** nuevo sello versionado que conserva la emisión anterior.
- **Regla de honestidad:** no forzar coincidencias.
- **Recepción:** archivo cargado al Conciliador para su verificación.
- **Token de servicio:** secreto `X-Servicio-Token` compartido entre APIs.

## Anexo D. Despliegue

Desde la raíz del repositorio:

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

Direcciones locales:

| Servicio | Dirección |
|---|---|
| PYME | http://localhost:8001 |
| Banco | http://localhost:8002 |
| Conciliador | http://localhost:8080 |

Para Heroku se utiliza `Procfile` y `heroku_start.py`. Cada aplicación debe
configurar `SERVICIO` (`pyme`, `banco` o `conciliador`), `DATABASE_URL`,
`DB_SCHEMA`, `TOKEN_SERVICIO`, `CLAVE_SESION`, credenciales iniciales y URLs
de los pares. El proceso lee `PORT`, cambia al directorio del servicio y
activa `proxy_headers`.

## Anexo E. Evidencias sugeridas

La entrega final debe incorporar capturas numeradas de:

1. Inicio de sesión.
2. Panel PYME y Banco.
3. Cierre y sellado de lotes.
4. Cadena replicada.
5. Recepciones intactas.
6. Conciliación y diferencias.
7. Archivo alterado rechazado.
8. Alertas y auditoría.
9. Botón y documento **Reporte PDF**.
10. Estado de los contenedores y logs de despliegue.
