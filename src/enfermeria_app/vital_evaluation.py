"""Orientative adult alerts; values remain the original recorded measurements."""
from dataclasses import dataclass
from math import isfinite

DISCLAIMER = "Orientativo; no constituye diagnóstico médico."
SEVERE_PRESSURE_REPEAT_ADVICE = (
    "Repetir la presión después de al menos un minuto. Si continúa por encima de "
    "180 mmHg sistólica o 120 mmHg diastólica, contactar de inmediato a un "
    "profesional de salud."
)
URGENT_PRESSURE_ADVICE = (
    "Hay síntomas de alarma asociados: buscar atención médica urgente y llamar al "
    "911. No esperar a repetir la lectura ni retrasar la atención."
)
CRITICAL_ADVICE = SEVERE_PRESSURE_REPEAT_ADVICE + " " + URGENT_PRESSURE_ADVICE
CRITERIA_NOTE = (
    "Adultos. Presión: se usa la categoría más alta entre sistólica y diastólica; "
    "una sola lectura no diagnostica hipertensión. Glucemia: los rangos automáticos "
    "se aplican principalmente a mediciones en ayunas y una lectura capilar no "
    "diagnostica diabetes. Frecuencia cardíaca: referencia en reposo; ejercicio, "
    "medicación y condición física pueden modificarla."
)
SOURCES = (
    "https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings",
    "https://www.heart.org/en/health-topics/high-blood-pressure/the-facts-about-high-blood-pressure/all-about-heart-rate-pulse",
    "https://diabetes.org/living-with-diabetes/treatment-care/checking-your-blood-sugar",
)

SEVERITY_COLORS = {
    "neutral": ("#a7bac9", "#5e7380"),
    "normal": ("#56d38a", "#197348"),
    "surveillance": ("#f1bd63", "#806000"),
    "altered": ("#ff9f43", "#a44b00"),
    "important": ("#ef6a72", "#b02035"),
    "critical": ("#ff4d5f", "#8f1025"),
}

PRESSURE_ALARM_SYMPTOMS = (
    ("chest_pain", "Dolor de pecho"),
    ("breathing_difficulty", "Dificultad respiratoria"),
    ("weakness_numbness", "Debilidad o entumecimiento"),
    ("visual_change", "Alteración visual"),
    ("speech_difficulty", "Dificultad para hablar"),
    ("other_neurological", "Otro síntoma neurológico"),
)
PRESSURE_ALARM_SYMPTOM_LABELS = dict(PRESSURE_ALARM_SYMPTOMS)


@dataclass(frozen=True)
class Evaluation:
    code: str
    label: str
    color: str
    pdf_color: str
    note: str = ""
    severity: str = "neutral"


def _evaluation(code, label, severity, note=""):
    color, pdf_color = SEVERITY_COLORS[severity]
    return Evaluation(code, label, color, pdf_color, note, severity)


def _number(value):
    if value in (None, "", 0):
        return None  # The application uses zero to represent an unrecorded value.
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and number > 0 else None


def _symptom_codes(value):
    if not value:
        return ()
    values = value.split(",") if isinstance(value, str) else value
    allowed = PRESSURE_ALARM_SYMPTOM_LABELS
    return tuple(code for code in values if code in allowed)


def pressure_alarm_symptom_text(value):
    return ", ".join(PRESSURE_ALARM_SYMPTOM_LABELS[code] for code in _symptom_codes(value))


def evaluate_pressure(systolic, diastolic, alarm_symptoms=()):
    s, d = _number(systolic), _number(diastolic)
    if s is None and d is None:
        return _evaluation("missing", "Presión no registrada", "neutral")

    incomplete = "Lectura incompleta; registrar ambos valores y verificar la medición." if s is None or d is None else ""
    low = (s is not None and s < 90) or (d is not None and d < 60)
    symptoms = _symptom_codes(alarm_symptoms)

    if (s is not None and s > 180) or (d is not None and d > 120):
        if symptoms:
            result = _evaluation(
                "critical",
                "Atención médica urgente — presión severamente elevada con síntomas",
                "critical",
                URGENT_PRESSURE_ADVICE,
            )
        else:
            result = _evaluation(
                "critical",
                "Presión severamente elevada",
                "critical",
                SEVERE_PRESSURE_REPEAT_ADVICE,
            )
    elif (s is not None and s >= 140) or (d is not None and d >= 90):
        result = _evaluation(
            "stage2",
            "Lectura en rango de hipertensión etapa 2",
            "important",
            "Repetir y dar seguimiento; una sola lectura no diagnostica hipertensión.",
        )
    elif (s is not None and s >= 130) or (d is not None and d >= 80):
        result = _evaluation(
            "stage1",
            "Lectura en rango de hipertensión etapa 1",
            "altered",
            "Repetir y dar seguimiento; una sola lectura no diagnostica hipertensión.",
        )
    elif low:
        result = _evaluation(
            "low",
            "Lectura de presión baja",
            "altered",
            "Verificar la medición y valorar síntomas o antecedentes de la persona.",
        )
    elif s is not None and 120 <= s <= 129 and d is not None and d < 80:
        result = _evaluation(
            "elevated",
            "Presión elevada — vigilancia",
            "surveillance",
            "Repetir en controles posteriores y mantener seguimiento.",
        )
    elif incomplete:
        return _evaluation("incomplete", "Presión incompleta — sin clasificación", "neutral", incomplete)
    else:
        result = _evaluation("normal", "Presión en rango normal", "normal")

    notes = [result.note, incomplete]
    if low and result.code not in ("low", "missing", "incomplete"):
        notes.append("También hay un componente de presión baja; verificar ambos valores y solicitar valoración.")
    return Evaluation(result.code, result.label, result.color, result.pdf_color, " ".join(n for n in notes if n), result.severity)


def evaluate_glucose(value, sample_type="capillary", context="fasting"):
    glucose = _number(value)
    if glucose is None:
        return _evaluation("missing", "Glucemia no registrada", "neutral")

    sample_type = str(sample_type or "").strip().lower()
    context = str(context or "").strip().lower()
    capillary_note = " Esta lectura capilar no diagnostica diabetes." if sample_type == "capillary" else ""

    if glucose < 54:
        return _evaluation(
            "critical",
            "Alerta crítica — hipoglucemia nivel 2",
            "critical",
            "Requiere atención inmediata y valoración de síntomas." + capillary_note,
        )
    if glucose < 70:
        return _evaluation(
            "low",
            "Glucemia baja — hipoglucemia",
            "altered",
            "Actuar según el protocolo de hipoglucemia y vigilar síntomas." + capillary_note,
        )
    if glucose >= 200:
        return _evaluation(
            "critical",
            "Glucemia muy alta — evaluación prioritaria",
            "critical",
            "Requiere evaluación médica, especialmente si hay síntomas, y confirmación con el método apropiado." + capillary_note,
        )
    if context == "fasting":
        if glucose <= 99:
            return _evaluation("normal", "Glucemia en ayunas en rango normal", "normal")
        if glucose <= 125:
            return _evaluation(
                "elevated",
                "Glucemia en ayunas elevada — vigilancia",
                "surveillance",
                "Lectura alterada en ayunas; repetir y dar seguimiento." + capillary_note,
            )
        return _evaluation(
            "high",
            "Glucemia en ayunas alta — requiere evaluación",
            "important",
            "Requiere evaluación y confirmación; no establecer diagnóstico con una sola lectura." + capillary_note,
        )

    return _evaluation(
        "context_required",
        "Glucemia registrada — interpretar según condición",
        "surveillance",
        "La clasificación automática de 70 a 199 mg/dL se reserva para mediciones en ayunas; valorar según el momento de la comida y el método." + capillary_note,
    )


def evaluate_pulse(pulse):
    value = _number(pulse)
    if value is None:
        return _evaluation("missing", "Frecuencia no registrada", "neutral")
    if value < 60:
        return _evaluation("low", "Frecuencia baja", "altered")
    if value > 100:
        return _evaluation("high", "Frecuencia alta", "altered")
    return _evaluation("normal", "Frecuencia normal", "normal")
