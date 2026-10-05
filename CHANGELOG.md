# Historial de cambios

## 3.6.3

- Corrige el fallo de arranque de openpyxl causado por NumPy incompleto.
- Excluye la dependencia opcional y evita su carga accidental en el ejecutable.
- Añade una regresión que verifica Excel con un NumPy residual.
- Genera Linux localmente y limita GitHub Actions a Windows.
- Actualiza Linux mediante una copia completa y conserva el registro de errores.

## 3.5.1

- Añade una barra superior persistente con nombre de sección, fecha y reloj en todas las pantallas.
- Incorpora pantalla completa automática en Linux, `F11` para alternarla y `Esc` para salir sin cerrar la app.
- Permite abrir automáticamente en el área de trabajo 2 bajo Cinnamon/X11 mediante `wmctrl`.
- Añade alertas nativas de Linux para vencimientos, stock bajo, préstamos atrasados y cuarentenas.
- Las alertas se revisan cada diez minutos, no muestran identidad ni datos de salud y no se repiten mientras nada cambie.
- Reduce la vista compacta del Panel rápido y conserva la vista ampliada opcional.
- Centraliza las opciones exclusivas de Linux en Configuración.
- Mantiene sin cambios el PIN, código de recuperación, cifrado, base y formatos `.enfbackup` y `.enftransfer`.
- Conserva la compatibilidad con todos los datos de v3.5.0 y anteriores.

## 3.5.0

- Añade **Panel rápido de Enfermería** para Linux Mint y Windows 10/11.
- Resume vencimientos, stock bajo, equipos prestados, préstamos atrasados y lotes en cuarentena.
- Consulta SQLite en modo estrictamente de solo lectura y no muestra nombres ni datos de salud de seminaristas.
- Incluye vistas compacta y ampliada, actualización manual y automática cada cinco minutos.
- Añade opción **Siempre visible**, memoria de posición y tamaño y botón para abrir la aplicación principal.
- Incorpora acceso directo propio e inicio automático opcional desde Configuración.
- Reutiliza el ejecutable principal mediante `--panel` para no duplicar las bibliotecas ni aumentar innecesariamente el instalador.

## 3.4.1

- Renombra **Fichas sanitarias** como **Expedientes de salud** en toda la interfaz y en los PDF.
- Renombra **Controles médicos** como **Controles de salud** para reflejar que son registros de seguimiento y no diagnósticos clínicos.
- Renombra la ficha breve como **Resumen de salud para emergencias**.
- Actualiza los nombres sugeridos de los archivos PDF y del formulario de Google sin modificar la estructura de datos ni la compatibilidad de importación.
- Conserva todos los PDF en formato A4.

## 3.4.0

- Añade filtros combinables de seminaristas por etapa formativa, diócesis y alergias.
- Genera una ficha sanitaria de emergencia en PDF y registra quién la emitió.
- Incorpora cuarentena por lote sin alterar la ubicación general ni borrar existencias.
- Excluye lotes vencidos y en cuarentena del stock entregable y del descuento FEFO.
- Oculta por defecto los controles médicos anulados y los excluye de PDF/Excel; conserva una vista separada de auditoría.
- Añade copias y transferencias cifradas con AES-256-GCM y derivación PBKDF2 de 600.000 iteraciones.
- Añade recuperación supervisada del PIN con responsable institucional y código rotativo.
- Añade transferencia formal de encargado con base, configuración, manifiesto y manual de entrega.
- Prepara firma opcional del ejecutable y del instalador de Windows mediante `signtool` y un certificado institucional externo.
- Retira la función QR a petición del usuario.

## 3.3.5

- Restaura el calendario en **Fecha de nacimiento**, con estado inicial **No consta** y bloqueo de fechas futuras.
- Convierte **Año de formación** en una lista: Propedéutico, dos años de Filosofía y cuatro años de Teología.
- Convierte **Tipo de sangre** en una lista con los ocho grupos ABO/Rh.
- Normaliza variantes reconocibles importadas desde Excel o Google Forms, sin adivinar valores ambiguos.
- Conserva visibles los valores antiguos no reconocidos para que puedan revisarse manualmente.
- Permite eliminar definitivamente una ficha archivada, con doble confirmación, bloqueo si hay equipos pendientes y anonimización de movimientos.
- Autoajusta las columnas de las tablas al contenido, incluida la indicación de uso y las alertas de vencimiento.

## 3.1.0

- Nueva sección de controles médicos por seminarista con historial, IMC automático y anulación auditada.
- Formularios de productos y fichas redimensionables, con desplazamiento y botones siempre visibles.
- Tablas con columnas y filas ajustables y desplazamiento fluido.
- Existencia inicial, lote y vencimiento disponibles al crear un producto.
- Nueva imagen transparente de San Giuseppe Moscati.
- Botones principales de formularios traducidos a español.

## 3.0.0

- Configuración institucional y responsable desde la interfaz.
- PIN opcional del encargado con PBKDF2-HMAC-SHA256.
- Vista previa de importaciones sobre una copia temporal de la base.
- Copias y restauración guiadas con validación SQLite.
- Registro de auditoría de operaciones administrativas.
- Registro local de errores con rotación automática.
- Nueva sección profesional de Configuración, Seguridad, Copias, Auditoría y Acerca de.
- Títulos explicativos, barra de estado, icono propio y acabado visual revisado.
- Metadatos e instalador opcional para Windows 10/11.
- Instalación integrada en el menú de Linux Mint.

## 2.1.0

- Bloqueo de entregas y dosis desde lotes vencidos.
- Criterio de vencimiento unificado según la fecha local; el día de vencimiento sigue vigente.
- Registro de asignación por lotes para permitir anulaciones auditadas.
- Actualización parcial de fichas importadas sin borrar datos ausentes.
- Casos ambiguos por nombres repetidos pasan a revisión y no sobrescriben fichas.
- Conversión segura de cédulas y teléfonos numéricos, incluyendo recuperación del cero inicial cuando corresponde.
- Stock mínimo `0` válido.
- Préstamos y devoluciones atómicos.
- Copia automática y permisos locales restrictivos; declaración explícita de que la base no está cifrada.
- Exportaciones separadas de inventario, fichas y movimientos.
- Aviso de alergias durante entregas y dosis.
- Normalización automática de nombres de productos importados.
- Compatibilidad prevista para Linux y Windows 10/11.

## 2.0.0

- Primera migración desde GTK a PySide6.
# 3.3.4

- Rechaza filas y lotes vencidos durante la importación sin impedir que entren los lotes vigentes del mismo producto.
- Trata como válida durante todo el día la fecha de vencimiento igual a la fecha actual.
- Rechaza fechas escritas en un formato no reconocible en lugar de importarlas como “sin fecha”.
- Muestra en la vista previa los lotes vencidos y las unidades que no se importarán.
- Añade **Retirar vencidos** en Inventario para descontar todos los lotes vencidos del producto mediante movimientos auditables y reversibles.
- Renombra la acción individual como **Retirar lote seleccionado** y propone “Producto vencido” como motivo cuando corresponde.

# 3.3.3

- Corrige el botón **Confirmar importación**, que visualmente estaba disponible pero no aceptaba el diálogo.
- Agrupa las filas repetidas de un producto como lotes y conserva la suma total de sus existencias.
- Reconoce el encabezado `Fecha_Vencimiento` del inventario entregado.
- Hace la importación atómica, mucho más rápida e idempotente.
- Amplía la vista previa con filas reconocidas y entradas de stock o lotes.
- Asigna automáticamente la ubicación por categoría cuando el Excel indica `Por asignar`.

# 3.3.2

- Añade borrado definitivo, visible y protegido, para productos archivados que nunca tuvieron existencias, movimientos ni préstamos.
- Mantiene el archivado obligatorio para todo registro con historial y refuerza la explicación dentro de la interfaz y el manual.

# 3.3.1

- Logo oficial del Seminario integrado en fichas, controles médicos y portada del PDF general.
- Encabezado institucional diferenciado de la identidad propia de Enfermería San Giuseppe Moscati.
- Logo optimizado para fondo blanco y verificado visualmente en los tres tipos de PDF.

# 3.3.0

- Inicio rediseñado con una imagen mayor de San Giuseppe Moscati y su frase sobre el cuidado de los enfermos.
- Barra lateral contraíble: abierta en Inicio y compacta con iconos en las demás secciones.
- Normalización automática de productos, nombres propios y textos; correos, enlaces, fechas, teléfonos e identificaciones no se alteran.
- Consulta y restauración de fichas de seminaristas archivadas.
- Purga protegida de datos de prueba con confirmación escrita, PIN opcional y eliminación segura de páginas SQLite.
- Opción para borrar también las copias de seguridad locales durante la purga.

# 3.2.1

- Panel de inicio más compacto, sin encabezado de identidad duplicado.
- Tarjetas y textos con fondo plano y transparente, sin franjas oscuras heredadas.
- Resumen equilibrado en cuatro columnas con el patrono integrado en el espacio libre.
- Estado explícito cuando no existen alertas prioritarias.
- Las alertas muestran la ubicación física del medicamento para localizarlo sin abrir el inventario.

# 3.2.0

- Exportación exclusiva del control médico de cada seminarista.
- Tablas compactas con scroll interno para evitar grandes recuadros vacíos.
- Eliminación segura del inventario activo con historial restaurable.
- Nueva identidad: Enfermería / Enfermería San Giuseppe Moscati.
- Instalador de menú para Linux con icono propio y desinstalación no destructiva.

## 3.6.0
- Portal web de solo consulta y conexión privada importable.
- Publicación manual o automática cada cinco minutos de una copia consistente.
- Publicación en etapas con activación únicamente al recibir registros y archivos completos.
- Fichas y resúmenes PDF con fotos; expedientes ampliados con entregas y dosis.
- Lista de correos consultantes administrada desde la app.
