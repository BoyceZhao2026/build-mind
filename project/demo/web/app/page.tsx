"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import { API_BASE, apiJson, upload } from "@/lib/api";
import { browserRecordingToWav } from "@/lib/audio";

type Stage = "upload" | "confirm" | "ready" | "call";
type Problem = {
  problem_id: string;
  confirmed_text: string;
  problem_type: string;
  matched_case_id: string | null;
  match_score: number;
  objects: { object_id: string; name: string; value: unknown; unit: string | null; role: string }[];
  relationships: { relationship_id: string; natural_language: string }[];
  review_reasons: string[];
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
    const localUrl = URL.createObjectURL(file);
    setImageUrl(localUrl);
    try {
      const result = await upload<{ normalized_display_text: string }>("/api/problems/recognize", "image", file, file.name);
      setRecognizedText(result.normalized_display_text);
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
        body: JSON.stringify({ confirmed_text: recognizedText }),
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
    setStage("upload"); setImageUrl(""); setRecognizedText(""); setProblem(null);
    setSession(null); setMessages([]); setBlackboard(null); setBusinessTrace(null); setCompletionSummary(null); setError("");
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
          <div className="progress">
            {[["upload", "1", "上传题目"], ["confirm", "2", "确认题目"], ["ready", "3", "开始辅导"]].map(([key, n, label]) => (
              <div key={key} className={`progressItem ${stage === key ? "active" : ""}`}><b>{n}</b><span>{label}</span></div>
            ))}
          </div>

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
          </div>}

          {stage === "confirm" && <div className="confirmGrid">
            <div className="panel imagePanel">
              <div className="panelTitle"><span>原始图片</span><small>请重点核对数字与单位</small></div>
              {imageUrl ? <img src={imageUrl} alt="上传的题目"/> : <div className="samplePaper"><span>示例题</span><p>{SAMPLE_TEXT}</p></div>}
            </div>
            <div className="panel editPanel">
              <div className="panelTitle"><span>识别结果</span><small>可以直接修改</small></div>
              <textarea value={recognizedText} onChange={(e) => setRecognizedText(e.target.value)} aria-label="识别出的题目"/>
              <div className="notice">确认后才会分析题目；AI 不会在识图阶段补条件或解题。</div>
              <button className="primary" onClick={confirmProblem} disabled={processing}>{processing ? "正在确认…" : "题目无误，继续"}</button>
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
                <section><label>下一教学目标</label><p>{businessTrace.next_subgoal}</p></section>
                <section><label>安全审核</label><p>{businessTrace.guard?.decision ?? "—"} · {businessTrace.guard?.leakage_safe ? "未泄露答案" : "需要拦截"}</p></section>
                <small className="traceNote">展示结构化业务决策证据，不展示模型内部推理文本。{businessTrace.reference_match?.note}</small>
              </>}
            </details>
          </aside>
          {error && <div className="callError">{error}</div>}
        </section>
      )}
    </main>
  );
}
