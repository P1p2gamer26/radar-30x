"""Verificación de cifras de los guiones (sin red, sin LLM)."""
from radar.verificar import limpiar_guion, verificar_guion

EV = ["Solo 25.9 % de las empresas en Colombia usa IA", "Raised $50 million; app at $210,364 ARR", "gastó $24,000 en el experimento"]


def test_extraccion_y_normalizacion():
    g = {"hook": "En Colombia solo el 25,9% usa IA", "cta": "Una ronda de US$50 millones y 210 mil de ingresos, 24.000 dólares"}
    v = verificar_guion(g, EV)
    assert (v["cifras"], v["verificadas"], v["sin_respaldo"]) == (4, 4, [])


def test_ejemplo_no_es_cifra():
    v = verificar_guion({"ejemplo": "Por ejemplo, un equipo de 10 personas ahorra tiempo"}, EV)
    assert v["cifras"] == 0 and v["ejemplos"] == ["10 personas"]
    # un porcentaje inventado nunca es ejemplo
    assert verificar_guion({"hook": "Por ejemplo, ahorra 40% del tiempo"}, EV)["sin_respaldo"] == ["40%"]


def test_sin_respaldo_se_quita():
    g = {"hook": "Hola", "cta": "x", "duration": "45 s", "beats": [
        {"texto": "a", "voz": "El 25,9% usa IA."}, {"texto": "b", "voz": "Crece 300%. Es rápido."},
        {"texto": "c", "voz": "Sin cifra"}, {"texto": "d", "voz": "Otra con 77% inventado"}]}
    limpio, acc = limpiar_guion(g, EV)
    assert limpio["beats"][1]["voz"] == "Es rápido."  # frase quitada
    assert len(limpio["beats"]) == 3 and acc  # el beat con cifra inventada se quita (mínimo 3)
    assert verificar_guion(limpio, EV)["sin_respaldo"] == []
