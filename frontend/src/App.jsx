import { useState, useRef, useEffect, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import {
  Download,
  Search,
  Loader2,
  MessageCircle,
  Send,
  FileText,
  FileJson,
  X,
  Clock,
  Database,
  Shield,
  DollarSign,
  Sparkles,
  Settings,
  BookOpen,
} from "lucide-react";
import "./App.css";

function App() {
  const [topic, setTopic] = useState("");
  const [depth, setDepth] = useState("deep");
  const [outputFormat, setOutputFormat] = useState("both");
  const [loading, setLoading] = useState(false);
  const [reportUrl, setReportUrl] = useState(null);
  const [reportContent, setReportContent] = useState(null);
  const [reportId, setReportId] = useState(null);
  const [error, setError] = useState(null);
  const [progressSteps, setProgressSteps] = useState([]);
  const [activeTab, setActiveTab] = useState("markdown");

  // Chat state
  const [chatEnabled, setChatEnabled] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  // Report metadata state
  const [confidenceScores, setConfidenceScores] = useState({});
  const [sourceCount, setSourceCount] = useState(0);
  const [runtimeSeconds, setRuntimeSeconds] = useState(0);
  const [costEstimate, setCostEstimate] = useState(0);
  const [jsonReport, setJsonReport] = useState(null);

  const chatEndRef = useRef(null);
  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Extract executive summary from report content
  const executiveSummary = useMemo(() => {
    if (!reportContent) return null;
    // Try to find the executive summary section
    const patterns = [
      /## Executive Summary\n([\s\S]*?)(?=\n## )/i,
      /# Executive Summary\n([\s\S]*?)(?=\n#+ )/i,
      /## Summary\n([\s\S]*?)(?=\n## )/i,
    ];
    for (const pattern of patterns) {
      const match = reportContent.match(pattern);
      if (match) return match[1].trim();
    }
    return null;
  }, [reportContent]);

  // Compute average confidence
  const avgConfidence = useMemo(() => {
    const vals = Object.values(confidenceScores);
    return vals.length > 0
      ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
      : null;
  }, [confidenceScores]);

  const handleResearch = async () => {
    if (!topic.trim()) return;

    setLoading(true);
    setError(null);
    setReportUrl(null);
    setReportContent(null);
    setReportId(null);
    setProgressSteps([]);
    setChatEnabled(false);
    setChatOpen(false);
    setChatMessages([]);
    setConfidenceScores({});
    setSourceCount(0);
    setRuntimeSeconds(0);
    setCostEstimate(0);
    setJsonReport(null);

    try {
      const response = await fetch(`${API_URL}/api/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, depth, output_format: outputFormat }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;

          if (line.startsWith("data:") || line.startsWith("data: ")) {
            const dataStr = line.replace(/^data:\s*/, "");
            try {
              const eventData = JSON.parse(dataStr);
              handleSSEEvent(eventData);
            } catch (e) {
              console.warn("Failed to parse SSE data:", dataStr);
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setError(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSSEEvent = (eventData) => {
    const { type, message, data } = eventData;

    const iconMap = {
      query_analyzing: "🔍",
      query_analyzed: "✅",
      cache_hit: "⚡",
      plan_generating: "📋",
      plan_generated: "✅",
      section_researching: "🔎",
      section_writing: "✍️",
      section_complete: "✅",
      reflection_loop: "🔄",
      fact_checking: "🔬",
      fact_check_complete: "✅",
      synthesis_writing: "✍️",
      compiling_output: "📄",
      report_ready: "🎉",
      error: "❌",
    };

    const icon = iconMap[type] || "🔄";

    setProgressSteps((prev) => [
      ...prev,
      {
        id: Date.now(),
        type,
        message,
        icon,
        data: data || {},
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);

    // Handle report_ready event
    if (type === "report_ready" && data) {
      setReportContent(data.content || data.markdown_content);
      setReportId(data.report_id);
      setChatEnabled(data.chat_enabled || false);
      if (data.pdf_url && data.pdf_filename) {
        setReportUrl(`${API_URL}${data.pdf_url}`);
      }
      setConfidenceScores(data.confidence_scores || {});
      setSourceCount(data.source_count || 0);
      setRuntimeSeconds(data.runtime_seconds || 0);
      setCostEstimate(data.cost_estimate_usd || 0);
      setJsonReport(data.json_report || null);
      setLoading(false);
    }

    if (type === "error") {
      setError(message);
      setLoading(false);
    }
  };

  const handleChat = async () => {
    if (!chatInput.trim() || !reportId) return;

    const question = chatInput;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: question }]);
    setChatLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/chat/${reportId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (!response.ok) throw new Error("Chat request failed");

      const result = await response.json();
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.answer,
          sources: result.sources || [],
        },
      ]);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.message}`, sources: [] },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion) => {
    setChatInput(suggestion);
  };

  const handleDownload = () => {
    if (reportUrl) window.open(reportUrl, "_blank");
  };

  const SUGGESTION_CHIPS = [
    "What are the key findings?",
    "Which sources were most cited?",
    "Any limitations or gaps?",
  ];

  return (
    <div className="container">
      <header className="header">
        <h1>Deep Research Agent</h1>
        <p className="subtitle">
          AI-powered deep research with real-time progress tracking
        </p>
        <span className="version-badge">v2.0</span>
      </header>

      {/* Search Card */}
      <div className="card">
        <div className="input-group">
          <input
            type="text"
            placeholder="What would you like to research?"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleResearch()}
          />
          <select
            className="depth-select"
            value={depth}
            onChange={(e) => setDepth(e.target.value)}
            title="Research depth"
          >
            <option value="quick">Quick</option>
            <option value="deep">Deep</option>
          </select>
          <select
            className="format-select"
            value={outputFormat}
            onChange={(e) => setOutputFormat(e.target.value)}
            title="Output format"
          >
            <option value="both">PDF + MD</option>
            <option value="pdf">PDF Only</option>
            <option value="markdown">Markdown Only</option>
          </select>
          <button onClick={handleResearch} disabled={loading}>
            {loading ? (
              <Loader2 className="spinner-icon" size={18} />
            ) : (
              <Search size={18} />
            )}
            {loading ? "Researching..." : "Research"}
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>❌</span> {error}
        </div>
      )}

      {/* Progress Timeline */}
      {progressSteps.length > 0 && (
        <div className="progress-timeline">
          <h3 className="timeline-title">Research Progress</h3>
          <div className="timeline-steps">
            {progressSteps.map((step) => (
              <div
                key={step.id}
                className={`timeline-step ${step.type === "error" ? "step-error" : ""}`}
              >
                <span className="step-icon">{step.icon}</span>
                <span className="step-message">{step.message}</span>
                {step.data?.sections && (
                  <span className="step-badge">
                    {step.data.sections.length} sections
                  </span>
                )}
                {step.data?.confidence_score && (
                  <span className="confidence-badge">
                    {Math.round(step.data.confidence_score)}%
                  </span>
                )}
                <span className="step-time">{step.timestamp}</span>
              </div>
            ))}
            {loading && (
              <div className="timeline-step step-active">
                <span className="step-icon">
                  <Loader2 size={16} className="spinner-icon" />
                </span>
                <span className="step-message">Processing...</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Report Display */}
      {reportContent && (
        <div className="report-container">
          <div className="report-header">
            <h2>
              <Search size={18} /> Research Report: {topic}
            </h2>
            <div className="report-actions">
              {reportUrl && (
                <button
                  className="action-btn"
                  onClick={handleDownload}
                  title="Download PDF"
                >
                  <Download size={16} /> PDF
                </button>
              )}
              {chatEnabled && (
                <button
                  className="action-btn chat-btn"
                  onClick={() => setChatOpen(!chatOpen)}
                  title="Ask questions about this report"
                >
                  <MessageCircle size={16} /> Chat
                </button>
              )}
            </div>
          </div>

          {/* Report Metadata Bar */}
          {(runtimeSeconds > 0 ||
            sourceCount > 0 ||
            avgConfidence !== null) && (
            <div className="report-meta-bar">
              {runtimeSeconds > 0 && (
                <div className="meta-chip">
                  <Clock size={13} />
                  <span>{runtimeSeconds.toFixed(1)}s</span>
                </div>
              )}
              {sourceCount > 0 && (
                <div className="meta-chip">
                  <Database size={13} />
                  <span>{sourceCount} sources</span>
                </div>
              )}
              {avgConfidence !== null && (
                <div
                  className={`meta-chip ${avgConfidence >= 70 ? "meta-high" : "meta-low"}`}
                >
                  <Shield size={13} />
                  <span>{avgConfidence}% avg confidence</span>
                </div>
              )}
              {costEstimate > 0 && (
                <div className="meta-chip">
                  <DollarSign size={13} />
                  <span>${costEstimate.toFixed(4)}</span>
                </div>
              )}
            </div>
          )}

          {/* Executive Summary Card */}
          {executiveSummary && (
            <div className="exec-summary-card">
              <div className="exec-summary-header">
                <BookOpen size={15} />
                <span>Executive Summary</span>
              </div>
              <div className="exec-summary-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {executiveSummary}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* Format Tabs */}
          <div className="format-tabs">
            <button
              className={`tab ${activeTab === "markdown" ? "tab-active" : ""}`}
              onClick={() => setActiveTab("markdown")}
            >
              <FileText size={14} /> Rendered
            </button>
            <button
              className={`tab ${activeTab === "pdf" ? "tab-active" : ""}`}
              onClick={() => setActiveTab("pdf")}
            >
              <Download size={14} /> PDF
            </button>
            <button
              className={`tab ${activeTab === "raw" ? "tab-active" : ""}`}
              onClick={() => setActiveTab("raw")}
            >
              <FileJson size={14} /> JSON
            </button>
          </div>

          {/* Tab Content */}
          <div className="report-content">
            {activeTab === "markdown" && (
              <div className="markdown-body">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeHighlight]}
                  components={{
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer">
                        {children}
                      </a>
                    ),
                  }}
                >
                  {reportContent}
                </ReactMarkdown>
              </div>
            )}
            {activeTab === "pdf" && reportUrl && (
              <div className="pdf-viewer">
                <iframe src={reportUrl} title="Research Report"></iframe>
              </div>
            )}
            {activeTab === "pdf" && !reportUrl && (
              <div className="tab-placeholder">
                PDF generation in progress or unavailable.
              </div>
            )}
            {activeTab === "raw" && (
              <pre className="raw-content">
                {jsonReport
                  ? JSON.stringify(jsonReport, null, 2)
                  : reportContent}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Follow-up Chat Panel */}
      {chatOpen && (
        <div className="chat-panel">
          <div className="chat-header">
            <h3>
              <MessageCircle size={16} /> Ask about this report
            </h3>
            <button className="chat-close" onClick={() => setChatOpen(false)}>
              <X size={16} />
            </button>
          </div>
          <div className="chat-messages">
            {chatMessages.length === 0 && (
              <div className="chat-empty">
                <Sparkles
                  size={20}
                  style={{ marginBottom: "0.5rem", opacity: 0.5 }}
                />
                <p>Ask any question about the generated report.</p>
                <div className="suggestion-chips">
                  {SUGGESTION_CHIPS.map((chip, i) => (
                    <button
                      key={i}
                      className="suggestion-chip"
                      onClick={() => handleSuggestionClick(chip)}
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {chatMessages.map((msg, i) => (
              <div key={i} className={`chat-message ${msg.role}`}>
                <div className="message-content">{msg.content}</div>
                {msg.role === "assistant" &&
                  msg.sources &&
                  msg.sources.length > 0 && (
                    <div className="chat-sources">
                      <span className="sources-label">Sources cited:</span>
                      {msg.sources.map((src, j) => (
                        <div key={j} className="source-snippet">
                          {src.length > 120 ? src.substring(0, 120) + "…" : src}
                        </div>
                      ))}
                    </div>
                  )}
              </div>
            ))}
            {chatLoading && (
              <div className="chat-message assistant">
                <div className="message-content">
                  <Loader2 size={14} className="spinner-icon" /> Thinking...
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="chat-input-area">
            <input
              type="text"
              placeholder="Ask a follow-up question..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleChat()}
            />
            <button
              onClick={handleChat}
              disabled={chatLoading || !chatInput.trim()}
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
