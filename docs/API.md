# API 文档

本项目提供一组 HTTP JSON 接口，用于创建图片生成任务、创建 PPT 多页图片任务、查询任务状态，以及查看管理员审计记录。

当前接口主要服务于本项目前端页面，但外部项目也可以通过 HTTP 调用。若要暴露到公网，建议先增加 API Key、限流、CORS 配置和任务持久化。

## 服务地址

启动服务：

```bash
npm run ui
```

默认地址：

```text
http://localhost:5173
```

可通过环境变量修改端口：

```bash
UI_PORT=8080 npm run ui
```

## 环境变量

| 变量 | 必填 | 说明 |
|---|---:|---|
| `GEMINI_API_KEY` | 是 | Gemini API Key |
| `GEMINI_MODEL` | 否 | 图片模型。可以是单个模型，也可以是逗号分隔模型列表 |
| `GEMINI_BASE_URL` | 否 | Gemini API Base URL，默认 `https://generativelanguage.googleapis.com/v1beta` |
| `GEMINI_TEXT_MODEL` | 否 | 文本生成模型，PPT 大纲生成可用 |
| `UI_PORT` | 否 | HTTP 服务端口，默认 `5173` |
| `ADMIN_PASSWORD` | 管理接口必填 | 管理员登录密码 |
| `ADMIN_COOKIE_SECURE` | 否 | 设置为 `1` 时，管理员 cookie 带 `Secure` 标记 |

## 通用说明

- 请求体均为 JSON。
- 响应体均为 JSON，图片文件接口除外。
- 图片生成任务是异步任务：先创建任务拿到 `taskId`，再轮询查询任务状态。
- 任务状态存储在内存中，服务重启后会丢失。
- 当前最多保留 30 个任务，超过后会清理最旧任务。
- 风格已封装在服务端，外部项目可以先调用 `/api/styles` 获取 `styleId`，再在生成接口中传入 `styleId`。
- `/api/tasks` 和 `/api/ppt` 当前没有鉴权。
- `/api/audit`、`/api/audit/:auditId`、`/api/audit-image` 需要管理员登录 cookie。

## 错误格式

常见错误响应：

```json
{
  "error": "Prompt is required."
}
```

常见状态码：

| 状态码 | 说明 |
|---:|---|
| `400` | 请求体为空、JSON 无效或缺少必要字段 |
| `401` | 管理接口未登录、密码错误或会话过期 |
| `404` | 任务、审计记录或图片不存在 |
| `409` | 任务尚未完成，暂时不能下载图片 |
| `405` | HTTP 方法不允许 |
| `500` | 服务端错误或必要环境变量未配置 |

## 查询风格列表

```http
GET /api/styles
```

返回服务端内置的风格列表。外部项目推荐先调用此接口，让用户选择风格，然后把选中的 `id` 作为 `styleId` 传给 `/api/tasks` 或 `/api/ppt`。

### 请求示例

```bash
curl http://localhost:5173/api/styles
```

### 成功响应

```json
{
  "styles": [
    {
      "id": "character",
      "title": "通用手绘风格",
      "description": "松弛线稿、明快色块和手绘图标，适合通用主题的信息表达。",
      "tags": ["人物", "松弛线稿"],
      "aspect": "16:9",
      "negative": "彩色渐变, 3D, 强阴影, 粗黑外框, 密集文字",
      "previewUrl": "/assets/style-showcase/2026-04-15/compressed/character-16x9.png",
      "originalPreviewUrl": "/assets/style-showcase/2026-04-15/character-16x9.png"
    }
  ]
}
```

## 查询单个风格

```http
GET /api/styles/:styleId
```

返回单个风格的完整信息，包括服务端用于拼接最终提示词的 `prompt`。通常外部项目不需要直接使用 `prompt`，生成时传 `styleId` 即可。

### 请求示例

```bash
curl http://localhost:5173/api/styles/character
```

## 创建图片生成任务

```http
POST /api/tasks
Content-Type: application/json
```

### 请求字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `prompt` | string | 条件必填 | 无 | 直接生成用的提示词。未传 `styleId` 时不能为空 |
| `styleId` | string | 否 | 无 | 服务端内置风格 ID。传入后可只传 `userContent`，服务端会自动拼接风格提示词 |
| `count` | number | 否 | `2` | 图片数量，范围 `1` 到 `2` |
| `aspect` | string | 否 | 风格默认值或 `16:9` | 图片比例，如 `1:1`、`4:3`、`16:9`、`9:16` |
| `negative` | string | 否 | 风格默认值或无 | 负面提示词 |
| `size` | string | 否 | 无 | 图片尺寸，如 `1K`、`2K`、`4K` |
| `modelMode` | string | 否 | `quality` 行为 | 使用 `GEMINI_MODEL` 列表解析。`speed` 取第一个模型，`quality` 取第二个或第一个模型 |
| `model` | string | 否 | 环境变量解析 | 显式指定模型 ID，优先级高于 `modelMode` |
| `templatePrompt` | string | 否 | 风格提示词或空字符串 | 模板提示词，主要用于审计记录 |
| `userContent` | string | 条件必填 | 空字符串 | 用户原始内容。传 `styleId` 时推荐使用此字段 |
| `finalPrompt` | string | 否 | 服务端拼接或 `prompt` | 实际送入生成模型的最终提示词。传入后优先级最高 |
| `referenceImages` | array | 否 | `[]` | 参考图数组，最多 6 张 |

`referenceImages` 项格式：

```json
{
  "data": "base64 image data",
  "mimeType": "image/png"
}
```

也支持 `mime_type` 字段名。传入参考图时，本接口会强制只生成 1 张图。

### 请求示例

使用服务端封装风格：

```bash
curl -X POST http://localhost:5173/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "styleId": "character",
    "userContent": "介绍一个 AI 图片生成工具的核心能力、使用流程和适用场景",
    "count": 1,
    "size": "1K",
    "modelMode": "quality"
  }'
```

直接传完整提示词：

```bash
curl -X POST http://localhost:5173/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "一张赛博朋克风格的城市海报，中文标题：未来城市",
    "count": 1,
    "aspect": "16:9",
    "size": "1K",
    "modelMode": "quality"
  }'
```

### 成功响应

```json
{
  "taskId": "2d7e6317-6a98-4c18-b132-38f0a1aa7ec0"
}
```

状态码：`202`

## 创建 PPT 多页图片任务

```http
POST /api/ppt
Content-Type: application/json
```

该接口会先根据 `userContent` 生成 PPT 大纲，再为每一页生成一张图片。

### 请求字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `userContent` | string | 是 | 无 | PPT 内容。不能为空 |
| `styleId` | string | 否 | 无 | 服务端内置风格 ID。传入后自动使用该风格的提示词、默认比例和负面提示词 |
| `aspect` | string | 否 | 风格默认值或 `16:9` | 图片比例 |
| `size` | string | 否 | 无 | 图片尺寸，如 `1K`、`2K`、`4K` |
| `negative` | string | 否 | 风格默认值或无 | 负面提示词 |
| `templatePrompt` | string | 否 | 风格提示词或空字符串 | 模板提示词，主要用于审计记录 |
| `stylePrompt` | string | 否 | 风格提示词或空字符串 | 每页图片生成时追加的风格提示词。传入后覆盖 `styleId` 对应提示词 |
| `styleTitle` | string | 否 | 风格名称或空字符串 | 风格名称，主要用于审计记录 |
| `modelMode` | string | 否 | `quality` 行为 | 使用 `GEMINI_MODEL` 列表解析 |
| `model` | string | 否 | 环境变量解析 | 显式指定图片生成模型 ID |

### 请求示例

使用服务端封装风格：

```bash
curl -X POST http://localhost:5173/api/ppt \
  -H 'Content-Type: application/json' \
  -d '{
    "styleId": "swiss-grid",
    "userContent": "介绍一个 AI 图片生成工具的核心能力、使用流程和适用场景",
    "size": "1K"
  }'
```

直接传风格提示词：

```bash
curl -X POST http://localhost:5173/api/ppt \
  -H 'Content-Type: application/json' \
  -d '{
    "userContent": "介绍一个 AI 图片生成工具的核心能力、使用流程和适用场景",
    "aspect": "16:9",
    "size": "1K",
    "styleTitle": "瑞士极简网格",
    "stylePrompt": "经典瑞士国际主义风格，严格网格系统，大量留白，中文清晰可读"
  }'
```

### 成功响应

```json
{
  "taskId": "84a0a0f2-1d98-41ac-a7ab-2ca8fbb7ce37"
}
```

状态码：`202`

## 查询任务状态

```http
GET /api/tasks/:taskId
```

### 请求示例

```bash
curl http://localhost:5173/api/tasks/2d7e6317-6a98-4c18-b132-38f0a1aa7ec0
```

### 处理中响应

普通图片任务：

```json
{
  "id": "2d7e6317-6a98-4c18-b132-38f0a1aa7ec0",
  "status": "pending",
  "createdAt": "2026-04-16T08:00:00.000Z",
  "model": "gemini-3-pro-image-preview",
  "size": "1K"
}
```

PPT 任务：

```json
{
  "id": "84a0a0f2-1d98-41ac-a7ab-2ca8fbb7ce37",
  "type": "ppt",
  "status": "pending",
  "createdAt": "2026-04-16T08:00:00.000Z",
  "model": "gemini-3-pro-image-preview",
  "size": "1K",
  "totalSlides": 6,
  "completedSlides": 2,
  "outlineModel": "gemini-3-pro-preview"
}
```

### 完成响应

```json
{
  "id": "2d7e6317-6a98-4c18-b132-38f0a1aa7ec0",
  "status": "completed",
  "createdAt": "2026-04-16T08:00:00.000Z",
  "model": "gemini-3-pro-image-preview",
  "size": "1K",
  "images": ["base64 image data"],
  "auditId": "419365d1-b545-4382-a6e1-045d4e49cb14",
  "completedAt": "2026-04-16T08:00:12.000Z",
  "latencyMs": 12000,
  "savedImages": ["images/2026-04-16/2d7e6317-6a98-4c18-b132-38f0a1aa7ec0-1.png"],
  "savedReferences": [],
  "downloadUrls": ["/api/tasks/2d7e6317-6a98-4c18-b132-38f0a1aa7ec0/images/1"]
}
```

`images` 是 base64 编码的 PNG 图片数据，不包含 Data URL 前缀。浏览器中可这样使用：

```js
const src = `data:image/png;base64,${imageBase64}`;
```

如果外部项目只需要拿 PNG 文件，优先使用 `downloadUrls` 或下面的下载接口。它直接返回图片二进制内容，比从 JSON 里读取 base64 再解码更快，传输体积也更小。

### 失败响应

```json
{
  "id": "2d7e6317-6a98-4c18-b132-38f0a1aa7ec0",
  "status": "error",
  "createdAt": "2026-04-16T08:00:00.000Z",
  "model": "gemini-3-pro-image-preview",
  "size": "1K",
  "error": "API request failed: 400 Bad Request",
  "auditId": "419365d1-b545-4382-a6e1-045d4e49cb14",
  "completedAt": "2026-04-16T08:00:12.000Z",
  "latencyMs": 12000
}
```

## 下载任务图片

```http
GET /api/tasks/:taskId/images/:index
```

该接口直接返回生成好的 PNG 二进制内容，适合外部项目下载或转存图片。`:index` 从 `1` 开始。

接口不需要管理员登录，但任务必须仍存在于内存中，且状态必须是 `completed`。

### 请求示例

```bash
curl http://localhost:5173/api/tasks/2d7e6317-6a98-4c18-b132-38f0a1aa7ec0/images/1 \
  --output generated.png
```

### 成功响应

```http
HTTP/1.1 200 OK
Content-Type: image/png
Content-Disposition: attachment; filename="generated-2d7e6317-6a98-4c18-b132-38f0a1aa7ec0-1.png"
Content-Length: 123456
```

响应体是 PNG 文件二进制内容。

### 错误响应

任务未完成：

```json
{
  "error": "Task is not completed."
}
```

状态码：`409`

图片序号不存在：

```json
{
  "error": "Image not found."
}
```

状态码：`404`

## 管理员登录

```http
POST /api/admin/login
Content-Type: application/json
```

需要服务端配置 `ADMIN_PASSWORD`。

### 请求示例

```bash
curl -i -X POST http://localhost:5173/api/admin/login \
  -H 'Content-Type: application/json' \
  -d '{"password":"your_admin_password"}'
```

### 成功响应

```json
{
  "ok": true
}
```

成功后服务端会设置 `admin_session` HttpOnly cookie，有效期 12 小时。

## 管理员登出

```http
POST /api/admin/logout
```

### 请求示例

```bash
curl -X POST http://localhost:5173/api/admin/logout \
  --cookie 'admin_session=...'
```

### 成功响应

```json
{
  "ok": true
}
```

## 查询审计记录

```http
GET /api/audit?limit=50&offset=0
```

需要管理员登录 cookie。

### 查询参数

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|---|---|---:|---|---|
| `limit` | number | `50` | `1` 到 `100` | 返回条数 |
| `offset` | number | `0` | `0` 到 `5000` | 偏移量 |

### 请求示例

```bash
curl http://localhost:5173/api/audit?limit=20 \
  --cookie 'admin_session=...'
```

### 成功响应

```json
{
  "entries": [
    {
      "id": "419365d1-b545-4382-a6e1-045d4e49cb14",
      "taskId": "2d7e6317-6a98-4c18-b132-38f0a1aa7ec0",
      "status": "completed",
      "createdAt": "2026-04-16T08:00:00.000Z",
      "completedAt": "2026-04-16T08:00:12.000Z",
      "latencyMs": 12000,
      "model": "gemini-3-pro-image-preview",
      "aspect": "16:9",
      "size": "1K",
      "promptTemplate": "",
      "promptUser": "",
      "promptFinal": "一张赛博朋克风格的城市海报，中文标题：未来城市",
      "negative": "",
      "images": [
        {
          "index": 1,
          "path": "images/2026-04-16/2d7e6317-6a98-4c18-b132-38f0a1aa7ec0-1.png",
          "bytes": 123456,
          "sha256": "..."
        }
      ],
      "references": []
    }
  ],
  "limit": 20,
  "offset": 0
}
```

## 查询单条审计记录

```http
GET /api/audit/:auditId
```

需要管理员登录 cookie。

### 请求示例

```bash
curl http://localhost:5173/api/audit/419365d1-b545-4382-a6e1-045d4e49cb14 \
  --cookie 'admin_session=...'
```

成功响应为单条审计记录对象。

## 读取审计图片

```http
GET /api/audit-image?path=:path
```

需要管理员登录 cookie。`path` 来自审计记录中的 `images[].path` 或 `references[].path`。

### 请求示例

```bash
curl 'http://localhost:5173/api/audit-image?path=images/2026-04-16/example.png' \
  --cookie 'admin_session=...' \
  --output image.png
```

成功响应为图片二进制内容，`Content-Type` 根据文件后缀返回。

## 外部项目调用建议

后端项目调用推荐流程：

1. 调用 `POST /api/tasks` 或 `POST /api/ppt` 创建任务。
2. 保存返回的 `taskId`。
3. 每隔 1 到 3 秒调用 `GET /api/tasks/:taskId`。
4. `status` 为 `completed` 时，优先使用 `downloadUrls` 下载 PNG 文件。
5. `status` 为 `error` 时读取 `error` 字段并停止轮询。

浏览器前端跨域调用时，当前服务没有返回 CORS 头。建议让外部项目前端调用自己的后端，再由后端转发到本服务；或者在本服务中增加 CORS 支持。

公网部署前建议至少增加：

- API Key 鉴权，保护 `/api/tasks` 和 `/api/ppt`。
- 请求体大小限制，避免超大 base64 参考图撑爆内存。
- 任务持久化，避免重启丢任务。
- 对象存储上传或长期文件索引，避免任务从内存清理后无法通过 `taskId` 下载。
- 限流和并发控制，避免生成模型请求过载。
