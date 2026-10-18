# Changelog

Generado desde `git log` (agrupado por día; más reciente primero).

## 2026-10-18

- feat: 'Jev abierto' medido: estudiante + DeepSeek gratis en cascada acierta 88,9 % (LLM solo 86,9 %, estudiante 79,7 %) llamando al LLM en 39 % de las piezas
- feat: 4 guiones por tema (reel, video largo, LinkedIn, recomendación) con pestañas y copiar; oportunidades por red (vacías con datos reales, sin inventar); hero con temas para preparar; clics atraviesan el texto del hero
- feat(ui): Estrellita acompaña en toda la app con ideas desde los datos; título del vuelo arriba a la izquierda sin etiquetas de anillo encima
- docs: Jev intentado por OpenCode Zen, sin acceso a tiempo; dicho con honestidad
- feat(ui): 'Las 3 preguntas, contestadas' con evidencia, mascota guía en el hero y hero legible en móvil
- feat: servidor MCP del radar (top_temas, tema, analizar) por stdio, solo stdlib
- ui: favicon = estrellita mascota de EstelarIA
- feat: comando backtest (corte día 7 → días 8-14 vs popularidad y azar) + plan para el cierre
- ux: el panel espera al vuelo y los rayos (2,3 s) para que primero se vea la animación
- feat(ui): paleta galaxia (negro, azul, morado) en toda la página, nebulosas vivas y órbita esférica en Explorar
- feat(modelo): 5.687 etiquetas (consenso de 2 LLM, hold-out fijo intacto): tema 80% top-1 / 98% top-3
- feat(ui): vuelo cinematográfico al tocar estrella/planeta (arco, FOV, warp, halo, rayos)
- feat(ui): modo Explorar el universo (girar, zoom, volar a planetas y estrellas), rayos estrella→redes de origen y paneles 'De dónde viene' / 'Qué trae esta red'
- fix: CSV sin comilla en celdas vacías; en el escáner 'Tu versión' primero y la idea del tema plegada y rotulada como de cero
- ui: puntajes en lenguaje simple en el panel y la página de tema
- feat: reels para los 20 temas, escáner con guion por formato y 'Tu versión' en slides/tomas, veredicto en lenguaje de acción, plan CSV con día y responsable + IMPORTDATA, 'Probar con tu pieza' en el hero, privacidad (IP, CSRF, contacto), costo a 50 cuentas
- fix(ui): variable duplicada que dejaba la home en blanco
- feat: escáner por plataforma con 'Tu versión' desde la pieza, plan semanal CSV/JSON + copiar para WhatsApp/Slack, privacidad visible, README con resultados generados, home con métricas del radar (75% / 95% top-3 / 92% seguro)
- feat: nuevo nombre EstelarIA (estrellas nacientes = temas tempranos)

## 2026-10-17

- feat(modelo): etiquetas de consenso de 2 LLM, embeddings multilingües + regresión logística (tema 74.5% top-1, 94.8% top-3, 91.6% cuando está seguro; base 24.8%), LR exportado a JSON para el escáner en Python puro
- feat: escáner coherente con el encaje de la pieza, home en 10 s (microguía, leyenda, 'Esta semana produce', comunidad como sensor), hold-out honesto (tema 61% vs 28%), costo Apify medido, fuentes explicadas con honestidad
- feat(ui): universo RadarIA (planetas = redes, estrellas = temas, órbitas de decisión, cometa al descubrir), nombres legibles de formato y gancho
- feat: modelo propio con ensamble NB+kNN (tema 61% vs base 29%), decisión honesta (solo temas tempranos y con encaje), guiones LLM para 20 temas + reel IG/TikTok, lenguaje simple, benchmark 30X claro, sin texto de terceros
- fix(privacidad): fuera URLs con @usuario de particulares, alias para canales que no son de 30X, nota legal de Apify; guiones LLM del top 10 regenerados
- docs+ui: README con Apify y captura, titular honesto (temas para producir ya), favicon
- feat(analizar): escáner con barrido, palabras que delatan el tema, medidores, guion de 30X, piezas parecidas y benchmark
- feat: nuevo nombre RadarIA (radar + IA)
- feat: Instagram y TikTok públicos vía Apify (plan gratis, USD 0.55/semana), benchmark 30X multiplataforma, costo semanal en la home
- feat(ui): radar que descubre temas en vivo, rotando plataformas; evidencia con la mejor pieza de cada fuente (incl. LinkedIn)
- feat: LinkedIn vía Google News, calibración semanal relativa, encaje ejecutivo con afinidad 30X, guiones por tema con LLM, estudiante con validación cruzada, límite por IP en /analizar, datos reales
- feat(ui): temas como blips sobre el radar dentro de su anillo de decisión; halo fino
- feat: respaldo de modelo en el profesor, push del estudiante a Hugging Face, verify.sh y radar diario en Actions
- chore(deploy): sin collectstatic en PythonAnywhere free (whitenoise con finders)
- chore(deploy): DECISION_MODE=replay en producción
- feat(ui): dunas iluminadas, barrido de radar visible, color por etapa, etiquetas sin solapes, titular con plural
- feat(ui): escena 3D 'cielo de temas', ranking, panel de tema, analizar y cómo funciona (estilo 30X)
- chore(deploy): el servidor sigue origin/main
- fix(privacidad): quitar emails, URLs y @handles de descripciones de YouTube; snapshot saneado
- docs: README y licencia MIT
- chore: deploy PythonAnywhere; sacar .prompts del repo
- feat: estudiante Naive Bayes, build de radar.json, /analizar (comunidad como sensor), adaptación con LLM, tests
- feat: fuentes (HN, Google News, YouTube RSS, Wikipedia), taxonomía de 20 temas, tendencias, etiquetado profesor
- chore: base del radar (decision de hackathon-starter, SPEC, AGENTS)
