@echo off
title CNC_2_LLM — Semantic Embedding Dashboard
cd /d "%~dp0"
echo Spoustim Semantic Embedding Dashboard...
echo.
streamlit run semantic_embedding_dashboard.py
echo.
pause
