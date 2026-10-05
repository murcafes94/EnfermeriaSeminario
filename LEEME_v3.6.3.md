# Enfermería San Giuseppe Moscati 3.6.3

Corrige el fallo de inicio «module numpy has no attribute short».
NumPy es opcional para openpyxl y no se utiliza en esta aplicación.
El paquete lo excluye y deshabilita su carga accidental desde carpetas residuales.
La importación y exportación de Excel conservan sus números y formatos.

Linux se compila localmente; GitHub Actions genera únicamente Windows.

## Linux

Extrae el ZIP en una carpeta nueva. No mezcles archivos con paquetes anteriores.
Desde la carpeta EnfermeriaSeminario-3.6.3 ejecuta:

    chmod +x EnfermeriaSeminario
    bash Abrir_Enfermeria.sh

Cuando abra, actualiza el acceso del menú:

    bash Instalar_en_menu_de_aplicaciones.sh

No necesita instalar Python. Compatible con Ubuntu 24.04 / Mint 22, x86_64.
Los datos permanecen en el perfil, normalmente:
~/.local/share/EnfermeriaSeminario/enfermeria.db
El registro de inicio se guarda en:
~/.local/state/EnfermeriaSeminario/inicio-linux.log

## Windows

Abre EnfermeriaSanGiuseppeMoscati-Setup-3.6.3.exe.

Se mantienen las evaluaciones orientativas de presión y pulso de 3.6.2.
Orientativo; no constituye diagnóstico médico.
