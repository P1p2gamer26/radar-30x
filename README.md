# EstelarIA

> Estelar + IA: EstelarIA encuentra las estrellas nacientes del contenido de IA (los temas que recién empiezan a brillar) antes de que todos las copien.

**Qué temas de IA están despegando en redes, por qué funcionan y cómo los adapta 30X para ejecutivos de LatAm.**
Hackathon 30X · reto *Radar de contenido*.

- Demo: https://p1p2gamer26.pythonanywhere.com/
- Video (3 min): se agrega con la entrega

![EstelarIA: el radar descubre en vivo qué tema de IA despega y de qué plataforma viene](docs/hero.png)

## El problema
El equipo de media de 30X paga scraping (miles de USD al año) que solo trae datos. No dice **por qué** funcionó una pieza, si una tendencia **recién empieza o ya todos la copiaron**, ni si **le sirve a su audiencia**.

## Qué hace
Cada semana responde: *¿cuáles son los 10 temas de IA que más crecen, por qué y cómo los adaptamos?*

1. **Recolecta** señales públicas sin login: Hacker News (Algolia), Google News (es-419 y en), canales públicos de YouTube por RSS (incluidos los de 30X), páginas vistas de Wikipedia, posts públicos de LinkedIn indexados en Google News, y posts/reels públicos de Instagram y TikTok (30X, Andrés Bilbao y hashtags de IA) vía Apify.
2. **Etiqueta** una muestra con un LLM "profesor" barato: tema, formato, gancho, tipo de autor y si le sirve a un ejecutivo.
3. **Entrena un modelo propio** (`radar/student.py`) con las etiquetas donde un segundo LLM coincide con el profesor (consenso, `python manage.py review_labels`). Offline: embeddings multilingües + regresión logística clasifican el corpus al armar `radar.json`. En el servidor: regresión logística sobre TF-IDF exportada a JSON e inferida en Python puro (NB/kNN de respaldo), a **costo cero**.
4. **Mide crecimiento y etapa** por tema (`radar/trend.py`): crecimiento frente a su base, z-score y etapa (`temprana`, `creciendo`, `saturada`, `bajando`, `estable`). Así contesta si el tema recién empieza o ya todos lo copiaron.
5. **Decide** con umbrales trazables (`decision/decide.py`): `Recomendar` (≥ 0.80), `Aprender` (≥ 0.50) o `Descartar`. El motivo cita los números.
6. **Explica y adapta**: formato y gancho ganadores, mejor día y un guion corto para 30X (gancho de 3 s, beats, CTA).
7. **La comunidad como sensor**: en `/analizar` cualquiera pega una pieza pública de Instagram, TikTok o LinkedIn y el radar la clasifica al instante (escáner). Sirve para piezas que el equipo ve en su día a día y aún no están en el radar.

## Resultados

<!-- RESULTADOS -->
Corrida 2026-W42 (generada 2026-10-17; datos en `data/`, reproducible sin red). Generado por `python manage.py readme_resultados`.

- **Señales:** 5.718 (Hacker News 3.240, Google News 2.018, LinkedIn (vía Google News) 180, Instagram (vía Apify) 127, YouTube 108, TikTok (vía Apify) 45, Wikipedia 20).
- **Temas:** 20 analizados; 1 Recomendar (Educación y formación en IA), 5 Aprender, 14 Descartar.
- **Costo:** USD 0.55 por semana (scraping de Instagram/TikTok vía Apify) y USD 0.81 una sola vez por etiquetar 1.226 señales con el LLM (USD 0.000141 por señal); el estudiante clasifica a USD 0.00.
- **Modelo propio, tema** (hold-out fijo del 20 %, 234 piezas): top-1 **74 %**, top-3 95 %, cuando está seguro acierta 92 % y cubre el 62 % de las piezas; contra todas las etiquetas (incluidas las dudosas) 64 %; adivinar da 25 %.

| Tarea | Top-1 | Top-3 | Cuando está seguro (cobertura) | Contra todas | Base |
|---|---|---|---|---|---|
| Tema (radar, offline) | 74 % | 95 % | 92 % (62 %) | 64 % | 25 % |
| Formato (radar, offline) | 74 % | 93 % | 92 % (56 %) | 62 % | 53 % |
| Gancho (radar, offline) | 56 % | 85 % | 95 % (14 %) | 43 % | 16 % |
| Tema (escáner, servidor) | 71 % | 91 % | 93 % (19 %) | 61 % | 25 % |
<!-- /RESULTADOS -->

## Integraciones: sacar el plan de la semana
El plan (temas Recomendar + Aprender con etapa, por qué, guion, reel y plataforma) sale en dos formatos, siempre desde `data/radar.json`:

- `GET /api/semana.csv`: descarga el CSV (también el botón "Descargar plan (CSV)" de la home).
- `GET /api/semana.json`: lo mismo en JSON (`{"week": ..., "temas": [...]}`).
- Botón "Copiar para WhatsApp/Slack" en la home: resumen corto en texto.

**Notion o Google Sheets:** descarga el CSV e impórtalo (Notion: Importar > CSV; Sheets: Archivo > Importar). Para que se actualice solo en Sheets: `=IMPORTDATA("https://TU-DOMINIO/api/semana.csv")`.

**Webhook (Slack, Make, Zapier, n8n):** un cron semanal que haga GET al JSON y lo reenvíe, por ejemplo cada lunes 7:00:
```bash
0 7 * * 1  curl -s https://TU-DOMINIO/api/semana.json | curl -s -X POST -H "Content-Type: application/json" -d @- "$WEBHOOK_URL"
```

## Costo
Lo que cuesta cada corrida (por señal, profesor y estudiante) se ve en la home y en `data/radar.json` → `totals`. El estudiante clasifica gratis; solo la muestra del profesor tiene costo. La alternativa paga de referencia es de ~USD 3.000 al año (Apify, Exolyt, Sprout); las fuentes están en la página `/como-funciona/`.

## Cómo correrlo
```bash
python -m venv .venv && .venv/Scripts/activate   # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
set DJANGO_DEBUG=1                               # Linux/Mac: export DJANGO_DEBUG=1
python manage.py migrate
python manage.py runserver                       # http://127.0.0.1:8000
bash verify.sh                                   # tests + contrato de radar.json + sin datos personales
```
La demo corre **sin red**: lee `data/radar.json`, `data/student.json` y los snapshots versionados en `data/`.

Para actualizar los datos (con red):
```bash
python manage.py collect          # fuentes públicas -> data/snapshots/
python manage.py label            # profesor LLM (OpenAI-compatible, variables en .env.example)
python manage.py review_labels    # segundo LLM -> marca de consenso en labels.json
python manage.py train_student    # modelo propio -> data/student.json
python manage.py build_radar      # -> data/radar.json
python manage.py readme_resultados # reescribe la sección Resultados de este README
```
`.github/workflows/radar.yml` lo hace solo cada día a las 6:00 (Bogotá) con el estudiante, gratis.

## Estructura
| Ruta | Qué es |
|---|---|
| `radar/sources.py` | recolectores (HN, Google News, YouTube RSS, Wikipedia) |
| `radar/taxonomy.py` | temas, formatos, ganchos y tipos de autor |
| `radar/label.py` | profesor LLM con validación estricta del JSON |
| `radar/student.py` | modelo propio: NB/kNN + LR TF-IDF en JSON (Python puro) y embeddings+LR offline |
| `radar/trend.py` | crecimiento, z-score y etapa |
| `radar/build.py` | arma `data/radar.json` (contrato en `SPEC.md`) |
| `decision/decide.py` | motor de decisión con umbrales, regla de respaldo y registro |
| `radar/templates`, `radar/static` | web: escena 3D (Three.js) con los temas como estrellas sobre un radar |
| `deploy/` | despliegue en PythonAnywhere |

## Reglas que cumple
- Solo contenido público y sin login propio: Hacker News, Google News, YouTube y Wikipedia se leen por APIs o feeds públicos; Instagram y TikTok, por scraping de contenido público vía Apify (autorizado por la organización, plan gratis, ~USD 0.55 por semana), sin login y sin guardar usuarios ni texto de terceros; LinkedIn, por titulares públicos indexados en Google News. Nunca iniciamos sesión en esas redes.
- Sin datos personales: los autores se guardan solo como tipo (medio, creador, empresa, comunidad, academia).
- Sin secretos en el repo. `verify.sh` revisa que `radar.json` y `data/snapshots/*.json` no tengan emails ni handles de terceros (las URL con forma de email, como los message-id de listas de correo, se descartan al recolectar).

## Licencia
MIT
