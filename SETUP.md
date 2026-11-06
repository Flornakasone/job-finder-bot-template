# SETUP · Armá tu propio bot de búsqueda laboral

Tiempo: **20–30 minutos**. Costo: **USD 0**. No hace falta programar.

Al final vas a recibir cada mañana en Telegram las ofertas nuevas que encajan con vos,
ordenadas por % de match y (opcional) con una evaluación de IA: si te conviene postularte,
qué requisitos cumplís y cuáles te faltan.

> **¿Usás un asistente de IA (Claude, ChatGPT, Gemini…)?** Pasale este archivo y escribile:
> *"Leé SETUP.md y guiame paso a paso para armar mi bot."* Las instrucciones para el asistente
> están al final ([Para asistentes de IA](#para-asistentes-de-ia)).

---

## Qué vas a necesitar

| | Para qué | ¿Obligatorio? |
|---|---|---|
| Cuenta de **GitHub** (gratis) | Ahí vive y corre el bot, todos los días | ✅ |
| **Telegram** en tu celular | Ahí te llega el resumen | ✅ |
| Cuenta de **Groq** (gratis) | Evaluación con IA ("Postulate / No te conviene", "Cumplo", "Falta") | Opcional |

---

## Paso 1 · Tu copia privada del bot (3 min)

1. Entrá al repo del template y apretá **Use this template → Create a new repository**.
2. Nombre: el que quieras (ej. `mi-job-bot`).
3. Elegí **Private**. ⚠️ Importante: tu configuración (rubro, skills, empresas) se guarda en
   el repo; si es privado, nadie más la ve.
4. **Create repository**.

> ¿Por qué "Use this template" y no "Fork"? Porque un fork de un repo público es público.

---

## Paso 2 · Tu bot de Telegram (5 min)

1. En Telegram, abrí **@BotFather** → `/newbot` → elegí nombre y usuario (tiene que terminar en `bot`).
2. BotFather te da un **token** (algo como `123456789:AAH...`). Guardalo: es tu `TELEGRAM_TOKEN`.
   🔒 Es como una contraseña: no lo compartas ni lo pegues en ningún chat.
3. Abrí tu bot nuevo y mandale **"hola"**.
4. En el navegador abrí (reemplazando `TU_TOKEN`):
   `https://api.telegram.org/botTU_TOKEN/getUpdates`
5. Buscá `"chat":{"id":` → ese número es tu `TELEGRAM_CHAT_ID`.
   Si ves `"result":[]`, volvé a mandarle "hola" al bot y recargá.

---

## Paso 3 · Tu configuración: la carpeta `me/` (10 min)

Todo lo tuyo vive en `me/`. Para editar sin instalar nada:
en tu repo, apretá la tecla **`.`** (punto) → se abre un editor en el navegador.

1. Copiá la carpeta `templates/me` como `me` (en el editor: creá la carpeta `me/` y
   copiá adentro los 5 archivos de `templates/me/`, sin el README).
2. Editá cada archivo:

| Archivo | Qué poner | Ejemplo |
|---|---|---|
| `keywords.txt` | Palabras que tiene que tener el **título** de la oferta | `ux`, `product designer`, `diseñador` |
| `skills.txt` | Tus skills (suman al % de match) | `figma`, `user research`, `prototipado` |
| `tech.txt` | Herramientas/requisitos típicos de tu área. Lo que pidan y no esté en `skills.txt` resta puntos y aparece en el reporte semanal | `sketch`, `adobe xd`, `html`, `css` |
| `empresas.txt` | (Opcional) Portales de empresas que te interesan | ver instrucciones adentro del archivo |
| `settings.toml` | Ubicación, idiomas, roles prioritarios, piso de % | ver abajo |

### `settings.toml`: lo más importante

```toml
[location]
# Para trabajos remotos: además de "worldwide/anywhere/global", ¿qué ubicaciones te sirven?
accepted = ["argentina", "latam", "buenos aires"]       # ej. España: ["spain", "europe", "emea"]
# ¿Dónde aceptás presencial o híbrido?
onsite_ok = ["caba", "buenos aires"]                    # ej. ["madrid"]

[filters]
spoken_languages = ["Spanish", "English"]               # descarta títulos que pidan otros idiomas
title_region_blocklist = ["US", "USA", "United States", "UK", "Canada"]   # "solo US", etc.

[[roles]]               # el PRIMER grupo que aparezca en el título define cuánto suma el rol
weight = 1.0
words = ["product designer", "ux designer"]

[[roles]]
weight = 0.6
words = ["ui designer", "graphic designer"]
```

3. Guardá y hacé **commit** (en el editor web: ícono de ramas a la izquierda → mensaje → ✓).

---

## Paso 4 · Tu perfil para el % de match (5 min)

Escribí un texto corto con lo que hacés. **Sin nombre, email, teléfono, LinkedIn ni empresas.**

```
Diseñadora UX semi senior, 4 años de experiencia.
Investigación con usuarios, prototipado en Figma, diseño de apps mobile, design systems.
Sector: e-commerce y salud. Busco: UX/Product Designer, remoto o híbrido.
```

Este texto es tu `PROFILE_TEXT`: se usa **dentro de GitHub** y nunca se manda a ningún servicio.

---

## Paso 5 · (Opcional) Evaluación con IA (5 min)

1. Creá una cuenta en **console.groq.com** (sin tarjeta).
2. **Settings → Data Controls → Zero Data Retention: activado** (Groq no guarda lo que le mandás).
3. **API Keys → Create API Key** → copiala (se muestra una sola vez). Es tu `GROQ_API_KEY`.
4. Escribí una versión **más general** de tu perfil: es lo único que sale de GitHub.
   Sin nombres de empresas, productos internos ni nada que te identifique. Es tu `LLM_PROFILE`.

Si salteás este paso, el bot funciona igual (sin las líneas de IA).

---

## Paso 6 · Cargar los secretos (3 min)

En tu repo: **Settings → Secrets and variables → Actions → New repository secret**.
Uno por uno:

| Nombre | Valor | ¿Obligatorio? |
|---|---|---|
| `TELEGRAM_TOKEN` | El token del Paso 2 | ✅ |
| `TELEGRAM_CHAT_ID` | El número del Paso 2 | ✅ |
| `PROFILE_TEXT` | Tu perfil del Paso 4 | Recomendado (sin él, ordena por fecha) |
| `GROQ_API_KEY` | La key del Paso 5 | Opcional |
| `LLM_PROFILE` | El perfil general del Paso 5 | Opcional |

🔒 Los secretos no se ven nunca más, ni en los logs: GitHub los reemplaza por `***`.

---

## Paso 7 · Primera prueba (5 min)

1. Pestaña **Actions** → si pregunta, **I understand… enable workflows**.
2. **Job bot diario → Run workflow** → tildá **Forzar envío** → **Run workflow**.
3. En ~5–8 minutos te llega el resumen a Telegram. 🎉

Desde ahí corre solo todos los días a la madrugada (hora Argentina).
Para cambiar el horario: `.github/workflows/daily.yml`, líneas `cron` (están en hora UTC).

---

## Ajustar con el uso

| Si… | Cambiá… |
|---|---|
| Te llegan rubros que no querés | Sacá palabras de `me/keywords.txt` |
| No te llega casi nada | Sumá palabras a `keywords.txt` o bajá `min_score` en `settings.toml` |
| El % no refleja lo que sabés | Sumá skills a `me/skills.txt` |
| Querés seguir una empresa | Una línea en `me/empresas.txt` |
| Cambiaste de búsqueda | Actualizá el secreto `PROFILE_TEXT` |

---

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| No llega nada a Telegram | Token o chat_id mal copiados | Revisá los secretos (Paso 6) y que le hayas escrito "hola" al bot |
| El log dice "no existe la carpeta me/" | Falta el Paso 3 | Copiá `templates/me` a `me/` |
| "Hoy no pude leer ninguna fuente" | Las fuentes no respondieron | Se reintenta solo al día siguiente |
| La prueba manual dice "ya se mandó" | Ya se envió el resumen de hoy | Tildá **Forzar envío** |
| No aparecen líneas de IA | Falta `GROQ_API_KEY` o `LLM_PROFILE` | Paso 5 y 6 |

---

## Para asistentes de IA

Instrucciones para el asistente que guía a la persona:

1. **Nunca pidas que pegue en el chat** el token, el chat_id, la API key ni su perfil completo.
   Indicale que los cargue directamente en GitHub Secrets (Paso 6).
2. Hacé los pasos **en orden, de a uno**, y esperá confirmación antes de seguir.
3. En el Paso 3, **entrevistala** para armar `me/`: rubro y puestos que busca, skills,
   herramientas típicas de su área, país/ciudad, si acepta presencial o híbrido y dónde,
   idiomas que habla. Proponé el contenido de cada archivo y que ella lo revise.
4. Para el perfil (Pasos 4 y 5) ayudala a **sacar datos que la identifiquen**:
   nombre, contacto, empresas, productos internos, fechas exactas.
5. Si no es de un área técnica, adaptá `tech.txt` a su área (ej. diseño, marketing, ventas).
6. No inventes datos de la persona: si algo no lo sabés, preguntá.
