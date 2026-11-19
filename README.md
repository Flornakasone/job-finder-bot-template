# job-finder-bot 🤖📬

**Un agente de búsqueda laboral que diseñé con IA, para practicar desarrollo asistido por IA y aprender en el proceso.**

Todos los días revisa ~1.000 ofertas de empleo, se queda con las que encajan con vos y te manda un resumen a Telegram, con % de match y una evaluación de IA de qué requisitos cumplís y cuáles te faltan.

> **Sobre este proyecto.** No es una muestra de lo que sé programar: es una muestra de **cómo uso la IA como potenciador**.
> La IA escribió el código. Yo puse el criterio de QA y de producto: definí qué necesitaba y los criterios de aceptación,
> revisé cada cambio, encontré bugs, y verifiqué que lo que generaba la IA fuera correcto, seguro y respetara los términos de cada servicio.

```
🗂 06/11 · 10 ofertas nuevas (de 904 revisadas)

🟡 56% | QA Analyst Sr – Consultora Ejemplo
📍 Buenos Aires, Argentina (Presencial)
🗣 Inglés: no menciona
🧭 🟢 Postulate
✅ Cumplo: experiencia en testing funcional y de APIs, conocimientos de SQL
⚠️ Falta: Cypress (deseable)
🔗 https://… (vía Teamtailor)
```

**¿Lo querés para tu búsqueda?** Sirve para cualquier área y país → [SETUP.md](SETUP.md) (20–30 min, sin programar, USD 0).

---

## Qué hace

```
 7 fuentes + portales de empresas
            │  ~1.000 ofertas/día
            ▼
 Integrity gate ─── texto invisible, instrucciones ocultas para IA
            ▼
 Filtros ─────────── rubro, ubicación, idioma, inglés, estafas, "solo US"
            ▼
 Deduplicación ───── no repite ofertas (solo guarda hashes)
            ▼
 % de match ──────── embeddings locales + skills + rol − requisitos que faltan
            ▼
 Evaluación IA ───── solo el top 10: Postulate / Con reservas / No te conviene
            ▼
 Telegram ────────── resumen diario + reporte semanal de skills más pedidas
```

| Pieza | Detalle |
|---|---|
| **Fuentes** | Remotive, Jobicy, Himalayas, Get on Board, Remote OK, We Work Remotely + portales de empresas (Greenhouse, Lever, Ashby, Teamtailor). Solo APIs y feeds públicos, términos de uso verificados, con atribución |
| **Match** | Modelo de embeddings multilingüe que corre **dentro de GitHub Actions**: el perfil nunca sale de GitHub |
| **IA** | Groq (free tier, Zero Data Retention) recibe solo un perfil **generalizado** y avisos ya limpiados. Cada requisito que la IA dice que cumplís se **verifica en código** contra el texto del aviso ([ADR 0002](docs/decisions/0002-grounding-de-la-evaluacion-ia.md)) |
| **Reporte semanal** | "Playwright apareció en 14 avisos": qué aprender primero, con datos reales |
| **Infra** | GitHub Actions + Telegram. Costo: USD 0 |

---

## Mi rol: QA en un desarrollo asistido por IA

### Bugs y riesgos que encontré revisando lo que generaba la IA

| Pregunta que hice | Qué encontró |
|---|---|
| *"Si la API pide esperar 1 hora, ¿qué pasa con los 59 min de diferencia?"* | Reintentos inútiles ante un cupo diario agotado → ahora corta en el momento |
| *"¿Están mapeados los errores?"* | Todos los errores se trataban igual → tabla de decisión: cuáles cortan todo y cuáles saltean un aviso |
| *"La API key no debería mostrarse nunca"* | Tests en 3 capas: mensajes de error, tracebacks y body de la request |
| *"¿Qué pasa si falla el reporte semanal?"* | Habría duplicado el resumen diario al día siguiente |
| *Leyendo `main()`* | Un error que ningún test detectaba → test de humo de la CLI |
| *El 100% del bot vs. ~45% de un evaluador de CV* | El % medía afinidad, no requisitos → penalización por requisitos faltantes ([ADR 0001](docs/decisions/0001-match-en-dos-etapas.md)) |

### Cómo validé a la IA (en vez de creerle)

- **El LLM "inventaba" requisitos.** Para un aviso de Customer Experience respondió *"Cumplo: testing funcional, APIs REST, SQL, Jira, AWS"* y "Postulate": eran skills de mi perfil, no del aviso. Pedirle mejor no es un control; verificar sí → cada requisito tiene que ser una cita del aviso, el código descarta las que no aparecen, y sin requisitos verificados no puede decir "Postulate" ([ADR 0002](docs/decisions/0002-grounding-de-la-evaluacion-ia.md)).
- **Una IA sugirió 10 empresas con sus slugs: 2 eran falsos.** Lo detecté verificando cada una contra la API real antes de sumarla.
- **El LLM evaluó como "Postulate" un aviso sin descripción** (un embudo de capacitación paga). El modelo no sabe decir "no sé" → filtro de estafas y pendiente para v2.
- **La documentación de las APIs no coincidía con las respuestas reales** (Himalayas devolvía strings donde la doc decía objetos; Teamtailor sin namespace donde se esperaba). Los *contract checks* con respuestas reales lo detectaron.

### Estrategia de testing

- **Más de 500 tests**, todos sin internet ni servicios reales: *test doubles* para APIs, Telegram, el modelo y el LLM.
- **Contract checks** contra respuestas reales de cada fuente.
- **Valores límite** (piso de %, ventanas de días, reintentos), **regresiones** con avisos y salidas reales.
- **Seguridad:** prompt injection, texto invisible, HTML escondido, XXE en feeds XML, secretos con valores trampa que no pueden aparecer en ningún log.
- **Documentación testeada:** un test falla si un secreto del workflow no está explicado en [SETUP.md](SETUP.md).

---

## Privacidad y seguridad por diseño

- El CV y los datos personales **nunca** se publican: ni en logs, ni en commits, ni en mensajes de error.
- A servicios externos solo va un perfil anonimizado y generalizado.
- Para deduplicar se guardan solo hashes de ofertas.
- Nada de scraping que viole términos ni credenciales de plataformas: LinkedIn, Indeed y similares quedaron afuera a propósito.
- Avisos con instrucciones para una IA (*"ignore previous instructions"*) **nunca** llegan al LLM.

---

### Trazabilidad

Trabajé con un board de GitHub Projects: cada cambio nace en un issue con criterios de aceptación
y se cierra con un Pull Request revisado (`Closes #N`). El repo de desarrollo es privado porque
contiene mi configuración personal; el historial completo de PRs está en [docs/HISTORIAL.md](docs/HISTORIAL.md).

---

## Lo que aprendí

Git y Pull Requests con trazabilidad issue → PR · TDD · test doubles · contract testing · APIs REST y feeds RSS ·
GitHub Actions · idempotencia · embeddings · prompt injection · evaluación de salidas de LLMs ·
cómo trabajar con una IA: pedir, revisar, desafiar y verificar.

---

## Estructura

```
src/            código del bot
  sources/      una fuente por archivo (contrato: NAME + fetch())
config/         lo que sirve para cualquiera (excluded.txt)
templates/me/   ejemplos de configuración personal
me/             TU configuración (no viene en el template: la armás con SETUP.md)
docs/decisions/ decisiones técnicas (ADRs)
tests/          más de 500 tests
```

## Licencia

[MIT](LICENSE)
