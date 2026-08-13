# 通话式 AI 数学陪练 Demo

这是一个用于验证业务可行性的本地 Web Demo：学生上传题目图片，确认识别文本，然后通过模拟电话的界面与 AI 老师讨论。系统只做引导，不直接给答案。

## 已实现

- 桌面 Web 手动上传 JPG、PNG 或 WebP 图片。
- `qwen3-vl-flash` 忠实转写题目，学生确认后才进入辅导。
- 加载仓库根目录 `evaluation/cases/all_cases.yaml` 金标准。
- 金标准文本匹配、题目对象和参考步骤加载。
- 陌生题不拒绝，标记事后抽查原因并继续辅导。
- 拨号式开始辅导、按轮录音、Fun-ASR Realtime 转写。
- 引导状态机、逐步提示、答案请求拦截、学生质疑入口。
- 最近 6 条对话上下文、当前问题关联、理解证据和未解决问题的跨轮累积。
- 重复问题 Guard：一轮只问一个主要问题，近期相似问题会自动重写。
- 字幕、当前任务、题目对象、已确认步骤和 AI 黑板。
- CosyVoice Realtime 朗读；Mock 模式使用浏览器系统语音。
- LLM Registry 和 OpenAI-compatible Provider；真实模式下 LLM 分别完成学生步骤分析与自然教学回复生成，状态机控制教学动作，Guard 负责答案防泄露，可继续添加不同模型做回放对比。
- 图形题技术原型：Shapely 验证辅助线分割、区域覆盖和重叠，SymPy 生成面积约束，返回可追踪的几何事实与规则 DAG。
- SVG 教学黑板实验台：在首页进入“体验图形题技术原型”，对比原图示意和重绘图，并观察验证后的区域高亮、空间检查和符号关系。
- 陌生文字题在开始通话前生成动态教师备课包：LLM 提取声明式方程与候选解法，SymPy 通过安全表达式解析器完成求解、定义域和回代验证。
- 学生结构化等式会与动态备课约束做 SymPy 等价性检查，结果显示在业务逻辑观察台。
- 图片识别可同时返回 `DiagramGraphDraft`；检测到图形时，确认页展示实体、关系和不确定项，学生确认后才进入辅导。

## 目录

```text
demo/
├── api/   # FastAPI、领域模型、状态机和阿里云适配器
├── web/   # Next.js 桌面 Web
└── docker-compose.yml
```

## 1. Mock 模式快速启动

Mock 模式不需要任何云服务密钥。图片识别和语音识别会返回内置示例内容，适合先检查完整交互。

### 启动后端

```bash
cd project/demo/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

验证：打开 <http://localhost:8000/health>。

### 启动前端

另开一个终端：

```bash
cd project/demo/web
npm install
cp .env.local.example .env.local
npm run dev
```

打开 <http://localhost:3000>，也可以直接点击“使用内置示例题”。

### 统一启动并保存日志

依赖安装完成后，也可以在 `project/demo` 下执行：

```bash
python3 scripts/dev.py
```

日志会持续追加到：

```text
logs/api.log
logs/web.log
logs/model-calls.jsonl
```

实时查看：

```bash
tail -f logs/api.log
tail -f logs/web.log
tail -f logs/model-calls.jsonl
```

`model-calls.jsonl` 只记录任务类型、模型、耗时、token、状态和错误类型，
不记录 API Key、图片、音频、完整提示词或学生原文。

## 2. 阿里云模式

编辑 `api/.env`：

```dotenv
DEMO_MODE=aliyun
DISABLE_SYSTEM_PROXY=true
DASHSCOPE_API_KEY=你的百炼APIKey
DASHSCOPE_WORKSPACE_ID=你的业务空间ID
```

`DISABLE_SYSTEM_PROXY=true` 会在 API 进程启动时清除继承到的
`HTTP_PROXY`、`HTTPS_PROXY` 和 `ALL_PROXY`，并设置 `NO_PROXY=*`。
因此 FastAPI 内的 OpenAI-compatible 客户端、DashScope SDK 和 WebSocket
调用不会使用电脑代理。若将来需要代理，改为 `false` 后重启 API。

当前默认模型：

- 图片识别：`qwen3-vl-flash`
- STT：`fun-asr-realtime`
- TTS：`cosyvoice-v3-flash`
- TTS 音色：`longanyang`（与 CosyVoice v3 匹配）
- 学生步骤判断 LLM：`qwen-plus`（可通过 `QWEN_LLM_MODEL` 替换）

API Key 只能放在 `api/.env`，不要写入前端环境变量或提交到 Git。

浏览器录音结束后会在前端解码，并转换成 16 kHz、16 bit、单声道 WAV，
再发送给 Fun-ASR，避免直接上传 WebM 导致 `UNSUPPORTED_FORMAT`。

## 3. 测试与构建

```bash
cd project/demo/api
source .venv/bin/activate
pytest

cd ../web
npm run build
```

### 图形题确定性闭环

首版图形能力故意从人工确认的结构化图形开始，不把视觉识别和数学验证同时混在一个步骤中：

```text
确认后的多边形 + 学生确认的辅助线
→ Shapely 分割、覆盖、重叠和碎片检查
→ GeometryFact 与 VerificationTrace
→ SymPy 面积约束
→ SVG 区域高亮
```

API：

```text
POST /api/geometry/validate-split
```

Shapely、SymPy 和 OpenCV 类能力都在本地 API 内运行；当前接口只返回学生可见的符号关系，内部数值仅用于验证，不在实验台直接展示最终答案。

## 当前 Demo 限制

- 会话保存在后端内存中，重启即清空。
- 为便于复现视觉识别问题，上传原图默认保存在 `project/demo/tmp/uploads`，保留 24 小时并在后续上传时清理过期文件；可通过 `.env` 中的 `SAVE_UPLOADED_IMAGES=false` 关闭。
- 首版采用显式半双工：学生点击说话，再点击“我说完了”。
- 金标准题提供参考路径；陌生文字题会动态生成备课包，只有通过 SymPy 验证的备课包才作为教学参考。动态备课的覆盖率和多解法质量仍需持续评测。
- 数学步骤判断目前是规则化 Demo，不代表生产级准确率。
- 上传图形题会由多模态模型生成 `DiagramGraphDraft`，目前只支持批量确认；尚未支持在原图上逐个修改实体、标注绑定和阴影边界，也尚未自动接入通用几何求解器。
- 已接通首条图形备课闭环：确认后的网格行列、单格面积和多边形格点坐标会转换成几何事实，经面积规则与 SymPy 回代验证后生成备课包。仅有整图归一化坐标时拒绝计算，避免把图片坐标误当网格坐标。
- 几何规则首版只实现“辅助线分割为多个已确认长方形并相加”，圆、三角形、补形和平移规则尚待按文档顺序接入。
- 尚未实现登录、多用户并发、长期学情和家长端。
