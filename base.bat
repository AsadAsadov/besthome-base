@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

REM ========= SETTINGS =========
set "BAK_DIR=C:\Backup"
set "SQL_BAK_DIR=C:\Program Files\Microsoft SQL Server\MSSQL16.SQLEXPRESS\MSSQL\Backup"
set "DST_BAK=%SQL_BAK_DIR%\estate_latest.bak"

set "SQLSERVER=SERVER\SQLEXPRESS"
set "DBNAME=besthome"
set "SYNC_DAYS=-1"
REM ============================

echo.
echo [1] En son .BAK tapilir: %BAK_DIR%

REM --- PowerShell finds latest BAK and writes to temp file (UNICODE SAFE) ---
set "TMP_BAK=%TEMP%\latest_bak_path.txt"

powershell -NoProfile -Command ^
  "$f = Get-ChildItem -LiteralPath '%BAK_DIR%' -File | Where-Object { $_.Extension -match '\.bak$|\.BAK$' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if($f){$f.FullName} else {''}" > "%TMP_BAK%"

set /p LATEST_BAK=<"%TMP_BAK%"
del "%TMP_BAK%"

if "%LATEST_BAK%"=="" (
  echo ❌ Xeta: .BAK tapilmadi.
  pause
  exit /b 1
)

echo Tapildi:
echo %LATEST_BAK%
echo.

REM --- WAIT until file size is stable (backup bitmis olsun) ---
echo [1.1] Backup tamamlanmasi gozlenir (olcu yoxlanir)...

set SIZE1=0
set SIZE2=1

:WAIT_LOOP
powershell -NoProfile -Command ^
  "(Get-Item -LiteralPath '%LATEST_BAK%').Length" > "%TEMP%\size.txt"
set /p SIZE2=<"%TEMP%\size.txt"

if "%SIZE1%"=="%SIZE2%" goto SIZE_OK
set SIZE1=%SIZE2%
timeout /t 5 >nul
goto WAIT_LOOP

:SIZE_OK
echo Backup sabitdir: %SIZE2% bayt
echo.

echo [1.2] Kopyalanir (PowerShell Copy-Item)...
powershell -NoProfile -Command ^
  "Copy-Item -LiteralPath '%LATEST_BAK%' -Destination '%DST_BAK%' -Force"

if errorlevel 1 (
  echo ❌ Kopyalama xetasi
  pause
  exit /b 1
)

echo [1.3] Kopyalanan faylin olcusu yoxlanir (PowerShell)...

powershell -NoProfile -Command ^
  "$s = (Get-Item -LiteralPath '%DST_BAK%').Length; if($s -gt 0){ Write-Host 'OK:' $s } else { exit 1 }"

if errorlevel 1 (
  echo ❌ Kopyalanan fayl oxuna bilmir.
  pause
  exit /b 1
)

echo ✅ Kopyalama dogrulandi.
echo.

echo [2] SQL RESTORE gedir (gozle)...

set "SQLFILE=%TEMP%\restore_besthome.sql"

(
echo ALTER DATABASE [besthome] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
echo RESTORE DATABASE [besthome] FROM DISK = N'%DST_BAK%' WITH REPLACE;
echo ALTER DATABASE [besthome] SET MULTI_USER;
) > "%SQLFILE%"

sqlcmd -S "%SQLSERVER%" -E -b -i "%SQLFILE%"

if errorlevel 1 (
  echo ❌ RESTORE XETASI
  del "%SQLFILE%"
  pause
  exit /b 1
)

del "%SQLFILE%"
echo ✅ RESTORE tamamlandi.
echo.

echo [3] SQLite sinxron baslayir...
cd /d "%~dp0"
python estatebase_sync.py --days %SYNC_DAYS%

if errorlevel 1 (
  echo ❌ Sync xetasi
  pause
  exit /b 1
)

echo.
echo ✅ HER SEY TAMAM!
pause
