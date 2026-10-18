## Qué cambia

## Cómo se probó
- [ ] `DECISION_MODE=replay python -m pytest -q` sale 0
- [ ] `bash verify.sh` sale 0
- [ ] Sin secretos, sin datos personales, sin `|safe` ni `innerHTML` con datos externos
- [ ] Si cambia cifras, se regeneró con `python manage.py readme_resultados`
