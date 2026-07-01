import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

// ---------------- AUTH HELPERS ----------------
function getToken() {
  return localStorage.getItem("auth_token") || "";
}

function getUsername() {
  return localStorage.getItem("auth_username") || "";
}

function setAuth(token, username) {
  localStorage.setItem("auth_token", token);
  localStorage.setItem("auth_username", username);
}

function clearAuth() {
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_username");
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Token ${token}` } : {};
}

const THINKING_STAGES = [
  "Reading the question",
  "Retrieving relevant document sections",
  "Checking source coverage",
  "Preparing the answer",
];

const WAITING_LINES = [
  "Scanning your uploaded PDFs for the strongest match.",
  "Good answers start with grounded sources.",
  "Checking document context before writing the response.",
  "Matching your question with relevant sections.",
  "Preparing a source-aware answer.",
];

const ICONS = {
  alert: (
    <>
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z" />
    </>
  ),
  bot: (
    <>
      <path d="M12 8V4" />
      <rect x="5" y="8" width="14" height="11" rx="3" />
      <path d="M9 13h.01" />
      <path d="M15 13h.01" />
      <path d="M9 17h6" />
    </>
  ),
  check: (
    <>
      <path d="m5 12 4 4L19 6" />
    </>
  ),
  chevron: (
    <>
      <path d="m9 18 6-6-6-6" />
    </>
  ),
  close: (
    <>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </>
  ),
  document: (
    <>
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6" />
      <path d="M9 17h6" />
    </>
  ),
  download: (
    <>
      <path d="M12 4v12" />
      <path d="m7 11 5 5 5-5" />
      <path d="M5 20h14" />
    </>
  ),
  folder: (
    <>
      <path d="M3 7h6l2 2h10v9a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z" />
      <path d="M3 7V6a3 3 0 0 1 3-3h3l2 2h5a3 3 0 0 1 3 3v1" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 11a8 8 0 0 0-14.7-4.4L3 9" />
      <path d="M3 4v5h5" />
      <path d="M4 13a8 8 0 0 0 14.7 4.4L21 15" />
      <path d="M16 15h5v5" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </>
  ),
  send: (
    <>
      <path d="M21 3 10 14" />
      <path d="m21 3-7 18-4-7-7-4z" />
    </>
  ),
  trash: (
    <>
      <path d="M4 7h16" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
      <path d="M6 7l1 14h10l1-14" />
      <path d="M9 7V4h6v3" />
    </>
  ),
  upload: (
    <>
      <path d="M12 16V4" />
      <path d="m7 9 5-5 5 5" />
      <path d="M5 20h14" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </>
  ),
  moon: (
    <>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="5" />
      <path d="M12 1v2" />
      <path d="M12 21v2" />
      <path d="M4.22 4.22l1.42 1.42" />
      <path d="M18.36 18.36l1.42 1.42" />
      <path d="M1 12h2" />
      <path d="M21 12h2" />
      <path d="M4.22 19.78l1.42-1.42" />
      <path d="M18.36 5.64l1.42-1.42" />
    </>
  ),
};

function Icon({ name, size = 18 }) {
  return (
    <svg
      aria-hidden="true"
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {ICONS[name]}
    </svg>
  );
}

function normalizeFile(file) {
  if (typeof file === "string") {
    return {
      name: file,
      hasText: null,
      error: "",
    };
  }

  return {
    name: file.name,
    hasText: typeof file.has_text === "boolean" ? file.has_text : null,
    error: file.error || "",
  };
}

function compactName(name) {
  if (!name) return "";
  return name.replace(/\.(pdf|docx|pptx|txt)$/i, "").replace(/[_-]+/g, " ");
}

function isGlobalSearchOffer(text) {
  return /do you want me to search globally outside the pdfs/i.test(text || "");
}

function renderInlineText(text) {
  const parts = String(text || "").split(/(\*\*[^*]+\*\*|`[^`]+`)/g);

  return parts.map((part, index) => {
    if (!part) return null;

    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }

    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }

    return <span key={index}>{part}</span>;
  });
}

function parseAnswerBlocks(text) {
  const lines = String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const qaMatch = line.match(/^\d+\.\s*Q:\s*(.+)$/i);

    if (qaMatch) {
      const answerLine = lines[index + 1]?.match(/^A:\s*(.+)$/i);
      blocks.push({
        type: "qa",
        question: qaMatch[1],
        answer: answerLine ? answerLine[1] : "",
      });
      index += answerLine ? 2 : 1;
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^[-*]\s+/, ""));
        index += 1;
      }
      blocks.push({ type: "bullets", items });
      continue;
    }

    const headingMatch = line.match(/^#{1,3}\s+(.+)$/);
    if (headingMatch) {
      blocks.push({ type: "heading", text: headingMatch[1] });
      index += 1;
      continue;
    }

    if (/not found in uploaded pdfs/i.test(line)) {
      blocks.push({ type: "notice", text: line });
      index += 1;
      continue;
    }

    const paragraph = [line];
    index += 1;
    while (
      index < lines.length &&
      !/^[-*]\s+/.test(lines[index]) &&
      !/^\d+\.\s*Q:/i.test(lines[index]) &&
      !/^#{1,3}\s+/.test(lines[index]) &&
      !/not found in uploaded pdfs/i.test(lines[index])
    ) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push({ type: "paragraph", text: paragraph.join(" ") });
  }

  return blocks;
}

function FormattedAnswer({
  text,
  showGlobalActions = false,
  globalSearching = false,
  onGlobalSearch,
  onDismissGlobalSearch,
}) {
  const blocks = parseAnswerBlocks(text);

  if (!blocks.length) {
    return null;
  }

  return (
    <div className="formatted-answer">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return <h3 key={index}>{renderInlineText(block.text)}</h3>;
        }

        if (block.type === "bullets") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInlineText(item)}</li>
              ))}
            </ul>
          );
        }

        if (block.type === "qa") {
          return (
            <section key={index} className="qa-card">
              <div className="qa-label">Q{index + 1}</div>
              <div className="qa-content">
                <h3>{renderInlineText(block.question)}</h3>
                {block.answer && <p>{renderInlineText(block.answer)}</p>}
              </div>
            </section>
          );
        }

        if (block.type === "notice") {
          return (
            <div key={index} className="answer-notice-block">
              <div className="answer-notice">
                <Icon name="search" size={16} />
                <span>{renderInlineText(block.text)}</span>
              </div>
              {showGlobalActions && (
                <div className="global-action-row" aria-label="Global search options">
                  <button
                    type="button"
                    className="global-search-button"
                    onClick={onGlobalSearch}
                    disabled={globalSearching}
                  >
                    <Icon name="search" size={15} />
                    <span>{globalSearching ? "Searching" : "Search globally"}</span>
                  </button>
                  <button
                    type="button"
                    className="global-dismiss-button"
                    onClick={onDismissGlobalSearch}
                    disabled={globalSearching}
                  >
                    <Icon name="close" size={15} />
                    <span>No</span>
                  </button>
                </div>
              )}
            </div>
          );
        }

        return <p key={index}>{renderInlineText(block.text)}</p>;
      })}
    </div>
  );
}

function parseServerEvent(eventText) {
  const dataLines = eventText
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s?/, ""));

  if (!dataLines.length) return null;
  return JSON.parse(dataLines.join("\n"));
}

async function readChatStream(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");

    while (boundary !== -1) {
      const eventText = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);

      if (eventText) {
        const event = parseServerEvent(eventText);
        if (event) onEvent(event);
      }

      boundary = buffer.indexOf("\n\n");
    }
  }

  buffer += decoder.decode();
  const finalEvent = buffer.trim();
  if (finalEvent) {
    const event = parseServerEvent(finalEvent);
    if (event) onEvent(event);
  }
}

function AuthScreen({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) return;

    if (mode === "register") {
      if (!name.trim()) {
        setError("Name is required");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match");
        return;
      }
    }

    setLoading(true);
    setError("");

    const endpoint = mode === "login" ? "auth/login/" : "auth/register/";
    const payload =
      mode === "login"
        ? { email: email.trim(), password: password.trim() }
        : {
            name: name.trim(),
            email: email.trim(),
            password: password.trim(),
            confirm_password: confirmPassword.trim(),
          };

    try {
      const res = await fetch(`${API_BASE}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Something went wrong");
        return;
      }

      setAuth(data.token, data.username);
      onAuth(data.username);
    } catch (err) {
      setError("Cannot connect to the server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-mark" aria-hidden="true">
            <span>ID</span>
          </div>
          <h1>
            <span className="lit-word">Insight</span>
            <strong className="lit-word">Docs</strong>
          </h1>
          <p>AI knowledge assistant</p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <h2>{mode === "login" ? "Sign in" : "Create account"}</h2>

          {error && <div className="auth-error">{error}</div>}

          {mode === "register" && (
            <label>
              <span>Name</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                disabled={loading}
                placeholder="Your full name"
              />
            </label>
          )}

          <label>
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              disabled={loading}
              placeholder="you@example.com"
            />
          </label>

          <label>
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              disabled={loading}
              placeholder="••••••••"
            />
          </label>

          {mode === "register" && (
            <label>
              <span>Confirm Password</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                disabled={loading}
                placeholder="••••••••"
              />
            </label>
          )}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? "Please wait..." : mode === "login" ? "Sign in" : "Register"}
          </button>

          <p className="auth-switch">
            {mode === "login" ? "Don't have an account?" : "Already have an account?"}{" "}
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
              }}
            >
              {mode === "login" ? "Register" : "Sign in"}
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}

function App() {
  const [authedUser, setAuthedUser] = useState(getUsername());
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [thinkingStage, setThinkingStage] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [activeFile, setActiveFile] = useState("");
  const [pendingDelete, setPendingDelete] = useState("");
  const [toast, setToast] = useState(null);
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem("theme") === "dark");
  const chatScrollRef = useRef(null);
  const toastTimerRef = useRef(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "light");
    localStorage.setItem("theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  const documents = useMemo(
    () => uploadedFiles.map(normalizeFile).sort((a, b) => a.name.localeCompare(b.name)),
    [uploadedFiles]
  );

  const activeDocument = useMemo(
    () => documents.find((document) => document.name === activeFile),
    [activeFile, documents]
  );
  const scopedFile = activeDocument ? activeFile : "";

  const indexedCount = documents.filter((document) => document.hasText === true).length;
  const issueCount = documents.filter((document) => document.hasText === false || document.error).length;
  const waitingLine = WAITING_LINES[Math.floor(elapsedSeconds / 5) % WAITING_LINES.length];
  const quickPrompts = useMemo(
    () => [
      activeDocument ? `Summarize ${compactName(activeDocument.name)}` : "Summarize all documents",
      "List the most important points",
      "What details are mentioned about experience?",
      "Find skills, tools, and technologies",
    ],
    [activeDocument]
  );

  const showToast = useCallback((message, type = "info") => {
    window.clearTimeout(toastTimerRef.current);
    setToast({ message, type });
    toastTimerRef.current = window.setTimeout(() => setToast(null), 3600);
  }, []);

  const fetchUploadedFiles = useCallback(
    async ({ silent = false } = {}) => {
      try {
        const response = await fetch(`${API_BASE}/list-pdfs/`, {
          headers: authHeaders(),
        });
        if (response.status === 401) {
          clearAuth();
          setAuthedUser("");
          return;
        }
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        setUploadedFiles(data.files || []);
        setError("");
      } catch (err) {
        setError(`Backend unavailable: ${err.message}`);
        if (!silent) {
          showToast("Could not load documents. Check the Django server.", "error");
        }
      }
    },
    [showToast]
  );

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => {
      fetchUploadedFiles();
    }, 0);
    const interval = window.setInterval(() => {
      fetchUploadedFiles({ silent: true });
    }, 60000);

    return () => {
      window.clearTimeout(initialRefresh);
      window.clearInterval(interval);
    };
  }, [fetchUploadedFiles]);

  useEffect(() => {
    if (!loading) {
      return undefined;
    }

    const startedAt = Date.now();
    const stageTimer = window.setInterval(() => {
      setThinkingStage((previous) => Math.min(previous + 1, THINKING_STAGES.length - 1));
    }, 2200);
    const elapsedTimer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    return () => {
      window.clearInterval(stageTimer);
      window.clearInterval(elapsedTimer);
    };
  }, [loading]);

  useEffect(() => {
    if (!chatScrollRef.current) return;

    chatScrollRef.current.scrollTo({
      top: chatScrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading, thinkingStage]);

  const sendMessage = async (event) => {
    event?.preventDefault();

    const question = input.trim();
    if (!question || loading) return;

    const scopedQuestion = activeDocument
      ? `In the document named ${activeDocument.name}, ${question}`
      : question;
    const botMessageId = `bot-${Date.now()}`;
    const updateBotMessage = (updates) => {
      setMessages((previous) =>
        previous.map((message) =>
          message.id === botMessageId
            ? {
                ...message,
                ...updates,
              }
            : message
        )
      );
    };

    setMessages((previous) => [
      ...previous,
      {
        id: `user-${Date.now()}`,
        role: "user",
        text: question,
        scope: activeDocument ? activeDocument.name : "All documents",
      },
      {
        id: botMessageId,
        role: "bot",
        text: "",
        sources: [],
        streaming: true,
        globalQuestion: question,
      },
    ]);
    setInput("");
    setThinkingStage(0);
    setElapsedSeconds(0);
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/chat-stream/?query=${encodeURIComponent(scopedQuestion)}`, {
        headers: authHeaders(),
      });
      if (response.status === 401) {
        clearAuth();
        setAuthedUser("");
        return;
      }
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error("Streaming is not supported in this browser");
      }

      let streamedText = "";
      let currentSources = [];

      await readChatStream(response, (payload) => {
        if (payload.type === "sources") {
          currentSources = payload.sources || [];
          updateBotMessage({ sources: currentSources });
          return;
        }

        if (payload.type === "token") {
          streamedText += payload.token || "";
          updateBotMessage({
            text: streamedText,
            sources: currentSources,
            streaming: true,
          });
          return;
        }

        if (payload.type === "final") {
          streamedText = payload.answer || streamedText || "No response";
          currentSources = payload.sources || currentSources;
          updateBotMessage({
            text: streamedText,
            sources: currentSources,
            streaming: false,
          });
        }
      });

      if (!streamedText.trim()) {
        updateBotMessage({
          text: "No response",
          sources: currentSources,
          streaming: false,
        });
      }
    } catch (err) {
      updateBotMessage({
        text: "I could not reach the assistant service. Check that the backend and Ollama are running.",
        sources: [],
        streaming: false,
      });
      showToast(`Chat request failed: ${err.message}`, "error");
    } finally {
      setLoading(false);
      setThinkingStage(0);
      setElapsedSeconds(0);
    }
  };

  const MAX_FILE_SIZE_MB = 10;
  const MAX_FILE_COUNT = 10;
  const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt"];

  const handleFileUpload = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length || uploading) return;

    // Check count limit on frontend
    const currentCount = documents.length;
    if (currentCount >= MAX_FILE_COUNT) {
      showToast(`Upload limit reached. Maximum ${MAX_FILE_COUNT} documents allowed.`, "error");
      event.target.value = "";
      return;
    }

    const allowed = files.slice(0, MAX_FILE_COUNT - currentCount);
    if (allowed.length < files.length) {
      showToast(`Only uploading ${allowed.length} of ${files.length} files (limit: ${MAX_FILE_COUNT}).`, "error");
    }

    setUploading(true);
    let successCount = 0;
    let failedCount = 0;

    for (const file of allowed) {
      const ext = "." + file.name.split(".").pop().toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        showToast(`${file.name}: unsupported format. Use PDF, DOCX, PPTX, or TXT.`, "error");
        failedCount += 1;
        continue;
      }

      // Check size limit on frontend
      if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        showToast(`${file.name} exceeds ${MAX_FILE_SIZE_MB} MB limit.`, "error");
        failedCount += 1;
        continue;
      }

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch(`${API_BASE}/upload/`, {
          method: "POST",
          headers: authHeaders(),
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        successCount += 1;
      } catch (err) {
        failedCount += 1;
        console.error(err);
      }
    }

    event.target.value = "";
    setUploading(false);
    await fetchUploadedFiles({ silent: true });

    if (successCount) {
      showToast(`${successCount} file${successCount > 1 ? "s" : ""} uploaded and indexed.`, "success");
    }

    if (failedCount) {
      showToast(`${failedCount} file could not be uploaded.`, "error");
    }
  };

  const confirmDeleteFile = async () => {
    if (!pendingDelete) return;

    const filename = pendingDelete;
    setPendingDelete("");

    try {
      const response = await fetch(`${API_BASE}/delete-pdf/?filename=${encodeURIComponent(filename)}`, {
        method: "DELETE",
        headers: authHeaders(),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || `HTTP ${response.status}`);
      }

      if (scopedFile === filename) {
        setActiveFile("");
      }

      await fetchUploadedFiles({ silent: true });
      showToast(`${compactName(filename)} deleted.`, "success");
    } catch (err) {
      showToast(`Unable to delete document: ${err.message}`, "error");
    }
  };

  const applyPrompt = (prompt) => {
    setInput(prompt);
  };

  const dismissGlobalSearch = (messageId) => {
    setMessages((previous) =>
      previous.map((message) =>
        message.id === messageId
          ? {
              ...message,
              globalDismissed: true,
              globalSearching: false,
            }
          : message
      )
    );
  };

  const exportChatAsPdf = async () => {
    if (!messages.length) return;

    try {
      const response = await fetch(`${API_BASE}/export-chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          messages: messages.map((m) => ({
            role: m.role,
            text: m.text,
            sources: m.sources || [],
          })),
        }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "chat-export.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast("Chat exported as PDF.", "success");
    } catch (err) {
      showToast(`Export failed: ${err.message}`, "error");
    }
  };

  const runGlobalSearch = async (messageId, question) => {
    if (!question) return;

    const globalMessageId = `global-${Date.now()}`;

    setMessages((previous) => [
      ...previous.map((message) =>
        message.id === messageId
          ? {
              ...message,
              globalSearching: true,
            }
          : message
      ),
      {
        id: globalMessageId,
        role: "bot",
        text: "Searching globally...",
        sources: [],
        streaming: true,
        scope: "Global web",
      },
    ]);

    try {
      const response = await fetch(`${API_BASE}/global-search/?query=${encodeURIComponent(question)}`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setMessages((previous) =>
        previous.map((message) => {
          if (message.id === messageId) {
            return {
              ...message,
              globalDismissed: true,
              globalSearching: false,
            };
          }

          if (message.id === globalMessageId) {
            return {
              ...message,
              text: data.answer || "No global result found.",
              sources: data.sources || [],
              streaming: false,
            };
          }

          return message;
        })
      );
    } catch (err) {
      setMessages((previous) =>
        previous.map((message) => {
          if (message.id === messageId) {
            return {
              ...message,
              globalSearching: false,
            };
          }

          if (message.id === globalMessageId) {
            return {
              ...message,
              text: `Global search failed: ${err.message}`,
              sources: [],
              streaming: false,
            };
          }

          return message;
        })
      );
    }
  };

  const handleLogout = () => {
    clearAuth();
    setAuthedUser("");
    setMessages([]);
    setUploadedFiles([]);
  };

  if (!authedUser) {
    return <AuthScreen onAuth={(username) => setAuthedUser(username)} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Document library">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            <span>ID</span>
          </div>
        </div>

        <div className="sidebar-controls">
          <label className={`upload-button ${uploading ? "is-busy" : ""}`}>
            <Icon name="upload" />
            <span>{uploading ? "Uploading" : "Upload Files"}</span>
            <input
              type="file"
              accept=".pdf,.docx,.pptx,.txt"
              multiple
              hidden
              disabled={uploading}
              onChange={handleFileUpload}
            />
          </label>
          <button
            className="icon-button"
            type="button"
            onClick={() => fetchUploadedFiles()}
            title="Refresh documents"
            aria-label="Refresh documents"
          >
            <Icon name="refresh" />
          </button>
        </div>

        <div className="library-stats" aria-label="Library summary">
          <div>
            <strong>{documents.length}</strong>
            <span>Documents</span>
          </div>
          <div>
            <strong>{indexedCount}</strong>
            <span>Indexed</span>
          </div>
          <div>
            <strong>{issueCount}</strong>
            <span>Issues</span>
          </div>
        </div>

        <button
          type="button"
          className={`document-row all-documents ${scopedFile ? "" : "is-active"}`}
          onClick={() => setActiveFile("")}
        >
          <span className="document-icon">
            <Icon name="search" />
          </span>
          <span className="document-copy">
            <strong>All documents</strong>
            <small>Search across the library</small>
          </span>
          <Icon name="chevron" size={16} />
        </button>

        <div className="document-list" aria-live="polite">
          {documents.length ? (
            documents.map((document) => {
              const isActive = document.name === activeFile;
              const statusLabel =
                document.hasText === true
                  ? "Indexed"
                  : document.hasText === false
                    ? document.error || "No text found"
                    : "Uploaded";

              return (
                <div
                  key={document.name}
                  className={`document-row document-item ${isActive ? "is-active" : ""}`}
                >
                  <button type="button" className="document-select" onClick={() => setActiveFile(document.name)}>
                    <span className="document-icon">
                      <Icon name="document" />
                    </span>
                    <span className="document-copy">
                      <strong title={document.name}>{compactName(document.name)}</strong>
                      <small className={document.hasText === false ? "is-error" : ""}>{statusLabel}</small>
                    </span>
                  </button>
                  <button
                    type="button"
                    className="delete-button"
                    title="Delete document"
                    aria-label={`Delete ${document.name}`}
                    onClick={(deleteEvent) => {
                      deleteEvent.stopPropagation();
                      setPendingDelete(document.name);
                    }}
                  >
                    <Icon name="trash" size={16} />
                  </button>
                </div>
              );
            })
          ) : (
            <div className="empty-library">
              <Icon name="document" size={24} />
              <strong>Library is empty</strong>
              <span>No PDFs are indexed yet.</span>
            </div>
          )}
        </div>

        {error && (
          <div className="sidebar-alert" role="status">
            <Icon name="alert" size={16} />
            <span>{error}</span>
          </div>
        )}
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-brand">
            <h1 aria-label="InsightDocs">
              <span className="lit-word">Insight</span>
              <strong className="lit-word">Docs</strong>
            </h1>
            <p className="topbar-subtitle">AI knowledge assistant</p>
            <p>Upload, search, and ask questions across your documents.</p>
          </div>
          <div className="topbar-user">
            <button
              type="button"
              className="theme-toggle"
              onClick={() => setDarkMode((prev) => !prev)}
              title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
              aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
            >
              <Icon name={darkMode ? "sun" : "moon"} size={16} />
            </button>
            <Icon name="user" size={16} />
            <span>{authedUser}</span>
            <button type="button" className="logout-button" onClick={handleLogout}>
              Sign out
            </button>
          </div>
        </header>

        <section className="chat-surface" aria-label="Assistant chat">
          <div className="context-bar">
            <div>
              <span className="context-label">Current scope</span>
              <strong>{activeDocument ? compactName(activeDocument.name) : "All documents"}</strong>
            </div>
            <div className="context-meta">
              <span>{documents.length} PDFs</span>
              <span>{messages.length} messages</span>
              {messages.length > 0 && (
                <button
                  type="button"
                  className="export-button"
                  onClick={exportChatAsPdf}
                  title="Download chat as PDF"
                  aria-label="Download chat as PDF"
                >
                  <Icon name="download" size={15} />
                  <span>Export</span>
                </button>
              )}
            </div>
          </div>

          <div className="messages-area" ref={chatScrollRef}>
            {messages.length === 0 && !loading ? (
              <div className="empty-chat">
                <div className="empty-chat-mark">
                  <Icon name="bot" size={28} />
                </div>
                <h2>Ready for document questions</h2>
                <div className="quick-prompts" aria-label="Quick prompts">
                  {quickPrompts.map((prompt) => (
                    <button key={prompt} type="button" onClick={() => applyPrompt(prompt)}>
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, index) => (
                <article key={message.id || `${message.role}-${index}`} className={`message-row ${message.role}`}>
                  <div className={`avatar ${message.role}`}>
                    <Icon name={message.role === "user" ? "user" : "bot"} size={17} />
                  </div>
                  <div className="message-stack">
                    <div className={`message-bubble ${message.role} ${message.streaming ? "is-streaming" : ""}`}>
                      {message.role === "bot" && message.text ? (
                        <FormattedAnswer
                          text={message.text}
                          showGlobalActions={
                            !message.streaming &&
                            !message.globalDismissed &&
                            isGlobalSearchOffer(message.text)
                          }
                          globalSearching={Boolean(message.globalSearching)}
                          onGlobalSearch={() => runGlobalSearch(message.id, message.globalQuestion)}
                          onDismissGlobalSearch={() => dismissGlobalSearch(message.id)}
                        />
                      ) : (
                        message.text || (message.streaming ? "Starting response..." : "")
                      )}
                    </div>
                    {message.scope && <span className="message-scope">{compactName(message.scope)}</span>}
                    {message.sources?.length > 0 && (
                      <div className="source-list">
                        <span>Sources</span>
                        {message.sources.map((source) => (
                          <strong key={source}>{compactName(source)}</strong>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              ))
            )}

            {loading && !messages.some((message) => message.streaming && message.text) && (
              <div className="message-row bot is-loading">
                <div className="avatar bot">
                  <Icon name="bot" size={17} />
                </div>
                <div className="thinking-card">
                  <div className="scanner-animation" aria-hidden="true">
                    <div className="scanner-orbit">
                      <span />
                      <span />
                    </div>
                    <div className="scanner-document">
                      <div className="scanner-line long" />
                      <div className="scanner-line medium" />
                      <div className="scanner-line short" />
                      <div className="scanner-beam" />
                    </div>
                  </div>
                  <div className="thinking-copy">
                    <div className="thinking-title">Working on your answer</div>
                    <div className="thinking-stage">{THINKING_STAGES[thinkingStage]}</div>
                    <div className="thinking-waiting-line">{waitingLine}</div>
                  </div>
                  <div className="thinking-progress">
                    <span />
                    <span />
                    <span />
                  </div>
                  <div className="thinking-time">{elapsedSeconds}s elapsed</div>
                </div>
              </div>
            )}
          </div>

          <form className="composer" onSubmit={sendMessage}>
            <div className="composer-input">
              <Icon name="search" size={18} />
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={
                  activeDocument
                    ? `Ask about ${compactName(activeDocument.name)}`
                    : "Ask about your knowledge base"
                }
                disabled={loading}
              />
            </div>
            <button className="send-button" type="submit" disabled={loading || !input.trim()} title="Send">
              <Icon name="send" />
              <span className="sr-only">Send</span>
            </button>
          </form>
        </section>
      </main>

      {toast && (
        <div className={`toast ${toast.type}`} role="status">
          <Icon name={toast.type === "error" ? "alert" : "check"} size={17} />
          <span>{toast.message}</span>
        </div>
      )}

      {pendingDelete && (
        <div className="modal-backdrop" role="presentation">
          <div className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-title">
            <button
              type="button"
              className="dialog-close"
              onClick={() => setPendingDelete("")}
              title="Close"
              aria-label="Close"
            >
              <Icon name="close" size={16} />
            </button>
            <div className="dialog-icon">
              <Icon name="trash" size={22} />
            </div>
            <h2 id="delete-title">Delete document?</h2>
            <p>{compactName(pendingDelete)} will be removed from the library and search index.</p>
            <div className="dialog-actions">
              <button type="button" className="secondary-button" onClick={() => setPendingDelete("")}>
                Cancel
              </button>
              <button type="button" className="danger-button" onClick={confirmDeleteFile}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
