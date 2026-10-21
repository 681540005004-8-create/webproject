@echo off
chcp 65001 > nul
echo ========================================================
echo   Pushing TaskFlow AI to GitHub
echo   Repository: https://github.com/681540005004-8-create/webproject.git
echo ========================================================
echo.

cd /d "%~dp0"
git remote set-url origin https://github.com/681540005004-8-create/webproject.git
git add .
git commit -m "feat: TaskFlow AI - Intelligent Schedule & Burnout Prevention Web Application" > nul 2>&1
git branch -M main
echo กำลังนำโค้ดขึ้น GitHub (หากมีหน้าต่างล็อกอินเด้งขึ้นมา กรุณากด Sign in with your browser)...
echo.
git push -u origin main

echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================================
    echo   [SUCCESS] นำโค้ดขึ้น GitHub สำเร็จเรียบร้อยแล้ว!
    echo   https://github.com/681540005004-8-create/webproject
    echo ========================================================
) else (
    echo ========================================================
    echo   [NOTICE] เกิดข้อผิดพลาดในการ Push หรือรอการยืนยันตัวตน
    echo   หากเป็น Private Repository หรือยังไม่ได้ตั้งค่าสิทธิ์
    echo   กรุณาใช้ Personal Access Token (PAT)
    echo ========================================================
)
echo.
pause
