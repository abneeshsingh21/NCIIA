@echo off
title N-CIIA Intelligence Platform Launcher
color 0A
echo.
echo  ███╗   ██╗      ██████╗██╗██╗ █████╗
echo  ████╗  ██║     ██╔════╝██║██║██╔══██╗
echo  ██╔██╗ ██║     ██║     ██║██║███████║
echo  ██║╚██╗██║     ██║     ██║██║██╔══██║
echo  ██║ ╚████║     ╚██████╗██║██║██║  ██║
echo  ╚═╝  ╚═══╝      ╚═════╝╚═╝╚═╝╚═╝  ╚═╝
echo.
echo  Cyber Intelligence Platform - Full Stack Launcher
echo  =======================================================
echo.

:: ── 1. Start Python Backend ──────────────────────────────────────────────────
echo  [1/3] Starting Python Backend on port 8000...
start "N-CIIA Backend" cmd /k "cd /d %~dp0nciia-core && call .venv\Scripts\activate && python run_server.py"
timeout /t 5 /nobreak >nul
echo       Backend started. ✓

:: ── 2. Start Cloudflare Tunnel ───────────────────────────────────────────────
echo  [2/3] Starting Cloudflare Tunnel...
start "N-CIIA Tunnel" cmd /k "cd /d %~dp0 && cloudflared.exe tunnel --url http://localhost:8000 --edge-ip-version 4"
echo       Tunnel starting... (check the 'N-CIIA Tunnel' window for your public URL)
timeout /t 8 /nobreak >nul

:: ── 3. Start Frontend Dev Server ─────────────────────────────────────────────
echo  [3/3] Starting Frontend Dashboard on port 5173...
start "N-CIIA Frontend" cmd /k "cd /d %~dp0nciia-dashboard && npm run dev"
timeout /t 4 /nobreak >nul
echo       Frontend started. ✓

echo.
echo  =======================================================
echo  ✅ ALL SERVICES ARE RUNNING!
echo.
echo  Dashboard:  http://localhost:5173
echo  Backend:    http://localhost:8000
echo.
echo  ⚡ IMPORTANT - CANARY TRACKER SETUP:
echo     1. Look at the 'N-CIIA Tunnel' window
echo     2. Find the line that says "Your quick Tunnel has been created"
echo     3. Copy the URL (e.g. https://xxxx.trycloudflare.com)
echo     4. Paste it in Canary Tracker → "Your Public Base URL" field
echo.
echo  Press any key to open the dashboard in your browser...
pause >nul
start http://localhost:5173
