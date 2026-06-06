@echo off
echo ====================================
echo   股票分析助手 - 启动脚本
echo ====================================
echo.

cd backend

echo [1/2] 检查依赖...
python -c "import fastapi, yfinance, pandas_ta" 2>nul
if errorlevel 1 (
    echo 正在安装依赖...
    pip install -r requirements.txt
)

echo.
echo [2/2] 启动服务...
echo 服务将在 http://localhost:8000 启动
echo 按 Ctrl+C 停止服务
echo.

python ./backend/main.py

pause
