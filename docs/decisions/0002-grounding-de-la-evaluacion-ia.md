# 0002 · No creerle al LLM: verificar cada requisito contra el aviso (grounding)

**Estado:** aceptada · **Fecha:** 2026-11-18 · **Issue:** #16 (seguimiento)

## Contexto
En producción, para un aviso de *Customer Experience Specialist*, la IA respondió:

```
38% · 🟢 Postulate
✅ Cumplo: testing funcional, APIs REST, SQL, BDD Gherkin, Jira, AWS
⚠️ Falta: nada importante
```

Ninguno de los 6 "Cumplo" aparece en el aviso: el modelo copió skills del **perfil**.
Además el veredicto contradecía el % y no detectó que el puesto pedía experiencia en CX / e-commerce.
El prompt ya decía "requisitos del aviso". Pedirlo mejor no alcanza: hay que **verificarlo**.

## Decisión
1. **Respuesta con evidencia:** el LLM devuelve cada requisito como **cita textual del aviso**
   (`{requisito, evidencia}` para lo que cumple, `{requisito, obligatorio}` para lo que falta).
2. **Validación en código (grounding):** cada cita tiene que estar en el aviso
   (≥ 80% de sus palabras, sin tildes/mayúsculas/conectores). Lo que no está se descarta.
3. **Coherencia:** si no queda ningún "Cumplo" verificable, el veredicto no puede ser "Postulate"
   → baja a "Postulate con reservas".
4. **Métrica:** el log muestra `ia_descartados=N` (requisitos inventados por el modelo).
5. **Modelo:** `gpt-oss-20b` → `gpt-oss-120b` (mismo cupo en el free tier, mejor razonamiento).

## Alternativas descartadas
- **Solo mejorar el prompt:** ya lo pedía y el modelo no lo cumplió. Un prompt no es un control.
- **Pedirle al LLM que se autoevalúe:** el mismo modelo que alucina no es un buen verificador.
- **Coincidencia textual exacta:** demasiado estricta; el modelo recorta o reordena frases.

## Consecuencias
- ✅ Una skill del perfil que el aviso no pide ya no puede aparecer como "Cumplo".
- ✅ La tasa de alucinación queda medida en cada corrida.
- ⚠️ El grounding valida que el requisito **exista en el aviso**, no que la persona **realmente lo cumpla**:
  eso sigue dependiendo del perfil. Por eso el veredicto es una guía, no una decisión.
- ⚠️ Un requisito parafraseado por el modelo puede descartarse de más (falso negativo). Se prefiere
  perder un ítem a mostrar uno inventado.
