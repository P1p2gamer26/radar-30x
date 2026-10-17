"""Taxonomía del radar: temas, formatos, ganchos y tipos de autor.

Los temas salen de la investigación (hackaton x30/radar/investigacion-fuentes.md §6),
pensados para ejecutivos de LatAm aprendiendo IA. Keywords en minúsculas, sin tildes.
"""
import re
import unicodedata

TOPICS = {
    "agentes-ia": {"name": "Agentes de IA", "wiki": ["AI_agent", "Model_Context_Protocol"],
                   "keywords": ["agentes de ia", "agente de ia", "agentic", "agente autonomo", "ai agent", "ai agents",
                                "agents", "agentic workflows", "mcp", "model context protocol", "multi-agent"]},
    "copilotos": {"name": "Copilotos y asistentes de trabajo", "wiki": ["Microsoft_Copilot", "ChatGPT"],
                  "keywords": ["copiloto", "copilot", "asistente de ia", "ai assistant", "chatgpt", "microsoft 365 copilot",
                               "gemini for workspace", "claude"]},
    "ia-ventas": {"name": "IA en ventas", "wiki": ["Sales_intelligence"],
                  "keywords": ["ventas con ia", "prospeccion", "crm", "ai sales", "sdr", "outbound", "lead generation",
                               "salesforce", "hubspot", "leads"]},
    "ia-marketing": {"name": "IA en marketing y contenido", "wiki": ["Generative_engine_optimization"],
                     "keywords": ["marketing con ia", "contenido generado", "ai marketing", "generative content", "seo",
                                  "geo", "generative engine optimization", "copywriting", "creadores de contenido"]},
    "ia-servicio": {"name": "IA en servicio al cliente", "wiki": ["Chatbot"],
                    "keywords": ["chatbot", "atencion al cliente", "customer support", "customer service", "voice agent",
                                 "voice agents", "call center", "contact center", "whatsapp"]},
    "ia-finanzas": {"name": "IA en finanzas", "wiki": ["Applications_of_artificial_intelligence"],
                    "keywords": ["finanzas", "contabilidad", "fraude", "finance ai", "fintech", "banca", "banking",
                                 "accounting", "pagos", "payments"]},
    "ia-talento": {"name": "IA en RR.HH. y talento", "wiki": ["Artificial_intelligence_in_hiring"],
                   "keywords": ["reclutamiento", "talento", "recursos humanos", "hr ai", "hiring", "recruiting",
                                "human resources"]},
    "automatizacion": {"name": "Productividad y automatización", "wiki": ["N8n", "Robotic_process_automation"],
                       "keywords": ["automatizar", "automatizacion", "no-code", "no code", "n8n", "automation", "zapier",
                                    "workflows", "make.com", "rpa", "productividad", "productivity"]},
    "regulacion-etica": {"name": "Regulación y ética de IA", "wiki": ["Artificial_Intelligence_Act", "Regulation_of_artificial_intelligence"],
                         "keywords": ["regulacion", "ley de ia", "sesgo", "privacidad", "ai act", "ai regulation",
                                      "ai safety", "etica", "ethics", "copyright", "derechos de autor", "lawsuit"]},
    "estrategia-adopcion": {"name": "Estrategia y adopción de IA", "wiki": ["Digital_transformation"],
                            "keywords": ["estrategia de ia", "transformacion digital", "adopcion", "ai strategy",
                                         "ai adoption", "enterprise ai", "ceo", "liderazgo", "leadership", "board"]},
    "roi-casos": {"name": "ROI y casos de uso empresariales", "wiki": ["Return_on_investment"],
                  "keywords": ["caso de uso", "casos de uso", "retorno", "implementacion", "ai roi", "roi", "use case",
                               "use cases", "pilot", "piloto", "ahorro", "productivity gains"]},
    "modelos-nuevos": {"name": "Modelos y lanzamientos", "wiki": ["Large_language_model", "GPT-5", "Gemini_(language_model)"],
                       "keywords": ["nuevo modelo", "lanzamiento", "gpt", "gpt-5", "openai", "anthropic", "gemini",
                                    "llama", "deepseek", "qwen", "mistral", "grok", "benchmark", "release"]},
    "vibe-coding": {"name": "Vibe coding: crear apps con IA", "wiki": ["Vibe_coding", "Cursor_(code_editor)"],
                    "keywords": ["vibe coding", "crear apps con ia", "cursor", "lovable", "claude code", "codex",
                                 "copilot coding", "bolt", "replit", "programar con ia", "ai coding"]},
    "datos-rag": {"name": "Datos, RAG y conocimiento corporativo", "wiki": ["Retrieval-augmented_generation"],
                  "keywords": ["base de conocimiento", "datos propios", "rag", "retrieval", "enterprise search",
                               "vector database", "embeddings", "knowledge base", "datos"]},
    "seguridad-riesgos": {"name": "Seguridad y riesgos de IA", "wiki": ["Prompt_injection", "Hallucination_(artificial_intelligence)"],
                          "keywords": ["alucinaciones", "alucinacion", "seguridad", "shadow ai", "hallucination",
                                       "data leak", "prompt injection", "jailbreak", "deepfake", "ciberseguridad",
                                       "security", "vulnerability"]},
    "empleo-futuro": {"name": "Empleo y futuro del trabajo", "wiki": ["Technological_unemployment"],
                      "keywords": ["reemplazo laboral", "futuro del trabajo", "habilidades", "future of work",
                                   "ai layoffs", "layoffs", "despidos", "upskilling", "empleo", "jobs"]},
    "startups-inversion": {"name": "Startups e inversión en IA", "wiki": ["AI_boom"],
                           "keywords": ["startup", "startups", "inversion", "ronda", "latam", "funding", "venture",
                                        "raises", "valuation", "valoracion", "unicornio", "ipo", "y combinator"]},
    "infra-costos": {"name": "Infraestructura y costos (chips, nube, tokens)", "wiki": ["Nvidia", "AI_data_center"],
                     "keywords": ["costo de tokens", "gpu", "gpus", "chips", "inference cost", "nvidia", "tokens",
                                  "data center", "centro de datos", "energia", "compute", "tpu"]},
    "video-voz": {"name": "Video, voz e imagen generativa", "wiki": ["Sora_(text-to-video_model)", "Veo_(text-to-video_model)"],
                  "keywords": ["video con ia", "voz clonada", "sora", "veo", "text-to-video", "midjourney", "elevenlabs",
                               "imagen generativa", "image generation", "avatar", "heygen", "runway"]},
    "educacion-ia": {"name": "Educación y formación en IA", "wiki": ["AI_literacy"],
                     "keywords": ["capacitacion en ia", "curso", "cursos", "ai training", "ai literacy", "aprender ia",
                                  "educacion", "education", "universidad", "bootcamp"]},
}

FORMATS = {
    "reel-cara": "Reel/short con cara hablando a cámara",
    "carrusel": "Carrusel / PDF documento",
    "post-texto": "Post de texto largo",
    "caso-paso-a-paso": "Caso de uso paso a paso / demo de proceso",
    "herramienta-60s": "Herramienta X en 60 segundos",
    "noticia-explicada": "Noticia explicada (qué significa para tu empresa)",
    "entrevista-clip": "Entrevista / clip de charla",
    "lista-ranking": "Lista / ranking",
    "opinion": "Opinión / predicción",
    "evento-live": "Live / webinar / evento",
}

HOOKS = {
    "resultado-numero": "Resultado cuantificado",
    "error-confesion": "Error o confesión",
    "pregunta": "Pregunta provocadora",
    "contrarian": "Contrarian / rompe un mito",
    "promesa-proceso": "Promesa de proceso (paso a paso)",
    "autoridad": "Autoridad / nombre propio",
    "urgencia-novedad": "Urgencia / novedad",
    "miedo-riesgo": "Miedo / riesgo",
    "lista-numerada": "Lista numerada",
    "antes-despues": "Antes / después",
}

AUTHOR_TYPES = ("medio", "creador", "empresa", "comunidad", "academia", "desconocido")


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes."""
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return sin_tildes.lower()


_PATRONES = {slug: re.compile(r"\b(" + "|".join(re.escape(k) for k in t["keywords"]) + r")\b")
             for slug, t in TOPICS.items()}


def match_topics(texto: str) -> list:
    """Slugs de los temas cuyas keywords aparecen como palabra completa, ordenados por nº de coincidencias."""
    t = normalizar(texto)
    hits = {slug: len(p.findall(t)) for slug, p in _PATRONES.items()}
    return [s for s, n in sorted(hits.items(), key=lambda kv: -kv[1]) if n]
