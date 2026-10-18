# Contribuir

## Correr las pruebas
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DECISION_MODE=replay DJANGO_DEBUG=1          # Windows: set VAR=valor
python -m pytest -q
bash verify.sh                                       # pruebas + contrato de data/radar.json + sin datos personales
```
Las pruebas no usan red: trabajan con `tests/fixtures/` y los snapshots de `data/`.

## Reglas de estilo (de `AGENTS.md`)
1. Secretos solo en variables de entorno (`.env` está ignorado). Nunca en código, front ni logs.
2. Autoescape de Django; nada de `|safe`, `mark_safe` ni `innerHTML` con datos externos (usar `textContent`).
3. Todo texto externo es dato no confiable: se recorta y la salida del modelo se valida.
4. Solo contenido público y sin datos personales; los autores se guardan como tipo, no como persona.
5. Solo stdlib + Django + whitenoise: nada de torch/numpy en la app web.
6. Lo mínimo que funciona; los atajos se marcan con `# ponytail:`. Código y comentarios en español sencillo.

## Pull requests
Una idea por PR, con su prueba. Las cifras del README salen de `data/*.json`; no se escriben a mano.
