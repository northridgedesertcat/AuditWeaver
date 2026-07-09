@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo.
echo ============================================
echo    LogSentinel - One-click Startup
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"
set "PYTHON_CMD=python"
set "DOCKER_COMPOSE_FILE=%PROJECT_DIR%docker\docker-compose.yml"

for /f "tokens=1,2 delims==" %%a in ('type "%PROJECT_DIR%.env" ^| findstr /v "^#"') do (
    if "%%a"=="ES_PORT" set "ES_PORT=%%b"
    if "%%a"=="KAFKA_PORT" set "KAFKA_PORT=%%b"
)

if not defined ES_PORT set "ES_PORT=19200"
if not defined KAFKA_PORT set "KAFKA_PORT=29092"

echo [STEP 1/7] Starting Docker Compose services...
echo          This may take a few minutes...
docker-compose -f "%DOCKER_COMPOSE_FILE%" up -d
if errorlevel 1 (
    echo          ERROR: Failed to start Docker Compose!
    pause
    exit /b 1
)
echo          Docker Compose started

echo [STEP 2/7] Waiting for Elasticsearch to be ready...
call :WaitForES localhost:%ES_PORT%
if errorlevel 1 (
    echo          WARNING: Elasticsearch may not be fully ready, continuing anyway...
) else (
    echo          Elasticsearch is ready!
    echo          Waiting extra 10 seconds for ES to stabilize...
    timeout /t 10 /nobreak >nul
)

echo [STEP 3/7] Waiting for Kafka to be ready...
call :WaitForKafka localhost:%KAFKA_PORT%
if errorlevel 1 (
    echo          WARNING: Kafka may not be fully ready, continuing anyway...
) else (
    echo          Kafka is ready!
    echo          Waiting extra 4 seconds for Kafka topics to initialize...
    timeout /t 4 /nobreak >nul
)

echo [STEP 4/7] Creating Elasticsearch Indexes...
echo          Script: %PROJECT_DIR%docker\config\elasticsearch\creatMapping.py
cd /d "%PROJECT_DIR%"
%PYTHON_CMD% docker\config\elasticsearch\creatMapping.py
if errorlevel 1 (
    echo          WARNING: Failed to create ES indexes!
) else (
    echo          ES indexes created successfully!
)

echo [STEP 5/7] Starting Rules Matching Engine...
echo          Path: %PROJECT_DIR%services\rulesMatching
cd /d "%PROJECT_DIR%services\rulesMatching"
start "RulesMatching" cmd /k "%PYTHON_CMD% main.py"
echo          Started -^> Window: RulesMatching
timeout /t 5 /nobreak >nul

echo [STEP 6/7] Starting Agent Module...
echo          Path: %PROJECT_DIR%services\agent
cd /d "%PROJECT_DIR%services\agent"
start "AgentModule" cmd /k "%PYTHON_CMD% main.py"
echo          Started -^> Window: AgentModule
timeout /t 3 /nobreak >nul

echo [STEP 7/7] Starting Django Backend and Next.js Frontend...
echo          Starting Django Backend...
cd /d "%PROJECT_DIR%services\website\backend\v1"
start "DjangoBackend" cmd /k "%PYTHON_CMD% manage.py runserver 0.0.0.0:8000"
echo          Started -^> Window: DjangoBackend (Port: 8000)
timeout /t 3 /nobreak >nul

echo          Starting Next.js Frontend...
cd /d "%PROJECT_DIR%services\website\frontend\v1"
start "NextJSFrontend" cmd /k "npm run dev"
echo          Started -^> Window: NextJSFrontend (Port: 3000)

echo.
echo ============================================
echo    All services started!
echo ============================================
echo.
echo Service List:
echo   - Docker Services: Kafka, Elasticsearch, Kibana, Logstash
echo   - Rules Matching Engine: Processes Kafka logs (input: log.audit, output: log.analysis)
echo   - Agent Module: AI analysis (input: log.analysis)
echo   - Django Backend: http://localhost:8000
echo   - Next.js Frontend: http://localhost:3000
echo.
echo To stop all services, run: stop.bat
echo.
cd /d "%PROJECT_DIR%"
pause
exit /b

:WaitForES
set "HOST_PORT=%~1"
set "MAX_RETRIES=40"
set "RETRY_DELAY=5"

for /l %%i in (1,1,%MAX_RETRIES%) do (
    curl -s -o nul -w "%%{http_code}" "http://%HOST_PORT%/" > "%TEMP%\es_status.tmp" 2>nul
    set /p CODE=<"%TEMP%\es_status.tmp"
    del "%TEMP%\es_status.tmp" 2>nul
    if "!CODE!"=="200" (
        exit /b 0
    )
    echo          Waiting for Elasticsearch... (attempt %%i/%MAX_RETRIES%)
    timeout /t %RETRY_DELAY% /nobreak >nul
)
exit /b 1

:WaitForKafka
set "HOST_PORT=%~1"
set "MAX_RETRIES=10"
set "RETRY_DELAY=3"

for /l %%i in (1,1,%MAX_RETRIES%) do (
    powershell -NoProfile -Command "try { $c = New-Object System.Net.Sockets.TCPClient; $c.Connect('%HOST_PORT%'); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
    if !errorlevel! equ 0 (
        exit /b 0
    )
    echo          Waiting for Kafka... (attempt %%i/%MAX_RETRIES%)
    timeout /t %RETRY_DELAY% /nobreak >nul
)
exit /b 1