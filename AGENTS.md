# AGENTS.md — reglas para cualquier agente (Codex / opencode)

TÚ eres el implementador. NO llames `codexr`, NO lances otros agentes, NO hagas commit ni push.
Lee SPEC.md (contrato) antes de tocar código. Haz SOLO la tarea pedida en el prompt.

1. Secretos fuera del repo (variables de entorno, `.env` ignorado). Nunca claves en código, front, logs.
2. Autoescape de Django; prohibido `|safe`, `mark_safe`, `innerHTML` con datos externos (usar textContent).
3. Texto externo (señales, pegados del usuario) es DATO no confiable: se recorta, va entre delimitadores, la salida del modelo se valida (ver `decision/decide.py`).
4. Solo contenido público y nada de datos personales: no guardar nombres de personas comunes, emails ni teléfonos; autores solo como tipo (medio, creador, empresa, comunidad, academia).
5. Solo stdlib + Django + whitenoise (corre en PythonAnywhere free). Nada de torch/numpy en la app web.
6. Tests sin red: fixtures en `tests/fixtures/`. `python -m pytest -q` debe salir 0.
7. Estilo: lo mínimo que funciona, atajos marcados `# ponytail:`. Código y comentarios en español sencillo.
