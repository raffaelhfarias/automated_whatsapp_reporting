@echo off
echo Iniciando captura e envio das mensagens...

cd /d "%~dp0"

REM Ativa o ambiente conda
echo Ativando ambiente conda...
call conda activate "VARIÁVEL DE AMBIENTE"

echo.
echo Executando main.py...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo Erro ao executar main.py
    pause
    exit /b 1
)

echo.
echo Processo concluido!
