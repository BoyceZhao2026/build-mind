"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import { API_BASE, apiJson, upload } from "@/lib/api";
import { browserRecordingToWav } from "@/lib/audio";

type Stage = "upload" | "confirm" | "ready" | "call" | "geometry";
type Problem = {
  problem_id: string;
  confirmed_text: string;
  problem_type: string;
  matched_case_id: string | null;
  match_score: number;
  objects: { object_id: string; name: string; value: unknown; unit: string | null; role: string }[];
  relationships: { relationship_id: string; natural_language: string }[];
  review_reasons: string[];
  diagram_graph?: DiagramGraph | null;
};
type Session = {
  session_id: string;
  phase: string;
  current_task: string;
  confirmed_steps: string[];
  turn_count: number;
  completion_summary?: CompletionSummary | null;
};
type CompletionSummary = {
  title: string; method: string; key_relationship: string; steps: string[];
  common_pitfall?: string | null; closing_message: string; trigger: "student" | "system";
};
type Message = { id: string; role: "student" | "assistant"; text: string; verdict?: string };
type Blackboard = { current_task: string; focus_objects: string[]; relation?: string; confirmed_steps: string[] };
type ReasoningNode = { node_id: string; claim: string; evidence: string; normalized_math?: string | null; verification_status: "verified" | "partially_verified" | "rejected" | "unverified"; depends_on: string[] };
type BusinessTrace = {
  intent?: string; verdict?: string; method_summary?: string | null; alignment?: string; confidence?: number;
  reasoning_graph?: ReasoningNode[]; remaining_gap?: string | null; next_subgoal?: string; teaching_action?: string;
  history_messages_submitted?: number; reference_match?: { note?: string };
  solution_status?: "in_progress" | "solved" | "understanding_verified";
  guard?: { decision?: string; violations?: string[]; leakage_safe?: boolean };
  math_tool_checks?: { node_id: string; status: string; basis?: string; reason?: string }[];
};
type GeometryPoint = { x: number; y: number };
type GeometryResult = {
  operation: {
    status: "valid" | "invalid" | "incomplete";
    output_entities: string[];
    output_regions: { points: GeometryPoint[] }[];
    checks: { check: string; passed: boolean; detail: string }[];
    reason?: string | null;
  };
  algebraic_constraints: string[];
  result_summary?: string | null;
  verification_trace: { trace_id: string; rule_id: string; status: string; produced_constraints: string[] }[];
  diagram_patch: { caption: string; focus_entities: string[] };
};
type DebugSolution = {
  available: boolean;
  source: "matched_gold_case" | "generated_and_verified" | "generated_unverified" | "fallback" | "not_generated";
  case_id?: string | null;
  solution_paths: {
    path_id: string; method: string; age_appropriate?: boolean | null;
    steps: { step_id: string; goal?: string | null; operation?: string | null; expression_after?: string | null; result_value?: unknown; unit?: string | null }[];
  }[];
  answer?: { final_value?: unknown; unit?: string; validation_expression?: string } | null;
  note: string;
};
type DiagramGraph = {
  schema_version: string; diagram_id: string; diagram_type: string; confidence: number; status: "draft" | "confirmed";
  entities: { entity_id: string; type: string; label?: string | null; geometry: Record<string, unknown>; confidence: number; status: string }[];
  relations: { relation_id: string; predicate: string; subjects: string[]; value?: unknown; source: string; confidence: number; status: string }[];
  uncertainties: { uncertainty_id: string; description: string; affected_entity_ids: string[]; requires_confirmation: boolean }[];
};

const SAMPLE_TEXT = "甲、乙两人同时从相距360米的两地相向而行。甲每分钟走50米，乙每分钟走70米。几分钟后两人相遇？";

export default function Home() {
  const [stage, setStage] = useState<Stage>("upload");
  const [imageUrl, setImageUrl] = useState("");
  const [recognizedText, setRecognizedText] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [blackboard, setBlackboard] = useState<Blackboard | null>(null);
  const [businessTrace, setBusinessTrace] = useState<BusinessTrace | null>(null);
  const [completionSummary, setCompletionSummary] = useState<CompletionSummary | null>(null);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [status, setStatus] = useState("等待上传题目");
  const [error, setError] = useState("");
  const [debugText, setDebugText] = useState("");
  const [geometryResult, setGeometryResult] = useState<GeometryResult | null>(null);
  const [showOriginalImage, setShowOriginalImage] = useState(false);
  const [debugSolution, setDebugSolution] = useState<DebugSolution | null>(null);
  const [diagramGraph, setDiagramGraph] = useState<DiagramGraph | null>(null);
  const [diagramConfirmed, setDiagramConfirmed] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function chooseImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setProcessing(true);
    setStatus("正在识别题目…");
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    const localUrl = URL.createObjectURL(file);
    setImageUrl(localUrl);
    try {
      const result = await upload<{ normalized_display_text: string; diagram_graph?: DiagramGraph | null }>("/api/problems/recognize", "image", file, file.name);
      setRecognizedText(result.normalized_display_text);
      setDiagramGraph(result.diagram_graph ?? null);
      setDiagramConfirmed(!result.diagram_graph);
      setStage("confirm");
      setStatus("请对照图片确认识别文字");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "识别失败");
      setStatus("识别失败，请重试");
    } finally {
      setProcessing(false);
    }
  }

  async function useSample() {
    setRecognizedText(SAMPLE_TEXT);
    setImageUrl("");
    setDiagramGraph(null);
    setDiagramConfirmed(true);
    setStage("confirm");
    setStatus("示例题已载入，请确认题目");
  }

  async function confirmProblem() {
    if (!recognizedText.trim()) return;
    setProcessing(true);
    setError("");
    try {
      const confirmed = await apiJson<Problem>("/api/problems/confirm", {
        method: "POST",
        body: JSON.stringify({ confirmed_text: recognizedText, diagram_graph: diagramGraph, diagram_confirmed: diagramConfirmed }),
      });
      setProblem(confirmed);
      setStage("ready");
      setStatus(confirmed.matched_case_id ? "题目已确认，可以呼叫老师" : "陌生题：将谨慎核对后继续辅导");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "确认失败");
    } finally {
      setProcessing(false);
    }
  }

  async function startCall() {
    if (!problem) return;
    setProcessing(true);
    try {
      const created = await apiJson<Session>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({ problem }),
      });
      setSession(created);
      try {
        setDebugSolution(await apiJson<DebugSolution>(`/api/sessions/${created.session_id}/debug-solution`));
      } catch {
        setDebugSolution({ available: false, source: "not_generated", solution_paths: [], note: "内部解法调试接口暂时不可用。" });
      }
      setBlackboard({ current_task: created.current_task, focus_objects: problem.objects.slice(0, 4).map((o) => o.name), confirmed_steps: [] });
      const greeting = `你好，我们一起想这道题。我不会直接告诉你答案。先看第一个小任务：${created.current_task}。你目前有什么想法？`;
      setMessages([{ id: crypto.randomUUID(), role: "assistant", text: greeting }]);
      setStage("call");
      setStatus("AI 老师正在通话中");
      await speak(greeting);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "无法开始通话");
    } finally {
      setProcessing(false);
    }
  }

  async function startRecording() {
    setError("");
    stopSpeaking();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => event.data.size && chunksRef.current.push(event.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const browserRecording = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        const wav = await browserRecordingToWav(browserRecording);
        await transcribeAndSend(wav);
      };
      recorder.start(250);
      setRecording(true);
      setStatus("正在听你说…说完后点击结束");
    } catch {
      setError("无法使用麦克风，请检查浏览器权限");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setRecording(false);
    setProcessing(true);
    setStatus("正在理解你的想法…");
  }

  async function transcribeAndSend(blob: Blob) {
    try {
      const transcript = await upload<{ display_text: string }>("/api/speech/transcribe", "audio", blob, "student.wav");
      await sendTurn(transcript.display_text);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "语音识别失败");
      setStatus("语音识别失败，可以重试");
    } finally {
      setProcessing(false);
    }
  }

  async function sendTurn(text: string) {
    if (!session || !text.trim()) return;
    const studentMessage = { id: crypto.randomUUID(), role: "student" as const, text: text.trim() };
    setMessages((current) => [...current, studentMessage]);
    setDebugText("");
    setProcessing(true);
    try {
      const result = await apiJson<{
        assistant_text: string;
        verdict: string;
        state: Session;
        blackboard: Blackboard;
        business_trace: BusinessTrace;
      }>(`/api/sessions/${session.session_id}/turn`, {
        method: "POST",
        body: JSON.stringify({ text: text.trim() }),
      });
      setSession(result.state);
      setBlackboard(result.blackboard);
      setBusinessTrace(result.business_trace);
      setCompletionSummary(result.state.completion_summary ?? null);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", text: result.assistant_text, verdict: result.verdict }]);
      setStatus("轮到你了");
      await speak(result.assistant_text);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "处理失败");
    } finally {
      setProcessing(false);
    }
  }

  async function completeLesson() {
    if (!session || session.phase === "complete") return;
    stopSpeaking();
    setProcessing(true);
    setError("");
    setStatus("正在整理这道题的解题思路…");
    try {
      const result = await apiJson<{ state: Session; summary: CompletionSummary; assistant_text: string }>(`/api/sessions/${session.session_id}/complete`, {
        method: "POST",
        body: JSON.stringify({ trigger: "student" }),
      });
      setSession(result.state);
      setCompletionSummary(result.summary);
      setBlackboard((current) => current ? { ...current, current_task: "本题辅导已完成" } : current);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", text: result.assistant_text }]);
      setStatus("本题已完成，解题思路已整理");
      await speak(result.assistant_text);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "完成本题失败");
      setStatus("暂时无法生成总结，请重试");
    } finally {
      setProcessing(false);
    }
  }

  async function validateGeometryDemo() {
    setProcessing(true);
    setError("");
    setStatus("正在验证辅助线、区域覆盖和面积关系…");
    try {
      const result = await apiJson<GeometryResult>("/api/geometry/validate-split", {
        method: "POST",
        body: JSON.stringify({
          problem_version: 1,
          diagram_version: 1,
          original_region_id: "region_shaded",
          original_region: { points: [
            { x: 0.1, y: 0.1 }, { x: 0.9, y: 0.1 },
            { x: 0.9, y: 0.9 }, { x: 0.1, y: 0.9 },
          ] },
          splitter_id: "helper_split_1",
          splitter: { start: { x: 0.5, y: 0.1 }, end: { x: 0.5, y: 0.9 } },
          expected_part_shape: "rectangle",
          part_dimensions: [
            { width: { value: 4, unit: "cm" }, height: { value: 8, unit: "cm" } },
            { width: { value: 4, unit: "cm" }, height: { value: 8, unit: "cm" } },
          ],
        }),
      });
      setGeometryResult(result);
      setStatus(result.operation.status === "valid" ? "辅助线与面积关系已经验证" : "这条辅助线还不能形成有效解法");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "图形验证失败");
      setStatus("图形验证失败，请检查 API 日志");
    } finally {
      setProcessing(false);
    }
  }

  async function speak(text: string) {
    stopSpeaking();
    setSpeaking(true);
    try {
      const response = await fetch(`${API_BASE}/api/speech/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (response.ok) {
        const audio = new Audio(URL.createObjectURL(await response.blob()));
        audioRef.current = audio;
        audio.onended = () => setSpeaking(false);
        await audio.play();
        return;
      }
    } catch { /* fall through to browser speech */ }
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "zh-CN";
      utterance.rate = 0.95;
      utterance.onend = () => setSpeaking(false);
      window.speechSynthesis.speak(utterance);
    } else {
      setSpeaking(false);
    }
  }

  function stopSpeaking() {
    audioRef.current?.pause();
    audioRef.current = null;
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    setSpeaking(false);
  }

  function reset() {
    stopSpeaking();
    recorderRef.current?.state === "recording" && recorderRef.current.stop();
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setStage("upload"); setImageUrl(""); setRecognizedText(""); setProblem(null);
    setSession(null); setMessages([]); setBlackboard(null); setBusinessTrace(null); setCompletionSummary(null); setError("");
    setGeometryResult(null);
    setShowOriginalImage(false);
    setDebugSolution(null);
    setDiagramGraph(null);
    setDiagramConfirmed(false);
    setStatus("等待上传题目");
  }

  return (
    <main>
      <header className="topbar">
        <div className="brand"><span className="brandMark">循</span><div><strong>循循</strong><small>AI 数学陪练</small></div></div>
        <div className="promise"><span className="pulse" /> 不直接给答案，陪你一步步想明白</div>
        {stage !== "upload" && <button className="ghost" onClick={reset}>换一道题</button>}
      </header>

      {stage !== "call" ? (
        <section className="setupShell">
          {stage !== "geometry" && <div className="progress">
            {[["upload", "1", "上传题目"], ["confirm", "2", "确认题目"], ["ready", "3", "开始辅导"]].map(([key, n, label]) => (
              <div key={key} className={`progressItem ${stage === key ? "active" : ""}`}><b>{n}</b><span>{label}</span></div>
            ))}
          </div>}

          {stage === "upload" && <div className="heroCard">
            <div className="eyebrow">六年级 · 数学应用题</div>
            <h1>把题目交给我，<br/><em>思路留给你。</em></h1>
            <p>上传一道清晰的题目图片。识别后由你确认，再像打电话一样和 AI 老师讨论。</p>
            <label className={`uploadZone ${processing ? "busy" : ""}`}>
              <input type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseImage} disabled={processing}/>
              <span className="uploadIcon">↥</span>
              <strong>{processing ? "正在识别题目…" : "选择题目图片"}</strong>
              <small>支持 JPG、PNG、WebP，最大 10MB</small>
            </label>
            <button className="sampleLink" onClick={useSample}>没有图片？使用内置示例题 →</button>
            <button className="geometryLink" onClick={() => { setStage("geometry"); setStatus("图形题确定性验证实验台"); }}>体验图形题技术原型 →</button>
          </div>}

          {stage === "geometry" && <div className="geometryLab">
            <div className="geometryIntro">
              <div><div className="eyebrow">图形题 · 技术原型</div><h2>先验证结构，再讨论计算</h2></div>
              <p>这里使用一条学生确认的辅助线，验证它是否把原区域完整分成两个互不重叠的长方形。像素面积只验证覆盖关系，真实面积由已确认尺寸交给 SymPy 计算。</p>
            </div>
            <div className="geometryViews">
              <article className="diagramCard sourceDiagram">
                <header><b>原题示意</b><small>事实核对层</small></header>
                <svg viewBox="0 0 100 100" role="img" aria-label="原始长方形示意图">
                  <rect x="10" y="10" width="80" height="80" fill="#dceee6" stroke="#18312b" strokeWidth="2"/>
                  <text x="50" y="7" textAnchor="middle">8 cm</text>
                  <text x="94" y="52">8 cm</text>
                </svg>
                <p>原图只用于确认边界、标注和题意，不从像素比例推断真实长度。</p>
              </article>
              <article className="diagramCard teachingDiagram">
                <header><b>AI 教学黑板</b><small>{geometryResult ? "已生成验证高亮" : "候选辅助线"}</small></header>
                <svg viewBox="0 0 100 100" role="img" aria-label="SVG 重绘教学图">
                  {!geometryResult && <rect x="10" y="10" width="80" height="80" fill="#edf5f1" stroke="#18312b" strokeWidth="2"/>}
                  {geometryResult?.operation.output_regions.map((region, index) => <polygon
                    key={geometryResult.operation.output_entities[index]}
                    points={region.points.map((point) => `${point.x * 100},${point.y * 100}`).join(" ")}
                    className={`verifiedRegion region${index + 1}`}
                  />)}
                  <line x1="50" y1="10" x2="50" y2="90" className={geometryResult?.operation.status === "valid" ? "helperLine verified" : "helperLine"}/>
                  <text x="30" y="54" textAnchor="middle">4 × 8</text>
                  <text x="70" y="54" textAnchor="middle">4 × 8</text>
                </svg>
                <p>{geometryResult?.diagram_patch.caption ?? "黄色虚线是学生提出、尚未验证的辅助线。"}</p>
              </article>
            </div>
            <div className="geometryActions">
              <button className="primary" onClick={validateGeometryDemo} disabled={processing}>{processing ? "正在验证…" : "确认辅助线并执行验证"}</button>
              <button className="ghost" onClick={() => setGeometryResult(null)} disabled={!geometryResult}>重置验证</button>
            </div>
            {geometryResult && <div className="geometryEvidence">
              <article><h3>空间检查</h3><ul>{geometryResult.operation.checks.map((check) => <li key={check.check} className={check.passed ? "pass" : "fail"}><span>{check.passed ? "✓" : "×"}</span><div><b>{check.check}</b><small>{check.detail}</small></div></li>)}</ul></article>
              <article><h3>数学约束</h3>{geometryResult.algebraic_constraints.map((constraint) => <code key={constraint}>{constraint}</code>)}<p>{geometryResult.result_summary}</p></article>
              <article><h3>验证轨迹</h3>{geometryResult.verification_trace.map((trace) => <div className="traceRow" key={trace.trace_id}><b>{trace.rule_id}</b><span>{trace.status}</span></div>)}</article>
            </div>}
          </div>}

          {stage === "confirm" && <div className="confirmGrid">
            <div className="panel imagePanel">
              <div className="panelTitle"><span>原始图片</span><small>请重点核对数字与单位</small></div>
              {imageUrl ? <img src={imageUrl} alt="上传的题目"/> : <div className="samplePaper"><span>示例题</span><p>{SAMPLE_TEXT}</p></div>}
            </div>
            <div className="panel editPanel">
              <div className="panelTitle"><span>识别结果</span><small>可以直接修改</small></div>
              <textarea value={recognizedText} onChange={(e) => setRecognizedText(e.target.value)} aria-label="识别出的题目"/>
              {diagramGraph && <div className="diagramConfirmation">
                <div className="diagramConfirmTitle"><b>识别到题目图形</b><span>{diagramGraph.diagram_type} · {Math.round(diagramGraph.confidence * 100)}%</span></div>
                <div className="diagramEntityList">
                  {diagramGraph.entities.slice(0, 12).map((entity) => <span key={entity.entity_id}>{entity.label || entity.entity_id}<small>{entity.type}</small><code>{JSON.stringify(entity.geometry)}</code></span>)}
                </div>
                {diagramGraph.relations.length > 0 && <ul>{diagramGraph.relations.slice(0, 8).map((relation) => <li key={relation.relation_id}><code>{relation.predicate}({relation.subjects.join(", ")})</code><small>{relation.source} · {Math.round(relation.confidence * 100)}%</small></li>)}</ul>}
                {diagramGraph.uncertainties.map((item) => <div className="diagramUncertainty" key={item.uncertainty_id}>需要核对：{item.description}</div>)}
                <label className="diagramConfirmCheck"><input type="checkbox" checked={diagramConfirmed} onChange={(event) => setDiagramConfirmed(event.target.checked)}/><span>我已对照原图确认这些图形对象和关键关系</span></label>
              </div>}
              <div className="notice">确认后才会分析题目；AI 不会在识图阶段补条件或解题。</div>
              <button className="primary" onClick={confirmProblem} disabled={processing || (!!diagramGraph && !diagramConfirmed)}>{processing ? "正在确认…" : diagramGraph && !diagramConfirmed ? "请先确认图形" : "题目无误，继续"}</button>
            </div>
          </div>}

          {stage === "ready" && problem && <div className="readyCard">
            <div className="readyIcon">✓</div><div className="eyebrow">题目已确认</div>
            <h2>{problem.matched_case_id ? "我已经准备好陪你思考" : "这是一道新题，我们会更谨慎地核对"}</h2>
            <p>{problem.confirmed_text}</p>
            <div className="chips">
              <span>{problem.problem_type === "motion" ? "行程问题" : "应用题"}</span>
              <span>{problem.matched_case_id ? "已匹配参考步骤" : "动态生成思路"}</span>
              <span>引导模式</span>
            </div>
            <button className="callButton" onClick={startCall} disabled={processing}><span>☎</span>{processing ? "正在接通…" : "呼叫 AI 老师"}</button>
            <small className="privacy">麦克风只在你点击说话后开启</small>
          </div>}
          {error && <div className="errorBanner">{error}</div>}
          <div className="statusLine">{status}</div>
        </section>
      ) : (
        <section className="classroom">
          <aside className="problemRail">
            <div className="railHeader">本题</div>
            {imageUrl && <button className="railProblemImage" onClick={() => setShowOriginalImage(true)} aria-label="放大查看原题图片">
              <img src={imageUrl} alt="学生上传的原题和图形"/>
              <span>查看原题图</span>
            </button>}
            <p>{problem?.confirmed_text}</p>
            <div className="objectList">
              {problem?.objects.slice(0, 6).map((object) => <div key={object.object_id}><span>{object.name}</span><b>{object.value == null ? "?" : `${object.value}${object.unit ?? ""}`}</b></div>)}
            </div>
            {problem?.review_reasons.length ? <div className="caution">新题模式 · 正在谨慎核对</div> : <div className="matched">已加载参考步骤</div>}
          </aside>

          <section className="callStage">
            <div className="callTop"><span className="liveDot"/><div><b>AI 老师</b><small>{session?.phase === "complete" ? "本题已完成" : speaking ? "正在讲解" : recording ? "正在听你说" : "在线"}</small></div><time>{session?.turn_count ?? 0} 轮对话</time></div>
            <div className="conversation">
              {messages.map((message) => <div className={`message ${message.role}`} key={message.id}>
                <span className="speaker">{message.role === "assistant" ? "AI 老师" : "我"}</span>
                <p onClick={() => message.role === "assistant" && speak(message.text)}>{message.text}</p>
                {message.role === "assistant" && <small>点击文字可重新朗读</small>}
              </div>)}
              {completionSummary && <article className="summaryCard">
                <div className="summaryHeading"><span>思路总结</span><small>{completionSummary.trigger === "student" ? "你主动完成" : "理解验证完成"}</small></div>
                <h2>{completionSummary.title}</h2>
                <section><label>使用的方法</label><p>{completionSummary.method}</p></section>
                <section><label>关键数量关系</label><strong>{completionSummary.key_relationship}</strong></section>
                <section><label>思路步骤</label><ol>{completionSummary.steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol></section>
                {completionSummary.common_pitfall && <section className="pitfall"><label>下次注意</label><p>{completionSummary.common_pitfall}</p></section>}
                <footer>{completionSummary.closing_message}</footer>
              </article>}
              {processing && <div className="thinking"><i/><i/><i/> 正在认真理解你的思路</div>}
              <div ref={bottomRef}/>
            </div>
            <div className="callControls">
              {session?.phase === "complete" && <div className="completeBanner">✓ 本题辅导已完成，可以点击右上角换一道题</div>}
              {speaking && <button className="interrupt" onClick={stopSpeaking}>打断讲解</button>}
              <button className={`micButton ${recording ? "recording" : ""}`} onClick={recording ? stopRecording : startRecording} disabled={processing || speaking || session?.phase === "complete"}>
                <span>{recording ? "■" : "●"}</span>{recording ? "我说完了" : "点击说话"}
              </button>
              {session?.phase !== "complete" && <button className="finishButton" onClick={completeLesson} disabled={processing || speaking || recording}>✓ 我已理解，完成本题</button>}
              <div className="debugInput"><input disabled={session?.phase === "complete"} value={debugText} onChange={(e) => setDebugText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendTurn(debugText)} placeholder="调试：也可以输入文字"/><button disabled={session?.phase === "complete"} onClick={() => sendTurn(debugText)}>发送</button></div>
              <small>{status}</small>
            </div>
          </section>

          <aside className="blackboard">
            <div className="boardTitle"><span>AI 黑板</span><small>只显示当前必要信息</small></div>
            <section><label>当前小任务</label><h3>{blackboard?.current_task}</h3></section>
            <section><label>关注这些量</label><div className="boardChips">{blackboard?.focus_objects.map((item) => <span key={item}>{item}</span>)}</div></section>
            {blackboard?.relation && <section><label>正在建立的关系</label><p>{blackboard.relation}</p></section>}
            <section><label>已经确认</label>{blackboard?.confirmed_steps.length ? <ol>{blackboard.confirmed_steps.map((item) => <li key={item}>{item}</li>)}</ol> : <p className="muted">还没有，慢慢来</p>}</section>
            <div className="boardRule">先说想法 → 一起验证 → 再走下一步</div>
            <details className="logicPanel" open>
              <summary>业务逻辑观察台</summary>
              {!businessTrace ? <p className="muted">学生回答后，这里会展示系统的结构化判断。</p> : <>
                <div className="logicGrid">
                  <div><label>意图 / 判断</label><b>{businessTrace.intent} · {businessTrace.verdict}</b></div>
                  <div><label>思路连续性</label><b>{businessTrace.alignment} · {Math.round((businessTrace.confidence ?? 0) * 100)}%</b></div>
                  <div><label>教学动作</label><b>{businessTrace.teaching_action}</b></div>
                  <div><label>提交历史</label><b>{businessTrace.history_messages_submitted ?? 0} 条消息</b></div>
                  <div><label>解题状态</label><b>{businessTrace.solution_status}</b></div>
                </div>
                {businessTrace.method_summary && <section><label>学生当前思路</label><p>{businessTrace.method_summary}</p></section>}
                <section><label>学生动态推理图</label>
                  {businessTrace.reasoning_graph?.length ? <ol className="reasoningGraph">{businessTrace.reasoning_graph.map((node) => <li key={node.node_id} className={node.verification_status}>
                    <b>{node.claim}</b><small>{node.verification_status} · 证据：“{node.evidence}”</small>{node.normalized_math && <code>{node.normalized_math}</code>}
                  </li>)}</ol> : <p className="muted">尚无经过提取的数学主张</p>}
                </section>
                {businessTrace.remaining_gap && <section><label>当前缺口</label><p>{businessTrace.remaining_gap}</p></section>}
                {businessTrace.math_tool_checks?.length ? <section><label>SymPy 数学验证</label>{businessTrace.math_tool_checks.map((check) => <p key={check.node_id}>{check.node_id} · {check.status} · {check.basis || check.reason}</p>)}</section> : null}
                <section><label>下一教学目标</label><p>{businessTrace.next_subgoal}</p></section>
                <section><label>安全审核</label><p>{businessTrace.guard?.decision ?? "—"} · {businessTrace.guard?.leakage_safe ? "未泄露答案" : "需要拦截"}</p></section>
                <small className="traceNote">展示结构化业务决策证据，不展示模型内部推理文本。{businessTrace.reference_match?.note}</small>
              </>}
            </details>
            <details className="demoSolutionPanel">
              <summary>Demo 调试：内部解法与答案</summary>
              <div className="demoWarning">仅供产品测试，不属于学生教学界面</div>
              {!debugSolution?.available ? <p className="muted">{debugSolution?.note ?? "正在加载内部备课结果…"}</p> : <>
                <p className="debugSource">来源：{debugSolution.source} · {debugSolution.case_id}</p>
                {debugSolution.solution_paths.map((path) => <section key={path.path_id} className="debugPath">
                  <label>{path.method}</label>
                  <ol>{path.steps.map((step) => <li key={step.step_id}>
                    <b>{step.goal}</b>
                    <span>{step.operation}</span>
                    {step.expression_after && <code>{step.expression_after}</code>}
                  </li>)}</ol>
                </section>)}
                <section className="debugAnswer"><label>内部最终答案</label><strong>{JSON.stringify(debugSolution.answer?.final_value)} {debugSolution.answer?.unit}</strong>{debugSolution.answer?.validation_expression && <code>{debugSolution.answer.validation_expression}</code>}</section>
                <small className="traceNote">{debugSolution.note}</small>
              </>}
            </details>
          </aside>
          {error && <div className="callError">{error}</div>}
          {showOriginalImage && imageUrl && <div className="originalImageModal" role="dialog" aria-modal="true" aria-label="原题图片">
            <button className="modalBackdrop" onClick={() => setShowOriginalImage(false)} aria-label="关闭原题图片"/>
            <div className="originalImageDialog">
              <header><div><b>原题图片</b><small>用于核对题干、标注和图形</small></div><button onClick={() => setShowOriginalImage(false)} aria-label="关闭">×</button></header>
              <img src={imageUrl} alt="放大后的原题和图形"/>
            </div>
          </div>}
        </section>
      )}
    </main>
  );
}
