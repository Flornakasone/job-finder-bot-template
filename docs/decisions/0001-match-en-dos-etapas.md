# 0001 · Match en dos etapas: gaps locales + LLM para el top 10

**Estado:** aceptada · **Fecha:** 2026-11-02 · **Issues:** #14, #15, #16

## Contexto
El % de match medía **afinidad de tema** (embeddings + skills + rol), no si cumplo los requisitos.
Hallazgo en producción: un aviso de QA para Dynamics 365 salió con **100%** en el bot y con **~45%**
en un evaluador de CV, porque pedía testing de CRM y automatización de UI que no tengo.

La opción obvia es "que un LLM compare el CV con cada aviso", pero tiene dos límites:

| Límite | Detalle |
|---|---|
| Privacidad | El CV nunca sale de GitHub. A servicios externos solo va un perfil anonimizado. |
| Costo / cupo | El free tier del LLM no alcanza para ~300 avisos por día. |

## Decisión
Un embudo de dos etapas:

1. **Local, sobre todos los avisos (gratis, sin red):**
   `gaps = requisitos detectados en el aviso − mis skills`
   - `config/tech.txt`: vocabulario genérico de tecnologías (no dice nada sobre mí).
   - `config/skills.txt`: lo que sé. Cuando aprendo algo, lo agrego y deja de ser gap.
   - Un gap pedido como obligatorio resta puntos (con tope). Si es "plus" o "nice to have", no resta.
2. **LLM, solo sobre el top 10:** evalúa requisitos como un recruiter y agrega "💡 Aporto" / "⚠️ Te falta".
   - Recibe solo el perfil anonimizado y el aviso, ya limpio por el integrity gate (#15).
   - Si el LLM falla o no hay cupo, el resumen sale igual.

## Alternativas descartadas
- **Lista manual de "lo que no tengo"** (`gaps.txt`): define el perfil por la negativa y se desactualiza.
- **LLM sobre todos los avisos:** excede el free tier.
- **Mandar el CV completo al LLM:** viola la regla de privacidad.

## Consecuencias
- ✅ El ranking refleja los requisitos, no solo el tema, sin costo y sin exponer datos.
- ✅ La etapa local filtra antes y mejora la calidad del top 10 que recibe el LLM.
- ⚠️ `tech.txt` hay que mantenerlo: un requisito que no esté en el vocabulario no se detecta.
- ⚠️ La detección de obligatorio vs deseable es por frase y puede fallar; se cubre con tests de regresión con avisos reales.
