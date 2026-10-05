# Enfermería San Giuseppe Moscati 3.6.1

Incluye evaluación automática orientativa de presión y frecuencia cardíaca para
adultos, con colores, actualización en vivo y etiquetas en el historial y los PDF A4.
Los controles anteriores también se evalúan al abrirlos o exportarlos.

Presión: baja si sistólica <90 o diastólica <60; normal entre 90–119 y 60–79;
elevada/seguimiento entre 120–139 o 80–89; alta desde 140 o 90; alerta crítica
por encima de 180 o 120. La categoría de alta/crítica prevalece y cualquier
componente bajo concurrente se señala por separado. Las lecturas incompletas
nunca se clasifican como normales. 180/120 exactos pertenecen a presión alta.
La categoría elevada/seguimiento agrupa rangos: la AHA clasifica 130–139 o 80–89
como hipertensión de etapa 1.

Frecuencia cardíaca en reposo: baja <60, normal 60–100, alta >100 lpm.
Se recuerda que ejercicio, medicación y condición física influyen en el pulso.

Ante una alerta crítica con síntomas, llamar al 911 de inmediato, sin esperar
una nueva medición. Sin síntomas, repetir tras al menos un minuto y contactar
inmediatamente a un profesional si la lectura continúa por encima del umbral.

Orientativo; no constituye diagnóstico médico.

Fuentes:
https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings
https://www.heart.org/en/health-topics/high-blood-pressure/the-facts-about-high-blood-pressure/all-about-heart-rate-pulse

## Instalación y actualización

Windows: abrir EnfermeriaSanGiuseppeMoscati-Setup-3.6.1.exe.
Linux: extraer el tar.gz, abrir la aplicación o ejecutar
Instalar_en_menu_de_aplicaciones.sh dentro de la carpeta extraída.

Los datos se guardan en el perfil del usuario, fuera de la carpeta de la app.
Antes de actualizar, cerrar la app y guardar una copia de seguridad desde ella.
No borrar ni reemplazar enfermeria.db. Esta actualización no cambia las tablas.
Después de actualizar, sincronizar desde la app para renovar los PDF de consulta
web con las nuevas evaluaciones.
