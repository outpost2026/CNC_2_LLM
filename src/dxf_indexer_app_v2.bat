@echo off
title DXF Geometry Indexer V2 — Dev Dashboard
cd /d "%~dp0"
echo Spoustim DXF Indexer Dev Dashboard...
echo.
streamlit run dxf_indexer_app_v2.py
echo.
pause
