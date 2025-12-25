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
    echo -e "  ${GREEN}crawl${NC}     爬取数据"
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
    echo -e "${YELLOW}示例:${NC}"
    echo -e "  $0 crawl                          # 爬取所有"
    echo -e "  $0 crawl --vendor aws             # 仅爬取 AWS"
    echo -e "  $0 crawl --vendor gcp --source whatsnew  # 爬取 GCP whatsnew"
    echo -e "  $0 crawl --limit 10               # 每个源最多10篇"
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
    crawl)
        shift
        do_crawl "$@"
        ;;
    setup)
        do_setup
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
