# RadarIA

> Radar + IA: si un tema de IA se está moviendo, RadarIA lo ve venir antes de que todos lo copien.

**Qué temas de IA están despegando en redes, por qué funcionan y cómo los adapta 30X para ejecutivos de LatAm.**
Hackathon 30X · reto *Radar de contenido*.

- Demo: https://p1p2gamer26.pythonanywhere.com/
- Video (3 min): _pendiente_

## El problema
El equipo de media de 30X paga scraping (miles de USD al año) que solo trae datos. No dice **por qué** funcionó una pieza, si una tendencia **recién empieza o ya todos la copiaron**, ni si **le sirve a su audiencia**.

## Qué hace
Cada semana responde: *¿cuáles son los 10 temas de IA que más crecen, por qué y cómo los adaptamos?*

1. **Recolecta** señales públicas sin login: Hacker News (Algolia), Google News (es-419 y en), canales públicos de YouTube por RSS (incluidos los de 30X), páginas vistas de Wikipedia y posts públicos de LinkedIn indexados en Google News.
2. **Etiqueta** una muestra con un LLM "profesor" barato: tema, formato, gancho, tipo de autor y si le sirve a un ejecutivo.
3. **Entrena un modelo propio** (Naive Bayes en Python puro, `radar/student.py`) con esas etiquetas. Clasifica todo lo demás a **costo cero** y corre en el servidor gratuito.
4. **Mide crecimiento y etapa** por tema (`radar/trend.py`): crecimiento frente a su base, z-score y etapa (`temprana`, `creciendo`, `saturada`, `bajando`, `estable`). Así contesta si el tema recién empieza o ya todos lo copiaron.
5. **Decide** con umbrales trazables (`decision/decide.py`): `Recomendar` (≥ 0.80), `Aprender` (≥ 0.50) o `Descartar`. El motivo cita los números.
6. **Explica y adapta**: formato y gancho ganadores, mejor día y un guion corto para 30X (gancho de 3 s, beats, CTA).
7. **La comunidad como sensor**: en `/analizar` cualquiera pega una pieza pública de Instagram, TikTok o LinkedIn y el radar la clasifica. Cubre las redes que no se pueden recolectar sin violar sus términos.

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
python manage.py train_student    # modelo propio -> data/student.json
python manage.py build_radar      # -> data/radar.json
```
`.github/workflows/radar.yml` lo hace solo cada día a las 6:00 (Bogotá) con el estudiante, gratis.

## Estructura
| Ruta | Qué es |
|---|---|
| `radar/sources.py` | recolectores (HN, Google News, YouTube RSS, Wikipedia) |
| `radar/taxonomy.py` | temas, formatos, ganchos y tipos de autor |
| `radar/label.py` | profesor LLM con validación estricta del JSON |
| `radar/student.py` | modelo propio Naive Bayes (stdlib) |
| `radar/trend.py` | crecimiento, z-score y etapa |
| `radar/build.py` | arma `data/radar.json` (contrato en `SPEC.md`) |
| `decision/decide.py` | motor de decisión con umbrales, regla de respaldo y registro |
| `radar/templates`, `radar/static` | web: escena 3D (Three.js) con los temas como estrellas sobre un radar |
| `deploy/` | despliegue en PythonAnywhere |

## Reglas que cumple
- Solo contenido público y sin login. No evadimos el login de Instagram, TikTok ni LinkedIn.
- Sin datos personales: los autores se guardan solo como tipo (medio, creador, empresa, comunidad, academia).
- Sin secretos en el repo. `verify.sh` revisa que `radar.json` no tenga emails.

## Licencia
MIT
