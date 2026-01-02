# Cloud Intelligence Spy (CNetSpy)

**云计算竞争情报爬虫系统**

CNetSpy 是一个全栈式竞争情报系统，旨在自动化监控全球主流云厂商（AWS、Azure、Google Cloud、华为云、腾讯云、火山引擎等）的产品动态、技术博客和发布说明。

系统集成了 **多源数据爬取**、**AI 智能分析**（基于 Gemini/Claude）、**Web 可视化大屏** 以及 **MCP (Model Context Protocol) 服务**，帮助用户高效获取和分析云技术领域的最新趋势。

---

## ✨ 核心功能

*   **🌐 多厂商全覆盖**: 支持 AWS, Azure, GCP, 华为云, 腾讯云, 火山引擎。
*   **🕷️ 多渠道采集**: 自动抓取产品更新日志 (What's New)、技术博客 (Tech Blogs) 等多源异构数据。
*   **🧠 AI 智能分析**:
    *   自动提取核心内容摘要。
    *   智能识别产品分类与子类。
    *   提取技术标签。
    *   跨语言自动翻译（英译中）。
*   **📊 数据质量管理**: 内置强大的数据检查工具，支持自动检测重复、空分类、URL 异常，并提供 CLI 一键修复建议。
*   **🖥️ Web 可视化**: 基于 React + Tailwind CSS 的现代化仪表盘，支持多维筛选、时间线浏览和趋势分析。
*   **🤖 MCP Server 集成**: 提供 MCP 协议接口，可直接作为 Claude Desktop 或 Cursor 的上下文工具使用，实现对话式数据查询。
*   **⏰ 自动化调度**: 内置调度器，支持每日自动爬取、分析及生成周报/月报。

---

## 🚀 快速开始

### 前置要求
*   Linux / macOS
*   Python 3.10+
*   Node.js 18+ (用于前端)

### 1. 安装与初始化
项目提供了一键初始化脚本，会自动创建虚拟环境、安装 Python/Node.js 依赖并下载 Playwright 浏览器内核。

```bash
# 赋予脚本执行权限
chmod +x run.sh

# 执行初始化
./run.sh setup
```

### 2. 配置环境
复制示例配置文件并填入必要的 API Key（主要用于 AI 分析）。

```bash
cp .env.example .env
vim .env
# 填入 GEMINI_API_KEY 或其他模型配置
```

### 3. 启动服务
一键启动所有服务（后端 API + 前端 Web + MCP Server）：

```bash
# 开发模式（支持热重载）
./run.sh start dev

# 生产模式
./run.sh start
```
启动后访问：
- **Web UI**: http://localhost:5173 (Dev) 或 http://localhost:3000 (Prod)
- **API Docs**: http://localhost:8088/docs

---

## 🛠️ 常用命令指南

项目核心操作均通过 `./run.sh` 脚本管理。

### 🕷️ 数据爬取 (Crawler)
```bash
# 爬取所有厂商的所有源
./run.sh crawl

# 仅爬取特定厂商
./run.sh crawl --vendor tencentcloud

# 指定数据源类型（支持模糊匹配）
./run.sh crawl --vendor aws --source blog

# 强制重爬（忽略已存在记录）
./run.sh crawl --vendor tencentcloud --force
```

### 🧠 AI 分析 (Analyzer)
```bash
# 自动分析所有未处理的记录
./run.sh analyze

# 指定厂商进行分析
./run.sh analyze --vendor tencentcloud

# 批量分析指定 ID
./run.sh analyze --batch id1,id2,id3
```

### 🏥 数据体检与修复 (Data Check)
强大的数据治理工具，用于发现和修复数据质量问题。

```bash
# 全量检查（完整性、格式、重复、AI 质量等）
./run.sh check

# 查看待处理的质量问题（如空分类、非网络内容等）
./run.sh check --issues

# 针对问题的修复操作（系统会在 --issues 输出中给出建议命令）
# 示例：手动归类
./run.sh check --resolve <ID> --set-subcategory "Private 5G"
# 示例：删除无效记录
./run.sh check --resolve <ID> --delete
```

### 🤖 Model Context Protocol (MCP)
启动 MCP Server，允许 LLM 直接调用系统工具。

```bash
# 启动 SSE 模式（适用于 Cursor/远程调用）
./run.sh mcp --sse

# 启动 Stdio 模式（适用于本地 Claude Desktop）
./run.sh mcp
```

---

## 📂 项目结构

```
cnetspy/
├── config/             # 配置文件 (厂商源、Prompt、调度配置等)
├── data/               # 数据存储
│   ├── raw/            # 爬取的原始 Markdown/HTML 文件
│   └── sqlite/         # 核心数据库 (updates.db)
├── scripts/            # 实用维护脚本 (如数据检查、迁移等)
├── src/                # 后端源码
│   ├── api/            # FastAPI 服务端
│   ├── analyzers/      # AI 分析逻辑
│   ├── crawlers/       # 各厂商爬虫实现
│   ├── mcp/            # MCP Server 实现
│   └── storage/        # 数据库与文件存储层
├── web/                # 前端源码 (React)
└── run.sh              # 项目主控脚本
```

## 📅 定时任务
系统内置调度器，默认配置如下（可在 `config/scheduler.yaml` 中修改）：
*   **每日 08:00**: 执行全量爬取 + 自动分析。
*   **每周一 09:00**: 生成周报。
*   **每月 1日 09:00**: 生成月报。

手动触发任务：
```bash
./run.sh scheduler --job daily_crawl_analyze
```

---

## 📝 License
[MIT](LICENSE)
