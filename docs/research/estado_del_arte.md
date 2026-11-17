# Estado del arte

## Alcance

La [matriz de literatura](matriz_literatura.csv) reúne 30 estudios para el diseño y la evaluación de un RAG de consulta de reglamentos de la Universidad Nacional de San Agustín de Arequipa (UNSA). La revisión se centra en la inyección indirecta y considera antecedentes sobre envenenamiento del corpus, divulgación de información y agentes como evidencia complementaria. La matriz identifica publicación, año, método, evaluación, métricas y limitaciones. Las claves de citación están en [referencias.bib](referencias.bib).

## Inyección indirecta en consultas documentales

Un RAG incorpora a la entrada del generador pasajes recuperados para responder una consulta. La inyección indirecta ocurre cuando el modelo interpreta una instrucción de esos pasajes como parte de la tarea autorizada. BIPIA estudia este problema en distintos contextos de uso. Milani, Franzoni y Florindi muestran, en evaluaciones de CV, que un modelo puede avisar que detectó una instrucción y aun así producir una valoración sesgada. En un RAG normativo importa observar tanto la advertencia como la fidelidad de la respuesta a la consulta y a las fuentes. [Yi et al. (2025)][yi2025bipia], [Milani et al. (2026)][milani2026ipi].

El envenenamiento del corpus también puede alterar una respuesta mediante hechos falsos o evidencia conflictiva. PoisonedRAG, RAGForensics, RAGuard y RADE son antecedentes para estudiar la calidad de la evidencia recuperada, el costo del filtrado y la pérdida de fuentes útiles. SD-RAG, por su parte, estudia divulgación selectiva ante intentos de extraer información. Estos trabajos delimitan problemas relacionados con objetivos y métricas propios. [Zou et al. (2025)][zou2025poisonedrag], [Zhang et al. (2025)][zhang2025ragforensics], [Cheng et al. (2025)][cheng2025raguard], [Yin et al. (2027)][yin2027rade], [Al Masoud et al. (2026)][almasoud2026sdrag].

## Separación y detección

Spotlighting evalúa marcas de procedencia del texto externo. StruQ combina una interfaz estructurada con un modelo ajustado para distinguir instrucciones y datos. SEP mide por separado la capacidad de seguir una orden autorizada y la capacidad de ignorarla cuando aparece como dato. En conjunto, estos trabajos motivan una condición de referencia con separación explícita y una evaluación que observe si el usuario sigue recibiendo una respuesta útil. El grado de protección esperado depende del modelo y del mecanismo empleado. [Hines et al. (2024)][hines2024spotlighting], [Chen et al. (2025), StruQ][chen2025struq], [Zverev et al. (2025)][zverev2025sep].

PromptShield e InstructDetector evalúan detectores especializados. Attention Tracker examina señales internas del modelo y CachePrune modifica la caché KV para tratar el contexto como datos. El trabajo de Chen et al. sobre detección y eliminación estudia el equilibrio entre retirar instrucciones y preservar contenido. InjecGuard documenta el riesgo de bloquear texto legítimo por su vocabulario. Para un corpus normativo, ese riesgo es relevante porque los propios reglamentos contienen mandatos y prohibiciones. [Jacob et al. (2025)][jacob2025promptshield], [Wen et al. (2025)][wen2025instructdetector], [Hung et al. (2025)][hung2025attentiontracker], [Wang et al. (2026)][wang2026cacheprune], [Chen et al. (2025), detección y eliminación][chen2025detectremove], [Li y Liu (2025)][li2025injecguard].

Jatmo especializa modelos en tareas concretas. SecAlign y The Instruction Hierarchy estudian cambios en el entrenamiento para priorizar instrucciones legítimas. Otros trabajos evalúan validación en inferencia o arquitecturas multicapa, con costos y requisitos distintos. Estas alternativas informan el diseño futuro y ayudan a identificar dependencias de entrenamiento, acceso al modelo y cómputo. [Piet et al. (2024)][piet2024jatmo], [Chen et al. (2025), SecAlign][chen2025secalign], [Wallace et al. (2024)][wallace2024hierarchy], [Chen et al. (2025), defensa en inferencia][chen2025defense], [Gokcimen y Das (2025)][gokcimen2025seguridad], [Alzahrani (2026)][alzahrani2026promptguard].

## Evaluación y transferencia a la UNSA

Liu et al. distinguen desempeño de la tarea legítima, cumplimiento de instrucciones inyectadas y errores del detector. Rag ’n Roll muestra por qué en RAG conviene evaluar desde la recuperación hasta la respuesta y registrar los casos ambiguos. AgentDojo y su replicación por Khan et al. aportan comparaciones de seguridad y utilidad en agentes. Task Shield, MELON y el análisis de resultados de herramientas se apoyan también en tareas con herramientas. Sus resultados orientan el protocolo de evaluación y su transferencia a respuestas documentales debe verificarse. TrustTrace aporta criterios para reconstruir de qué fuente y etapa provino una influencia. [Liu et al. (2024)][liu2024benchmark], [De Stefano et al. (2024)][destefano2024ragnroll], [Debenedetti et al. (2024)][debenedetti2024agentdojo], [Khan et al. (2026)][khan2026replication], [Jia et al. (2025)][jia2025taskshield], [Zhu et al. (2025)][zhu2025melon], [Yu et al. (2026)][yu2026toolparsing], [Chen y Lu (2026)][chen2026trusttrace].

La brecha del proyecto es medir si una defensa ligera reduce el desvío de respuestas sobre reglamentos de la UNSA en español, manteniendo la recuperación y el uso de evidencia útil. La comparación pareada A/B/C permite estudiar esa pregunta con el mismo recuperador, conjunto de casos y modelo por corrida. El impacto del OCR, las relaciones normativas y los falsos positivos en textos legítimos requiere pruebas propias. El [baseline offline](../BASELINE_OFFLINE.md) documenta el prototipo y sus resultados de recuperación y detección. La evaluación del efecto sobre las respuestas del LLM real sigue pendiente. La relación entre la evidencia y cada decisión del proyecto se detalla en [Decisiones de diseño](decisiones_de_diseno.md).

[yi2025bipia]: https://dl.acm.org/doi/10.1145/3690624.3709179
[milani2026ipi]: https://link.springer.com/article/10.1007/s00521-026-12266-x
[zou2025poisonedrag]: https://www.usenix.org/conference/usenixsecurity25/presentation/zou-poisonedrag
[zhang2025ragforensics]: https://dl.acm.org/doi/10.1145/3696410.3714756
[cheng2025raguard]: https://doi.org/10.1109/BigData66926.2025.11402647
[yin2027rade]: https://www.sciencedirect.com/science/article/pii/S095741742602806X
[almasoud2026sdrag]: https://www.sciencedirect.com/science/article/pii/S0957417426020646
[hines2024spotlighting]: https://ceur-ws.org/Vol-3920/paper03.pdf
[chen2025struq]: https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe
[zverev2025sep]: https://proceedings.iclr.cc/paper_files/paper/2025/hash/a77eadda332b6d4a9ae1e0e4024555f2-Abstract-Conference.html
[jacob2025promptshield]: https://dl.acm.org/doi/10.1145/3714393.3726501
[wen2025instructdetector]: https://aclanthology.org/2025.findings-emnlp.1060/
[hung2025attentiontracker]: https://aclanthology.org/2025.findings-naacl.123/
[wang2026cacheprune]: https://aclanthology.org/2026.acl-long.70/
[chen2025detectremove]: https://aclanthology.org/2025.acl-long.890/
[li2025injecguard]: https://arxiv.org/abs/2410.22770v3
[piet2024jatmo]: https://link.springer.com/chapter/10.1007/978-3-031-70879-4_6
[chen2025secalign]: https://dl.acm.org/doi/10.1145/3719027.3744836
[wallace2024hierarchy]: https://arxiv.org/abs/2404.13208v1
[chen2025defense]: https://aclanthology.org/2025.acl-long.897/
[gokcimen2025seguridad]: https://www.sciencedirect.com/science/article/pii/S111001682500328X
[alzahrani2026promptguard]: https://www.nature.com/articles/s41598-025-31086-y
[liu2024benchmark]: https://www.usenix.org/conference/usenixsecurity24/presentation/liu-yupei
[destefano2024ragnroll]: https://arxiv.org/abs/2408.05025v2
[debenedetti2024agentdojo]: https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html
[khan2026replication]: https://www.mdpi.com/2073-431X/15/9/570
[jia2025taskshield]: https://aclanthology.org/2025.acl-long.1435/
[zhu2025melon]: https://proceedings.mlr.press/v267/zhu25z.html
[yu2026toolparsing]: https://arxiv.org/abs/2601.04795v1
[chen2026trusttrace]: https://ieeexplore.ieee.org/document/11664419/
