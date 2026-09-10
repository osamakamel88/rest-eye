@echo off
title Push REST-EYE to GitHub
echo ========================================================
echo   Pushing REST-EYE commits to GitHub:
echo   https://github.com/osamakamel88/rest-eye.git
echo ========================================================
cd /d "C:\Users\sa7aba\Documents\antigravity\intelligent-davinci"
git status
echo.
git push -u origin master
echo.
echo Done! All files and commits pushed to GitHub.
pause
