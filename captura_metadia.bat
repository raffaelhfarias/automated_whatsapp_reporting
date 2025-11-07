@echo off
echo Iniciando captura automática de metas...

cd /d "%~dp0"

REM Ativa o ambiente conda
echo Ativando ambiente conda...
call conda activate "VARIÁVEL DE AMBIENTE"

echo.
echo Executando captura_metadia.py...
python componentes/captura_metadia.py
if %ERRORLEVEL% NEQ 0 (
    echo Erro ao executar captura_metadia.py
    pause
    exit /b 1
)

echo.
echo Processo concluido!
