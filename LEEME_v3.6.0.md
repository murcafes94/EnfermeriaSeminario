# Enfermería San Giuseppe Moscati v3.6.0

La app sigue siendo la fuente principal en Linux o Windows. La web es un portal privado de consulta; conserva el inicio de sesión actual mediante ChatGPT.

## Conectar por primera vez

1. Abre la web de Enfermería con tu cuenta de encargado.
2. Pulsa **Conectar app** o **Descargar conexión para la app**. Se descargará `Enfermeria.enfconnection`.
3. En la app, abre **Configuración → Portal web → Importar conexión del portal** y selecciona ese archivo.
4. Revisa la dirección que aparece antes de aceptar.
5. Pulsa **Sincronizar ahora**. La primera publicación puede tardar porque incluye fotos y documentos PDF.
6. Si deseas, activa el envío automático cada cinco minutos mientras la app esté abierta.

El archivo de conexión contiene claves de publicación: consérvalo con el encargado y no lo compartas con los formadores. No se incorpora a los ZIP de código ni se publica en el repositorio. Linux lo guarda con permisos privados; Windows lo guarda dentro del perfil del usuario.

## Formadores

En **Portal web**, escribe los correos autorizados, uno por línea, y guarda las preferencias. Los mismos correos deben recibir acceso al sitio desde su configuración de acceso. La app no envía invitaciones. Deben entrar con la cuenta autorizada del sistema actual; no se ha añadido inicio independiente con Google.

Los formadores pueden buscar seminaristas, abrir fichas adaptadas al celular, llamar al contacto familiar, consultar controles y medicamentos, y descargar fichas completas o resúmenes de emergencia con fotos. No pueden editar registros.

## Qué se publica

Fichas, fotografías, controles de salud, inventario y lotes, y entregas/dosis. No se envían el PIN, claves de recuperación, copias cifradas, registros internos de seguridad ni la base completa.

Los expedientes PDF ahora incluyen controles y medicamentos entregados/dosis administradas. Se exportan la ficha individual, resumen de emergencia y un documento general con índice. Los controles y movimientos anulados no se presentan como vigentes.

La web muestra la última sincronización. Si un envío falla, conserva la copia anterior completa; los datos locales no se modifican. La sincronización automática necesita que la app esté abierta y tenga conexión. Cada envío usa una copia consistente de SQLite y conserva los ID de la app. Los registros web anteriores permanecen en sus tablas; no se mezclan automáticamente con los de la app.

## Cambio de encargado

Usa la transferencia cifrada existente para llevar la base a Linux o Windows. Importa también una conexión del portal en el nuevo equipo. Las claves de conexión no se incluyen en la transferencia de la base. Debe actualizarse la titularidad/autorización del portal y renovarse la clave de sincronización para retirar la publicación del equipo anterior. El identificador de la enfermería permanece en la base transferida.

## Instalación y verificación

Antes de actualizar, crea una copia cifrada desde Configuración → Copias. El paquete Linux incluye el instalador de menú habitual y utiliza la base existente. Para Windows, se incluye el código y su script de compilación; esta entrega no incluye un ejecutable Windows probado.

Se verificaron las regresiones existentes, la publicación completa/interrumpida, los PDF, la consulta autorizada y la revocación de acceso. No se han leído ni publicado datos sanitarios reales de la computadora del encargado.

## Usar en Windows sin compilar

Instala Python 3.13 de 64 bits. Extrae el ZIP en una carpeta permanente y abre CMD en ella (donde están run.py y requirements.txt). Ejecuta:

```bat
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Para abrir en ocasiones posteriores basta el último comando. Los datos se guardan dentro del perfil de Windows.

Para generar la aplicación portable, ejecuta `scripts\build_windows.bat` desde CMD. Se crea `dist\EnfermeriaSeminario\EnfermeriaSeminario.exe`; debes conservar toda su carpeta, no solo el EXE.

Para generar el instalador, instala Inno Setup 6 y compila `scripts\installer_windows.iss` después de generar la aplicación portable. El archivo resultante es `dist\installer\EnfermeriaSanGiuseppeMoscati-Setup-3.6.0.exe`. La creación y ejecución en Windows deben verificarse en una computadora Windows.


## Generar Windows desde la terminal de Linux

Necesitas una cuenta de GitHub e internet. La compilación se realiza en un
Windows de GitHub Actions y se descarga a tu Linux. No necesitas Wine ni
instalar Windows localmente. GitHub Actions debe estar habilitado y tener
minutos disponibles en tu cuenta.

Desde la carpeta de este código, ejecuta:

```bash
sudo apt update
sudo apt install git gh python3
bash scripts/build_windows_from_linux.sh
```

La primera vez GitHub te pedirá iniciar sesión en el navegador. El script crea
un repositorio privado nuevo para esa compilación. Copia únicamente código,
pruebas y las imágenes de la aplicación; no copia bases de datos, respaldos,
fotos de seminaristas ni la conexión privada de sincronización.

Al terminar indica una carpeta dentro de `dist/windows-...`, con:

- `EnfermeriaSanGiuseppeMoscati-Setup-3.6.0.exe`: instalador para entregar.
- `Enfermeria-Windows-Portable-3.6.0.zip`: alternativa portable; extraer toda la carpeta.
- Instrucciones y sumas SHA256.

Para recompilar sin crear otro repositorio, desde la carpeta `windows-build-...`
creada por el script puedes ejecutar `gh workflow run build-windows.yml` y
consultar `gh run list`. Si modificas el código, debes actualizarlo en ese
repositorio antes de repetir la compilación.

El flujo ejecuta las pruebas de datos y exportación en Windows antes de empaquetar.
La interfaz y la instalación deben probarse en un Windows antes de entregar el
instalador a los hermanos. Este paquete no incluye firma digital de editor.
