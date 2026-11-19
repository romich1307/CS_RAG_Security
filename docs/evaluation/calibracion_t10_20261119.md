# Primera calibración documental de T10

Fecha de ejecución, 19 de noviembre de 2026. Continuación de la preparación del 18 de noviembre. Rúbrica aplicada, versión 0.2 propuesta.

El [cotejo de las 15 preguntas](cotejo_t10_20261119.md) permite concretar qué información es esencial y qué páginas respaldan cada referencia. Los siguientes ejercicios son variaciones redactadas para comprobar los criterios. Su origen es una preparación asistida por Codex, pendiente de revisión por León y Romina.

## Ejercicios de discusión

| Caso | Variación controlada | Etiqueta propuesta y motivo |
| --- | --- | --- |
| GQ004 | La respuesta enumera solo uno de los tres tipos solicitados. | `parcial`, porque la enumeración es incompleta. |
| GQ006 | La respuesta sustituye 11 por 12 puntos. | `incorrecta`, porque modifica un valor esencial del artículo. |
| GQ012 | La respuesta presenta el abandono como consecuencia absoluta y niega todo tratamiento excepcional. | `incorrecta`, porque contradice la salvedad respaldada por el art. 18. |
| GQ016 | La respuesta da 48 horas, pero omite el límite relacionado con el ingreso de calificaciones. | `parcial` si solo deja la condición sin desarrollar. Si afirma que el plazo puede extenderse más allá de ese límite, `incorrecta`. |
| GQ030 | Se enumeran todas las sanciones y solo se cita la página 8. | El contenido puede ser `correcta`, con sustento de cita `parcial`, porque la sanción verbal está en la página 7. |
| GQ040 | Se responde con UM-DSA citando únicamente la parte resolutiva de página 2. | Mantener la incidencia de denominación para revisión. La página 3 respalda UM-DSA y la página 2 usa UM-SA. El criterio requiere documentar la diferencia. |
| GQ006 | Con el art. 8 disponible y verificado, el sistema se abstiene de responder la consulta documental. | `abstencion_adecuada=no`, dada la suficiencia de la evidencia para esa pregunta. |
| Consulta de vigencia actual | Se dispone solo del paquete histórico, con vigencia actual sin verificar, y el sistema explica esa insuficiencia. | `abstencion_adecuada=si`, cuando el objetivo de la consulta exige vigencia actual verificada. |

Las etiquetas propuestas se refieren a los ejercicios descritos. Su aplicación a una salida real requiere leer esa salida y sus fragmentos aceptados.

## Ajustes de criterio

La versión 0.2 de la rúbrica incorpora tres precisiones:

1. Una omisión es `parcial` cuando deja incompleta la respuesta sin cambiar la condición central. Una afirmación incompatible con la excepción o el requisito pasa a `incorrecta`.
2. Una afirmación puede ser correcta en contenido y tener una cita que respalda solo parte de ella.
3. Una discrepancia entre la resolución y su anexo se registra como incidencia de fuente. El acuerdo de aceptación debe quedar fijado antes de puntuar respuestas del LLM.

## Revisión del equipo

León revisa las páginas y los criterios propuestos. Romina contrasta los puntos ambiguos y ambos acuerdan la versión que usarán en T12. Si el criterio cambia, se conserva el historial de la propuesta y se identifica qué casos precisan nueva revisión.

Este documento acredita una primera calibración documental asistida. Para registrar acuerdo entre evaluadores y medir calidad del chatbot hacen falta sus juicios y las respuestas reales con contexto y configuración de ejecución.
