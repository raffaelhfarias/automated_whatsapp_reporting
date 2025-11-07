@echo off
echo Iniciando captura e envio das mensagens com Marcas...

cd /d "%~dp0"

REM Ativa o ambiente conda
echo Ativando ambiente conda...
call conda activate "VARIÁVEL DE AMBIENTE"

echo.
echo Executando main_com_marcas.py...
python main_com_marcas.py
if %ERRORLEVEL% NEQ 0 (
    echo Erro ao executar main_com_marcas.py
    pause
    exit /b 1
)

echo.

echo Processo concluido!
