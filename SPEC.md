# SPEC — Radar 30X (contrato para implementadores)

Pregunta que responde el producto: **"¿Cuáles son los 10 temas de IA que más están creciendo esta semana, por qué funcionan y cómo los adapta 30X para ejecutivos de LatAm?"**

## Estructura

```
config/            settings Django (env), urls
decision/          motor decide() (cascada LLM -> regla, record/replay) — YA EXISTE, reutilizar
radar/             app principal
  taxonomy.py      TOPICS, FORMATS, HOOKS, AUTHOR_TYPES (dicts con slug, nombre, keywords es/en)
  collectors/      un módulo por fuente; cada uno expone fetch(now) -> list[Signal dict]
    hn.py          Hacker News Algolia
    gnews.py       Google News RSS (es-419/CO y en-US)
    youtube.py     RSS de canales (config/channels.json)
    wiki.py        Wikimedia pageviews (demanda diaria por tema)
  collect.py       orquesta collectors -> data/snapshots/YYYY-MM-DD.json
  label.py         etiqueta señales con decide() (profesor LLM) -> data/labels.json
  student.py       modelo propio (Naive Bayes multinomial, stdlib) entrenado con las etiquetas del profesor
  trend.py         series diarias, crecimiento, etapa (temprana/creciendo/saturada/bajando)
  build.py         arma data/radar.json (contrato abajo)
  management/commands/  collect, label, train_student, build_radar
  views.py         /, /tema/<slug>/, /analizar/, /como-funciona/, /api/radar.json
data/              snapshots, labels.json, student.json, radar.json (se versionan: la demo corre sin red)
```

## Signal (dict)

```json
{"id": "hn:123", "source": "hn|gnews|youtube|wiki|comunidad", "url": "https://...",
 "title": "...", "text": "primeros 500 chars o ''", "lang": "es|en",
 "published_at": "2026-10-15T13:00:00Z", "author_type": "medio|creador|empresa|comunidad|academia|desconocido",
 "metrics": {"points": 0, "comments": 0, "views": 0}, "query": "tema/consulta que lo trajo"}
```
Sin nombres de personas ni handles en `author_type`; `title` se guarda tal cual (público).

## Taxonomía (radar/taxonomy.py)
- TOPICS (~16): agentes-ia, ia-ventas-marketing, copilotos-productividad, automatizacion-procesos, ia-generativa-video, modelos-nuevos (lanzamientos GPT/Claude/Gemini/Llama), open-source-local, regulacion-etica, ia-finanzas, ia-salud, ia-educacion-talento, datos-estrategia, vibe-coding (programar con IA), seguridad-ia, robotica-hardware, roi-adopcion (casos de negocio, adopción en empresas). Cada uno: `name` (es), `keywords` (lista es+en, minúsculas), `wiki` (1-3 artículos de en.wikipedia para pageviews).
- FORMATS: reel-cara (persona hablando a cámara), tutorial-pantalla, carrusel-lista, noticia-explicada, caso-de-uso, opinion-polemica, entrevista-podcast, herramienta-demo, informe-datos, meme-humor.
- HOOKS: numero-dato, pregunta, promesa-ahorro (tiempo/dinero), miedo-urgencia ("te estás quedando atrás"), contraste-antes-despues, autoridad (empresa/persona conocida), lista-top, secreto-truco, noticia-ultima-hora, historia-personal.

## Decisión por tema (umbrales 0.80 / 0.50, como decide())
- `momentum` 0..1 = min(1, max(0, (growth-1)/1.5)) mezclado con z-score (ver trend.py).
- `exec_fit` 0..1 = promedio de la pregunta "¿le sirve a un ejecutivo LatAm aprendiendo IA?" sobre las señales del tema.
- `p = 0.5*momentum + 0.5*exec_fit` -> `Recomendar` (≥0.80, producir esta semana) / `Aprender` (≥0.50, monitorear) / `Descartar`.
- `reason`: frase en español que cita los números ("crece x2.3 vs su base, 9 de 12 piezas sirven a ejecutivos, formato ganador: caso-de-uso").

## Etapas (trend.py)
Serie diaria de 14 días por tema = suma de pesos de señales (peso = 1 + log1p(points+comments+views/100)).
`growth = (media últimos 3 días + 1) / (media de los 11 anteriores + 1)`; `z` = (media últ. 3 - media base)/ (desv base + 1).
- temprana: growth ≥ 1.5 y volumen total ≤ mediana de los temas (pocos lo están cubriendo)
- creciendo: growth ≥ 1.2
- saturada: volumen ≥ percentil 75 y growth < 1.2
- bajando: growth < 0.8
- estable: lo demás

## data/radar.json (contrato con el frontend)

```json
{"generated_at": "...", "week": "2026-W42", "window_days": 14,
 "sources": [{"name": "hn", "label": "Hacker News", "signals": 120}],
 "totals": {"signals": 900, "labeled": 900, "teacher_cost_usd": 0.41, "student_cost_usd": 0.0,
            "cost_per_signal_usd": 0.00045, "paid_alternative_usd_year": 12000},
 "student": {"accuracy_topic": 0.86, "accuracy_format": 0.7, "n_train": 700, "n_test": 200},
 "topics": [{
   "slug": "agentes-ia", "name": "Agentes de IA", "rank": 1,
   "stage": "temprana|creciendo|saturada|bajando|estable",
   "growth": 2.3, "z": 1.8, "volume": 42, "series": [14 números], "wiki_series": [14 números],
   "momentum": 0.87, "exec_fit": 0.81, "p": 0.84, "decision": "Recomendar|Aprender|Descartar",
   "reason": "...",
   "why": {"format_winner": "caso-de-uso", "hook_winner": "numero-dato", "best_day": "martes",
           "author_mix": {"medio": 0.5, "creador": 0.3}, "formats": {"caso-de-uso": 0.4}, "hooks": {"numero-dato": 0.3}},
   "top_signals": [{"title": "...", "url": "...", "source": "hn", "published_at": "...",
                    "metrics": {}, "format": "...", "hook": "...", "velocity": 12.5}],
   "adapt": {"title": "...", "hook": "primeros 3 s", "format": "reel-cara", "beats": ["...", "...", "..."], "cta": "..."}
 }]}
```
`topics` ordenado por `p` desc; el frontend muestra los 10 primeros.

## Modelos y costo
- Profesor: LLM OpenAI-compatible (9Router local, gratis; precio de referencia Claude Haiku para el costo "si fuera pago": env LLM_PRICE_IN_PER_1M / OUT). Solo corre en `label` (modo record); la demo usa replay.
- Estudiante: Naive Bayes multinomial en stdlib sobre tokens de título+texto, entrenado con etiquetas del profesor; se guarda en data/student.json y se publica en Hugging Face Hub. En /analizar: estudiante primero (costo 0); si su confianza < 0.5 y hay LLM -> profesor; si no -> regla por keywords.
