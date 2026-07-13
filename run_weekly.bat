@echo off
set APIFY_API_TOKEN=apify_api_eKhRw0TfndscmotpVz9zEl78QdQ1hy03NfDC
set SPREADSHEET_URL=https://docs.google.com/spreadsheets/d/1Koie8Rc0JNfDaMKqisaGzTIHKP4ie4-pW-z2tNTPLxo/edit?gid=253119907#gid=253119907

cd /d %~dp0
echo Iniciando FixLab Lead Prospector...
echo.

python prospector.py --zona "Ciudad Autónoma de Buenos Aires, Argentina"

echo.
if %errorlevel% neq 0 (
    echo ERROR: El script termino con errores. Ver mensaje arriba.
) else (
    echo Proceso completado exitosamente.
)
pause
