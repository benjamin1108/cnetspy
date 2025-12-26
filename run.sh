#!/bin/bash

# 云计算竞争情报爬虫 - 启动脚本
# 精简版：仅保留爬虫功能

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 虚拟环境路径
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON="$VENV_DIR/bin/python"

# 检查虚拟环境
check_venv() {
    if [ ! -f "$PYTHON" ]; then
        echo -e "${RED}错误: 虚拟环境不存在${NC}"
        echo -e "请先运行: ${GREEN}$0 setup${NC}"
        exit 1
    fi
}

# 显示帮助
show_help() {
    echo -e "${BLUE}云计算竞争情报爬虫${NC}"
    echo ""
    echo -e "${YELLOW}用法:${NC}"
    echo -e "  $0 <命令> [选项]"
    echo ""
    echo -e "${YELLOW}命令:${NC}"
    echo -e "  ${GREEN}api${NC}       启动 API 服务"
    echo -e "  ${GREEN}crawl${NC}     爬取数据"
    echo -e "  ${GREEN}analyze${NC}   AI 分析"
    echo -e "  ${GREEN}check${NC}     数据质量检查"
    echo -e "  ${GREEN}setup${NC}     初始化环境"
    echo -e "  ${GREEN}clean${NC}     清理临时文件"
    echo -e "  ${GREEN}help${NC}      显示帮助"
    echo ""
    echo -e "${YELLOW}crawl 选项:${NC}"
    echo -e "  --vendor <名称>   指定厂商: aws, azure, gcp, huawei, tencentcloud, volcengine"
    echo -e "  --source <类型>   指定数据源: blog, whatsnew, updates"
    echo -e "  --limit <数量>    限制每个源的文章数量"
    echo -e "  --force           强制重新爬取"
    echo -e "  --debug           调试模式"
    echo ""
    echo -e "${YELLOW}api 选项:${NC}"
    echo -e "  --dev             开发模式（自动重载，默认）"
    echo -e "  --prod            生产模式（性能优化）"
    echo -e "  --host <地址>     监听地址（默认: 0.0.0.0）"
    echo -e "  --port <端口>     监听端口（默认: 8088）"
    echo -e ""
    echo -e "${YELLOW}analyze 选项:${NC}"
    echo -e "  --update-id <ID>  分析指定 ID 的更新记录"
    echo -e "  --batch           批量分析所有未处理记录"
    echo -e "  --limit <数量>    限制批量处理数量"
    echo -e "  --vendor <厂商>   仅分析指定厂商的记录"
    echo -e "  --dry-run         预览模式，不实际写入数据库"
    echo -e "  --verbose         显示详细日志"
    echo ""
    echo -e "${YELLOW}示例:${NC}"
    echo -e "  $0 api                            # 启动 API 服务（开发模式）"
    echo -e "  $0 api --prod                     # 生产模式启动"
    echo -e "  $0 api --port 8080                # 自定义端口"
    echo -e ""
    echo -e "  $0 crawl                          # 爬取所有"
    echo -e "  $0 crawl --vendor aws             # 仅爬取 AWS"
    echo -e "  $0 crawl --vendor gcp --source whatsnew  # 爬取 GCP whatsnew"
    echo -e "  $0 crawl --limit 10               # 每个源最多10篇"
    echo ""
    echo -e "  $0 analyze --update-id abc123     # 分析单条记录"
    echo -e "  $0 analyze --batch --limit 100    # 批量分析 100 条"
    echo -e "  $0 analyze --batch --vendor aws   # 仅分析 AWS 记录"
}

# 设置环境
do_setup() {
    echo -e "${BLUE}设置环境...${NC}"
    
    # 创建虚拟环境
    if [ ! -d "$VENV_DIR" ]; then
        echo "创建虚拟环境..."
        python3 -m venv "$VENV_DIR"
    fi
    
    # 激活并安装依赖
    source "$VENV_DIR/bin/activate"
    
    if [ -f "requirements.txt" ]; then
        echo "安装依赖..."
        pip install -r requirements.txt
    fi
    
    # 安装 playwright 浏览器
    echo "安装 Playwright 浏览器..."
    playwright install chromium
    
    echo -e "${GREEN}环境设置完成${NC}"
}

# 爬取数据
do_crawl() {
    check_venv
    
    echo -e "${BLUE}启动爬虫...${NC}"
    
    # 构建参数
    ARGS=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            --vendor)
                ARGS="$ARGS --vendor $2"
                shift 2
                ;;
            --source)
                ARGS="$ARGS --source $2"
                shift 2
                ;;
            --limit)
                ARGS="$ARGS --limit $2"
                shift 2
                ;;
            --force)
                ARGS="$ARGS --force"
                shift
                ;;
            --debug)
                ARGS="$ARGS --debug"
                shift
                ;;
            --config)
                ARGS="$ARGS --config $2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
    
    "$PYTHON" -m src.main $ARGS
}

# 数据质量检查
do_check() {
    check_venv
    
    echo -e "${BLUE}数据质量检查...${NC}"
    "$PYTHON" scripts/data_check.py
}

# 启动 API 服务
do_api() {
    check_venv
    
    # 默认参数
    MODE="dev"
    HOST="0.0.0.0"
    PORT="8088"
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dev)
                MODE="dev"
                shift
                ;;
            --prod)
                MODE="prod"
                shift
                ;;
            --host)
                HOST="$2"
                shift 2
                ;;
            --port)
                PORT="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
    
    # 检查 .env 文件
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}警告: .env 文件不存在${NC}"
        echo -e "建议运行: ${GREEN}cp .env.example .env${NC}"
        echo -e "然后编辑 .env 配置 GEMINI_API_KEY"
        echo ""
    fi
    
    echo -e "${BLUE}启动 API 服务...${NC}"
    echo -e "模式: ${GREEN}${MODE}${NC}"
    echo -e "地址: ${GREEN}http://${HOST}:${PORT}${NC}"
    echo -e "测试页面: ${GREEN}http://127.0.0.1:${PORT}/static/test.html${NC}"
    echo -e "API 文档: ${GREEN}http://127.0.0.1:${PORT}/docs${NC}"
    echo ""
    
    if [ "$MODE" = "dev" ]; then
        # 开发模式：自动重载
        "$PYTHON" -m uvicorn src.api.app:app \
            --host "$HOST" \
            --port "$PORT" \
            --reload
    else
        # 生产模式：多进程
        "$PYTHON" -m uvicorn src.api.app:app \
            --host "$HOST" \
            --port "$PORT" \
            --workers 4
    fi
}

# AI 分析
do_analyze() {
    check_venv
    
    echo -e "${BLUE}启动 AI 分析...${NC}"
    
    # 直接传递所有参数
    "$PYTHON" scripts/analyze_updates.py "$@"
}

# 清理临时文件
do_clean() {
    echo -e "${BLUE}清理临时文件...${NC}"
    
    # 清理 Python 缓存
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    find . -type f -name "*.pyc" -delete 2>/dev/null
    
    # 清理日志
    if [ -d "logs" ]; then
        rm -rf logs/*
        echo "已清理 logs 目录"
    fi
    
    echo -e "${GREEN}清理完成${NC}"
}

# 主入口
case "${1:-help}" in
    api)
        shift
        do_api "$@"
        ;;
    crawl)
        shift
        do_crawl "$@"
        ;;
    analyze)
        shift
        do_analyze "$@"
        ;;
    setup)
        do_setup
        ;;
    check)
        do_check
        ;;
    clean)
        do_clean
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}"
        show_help
        exit 1
        ;;
esac
