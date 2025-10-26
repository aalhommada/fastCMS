@echo off
echo ===============================
echo FastCMS - Fix and Run
echo ===============================
echo.

REM Activate venv
echo [1/6] Activating virtual environment...
if not exist .venv (
    echo ERROR: .venv not found. Run setup.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
echo OK
echo.

REM Install/fix dependencies
echo [2/6] Checking and installing dependencies...
pip install greenlet email-validator --quiet
pip install -r requirements.txt --quiet
echo OK
echo.

REM Check database exists
echo [3/6] Checking database...
if exist data\app.db (
    echo OK: Database exists
) else (
    echo Database not found, will create during migrations
)
echo.

REM Create migrations if needed
echo [4/6] Creating database migrations...
alembic revision --autogenerate -m "initial schema" 2>nul
if %errorlevel% equ 0 (
    echo OK: Migration created
) else (
    echo Note: Migration might already exist
)
echo.

REM Apply migrations
echo [5/6] Applying database migrations...
alembic upgrade head
if %errorlevel% equ 0 (
    echo OK: Database ready
) else (
    echo ERROR: Migration failed
    pause
    exit /b 1
)
echo.

REM Start server
echo [6/6] Starting server...
echo.
echo ===============================
echo FastCMS is starting!
echo ===============================
echo API Docs: http://localhost:8000/docs
echo Health: http://localhost:8000/health
echo.
echo Press Ctrl+C to stop
echo.

python app/main.py
