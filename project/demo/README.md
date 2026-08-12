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

## 当前 Demo 限制

- 会话保存在后端内存中，重启即清空。
- 首版采用显式半双工：学生点击说话，再点击“我说完了”。
- 金标准题使用确定性步骤引导；陌生题已允许进入，但动态参考解法生成仍需进一步接入 LLM 教学链路。
- 数学步骤判断目前是规则化 Demo，不代表生产级准确率。
- 尚未实现登录、多用户并发、长期学情和家长端。
