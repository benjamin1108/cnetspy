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
*   **🧪 完整测试体系**: 已覆盖白盒测试、黑盒 API 测试、数据层测试、配置测试、模块集成测试与覆盖率统计。

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

### 4. 运行测试
建议在提交前至少执行一次完整后端回归：

```bash
# 全量测试
./run.sh test --full

# 查看 API 覆盖率
./run.sh test --coverage
```

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

### 🧪 测试 (Testing)
项目当前测试重点覆盖后端核心链路，适合日常回归、发布前验证和问题复现。

```bash
# 1) 全量后端测试
./run.sh test --full

# 2) API 重点回归
./run.sh test --api

# 3) API 覆盖率
./run.sh test --coverage

# 4) 常用模式
./run.sh test --quick
./run.sh test --modules
./run.sh test --database
```

如果你需要直接调用 pytest，也可以继续使用：

```bash
./venv/bin/pytest \
  tests/test_update_service_whitebox.py \
  tests/test_api_app_whitebox.py \
  tests/test_api_routes_blackbox_extended.py \
  tests/test_analysis_service_whitebox.py \
  tests/test_api_routes_remaining_blackbox.py -q
```

按测试层次理解：
- 白盒测试：直接验证服务层、配置校验、应用启动逻辑、异常处理分支。
- 黑盒测试：通过 FastAPI `TestClient` 验证 API 输入输出、错误码和响应结构。
- 数据层测试：验证 SQLite 门面、Repository、CRUD、任务状态与质量跟踪。
- 集成测试：验证模块导入、关键模块协同、时间工具、Prompt 模板和配置加载。

当前后端测试规模：
- `329` 个用例全部通过。
- `src/api` 覆盖率约 `89%`。

推荐执行策略：
- 日常开发：`./run.sh test --quick`
- 接口改动后：`./run.sh test --api`
- 合并前回归：`./run.sh test --full`
- 版本发布前：`./run.sh test --full` + `./run.sh test --coverage`

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
├── tests/              # pytest 测试套件（白盒、黑盒、数据层、集成测试）
├── web/                # 前端源码 (React)
└── run.sh              # 项目主控脚本
```

测试目录示例：

```text
tests/
├── test_api_routes.py                    # 基础 API 黑盒测试
├── test_api_routes_blackbox_extended.py  # 扩展 API 黑盒测试
├── test_api_routes_remaining_blackbox.py # analysis/chat/reports 路由测试
├── test_api_app_whitebox.py              # 应用初始化 / 错误处理 / 依赖注入
├── test_update_service_whitebox.py       # 更新服务白盒测试
├── test_analysis_service_whitebox.py     # 分析服务白盒测试
├── test_database_crud.py                 # 数据层 CRUD
├── test_task_management.py               # 任务状态与进度
├── test_quality_tracking.py              # 数据质量跟踪
└── run_tests.py                          # 项目内置测试运行器
```

## 🧱 测试设计说明

### 白盒测试范围
- `src/api/app.py`
- `src/api/dependencies.py`
- `src/api/middleware/error_handler.py`
- `src/api/services/update_service.py`
- `src/api/services/analysis_service.py`

覆盖内容包括：
- 配置缺失与启动失败分支
- 调度器启停分支
- 时间与字段转换逻辑
- 任务进度解析
- 翻译流程异常处理
- 全局异常处理器返回结构

### 黑盒测试范围
- `/`
- `/health`
- `/api/v1/updates`
- `/api/v1/updates/{id}`
- `/api/v1/updates/{id}/raw`
- `/api/v1/stats/*`
- `/api/v1/vendors/*`
- `/api/v1/analysis/*`
- `/api/v1/reports/*`
- `/api/v1/chat/*`

覆盖内容包括：
- 正常查询
- 参数过滤
- 资源不存在
- 内容为空
- 服务层失败
- 返回结构与字段兼容性

### 当前仍需注意
- 前端 `web/` 目前尚未建立同等完整的可执行测试框架，当前测试重点在后端。
- `chat` 路由的部分真实第三方 SDK 初始化分支仍以 mock 为主，不建议把外部模型调用纳入单元测试。
- 如果后续新增 API 路由，建议同步补充黑盒测试和覆盖率门槛。

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
