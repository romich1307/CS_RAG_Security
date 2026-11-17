# Arquitectura

Flujo: pregunta → recuperador → defensa A/B/C → control de evidencia → generador
→ validación de citas → respuesta y trazabilidad.

`ingestion` lee exclusivamente el JSONL piloto para construir conocimiento;
combina metadatos por documento y valida identidad, página, método, OCR y cobertura.
La auditoría adicional verifica SHA-256 y tamaño de los PDF contra documents.json.
Los metadatos de documentos externos no se consideran documentos disponibles.
La exclusión histórica se verifica por directorio y etiqueta; una página histórica
inyectada al JSONL provoca error, no se omite silenciosamente.

La fragmentación respeta los párrafos existentes, subdividiendo los largos a 180
palabras con solapamiento 30, sin cruzar páginas. Los saltos del OCR pueden producir
fragmentos cortos: no equivalen necesariamente a artículos completos. Cada fragmento
conserva documento_id, archivo_pdf, pagina_pdf, metodo, revisión OCR, fecha,
estado_normativo, origen e identificador estable. No se reconstruye texto ausente.

`retrieval` calcula TF-IDF normalizado y similitud coseno. Normaliza acentos,
filtra palabras funcionales y ordena empates por posición. No es índice vectorial
de embeddings semánticos. Guarda JSON local y reconstruye vectores en memoria.
El corpus, preguntas y respuestas gold nunca se fusionan: solo evaluation lee gold.

`defenses` crea mensajes según el modo y registra reglas, puntuación y motivos.
`pipeline` aplica umbral coseno 0.12, abstención OCR y exigencia de verificación para
consultas de vigencia. El modo documental habilita consulta provisional nativa.
Los controles de evidencia y pertenencia de citas son comunes a A/B/C: A carece del
mecanismo experimental, pero mantiene estos controles del producto.

`generation` implementa mock y adaptador local intercambiables mediante argumento.
Los proveedores no reciben herramientas ni ejecutan código documental. El adaptador
local usa IP loopback literal, sin proxies ni redirecciones; timeout de 90 segundos.
Los mensajes JSON aíslan contenido mediante estructura, no crean una barrera formal
contra un LLM. La comprobación de citas valida pertenencia al contexto, no entailment.

`evaluation` reutiliza exactamente los mismos hits por pregunta en A/B/C; usa el
índice oficial para gold y una colección secundaria efímera por caso sintético.
`app/streamlit_app.py` muestra los resultados y el registro completo. La aplicación
se inicia manualmente en localhost; no despliega un servicio externo.
