# Enfermería San Giuseppe Moscati 3.7.0

Esta versión mejora el control de presión arterial e incorpora evaluación orientativa de glucemia.

- La presión usa la categoría de mayor severidad entre sistólica y diastólica.
- Una sola toma se presenta como lectura en un rango, no como diagnóstico de hipertensión.
- La presión severamente elevada muestra repetición de la medición y síntomas de alarma; con síntomas indica atención médica urgente.
- La glucemia registra valor, muestra Capilar o Laboratorio y condición Ayunas, 2 h después de comer o Aleatoria.
- Los rangos automáticos de 70 a 199 mg/dL se aplican a ayunas. Una lectura capilar alta requiere seguimiento y no diagnostica diabetes.
- Todos los datos nuevos se conservan en el historial, Excel, PDF y la copia web de consulta.

La actualización migra automáticamente la base existente y conserva expedientes, controles, movimientos, inventario y configuración.

## Linux

Extrae el ZIP en una carpeta nueva. No mezcles archivos con paquetes anteriores.
Desde la carpeta EnfermeriaSeminario-3.7.0 ejecuta:

    chmod +x EnfermeriaSeminario
    bash Abrir_Enfermeria.sh

Cuando abra, actualiza el acceso del menú:

    bash Instalar_en_menu_de_aplicaciones.sh

No necesita instalar Python. Compatible con Ubuntu 24.04 / Mint 22, x86_64.
Los datos permanecen en el perfil, normalmente:
~/.local/share/EnfermeriaSeminario/enfermeria.db

## Windows

Abre EnfermeriaSanGiuseppeMoscati-Setup-3.7.0.exe.

Orientativo; no constituye diagnóstico médico.
