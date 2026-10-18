# Seguridad

## Reportar una vulnerabilidad
Abre un aviso privado en GitHub (Security > Report a vulnerability) o escribe al autor por el perfil de GitHub de este repositorio. Por favor no publiques el detalle en un issue abierto. Responderemos en cuanto sea posible.

## Política de secretos
- Las claves (`LLM_API_KEY`, `APIFY_TOKEN`, `HF_TOKEN`, `DJANGO_SECRET_KEY`) viven solo en variables de entorno; `.env` está en `.gitignore`. `.env.example` trae nombres, nunca valores.
- Si una clave se filtra, se revoca primero y se limpia el historial después.
- `verify.sh` revisa que `data/radar.json` y `data/snapshots/` no contengan emails ni handles de terceros.

## Superficie de la app
Autoescape de Django, CSRF activo, límite por IP en `/analizar/`, y el texto pegado por el usuario se trata como dato no confiable.
