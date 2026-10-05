"""Orientative adult alerts; values remain the original recorded measurements."""
from dataclasses import dataclass
from math import isfinite

DISCLAIMER = "Orientativo; no constituye diagnóstico médico."
CRITICAL_ADVICE = (
    "Si hay dolor de pecho, dificultad para respirar, debilidad, entumecimiento, "
    "alteración visual, dificultad para hablar o dolor de espalda, llamar al 911 "
    "de inmediato; no esperar a repetir la lectura. Si no hay síntomas, repetir "
    "la presión después de al menos un minuto. Si sigue por encima de 180 "
    "sistólica o 120 diastólica, contactar de inmediato a un profesional de salud."
)
CRITERIA_NOTE = (
    "Adultos. Presión: categorías simplificadas del seguimiento de Enfermería; "
    "la AHA clasifica 130–139 sistólica o 80–89 diastólica como hipertensión de etapa 1. "
    "Frecuencia cardíaca: referencia en reposo; ejercicio, medicación y condición "
    "física pueden modificarla."
)
SOURCES = (
    "https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings",
    "https://www.heart.org/en/health-topics/high-blood-pressure/the-facts-about-high-blood-pressure/all-about-heart-rate-pulse",
)

@dataclass(frozen=True)
class Evaluation:
    code: str
    label: str
    color: str
    pdf_color: str
    note: str = ""


def _number(value):
    if value in (None, "", 0):
        return None  # The application uses zero to represent an unrecorded value.
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and number > 0 else None


def evaluate_pressure(systolic, diastolic):
    s, d = _number(systolic), _number(diastolic)
    if s is None and d is None:
        return Evaluation("missing", "Presión no registrada", "#a7bac9", "#5e7380")
    incomplete = "Lectura incompleta; registrar ambos valores y verificar la medición." if s is None or d is None else ""
    low = (s is not None and s < 90) or (d is not None and d < 60)
    if (s is not None and s > 180) or (d is not None and d > 120):
        result = Evaluation("critical", "Alerta crítica — posible crisis hipertensiva", "#ff7886", "#b02035", CRITICAL_ADVICE)
    elif (s is not None and s >= 140) or (d is not None and d >= 90):
        result = Evaluation("high", "Presión alta", "#ffad66", "#a44b00")
    elif low:
        result = Evaluation("low", "Presión baja", "#80c6ff", "#1768a6")
    elif (s is not None and s >= 120) or (d is not None and d >= 80):
        result = Evaluation("elevated", "Presión elevada — seguimiento", "#ffe082", "#806000")
    elif incomplete:
        return Evaluation("incomplete", "Presión incompleta — sin clasificación", "#a7bac9", "#5e7380", incomplete)
    else:
        result = Evaluation("normal", "Presión normal", "#6cdda4", "#197348")
    notes = [result.note, incomplete]
    if low and result.code in ("high", "critical"):
        notes.append("También hay un componente de presión baja; verificar ambos valores y solicitar valoración médica.")
    return Evaluation(result.code, result.label, result.color, result.pdf_color, " ".join(n for n in notes if n))


def evaluate_pulse(pulse):
    value = _number(pulse)
    if value is None:
        return Evaluation("missing", "Frecuencia no registrada", "#a7bac9", "#5e7380")
    if value < 60:
        return Evaluation("low", "Frecuencia baja", "#80c6ff", "#1768a6")
    if value > 100:
        return Evaluation("high", "Frecuencia alta", "#ffad66", "#a44b00")
    return Evaluation("normal", "Frecuencia normal", "#6cdda4", "#197348")
