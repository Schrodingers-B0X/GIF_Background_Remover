@echo off
setlocal
cd /d "%~dp0"
for %%i in (".") do set "foldername=%%~nxi"

set "envname=%foldername%_env"

if exist ".\%envname%" (
    echo Virtual environment already exists.
) else (
    echo Creating virtual environment...
    python -m venv ".\%envname%"
)

if exist ".\dist" (
    echo build and dist folder exists
    rmdir /s /q ".\dist"
    rmdir /s /q ".\build"
	del /q gif_bg_remover.spec
) else (
    echo No build and dist folder, continuing
)

call "%envname%\Scripts\activate.bat"
pip install Pillow, PyQt5, pyinstaller
pyinstaller --onefile --icon=icon.ico --windowed --add-data "icon.ico;." --add-data "info.png;." gif_bg_remover.py
echo.
echo EXE created
pause


