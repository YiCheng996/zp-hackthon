#!/bin/bash

echo "🧹 开始清除 TicketHunter 应用缓存..."
echo ""

# 切换到项目目录
cd "$(dirname "$0")"

# 1. 停止应用
echo "📌 步骤 1/5: 停止应用进程"
pkill -f "python.*app.py" 2>/dev/null
lsof -ti:8888 | xargs kill -9 2>/dev/null
sleep 2
echo "✅ 应用已停止"
echo ""

# 2. 清除 Python 缓存
echo "📌 步骤 2/5: 清除 Python 缓存文件"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type f -name "*.pyo" -delete 2>/dev/null
rm -rf .pytest_cache 2>/dev/null
echo "✅ Python 缓存已清除"
echo ""

# 3. 清除 Flask 缓存
echo "📌 步骤 3/5: 清除 Flask 缓存"
rm -rf flask_session 2>/dev/null
rm -rf .cache 2>/dev/null
rm -rf .flask_cache 2>/dev/null
echo "✅ Flask 缓存已清除"
echo ""

# 4. 清除数据库（可选）
echo "📌 步骤 4/5: 清除数据库（可选）"
read -p "是否清除数据库? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f tickethunter.db
    echo "✅ 数据库已清除"
else
    echo "⏭️  跳过数据库清除"
fi
echo ""

# 5. 清除日志文件（可选）
echo "📌 步骤 5/5: 清除日志文件（可选）"
read -p "是否清除日志文件? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f app.log
    rm -f nohup.out
    > log/tickethunter.log
    echo "✅ 日志文件已清除"
else
    echo "⏭️  跳过日志清除"
fi
echo ""

echo "╔═══════════════════════════════════════════╗"
echo "║  ✨ 缓存清除完成！                        ║"
echo "╚═══════════════════════════════════════════╝"
echo ""
echo "现在可以重新启动应用："
echo "  python app.py"
echo ""

