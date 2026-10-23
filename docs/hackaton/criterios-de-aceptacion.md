# Criterios de aceptación del hackaton: Wallet Perú, grupo 3

## 1. Estado y fuentes

**Estado: alcance inicial aprobado por una persona el 2026-10-23 para la versión
vigente de `wallet-demo-grupo3`.** Esto no acredita implementación ni pruebas y
no sustituye la aprobación final humana del Product Owner.

Fuentes de producto:

- [Épica: MVP de wallet en Perú](../userstories/epic/peru-wallet-mvp.sp.md).
- [W1: Registro y activación](../userstories/user-stories/user-onboarding-mvp-completion.sp.md).
- [W2: Confirmación de pagos](../userstories/user-stories/payer-low-value-payment-confirmation.sp.md).
- [W3: Visibilidad de pagos QR](../userstories/user-stories/merchant-qr-payment-status-visibility.sp.md).
- [W4: Idempotencia](../userstories/user-stories/payment-idempotency-protection.sp.md).
- [W5: Fallas y reversos](../userstories/user-stories/payment-failure-reversal-handling.sp.md).
- [W6: Conciliación](../userstories/user-stories/operations-transaction-reconciliation.sp.md).

Contrato de integración: OpenAPI 3.0.3, `Wallet mock W1–W6`, versión `0.2.0`,
compartido por el equipo. El contrato publicado del grupo se consulta en
<https://bcp-wallet-mock.yefri.workers.dev/groups/3/openapi.json>.
La disponibilidad del servicio y su coincidencia con el contrato compartido
deben verificarse antes de la demo; no se presuponen comprobadas.

Los requisitos de CrewAI, MCP y los cinco roles provienen del alcance acordado
para el hackaton, no de las historias originales.

## 2. Alcance mínimo propuesto

- Una web sencilla con tres pestañas: Registro, Pagos y QR, y Operaciones.
- Un backend ligero propio recibe las llamadas de la web y orquesta por HTTP el
  mock exclusivo del grupo 3:
  `https://bcp-wallet-mock.yefri.workers.dev/groups/3`. El navegador no llama
  directamente al mock.
- El backend es un adaptador/orquestador, no un procesador financiero. El mock
  es la fuente de verdad de wallets, pagos, saldos, eventos, soporte y
  conciliación. No se crea ledger, saldo o estado de pago paralelo.
- El backend/frontend pueden añadir funcionalidades que el mock no ofrece
  únicamente cuando estén trazadas a un criterio aprobado (por ejemplo, registro
  local de eventos analíticos de la demo). Cada función propia define contrato,
  propietario de datos, persistencia mínima y prueba. No se asume que deba existir
  una base de datos antes de que el Arquitecto determine su necesidad.
- CrewAI con cinco roles y aprobación humana del alcance antes de implementar.
- Un MCP local mínimo de consulta, conectado realmente a CrewAI.
- Evidencia de pruebas y un recorrido reproducible de los criterios `DEMO`
  trazados a W1-W6. Lo que el mock no cubre se identifica como `POSTERIOR` o
  `BLOQUEADO`; no se afirma que la demo implemente las seis historias completas.
- Un registro local exportable para trazas y analítica básica que el mock no
  proporciona. Es evidencia de la sesión, no un sistema analítico productivo.

### Convenciones de aceptación

- **Demo**: obligatorio para aceptar el alcance mínimo, una vez aprobado.
- **Posterior**: requisito original no cubierto íntegramente por el mock o que
  necesita medición posterior. No se elimina ni se declara cumplido por la demo.
- Los criterios funcionales se verifican con datos TEST, respuestas del servicio
  y consultas posteriores; una pantalla con datos fijos no demuestra integración.
- Un criterio no ejecutado o sin evidencia no cuenta como aprobado.
- Los controles de simulación se muestran separados del recorrido del usuario.
- La URL del mock se configura en backend, nunca en el frontend. El backend solo
  permite destinos y rutas autorizados del grupo 3 y no actúa como proxy abierto.
- Una funcionalidad propia no reemplaza ni altera el estado financiero autoritativo
  que informa el mock.
- Para las pruebas se conservan saldos iniciales e IDs de los recursos creados.
  Las operaciones de otros integrantes pueden afectar el estado compartido.

### Restricciones del contrato

- Los importes se envían como enteros en céntimos de PEN: `1500` representa
  `S/ 15.00`. Los mensajes de la web muestran soles.
- Una wallet recién registrada tiene saldo cero. Para pagos con fondos se usa
  `wallet-demo`, cuya semilla inicial es `100000` céntimos; su saldo actual puede
  variar por operaciones previas. No existe una recarga en el alcance.
- Destinatarios admitidos: `contact-demo` y `merchant-demo`.
- Crear un pago normalmente devuelve `202 PENDING`, incluso con escenario
  `APPROVED`. Se confirma mediante evento o resolución, no por el nombre del escenario.
- No hay envío automático de webhooks. La demo entrega eventos existentes.
- Estados de pago del mock: `PENDING`, `SUCCEEDED`, `REJECTED`, `REVERSED`.
  No existe estado de pago `EXPIRED`; el vencimiento de QR es un error distinto.
- `POST /payments` no admite `documento_deuda_id`. Un `qrId` del mock y una
  asociación local `qrId`–`paymentId` no demuestran que se consultó o pagó un
  documento de deuda de W3.
- Las respuestas no garantizan fechas de operación ni canal de proveedor.
  No se inventarán esos datos para aparentar filtros o reportes históricos.

## 3. Criterios funcionales de la demo

### W1. Registro y activación

| ID | Criterio verificable | Evidencia mínima |
|---|---|---|
| W1-01 | Al recorrer el registro, la web muestra los pasos requeridos, el actual y la siguiente acción. | Capturas del recorrido. |
| W1-02 | Un documento vacío o sin prefijo `TEST-` bloquea el envío y muestra cómo corregirlo. Solo se envía `documentType: TEST`; no se solicitan documentos personales reales. | Caso inválido sin petición y petición válida. |
| W1-03 | Crear KYC con `APPROVED` muestra IDs de verificación y wallet; consultar la wallet confirma `ACTIVE` y habilita el acceso a pagos. Se informa que la nueva cuenta no tiene fondos. | Respuestas de creación y consulta. |
| W1-04 | `MANUAL_REVIEW` muestra `PENDING`; la decisión explícita de una persona permite `ACTIVE` o `REJECTED` y actualiza la wallet y el caso de soporte. No se decide automáticamente. | Caso pendiente y decisión humana registrada. |
| W1-05 | `REJECTED` no se muestra como cuenta activa. `UNAVAILABLE` se muestra como indisponibilidad, sin anunciar creación exitosa. | Ambos escenarios y respuesta de error. |
| W1-06 | Se registran inicio, finalización de cada paso y cierre exitoso del onboarding con ID de sesión, wallet cuando exista y timestamp. La exportación permite calcular su duración. | Registro exportado de una sesión completa. |

### W2. Confirmación de pagos de bajo monto

| ID | Criterio verificable | Evidencia mínima |
|---|---|---|
| W2-01 | Antes de confirmar se muestran destino, monto y moneda; se bloquean importes vacíos, no positivos, con más de dos decimales o fuera del rango del contrato. Se convierte el importe a céntimos sin redondear silenciosamente una entrada inválida. | Confirmación y casos inválidos. |
| W2-02 | Se consulta saldo disponible y se impide enviar desde una wallet no activa o por un monto superior al disponible consultado. Si el servicio rechaza por saldo o estado cambiado, se muestra el error y se actualiza la consulta. | Consulta y escenario de saldo insuficiente. |
| W2-03 | Crear un pago muestra su ID y `PENDING` cuando corresponde; no presenta comprobante de éxito antes de confirmar el resultado. | Petición, respuesta `202` y vista pendiente. |
| W2-04 | Tras entregar el evento correcto o resolver el pago, la web vuelve a consultar estado, saldo e historial. `SUCCEEDED` muestra referencia y comprobante; `REJECTED` muestra una siguiente acción clara sin anunciar un cargo exitoso. | Pago aprobado, pago rechazado y consultas. |
| W2-05 | Reconsultar o repetir eventos no cambia un resultado confirmado de forma contradictoria. La demo no solicita reversos; si el mock ya devuelve `REVERSED`, se muestra como estado reportado. No se inventa `EXPIRED` como estado del mock. | Mismo ID consultado antes y después de una repetición. |
| W2-06 | El historial se obtiene del mock para la wallet seleccionada y se conserva tras recargar la web. | Consulta del historial después de recargar. |
| W2-07 | Se registran inicio de checkout, confirmación y resultado. Al observar `SUCCEEDED`, se emite una única activación por pago en el registro local, incluso al refrescar. Se incluye wallet, pago y timestamp, sin datos sensibles. | Exportación y refresco sin duplicar activación. |

El acceso a la pantalla de pagos desde una nueva cuenta no significa que pueda
pagar sin fondos. La demostración con saldo cambia explícitamente a `wallet-demo`.

### W3. Pago QR y visibilidad para el comercio

| ID | Criterio verificable | Evidencia mínima |
|---|---|---|
| W3-01 | Generar QR para `merchant-demo` muestra su payload como texto e imagen QR. Se permite pegar el payload y resolverlo sin cámara. | QR generado y respuesta de resolución. |
| W3-02 | Resolver el QR muestra comercio y monto antes de confirmar. Un QR abierto solicita monto; uno fijo conserva el importe y el pago envía su `qrId`. | Petición de pago con QR válido. |
| W3-03 | Un payload inválido, desconocido o vencido muestra un error accionable y no se presenta como pago creado. Un desacuerdo de comercio o monto reportado por la API no se oculta. | Casos inválido y vencido; error de discrepancia. |
| W3-04 | La vista de comercio muestra intentos QR de la sesión con referencia única y estado confirmado por el mock. Tras entregar un evento se actualiza la vista y no se aconseja entregar el producto mientras siga pendiente. | Mismo pago antes y después de confirmar. |
| W3-05 | Se puede filtrar por referencia real. El filtro por fecha usa solo la fecha de captura local, claramente rotulada, y se limita a recursos registrados por esta demo; no se presenta como fecha oficial del proveedor. | Dos registros de prueba y filtros por referencia y fecha local. |

El mock no ofrece historial global de comercios ni timestamps garantizados.
La web puede guardar localmente la asociación `qrId`–`paymentId` y la fecha de
captura para la demo; el estado financiero siempre se vuelve a consultar. El
mock no recibe `documento_deuda_id`, por lo que esta asociación no acredita una
deuda persistida, su reserva ni el control de un pago por deuda; esa parte de W3
es `POSTERIOR`.

### W4. Idempotencia y callbacks

| ID | Criterio verificable | Evidencia mínima |
|---|---|---|
| W4-01 | Cada nuevo intento genera una `Idempotency-Key` y conserva clave y payload para sus reintentos, incluso tras recargar. Cambiar monto o destinatario requiere un nuevo intento; no se genera otra clave para resolver un resultado incierto. | Clave original y solicitud repetida. |
| W4-02 | Repetir clave y contenido devuelve el mismo ID y estado actual del pago, sin otro pago ni cargo adicional. | Respuestas, historial, saldo y ledger antes y después. |
| W4-03 | Reutilizar intencionalmente la clave con distinto monto devuelve `409 IDEMPOTENCY_CONFLICT`; la web muestra el conflicto y no lo sustituye por éxito ni reintenta con otra clave automáticamente. | Petición alterada y error. |
| W4-04 | Entregar dos veces el mismo evento devuelve primero `duplicate:false` y después `duplicate:true`, sin nuevo movimiento de saldo ni asientos duplicados. La segunda respuesta no necesita contener `payment`; la web reconsulta el pago. | Respuestas del callback y consultas posteriores. |
| W4-05 | La traza local diferencia solicitud original, reintento y evento repetido mediante ID de solicitud local, correlación del intento, clave, ID de pago/evento cuando exista y resultado HTTP. | Exportación sin secretos. |
| W4-06 | La evidencia de conciliación distingue un pago financiero de sus reintentos mediante la traza correlacionada; los reintentos no se cuentan como pagos adicionales. El resultado nativo del mock se muestra sin modificarlo. | Resultado del mock junto con traza de duplicados. |

### W5. Fallas y soporte (sin reversos)

| ID | Criterio verificable | Evidencia mínima |
|---|---|---|
| W5-01 | Ante `TIMEOUT_AFTER_PROCESSING`, se conserva el `paymentId` de la respuesta y se ofrece consultar/resolver; no se anuncia fracaso definitivo ni se crea otro cobro. Una falla de red sin respuesta también se trata como incierta y conserva el intento. | Timeout simulado, resolución y único pago. |
| W5-02 | `PROVIDER_ERROR` muestra el error real y una acción de reintento controlado; el escenario no se confunde con un pago confirmado. Los errores con código del mock quedan en la traza junto con su referencia disponible. | Respuesta `503`, traza y consulta posterior. |
| W5-03 | Resolver un pago aún `PENDING` muestra el escalamiento y el caso de soporte. Repetir la resolución no crea casos duplicados para el mismo problema. | Respuesta `202` y lista de casos. |
| W5-04 | La ayuda diferencia rechazo (`REJECTED`), error conocido sin operación (`503 PROVIDER_ERROR`), resultado incierto (`504` o timeout de red), pendiente y éxito (`SUCCEEDED`). Solo ofrece reintento cuando el mock confirma que no creó el pago; para resultados inciertos guía a consultar/resolver. | Mensajes y acciones por escenario. |
| W5-05 | La demo no ofrece reverso, devolución ni disputa para un pago `SUCCEEDED`, de acuerdo con W5. Si la consulta del grupo ya devuelve `REVERSED`, se muestra el estado recibido sin afirmar que la demo lo solicitó. | Vista de éxito sin acción de reverso y, si existe, vista del estado `REVERSED` consultado. |
| W5-06 | La web, el backend, CrewAI y MCP no invocan el endpoint de reversos. La consulta de soporte es de solo lectura y nunca cambia pagos, saldos o ledger. | Inspección de rutas y llamadas durante el recorrido de soporte. |
| W5-07 | Se visualizan referencia, motivo y estado `OPEN`/`RESOLVED` del caso. Las acciones de operador quedan en la traza con recurso, acción, timestamp y resultado, sin afirmar identidad autenticada ni edición de casos que el mock no ofrece. | Caso consultado y traza de atención. |

El vencimiento de QR se registra como error `410 QR_EXPIRED`, no como pago
expirado. El mock puede exponer reversos, pero no se invocan en esta demo porque
W5 los excluye. Las disputas formales y los SLA quedan fuera de alcance.

### W6. Conciliación

| ID | Criterio verificable | Evidencia mínima |
|---|---|---|
| W6-01 | Ejecutar conciliación muestra la respuesta real `MATCHED` o `DIFFERENCES` y permite consultar reporte, ledger e incidencias. No corrige saldos ni mueve dinero desde la web. | Respuesta y fuentes consultadas. |
| W6-02 | Con confirmación explícita del facilitador, alterar con `AMOUNT` el settlement de un pago de prueba creado por esta demo genera una diferencia identificable. Es un reporte grupal compartido; no se alteran datos de otros integrantes deliberadamente. | Confirmación humana, respuesta de control y conciliación posterior. |
| W6-03 | Repetir conciliación con la misma causa no duplica la incidencia. Restaurar el settlement de prueba con `CLEAR` y conciliar nuevamente conserva el ID y muestra el estado devuelto por el mock, normalmente `RESOLVED`. | Incidencia en las tres ejecuciones; no se ejecuta `/control/reset`. |
| W6-04 | Se muestra un resumen de la ejecución: pagos consultados, pagos con diferencias, pagos sin diferencias e incidencias abiertas/resueltas. Se distingue número de pagos de número de incidencias y se identifican diferencias de wallet o recursos huérfanos por separado. | Resumen contrastado con IDs y respuesta. |
| W6-05 | Cada ejecución local se registra con timestamp. Se puede filtrar esa evidencia por fecha de ejecución local, sin afirmar que el mock tenga corte diario o filtros de fecha/canal del proveedor. | Dos ejecuciones registradas y filtro local. |

Una conciliación `MATCHED` solo se exige cuando las fuentes del grupo están
consistentes. Si otros integrantes dejan diferencias, se informan y se verifica
el ciclo de la incidencia propia; no se borran datos ajenos para obtener éxito.

## 4. CrewAI, MCP y aprobación humana

### Roles obligatorios

| Rol | Entregable verificable |
|---|---|
| Product Owner | Alcance y criterios propuestos para aprobación de una persona. |
| Arquitecto/a | Mapa sencillo de pantallas, endpoints, estados y límites del mock. |
| AI Engineer | Cambios de implementación propuestos conforme al alcance aprobado. |
| QA & Security | Casos, resultados reales disponibles, riesgos y verificaciones pendientes. |
| Presenter / Timekeeper | Guion, evidencias, pendientes y duración ensayada de la demo. |

| ID | Criterio verificable | Evidencia mínima |
|---|---|---|
| IA-01 | El flujo se ejecuta con CrewAI y los cinco roles anteriores, con tareas y entregables diferenciados. No se acepta un flujo LangGraph renombrado ni se añaden los roles antiguos como obligatorios. | Ejecución e identificación de agentes/tareas. |
| IA-02 | Tras proponer alcance y criterios, el flujo se detiene. Una persona puede aprobar, pedir ajustes o cancelar; solo una aprobación explícita habilita la implementación. Ausencia de respuesta y errores nunca equivalen a aprobación. | Pausa y prueba de aprobación y de rechazo/cancelación. |
| IA-03 | La decisión humana registra versión o identificador del alcance, decisión y timestamp. Un cambio material de alcance requiere nueva aprobación. La decisión automática de un agente no cuenta como aprobación humana. | Registro de decisión vinculado al alcance. |
| IA-04 | Un MCP local expone únicamente consultas de escenarios, wallet y pago del grupo 3. CrewAI descubre e invoca al menos una herramienta y utiliza su respuesta real en un entregable. | Descubrimiento, llamada MCP y resultado correlacionado. |
| IA-05 | Una falla MCP se informa como falla o bloqueo, sin inventar respuesta exitosa. El MCP no acepta URL arbitraria, shell, reinicio ni operaciones financieras de escritura. | Caso de error y rechazo de destino/acción no permitidos. |
| IA-06 | El navegador llama al backend propio; este orquesta por HTTP el mock fijo del grupo 3. La URL upstream no se expone al navegador y el backend no acepta destinos arbitrarios. Las funcionalidades propias solo cubren criterios aprobados y no alteran pagos/saldos/ledger del mock. Operaciones financieras no dependen de decisiones de un modelo. | Inspección de configuración/contratos y recorrido web con evidencia de ambas llamadas. |
| IA-07 | Tras implementación, QA y presentación, una persona Product Owner revisa resultados, evidencia y brechas y registra una aprobación final ligada a la versión. La aprobación inicial no sustituye esta revisión y ningún agente puede aprobar por la persona. | Decisión final humana vinculada a la versión y evidencia. |

MCP conecta agentes con herramientas: no instala un modelo local ni reemplaza
Copilot. El transporte local propuesto es stdio; no requiere exponer un servidor
HTTP. El modelo y su autenticación para CrewAI deben acordarse y comprobarse,
sin asumir que una sesión de Copilot habilita automáticamente cualquier proveedor.

## 5. Criterios transversales y evidencia

| ID | Criterio verificable |
|---|---|
| TR-01 | Solo se usan datos ficticios; secretos, credenciales y documentos reales no aparecen en código, prompts, trazas ni capturas. |
| TR-02 | La web identifica sandbox/grupo 3 y muestra errores accionables. Una falla de consulta no se convierte en saldo cero, historial vacío o éxito ficticio. |
| TR-03 | No hay reinicio automático. Si se ofrece reset, requiere confirmación humana con advertencia de que elimina los datos de todo el grupo; no forma parte obligatoria del recorrido. |
| TR-04 | El mock no valida firmas de callbacks ni ofrece controles productivos equivalentes. La demo no se presenta como sistema bancario seguro para producción. |
| TR-05 | Cada criterio probado registra ID, fecha, pasos o comando exacto, recursos, esperado, obtenido, resultado y evidencia. Estados: aprobado, fallido, no ejecutado o bloqueado. |
| TR-06 | Se conservan referencias e importes devueltos por la API; la web no inventa estados, fechas oficiales, canales ni resultados para completar pantallas. |
| TR-07 | El recorrido ensayado incluye onboarding, pago/QR, duplicado, timeout, verificación de que no se ofrecen reversos y conciliación, además de la evidencia de CrewAI, MCP y ambas aprobaciones humanas. |

## 6. Cobertura posterior y límites frente a las historias originales

Estos requisitos no se consideran satisfechos por sustituirlos con datos de
sesión. El Product Owner debe aprobar expresamente el recorte de demo.

| ID | Fuente | Requisito original y tratamiento |
|---|---|---|
| POST-01 | W1, CA 5 | Mediana de onboarding de 8 a 3 minutos dentro del trimestre. La demo prueba captura de eventos, no mejora estadística de una cohorte real. |
| POST-02 | W1, CA 6; épica | Conteos mensuales, atribución de gasto, MAU de 1,000–2,000 en meses 1–3 y CAC PEN 10. No hay adquisición real ni tres meses de datos. Reporte y atribución productivos quedan posteriores, sin cifras fabricadas. |
| POST-03 | W2, CA 5 | Abandono de checkout de 30% a 8% dentro del trimestre. Se instrumenta el flujo; no se declara alcanzada la meta durante el hackaton. |
| POST-04 | W2, CA 2 y 4; W5, CA 1 | Pago expirado: el mock no ofrece ese estado. Se prueban rechazo y resultado incierto; la expiración financiera requiere contrato/regla posterior, distinta del QR vencido. |
| POST-05 | W3, CA 4 | Historial por fecha oficial y referencia para comercios. La referencia se cubre; la fecha se limita a captura local. Un historial global durable con timestamps de origen queda posterior. |
| POST-06 | W4, CA 1; pregunta abierta | Ventana y retención de claves por canal. Se conserva la clave durante la demo y no se promete una retención productiva ni supervivencia al reset del grupo. |
| POST-07 | W5, CA 1–4; preguntas abiertas | Clasificación completa de fallas/expiraciones, disputas, identidad auditada del operador y SLA. Se muestran códigos/casos disponibles y trazas locales; no se implementa un sistema formal de disputas. |
| POST-08 | W6, CA 1, 3 y 4 | Corte diario, filtro por canal/fecha del proveedor y resumen diario oficial. El mock concilia todo el grupo sin esos campos; se ofrece resumen por ejecución local, no conciliación diaria productiva. |
| POST-09 | Épica | Operación multirriel, límites de proveedores reales, disponibilidad 24x7x365 y lanzamiento en un trimestre requieren integraciones y validaciones posteriores. El único proveedor de demo no demuestra esas capacidades. |
| POST-10 | W3, CA 1–6 | Vincular el pago a un documento de deuda persistido, reservarlo y evitar un segundo pago por deuda requiere un `documento_deuda_id` y reglas/API de deuda que el mock no ofrece. La demo prueba un pago QR del mock, no el pago de una deuda W3. |

### Trazabilidad de todos los criterios originales

La notación CA corresponde al número de criterio en cada historia fuente.

| Historia | Criterio original → cobertura propuesta |
|---|---|
| W1 | CA1 → W1-01; CA2 → W1-02; CA3 → W1-03/04; CA4 → W1-06; CA5 → POST-01; CA6 → POST-02. |
| W2 | CA1 → W2-01; CA2 → W2-03/04/05 y POST-04; CA3 → W2-04/06; CA4 → W4-01/02, W5-01/04 y POST-04; CA5 → POST-03; CA6 → W2-07 y POST-02. |
| W3 | CA1 → W3-01/02 y POST-10; CA2 → W2-03/04, W4-01/02 y POST-10; CA3 → W2-03/04 y W5-01/02; CA4 → W2-07 y POST-10; CA5 → W4-01/04 y POST-10; CA6 → W3-04/05, W4-04 y POST-05/10. |
| W4 | CA1 → W4-01 y POST-06; CA2 → W4-02/03; CA3 → W4-05; CA4 → W4-06. |
| W5 | CA1 → W5-01/02 y POST-04/07; CA2 → W5-03/04 y POST-07; CA3 → W5-04/05/06; CA4 → W5-07 y POST-07. |
| W6 | CA1 → W6-01 y POST-08; CA2 → W6-02/03; CA3 → W6-05 y POST-08; CA4 → W6-04/05 y POST-08. |

## 7. Decisiones pendientes de aprobación humana

1. El alcance mínimo y las limitaciones de la sección 6 fueron aprobados para
   la versión vigente de `wallet-demo-grupo3` el 2026-10-23. Un cambio material
   requiere una nueva aprobación humana.
2. Confirmar etiquetas: Pendiente (`PENDING`), Exitoso (`SUCCEEDED`),
   Rechazado (`REJECTED`) y Reversado (`REVERSED`).
3. Aprobar para la demo las fronteras de duración: inicio al comenzar el registro;
   fin exitoso al confirmar `ACTIVE`. Registrar por separado el tiempo en revisión.
4. Acordar importes de prueba, sin confundir el máximo técnico del mock con un
   límite regulatorio o una definición aprobada de “bajo monto”.
5. Confirmar modelo/autenticación de CrewAI y responsable de cada uno de los
   cinco roles, sin registrar credenciales.

## 8. Condición de cierre

La demo solo se declara lista cuando los criterios marcados como Demo en las
secciones 3–5 tienen evidencia real aprobada, las brechas están explícitas, QA
ha emitido su resultado y el Product Owner humano aprueba la versión final
después de revisar implementación, pruebas y presentación. La aprobación inicial
del alcance y la aprobación final son decisiones distintas; una respuesta de
CrewAI no sustituye ninguna de ellas. No basta generar informes con IA, pasar
pruebas antiguas de ReqFlow o mostrar pantallas sin llamadas reales.

La aceptación del hackaton no equivale a cumplir las metas trimestrales,
certificar controles regulatorios ni habilitar pagos reales.
