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
  Zap,
  Brain,
  FileCheck,
  ArrowRight,
  Check,
  RefreshCw,
  CheckCircle,
  XCircle,
  Activity,
} from "lucide-react";
import "./App.css";

// Rotating placeholder topics
const PLACEHOLDER_TOPICS = [
  "Quantum computing breakthroughs in 2025...",
  "Impact of AI on healthcare diagnostics...",
  "Climate change mitigation strategies...",
  "The future of space exploration...",
  "Advances in CRISPR gene editing...",
  "Decentralized finance and Web3...",
  "Neuromorphic computing architectures...",
  "Sustainable energy storage solutions...",
];

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
  const [suggestionChips, setSuggestionChips] = useState([]);

  // Report metadata state
  const [confidenceScores, setConfidenceScores] = useState({});
  const [sourceCount, setSourceCount] = useState(0);
  const [runtimeSeconds, setRuntimeSeconds] = useState(0);
  const [costEstimate, setCostEstimate] = useState(0);
  const [jsonReport, setJsonReport] = useState(null);

  // Rotating placeholder
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const [placeholderText, setPlaceholderText] = useState("");
  const [isTyping, setIsTyping] = useState(true);

  const chatEndRef = useRef(null);
  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Typewriter effect for placeholder
  useEffect(() => {
    const currentTopic = PLACEHOLDER_TOPICS[placeholderIndex];
    let charIndex = 0;
    let timeout;

    if (isTyping) {
      timeout = setInterval(() => {
        if (charIndex <= currentTopic.length) {
          setPlaceholderText(currentTopic.slice(0, charIndex));
          charIndex++;
        } else {
          clearInterval(timeout);
          setTimeout(() => setIsTyping(false), 2000);
        }
      }, 50);
    } else {
      timeout = setInterval(() => {
        if (charIndex < currentTopic.length) {
          setPlaceholderText(
            currentTopic.slice(0, currentTopic.length - charIndex),
          );
          charIndex++;
        } else {
          clearInterval(timeout);
          setPlaceholderIndex((prev) => (prev + 1) % PLACEHOLDER_TOPICS.length);
          setIsTyping(true);
        }
      }, 30);
    }

    return () => clearInterval(timeout);
  }, [placeholderIndex, isTyping]);

  // Extract executive summary from report content
  const executiveSummary = useMemo(() => {
    if (!reportContent) return null;
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
    setSuggestionChips([]);

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

    setProgressSteps((prev) => [
      ...prev,
      {
        id: Date.now(),
        type,
        message,
        data: data || {},
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);

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
      if (data.suggestion_chips && data.suggestion_chips.length > 0) {
        setSuggestionChips(data.suggestion_chips);
      } else {
        setSuggestionChips([
          "What are the key findings?",
          "Which sources were most cited?",
          "Any limitations or gaps?",
        ]);
      }
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

  const getStepIcon = (type) => {
    switch (type) {
      case "query_analyzing":
        return <Search size={16} />;
      case "query_analyzed":
        return <Check size={16} />;
      case "cache_hit":
        return <Zap size={16} />;
      case "plan_generating":
        return <FileText size={16} />;
      case "plan_generated":
        return <Check size={16} />;
      case "section_researching":
        return <Search size={16} />;
      case "section_writing":
        return <FileText size={16} />;
      case "section_complete":
        return <Check size={16} />;
      case "reflection_loop":
        return <RefreshCw size={16} />;
      case "fact_checking":
        return <Shield size={16} />;
      case "fact_check_complete":
        return <Check size={16} />;
      case "synthesis_writing":
        return <FileText size={16} />;
      case "compiling_output":
        return <Database size={16} />;
      case "report_ready":
        return <CheckCircle size={16} />;
      case "error":
        return <XCircle size={16} />;
      default:
        return <Activity size={16} />;
    }
  };

  return (
    <>
      {/* Animated Background */}
      <div className="app-bg">
        <div className="orb orb-1"></div>
        <div className="orb orb-2"></div>
        <div className="orb orb-3"></div>
        <div className="orb orb-4"></div>
        {/* Floating particles */}
        <div className="particles">
          {[...Array(20)].map((_, i) => (
            <div key={i} className={`particle particle-${i + 1}`}></div>
          ))}
        </div>
        {/* Grid pattern overlay */}
        <div className="grid-overlay"></div>
      </div>

      <div className="container">
        {/* Hero Header */}
        <header className="header">
          {/* Glowing Arc */}
          <div className="glow-arc">
            {[...Array(16)].map((_, i) => (
              <div key={i} className={`arc-dot arc-dot-${i + 1}`}></div>
            ))}
          </div>

          <h1>Deep Research Agent</h1>
          <p className="subtitle">
            AI-powered deep research with multi-source search, real-time
            streaming, and publication-quality reports
          </p>
          <span className="version-badge">v2.0</span>

          {/* Feature Pills */}
          <div className="feature-pills">
            <div className="feature-pill">
              <span className="feature-pill-icon">🔍</span>5 Search Providers
            </div>
            <div className="feature-pill">
              <span className="feature-pill-icon">🧠</span>
              3-Tier LLM Hierarchy
            </div>
            <div className="feature-pill">
              <span className="feature-pill-icon">⚡</span>
              Real-Time Streaming
            </div>
            <div className="feature-pill">
              <span className="feature-pill-icon">🔬</span>
              Fact Checking
            </div>
            <div className="feature-pill">
              <span className="feature-pill-icon">💬</span>
              Follow-up Chat
            </div>
          </div>
        </header>

        {/* Search Card with Animated Border */}
        <div className="card-wrapper">
          <div className="card-glow"></div>
          <div className="card">
            <div className="input-group">
              <input
                type="text"
                placeholder={topic ? "" : placeholderText + "│"}
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
        </div>

        {/* How It Works — Pipeline Visualization */}
        {!reportContent && !loading && progressSteps.length === 0 && (
          <div className="pipeline-section">
            <h3 className="pipeline-title">How It Works</h3>
            <div className="pipeline-steps">
              <div className="pipeline-step">
                <div className="pipeline-icon">
                  <Search size={22} />
                </div>
                <div className="pipeline-label">Analyze Query</div>
                <div className="pipeline-desc">
                  HyDE anchoring & cache check
                </div>
              </div>
              <div className="pipeline-connector">
                <ArrowRight size={16} />
              </div>
              <div className="pipeline-step">
                <div className="pipeline-icon">
                  <Database size={22} />
                </div>
                <div className="pipeline-label">Multi-Source Search</div>
                <div className="pipeline-desc">5 providers in parallel</div>
              </div>
              <div className="pipeline-connector">
                <ArrowRight size={16} />
              </div>
              <div className="pipeline-step">
                <div className="pipeline-icon">
                  <Brain size={22} />
                </div>
                <div className="pipeline-label">AI Synthesis</div>
                <div className="pipeline-desc">3-tier LLM hierarchy</div>
              </div>
              <div className="pipeline-connector">
                <ArrowRight size={16} />
              </div>
              <div className="pipeline-step">
                <div className="pipeline-icon">
                  <Shield size={22} />
                </div>
                <div className="pipeline-label">Fact Check</div>
                <div className="pipeline-desc">Cross-reference claims</div>
              </div>
              <div className="pipeline-connector">
                <ArrowRight size={16} />
              </div>
              <div className="pipeline-step">
                <div className="pipeline-icon">
                  <FileCheck size={22} />
                </div>
                <div className="pipeline-label">Final Report</div>
                <div className="pipeline-desc">PDF, Markdown, JSON</div>
              </div>
            </div>
          </div>
        )}

        {/* Stats Bar */}
        {!reportContent && !loading && progressSteps.length === 0 && (
          <div className="stats-bar">
            <div className="stat-item">
              <div className="stat-number">5</div>
              <div className="stat-label">Search Providers</div>
            </div>
            <div className="stat-divider"></div>
            <div className="stat-item">
              <div className="stat-number">3</div>
              <div className="stat-label">LLM Tiers</div>
            </div>
            <div className="stat-divider"></div>
            <div className="stat-item">
              <div className="stat-number">3x</div>
              <div className="stat-label">Reflection Loops</div>
            </div>
            <div className="stat-divider"></div>
            <div className="stat-item">
              <div className="stat-number">∞</div>
              <div className="stat-label">Follow-up Q&A</div>
            </div>
          </div>
        )}

        {error && (
          <div className="error-banner">
            <span>❌</span> {error}
          </div>
        )}

        {/* Progress Timeline */}
        {progressSteps.length > 0 && (
          <div className="progress-timeline">
            <h3 className="timeline-title">System Activity</h3>
            <div className="timeline-steps">
              {progressSteps.map((step) => (
                <div
                  key={step.id}
                  className={`timeline-step ${step.type === "error" ? "step-error" : ""}`}
                >
                  <span className="step-icon">{getStepIcon(step.type)}</span>
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

            {/* Executive Summary Card removed strictly to prevent duplication */}

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
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
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
                  <p>Ask about the contents of this report.</p>
                  <div className="suggestion-chips">
                    {suggestionChips.map((chip, i) => (
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
                placeholder="Ask a question about the report..."
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

        {/* Footer */}
        <footer className="footer">
          <div className="footer-brand">Deep Research Agent</div>
          <div className="footer-tech">
            Built with <span>LangGraph</span> · <span>FastAPI</span> ·{" "}
            <span>React</span>
          </div>
          <div className="footer-version">
            v2.0 — Multi-Source AI Research Pipeline
          </div>
        </footer>
      </div>
    </>
  );
}

export default App;
