# Enfermería San Giuseppe Moscati

Aplicación de escritorio para la Enfermería del Seminario Mayor de Guayaquil.
Python, PySide6 y SQLite. La versión actual es **3.6.1**.

Incluye inventario por lotes, entregas y dosis administradas, fichas sanitarias
con foto, controles de salud, evaluación orientativa de presión y frecuencia
cardíaca, exportaciones A4 y sincronización de consulta web.

## Descargar aplicaciones

En la pestaña Actions, abrir la última ejecución correcta de **Generar Windows**
y descargar el artefacto de Linux o Windows. La misma ejecución compila ambos.
El instalador Windows se abre con doble clic. En Linux se extrae el tar.gz y se
abre la aplicación o se usa su script de instalación en el menú.

Ver [las instrucciones de la versión](LEEME_v3.6.1.md).

## Ejecutar el código

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

En Windows, usar `.venv\Scripts\activate` para activar el entorno.
Pruebas: `python -m unittest discover -s tests -v`.

Este repositorio contiene código e imágenes de la aplicación. Los datos de
salud y las credenciales de conexión se guardan por separado en el equipo del
encargado. La evaluación es orientativa y no constituye diagnóstico médico.
