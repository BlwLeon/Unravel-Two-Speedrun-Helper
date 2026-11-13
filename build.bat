@echo off
rem Builds dist\UT2SpeedrunHelper.exe (needs Python 3.10+ on Windows)
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller || goto :error
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name UT2SpeedrunHelper ^
  --add-data "src\ut2helper\lua;ut2helper\lua" ^
  --paths src ^
  run_helper.py || goto :error
echo.
echo Done: dist\UT2SpeedrunHelper.exe
goto :eof
:error
echo Build failed.
exit /b 1
