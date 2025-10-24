#!/bin/bash

echo "🧹 清除所有应用缓存（包括数据库和日志）..."
cd "$(dirname "$0")"

# 停止应用
pkill -f "python.*app.py" 2>/dev/null
lsof -ti:8888 | xargs kill -9 2>/dev/null
sleep 2

# 清除所有缓存
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type f -name "*.pyo" -delete 2>/dev/null
rm -rf flask_session .cache .flask_cache .pytest_cache 2>/dev/null

# 清除数据库
rm -f tickethunter.db

# 清除日志
rm -f app.log nohup.out
> log/tickethunter.log 2>/dev/null

echo "✅ 所有缓存已清除！"
echo ""
echo "初始化数据库："
python init_db.py
echo ""
echo "重新启动应用："
python app.py > app.log 2>&1 &
sleep 3
echo "✅ 应用已启动"
echo ""
echo "访问地址: http://localhost:8888"
echo ""
tail -10 app.log

