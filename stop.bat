@echo off
chcp 65001 >nul
echo.
echo ============================================
echo    AuditWeaver - Stop All Services
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"
set "DOCKER_COMPOSE_PATH=%PROJECT_DIR%docker\docker-compose.yml"

echo [1/5] Stopping Rules Matching Engine...
taskkill /FI "WINDOWTITLE eq RulesMatching" /F >nul 2>&1
echo       Stopped -^> RulesMatching

echo [2/5] Stopping Agent Module...
taskkill /FI "WINDOWTITLE eq AgentModule" /F >nul 2>&1
echo       Stopped -^> AgentModule

echo [3/5] Stopping Django Backend...
taskkill /FI "WINDOWTITLE eq DjangoBackend" /F >nul 2>&1
echo       Stopped -^> DjangoBackend

echo [4/5] Stopping Next.js Frontend...
taskkill /FI "WINDOWTITLE eq NextJSFrontend" /F >nul 2>&1
echo       Stopped -^> NextJSFrontend

echo [5/5] Stopping Docker Compose services...
docker-compose -f "%DOCKER_COMPOSE_PATH%" down
echo       Stopped -^> Docker services (Kafka, Elasticsearch, etc.)

echo.
echo ============================================
echo    All services stopped successfully!
echo ============================================
echo.
pause