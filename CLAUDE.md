# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Project Management (via `run.sh`)
- **Start All Services**: `./run.sh start` (Production) or `./run.sh start dev` (Development with hot reload)
- **Environment Setup**: `./run.sh setup` (Creates venv, installs Python deps, installs Playwright browsers)
- **Stop Services**: `./run.sh stop`
- **Clean Temp Files**: `./run.sh clean`

### Backend (Python/FastAPI)
- **Start API**: `./run.sh api` (Dev) or `./run.sh api --prod` (Production)
- **Start MCP Server**: `./run.sh mcp` (Stdio) or `./run.sh mcp --sse` (SSE/HTTP)
- **Run Tests**: `./run.sh test` (Quick) or `./run.sh test --full` (All)
  - Single test: `python -m pytest tests/path/to/test.py`
- **Crawl Data**: `./run.sh crawl --vendor <vendor> --source <source>`
  - Example: `./run.sh crawl --vendor aws --limit 10`
- **Analyze Data**: `./run.sh analyze --update-id <id>` or `./run.sh analyze --batch <ids>`
- **Quality Check**: `./run.sh check`

### Frontend (React/Vite)
- **Start Dev Server**: `./run.sh web` (or `cd web && npm run dev`)
- **Build**: `cd web && npm run build`
- **Lint**: `cd web && npm run lint`
- **Preview**: `cd web && npm run preview`

## Architecture

### Overview
This is a monorepo containing a cloud computing competitive intelligence system. It consists of a Python backend for data crawling/analysis and a React frontend for visualization.

### Backend Structure (`src/`)
- **Crawlers** (`src/crawlers/`): Logic for fetching updates from cloud providers (AWS, Azure, GCP, etc.). Managed by `CrawlerManager`.
- **API** (`src/api/`): FastAPI application serving the REST API.
  - Entry point: `src/api/app.py`
  - Routes: `src/api/routes/`
- **Analysis** (`src/analyzers/`): AI-powered analysis of crawled data.
- **MCP** (`src/mcp/`): Model Context Protocol server implementation.
- **Reports** (`src/reports/`): Logic for generating weekly/monthly reports.
- **Scheduler** (`src/scheduler/`): Background task management.

### Frontend Structure (`web/`)
- **Tech Stack**: React, Vite, TypeScript, Tailwind CSS, TanStack Query.
- **Structure**: Standard Vite project structure.
  - `web/src/api/`: API client integration.
  - `web/src/pages/`: Route components.

### Data Flow
1. **Crawling**: `run.sh crawl` invokes `src.main` -> `CrawlerManager` to fetch data from vendor sources.
2. **Storage**: Data is stored locally (likely JSON/SQLite in `data/`).
3. **Analysis**: `analyze_updates.py` processes raw data using AI models to extract insights.
4. **API**: Exposes processed data to the frontend and MCP clients.
5. **Visualization**: Web UI consumes API to display updates, stats, and reports.
