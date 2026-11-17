# Decisiones de diseño y respaldo bibliográfico

La matriz vincula lo implementado en el prototipo y lo pendiente de validación con la literatura que lo motiva. La configuración actual está descrita en [Arquitectura](../ARQUITECTURA.md), [Metodología](../METODOLOGIA.md), [Modelo de amenaza](../AMENAZAS.md) y [Baseline offline](../BASELINE_OFFLINE.md).

## Trazabilidad de las decisiones existentes

| Decisión del proyecto | Evidencia bibliográfica y aplicación a la UNSA | Alcance actual |
| --- | --- | --- |
| Limitar el estudio al contenido recuperado. Mantener la evaluación de seguridad en una colección secundaria separada de la normativa y de las preguntas gold. | BIPIA identifica los datos externos como origen de inyecciones indirectas. PoisonedRAG permite distinguir la manipulación del corpus del comportamiento del generador. [Yi et al.][yi2025bipia], [Zou et al.][zou2025poisonedrag]. | Se estudia qué ocurre cuando aparece contenido de prueba en el contexto recuperado. La posibilidad de alterar el corpus oficial queda fuera del alcance. |
| Comparar A, B y C con los mismos fragmentos recuperados y parámetros. | Rag ’n Roll muestra que la configuración de recuperación cambia la exposición y el resultado. Liu et al. justifican evaluar la utilidad de la tarea legítima junto con la seguridad. [De Stefano et al.][destefano2024ragnroll], [Liu et al.][liu2024benchmark]. | A concatena contexto sin el mecanismo experimental. B separa roles y delimita el contexto. C serializa el contexto en JSON y excluye los fragmentos señalados por las reglas. Los controles de evidencia y citas son comunes a los tres modos. |
| Usar separación explícita entre instrucciones y datos como referencia. | Spotlighting y StruQ sustentan la separación de procedencias. SEP permite distinguir seguimiento legítimo de separación efectiva. [Hines et al.][hines2024spotlighting], [Chen et al.][chen2025struq], [Zverev et al.][zverev2025sep]. | El código actual utiliza roles, delimitación y estructura JSON. Su eficacia con un LLM real es una hipótesis por evaluar. StruQ incluye ajuste del modelo, que queda fuera del piloto. |
| Aplicar reglas heurísticas en C y conservar el motivo de cada exclusión. | InstructDetector y la detección y eliminación de Chen et al. motivan examinar el documento antes de generar. InjecGuard aporta un precedente para medir el bloqueo erróneo de texto legítimo. [Wen et al.][wen2025instructdetector], [Chen et al.][chen2025detectremove], [Li y Liu][li2025injecguard]. | Las reglas del prototipo son un punto de partida local. Su efecto debe medirse también en pasajes normativos inocuos y en la evidencia útil que conserva cada variante. |
| Mantener TF-IDF y coseno como referencia de recuperación. Separar recuperación, seguridad y calidad documental. | Rag ’n Roll mide el recorrido completo del RAG. RADE muestra la importancia de conservar los fragmentos que conectan evidencias. [De Stefano et al.][destefano2024ragnroll], [Yin et al.][yin2027rade]. | Se registra el acierto documento/página en top-k. Una comparación con recuperación semántica requiere la misma versión del corpus y las mismas preguntas verificadas. |
| Registrar las fuentes recuperadas y filtradas, validar pertenencia de citas y abstenerse ante evidencia insuficiente. | RAGForensics y TrustTrace estudian atribución a fuentes. Milani et al. muestran que una alerta puede coexistir con una respuesta sesgada. [Zhang et al.][zhang2025ragforensics], [Chen y Lu][chen2026trusttrace], [Milani et al.][milani2026ipi]. | El prototipo comprueba archivo y página en la evidencia disponible. La fidelidad del contenido y la vigencia normativa requieren verificación adicional. Los controles del proyecto para OCR e históricos se mantienen según el modelo de amenaza. |
| Medir por separado exposición, detección, respuesta y costo. | Liu et al. distinguen los errores del detector de los resultados de la tarea. Milani et al. distinguen alertas y mitigación. AgentDojo e InjecGuard aportan criterios de utilidad y falsas alarmas. [Liu et al.][liu2024benchmark], [Milani et al.][milani2026ipi], [Debenedetti et al.][debenedetti2024agentdojo], [Li y Liu][li2025injecguard]. | El piloto mock registró 34/40 aciertos documentales en top-5 por modo, recall del detector de 3/4 y FPR de 1/4. La ASR y la exactitud de respuesta del LLM figuran sin estimación. La latencia del pipeline excluye la recuperación compartida. |

## Hipótesis para la próxima evaluación

- **Seguridad y utilidad.** Evaluar si C reduce el cumplimiento de instrucciones externas frente a A y B cuando hay un LLM real identificado. Reportar ASR global y ASR sobre casos expuestos con sus denominadores. Revisar las salidas ambiguas, ya que mencionar o citar una instrucción puede tener un significado distinto de seguirla.
- **Falsas alarmas.** Medir por separado recall del detector y FPR. Revisar qué evidencias recuperadas descarta C y si esa exclusión afecta respuestas correctas, citas pertinentes o abstenciones. Fijar la rúbrica antes de leer los resultados.
- **Comparación de recuperación.** Conservar TF-IDF como referencia y documentar los aciertos y fallos de cualquier recuperador semántico evaluado más adelante. Mantener las preguntas de referencia fuera del índice y considerar el costo de la recuperación por separado.
- **Alternativas fuera del piloto.** El ajuste de preferencias, la edición de la caché KV y la verificación de llamadas a herramientas requieren capacidades diferentes de las del prototipo documental. Se conservan como antecedentes con criterios de prueba propios. [Chen et al.][chen2025secalign], [Wang et al.][wang2026cacheprune], [Jia et al.][jia2025taskshield].

[yi2025bipia]: https://dl.acm.org/doi/10.1145/3690624.3709179
[zou2025poisonedrag]: https://www.usenix.org/conference/usenixsecurity25/presentation/zou-poisonedrag
[destefano2024ragnroll]: https://arxiv.org/abs/2408.05025v2
[liu2024benchmark]: https://www.usenix.org/conference/usenixsecurity24/presentation/liu-yupei
[hines2024spotlighting]: https://ceur-ws.org/Vol-3920/paper03.pdf
[chen2025struq]: https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe
[zverev2025sep]: https://proceedings.iclr.cc/paper_files/paper/2025/hash/a77eadda332b6d4a9ae1e0e4024555f2-Abstract-Conference.html
[wen2025instructdetector]: https://aclanthology.org/2025.findings-emnlp.1060/
[chen2025detectremove]: https://aclanthology.org/2025.acl-long.890/
[li2025injecguard]: https://arxiv.org/abs/2410.22770v3
[yin2027rade]: https://www.sciencedirect.com/science/article/pii/S095741742602806X
[zhang2025ragforensics]: https://dl.acm.org/doi/10.1145/3696410.3714756
[chen2026trusttrace]: https://ieeexplore.ieee.org/document/11664419/
[milani2026ipi]: https://link.springer.com/article/10.1007/s00521-026-12266-x
[debenedetti2024agentdojo]: https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html
[chen2025secalign]: https://dl.acm.org/doi/10.1145/3719027.3744836
[wang2026cacheprune]: https://aclanthology.org/2026.acl-long.70/
[jia2025taskshield]: https://aclanthology.org/2025.acl-long.1435/
