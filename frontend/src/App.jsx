import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

// ---------------- AUTH HELPERS ----------------
function getToken() {
  return localStorage.getItem("auth_token") || "";
}

function getUsername() {
  return localStorage.getItem("auth_username") || "";
}

function getIsAdmin() {
  return localStorage.getItem("auth_is_admin") === "true";
}

function setAuth(token, username, isAdmin = false) {
  localStorage.setItem("auth_token", token);
  localStorage.setItem("auth_username", username);
  localStorage.setItem("auth_is_admin", isAdmin ? "true" : "false");
}

function clearAuth() {
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_username");
  localStorage.removeItem("auth_is_admin");
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
  chat: (
    <>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
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
  edit: (
    <>
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </>
  ),
  folder: (
    <>
      <path d="M3 7h6l2 2h10v9a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z" />
      <path d="M3 7V6a3 3 0 0 1 3-3h3l2 2h5a3 3 0 0 1 3 3v1" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
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
  mic: (
    <>
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </>
  ),
  micOff: (
    <>
      <line x1="2" x2="22" y1="2" y2="22" />
      <path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2" />
      <path d="M5 10v2a7 7 0 0 0 12 5.29" />
      <path d="M15 9.34V5a3 3 0 0 0-5.68-1.33" />
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12" />
      <line x1="12" x2="12" y1="19" y2="22" />
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

function extractText(children) {
  if (typeof children === "string") return children;
  if (Array.isArray(children)) return children.map(extractText).join("");
  if (children?.props?.children) return extractText(children.props.children);
  return "";
}

const SEARCH_TIPS = [
  "💡 Did you know? The first search engine was called Archie, created in 1990.",
  "🧠 Fun fact: Your brain processes information faster than any supercomputer!",
  "📚 Tip: You can upload multiple PDFs and search across all of them.",
  "🌍 Did you know? The internet has over 1.9 billion websites.",
  "⚡ Fun fact: Light takes 8 minutes to travel from the Sun to Earth.",
  "🎯 Tip: Try asking specific questions for more accurate answers.",
  "🐝 Did you know? Honey never spoils — 3000-year-old honey is still edible!",
  "🚀 Fun fact: NASA's internet speed is 91 Gbps!",
  "📖 Tip: You can highlight text in answers to save important parts.",
  "🧬 Did you know? DNA in your body could stretch to Pluto and back 17 times.",
  "🎵 Fun fact: Music can help improve focus and productivity.",
  "💻 Tip: Clear, well-formed questions give the best answers.",
  "🌊 Did you know? More than 80% of the ocean is still unexplored.",
  "🔬 Fun fact: There are more stars in the universe than grains of sand on Earth.",
  "📝 Tip: You can export your chat history as a PDF for reference.",
];

function GlobalSearchTip() {
  const [tipIndex, setTipIndex] = useState(() => Math.floor(Math.random() * SEARCH_TIPS.length));

  useEffect(() => {
    const interval = setInterval(() => {
      setTipIndex((prev) => (prev + 1) % SEARCH_TIPS.length);
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="global-search-tip">
      <span className="tip-text">{SEARCH_TIPS[tipIndex]}</span>
    </div>
  );
}

function applyHighlightsToDOM(container, highlights) {
  if (!container || !highlights || highlights.length === 0) return;

  // Remove existing highlights first
  container.querySelectorAll("mark.highlight").forEach((mark) => {
    const parent = mark.parentNode;
    while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
    parent.removeChild(mark);
    parent.normalize();
  });

  // Sort by length descending so longer matches are applied first
  const sorted = [...highlights].sort((a, b) => b.text.length - a.text.length);

  for (const h of sorted) {
    // Collect all text nodes with their positions in the full concatenated text
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    const textNodes = [];
    let fullText = "";
    let node;
    while ((node = walker.nextNode())) {
      if (node.parentElement?.closest("pre, code, mark.highlight")) continue;
      textNodes.push({ node, start: fullText.length, length: node.textContent.length });
      fullText += node.textContent;
    }

    if (!fullText) continue;

    // Normalize the highlight text and build a normalized version of fullText for matching
    const normalizedHighlight = h.text.replace(/\s+/g, " ").toLowerCase();
    // Build a mapping: normalizedIndex -> originalIndex
    const normalizedChars = [];
    const origToNorm = [];
    for (let i = 0; i < fullText.length; i++) {
      const ch = fullText[i];
      if (/\s/.test(ch)) {
        // Collapse whitespace: only add a single space if the last normalized char wasn't a space
        if (normalizedChars.length === 0 || normalizedChars[normalizedChars.length - 1] !== " ") {
          normalizedChars.push(" ");
          origToNorm.push(normalizedChars.length - 1);
        } else {
          origToNorm.push(normalizedChars.length - 1);
        }
      } else {
        normalizedChars.push(ch.toLowerCase());
        origToNorm.push(normalizedChars.length - 1);
      }
    }
    const normalizedFull = normalizedChars.join("");

    // Find the match in normalized text
    const matchNormIndex = normalizedFull.indexOf(normalizedHighlight);
    if (matchNormIndex === -1) continue;

    // Map back to original indices
    let matchOrigStart = -1;
    let matchOrigEnd = -1;
    for (let i = 0; i < origToNorm.length; i++) {
      if (origToNorm[i] === matchNormIndex && matchOrigStart === -1) {
        matchOrigStart = i;
      }
      if (origToNorm[i] === matchNormIndex + normalizedHighlight.length - 1) {
        matchOrigEnd = i + 1;
      }
    }
    if (matchOrigStart === -1 || matchOrigEnd === -1) continue;

    const matchIndex = matchOrigStart;
    const matchEnd = matchOrigEnd;

    // Find which text nodes this match spans and highlight them
    for (let i = textNodes.length - 1; i >= 0; i--) {
      const tn = textNodes[i];
      const tnEnd = tn.start + tn.length;

      // Skip nodes that don't overlap with this match
      if (tn.start >= matchEnd || tnEnd <= matchIndex) continue;

      // Calculate the portion of this text node that's within the match
      const highlightStart = Math.max(0, matchIndex - tn.start);
      const highlightEnd = Math.min(tn.length, matchEnd - tn.start);
      const nodeText = tn.node.textContent;

      if (highlightStart === 0 && highlightEnd === tn.length) {
        // Entire text node is within the match — wrap it
        const mark = document.createElement("mark");
        mark.className = `highlight highlight-${h.color || "yellow"}`;
        mark.textContent = nodeText;
        tn.node.parentNode.replaceChild(mark, tn.node);
      } else {
        // Partial match — split the text node
        const fragment = document.createDocumentFragment();
        if (highlightStart > 0) {
          fragment.appendChild(document.createTextNode(nodeText.slice(0, highlightStart)));
        }
        const mark = document.createElement("mark");
        mark.className = `highlight highlight-${h.color || "yellow"}`;
        mark.textContent = nodeText.slice(highlightStart, highlightEnd);
        fragment.appendChild(mark);
        if (highlightEnd < tn.length) {
          fragment.appendChild(document.createTextNode(nodeText.slice(highlightEnd)));
        }
        tn.node.parentNode.replaceChild(fragment, tn.node);
      }
    }
  }
}

function FormattedAnswer({
  text,
  highlights = [],
  onAddHighlight,
  onRemoveHighlight,
  showGlobalActions = false,
  globalSearching = false,
  onGlobalSearch,
  onDismissGlobalSearch,
}) {
  const isNotFound = /not found in uploaded pdfs/i.test(text || "");
  const [selectionPopup, setSelectionPopup] = useState(null);
  const contentRef = useRef(null);

  // Apply highlights to DOM after render
  useEffect(() => {
    if (contentRef.current && highlights.length > 0) {
      applyHighlightsToDOM(contentRef.current, highlights);
    }
  }, [text, highlights]);

  // Dismiss popup on click outside
  useEffect(() => {
    if (!selectionPopup) return;
    const handleClickOutside = () => {
      setTimeout(() => {
        const sel = window.getSelection();
        if (!sel || !sel.toString().trim()) {
          setSelectionPopup(null);
        }
      }, 10);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [selectionPopup]);

  if (!text) return null;

  const handleMouseUp = (e) => {
    if (!onAddHighlight) return;
    const selection = window.getSelection();
    let selectedText = selection?.toString().trim();
    if (!selectedText || selectedText.length < 3) {
      setSelectionPopup(null);
      return;
    }
    // Normalize whitespace (selections across elements may include newlines)
    selectedText = selectedText.replace(/\s+/g, " ");
    // Check selection is within this component
    const container = e.currentTarget;
    if (!selection.anchorNode || !container.contains(selection.anchorNode)) {
      setSelectionPopup(null);
      return;
    }
    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    setSelectionPopup({
      text: selectedText,
      top: Math.max(0, rect.top - containerRect.top - 40),
      left: Math.min(
        Math.max(rect.left - containerRect.left + rect.width / 2, 60),
        containerRect.width - 60
      ),
    });
  };

  const handleHighlight = (color) => {
    if (selectionPopup && onAddHighlight) {
      onAddHighlight(selectionPopup.text, color);
      window.getSelection()?.removeAllRanges();
      setSelectionPopup(null);
    }
  };

  const hasHighlights = highlights && highlights.length > 0;

  return (
    <div className="formatted-answer" onMouseUp={handleMouseUp}>
      {selectionPopup && (
        <div
          className="highlight-popup"
          style={{ top: selectionPopup.top, left: selectionPopup.left }}
        >
          <button type="button" className="hl-btn hl-yellow" onClick={() => handleHighlight("yellow")} title="Yellow" />
          <button type="button" className="hl-btn hl-green" onClick={() => handleHighlight("green")} title="Green" />
          <button type="button" className="hl-btn hl-blue" onClick={() => handleHighlight("blue")} title="Blue" />
          <button type="button" className="hl-btn hl-pink" onClick={() => handleHighlight("pink")} title="Pink" />
        </div>
      )}
      <div ref={contentRef}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ node, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || "");
              const inline = !match && !String(children).includes("\n");
              return !inline ? (
                <SyntaxHighlighter
                  style={oneDark}
                  language={match ? match[1] : "text"}
                  PreTag="div"
                  customStyle={{ borderRadius: "8px", fontSize: "0.85rem" }}
                >
                  {String(children).replace(/\n$/, "")}
                </SyntaxHighlighter>
              ) : (
                <code className="inline-code" {...props}>
                  {children}
                </code>
              );
            },
            table({ children }) {
              return (
                <div className="table-wrapper">
                  <table>{children}</table>
                </div>
              );
            },
          }}
        >
          {text}
        </ReactMarkdown>
      </div>

      {hasHighlights && onRemoveHighlight && (
        <div className="highlight-chips">
          {highlights.map((h, i) => (
            <span key={i} className={`highlight-chip highlight-${h.color || "yellow"}`}>
              {h.text.length > 30 ? h.text.slice(0, 30) + "…" : h.text}
              <button type="button" onClick={() => onRemoveHighlight(h.text)} title="Remove highlight">×</button>
            </span>
          ))}
        </div>
      )}

      {isNotFound && showGlobalActions && (
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
          {globalSearching && <GlobalSearchTip />}
        </div>
      )}
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
  const [mode, setMode] = useState("login"); // login, register, forgot, otp, reset
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (mode === "forgot") {
      if (!email.trim()) {
        setError("Email is required");
        return;
      }
      setLoading(true);
      setError("");
      setSuccess("");
      try {
        const res = await fetch(`${API_BASE}/auth/forgot-password/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email.trim() }),
        });
        const data = await res.json();
        if (!res.ok) {
          setError(data.error || "Something went wrong");
          return;
        }
        setSuccess("OTP sent to your email. Check your inbox.");
        setMode("otp");
      } catch {
        setError("Cannot connect to the server");
      } finally {
        setLoading(false);
      }
      return;
    }

    if (mode === "otp") {
      if (!otp.trim()) {
        setError("Please enter the OTP");
        return;
      }
      setLoading(true);
      setError("");
      setSuccess("");
      try {
        const res = await fetch(`${API_BASE}/auth/verify-otp/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email.trim(), otp: otp.trim() }),
        });
        const data = await res.json();
        if (!res.ok) {
          setError(data.error || "Invalid OTP");
          return;
        }
        setSuccess("OTP verified. Set your new password.");
        setMode("reset");
      } catch {
        setError("Cannot connect to the server");
      } finally {
        setLoading(false);
      }
      return;
    }

    if (mode === "reset") {
      if (!newPassword.trim()) {
        setError("New password is required");
        return;
      }
      if (newPassword !== confirmNewPassword) {
        setError("Passwords do not match");
        return;
      }
      if (newPassword.length < 6) {
        setError("Password must be at least 6 characters");
        return;
      }
      setLoading(true);
      setError("");
      setSuccess("");
      try {
        const res = await fetch(`${API_BASE}/auth/reset-password/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email.trim(), otp: otp.trim(), new_password: newPassword.trim() }),
        });
        const data = await res.json();
        if (!res.ok) {
          setError(data.error || "Something went wrong");
          return;
        }
        setSuccess(data.message || "Password reset successful!");
        setOtp("");
        setNewPassword("");
        setConfirmNewPassword("");
        setTimeout(() => {
          setMode("login");
          setSuccess("");
        }, 2000);
      } catch {
        setError("Cannot connect to the server");
      } finally {
        setLoading(false);
      }
      return;
    }

    // login / register flow
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

      setAuth(data.token, data.username, data.is_admin);
      onAuth(data.username);
    } catch (err) {
      setError("Cannot connect to the server");
    } finally {
      setLoading(false);
    }
  };

  const getTitle = () => {
    if (mode === "forgot") return "Forgot Password";
    if (mode === "otp") return "Enter OTP";
    if (mode === "reset") return "Reset Password";
    return mode === "login" ? "Sign in" : "Create account";
  };

  const getSubmitLabel = () => {
    if (loading) return "Please wait...";
    if (mode === "forgot") return "Send OTP";
    if (mode === "otp") return "Verify OTP";
    if (mode === "reset") return "Reset Password";
    return mode === "login" ? "Sign in" : "Register";
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
          <h2>{getTitle()}</h2>

          {error && <div className="auth-error">{error}</div>}
          {success && <div className="auth-success">{success}</div>}

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

          {(mode === "login" || mode === "register" || mode === "forgot") && (
            <label>
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                disabled={loading || mode === "otp" || mode === "reset"}
                placeholder="you@example.com"
              />
            </label>
          )}

          {(mode === "login" || mode === "register") && (
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
          )}

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

          {mode === "otp" && (
            <label>
              <span>OTP Code</span>
              <input
                type="text"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                disabled={loading}
                placeholder="Enter 6-digit OTP"
                maxLength={6}
                inputMode="numeric"
              />
            </label>
          )}

          {mode === "reset" && (
            <>
              <label>
                <span>New Password</span>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  disabled={loading}
                  placeholder="••••••••"
                />
              </label>
              <label>
                <span>Confirm New Password</span>
                <input
                  type="password"
                  value={confirmNewPassword}
                  onChange={(e) => setConfirmNewPassword(e.target.value)}
                  autoComplete="new-password"
                  disabled={loading}
                  placeholder="••••••••"
                />
              </label>
            </>
          )}

          <button type="submit" className="auth-submit" disabled={loading}>
            {getSubmitLabel()}
          </button>

          {mode === "login" && (
            <p className="auth-forgot">
              <button
                type="button"
                onClick={() => {
                  setMode("forgot");
                  setError("");
                  setSuccess("");
                }}
              >
                Forgot password?
              </button>
            </p>
          )}

          <p className="auth-switch">
            {(mode === "login" || mode === "register") && (
              <>
                {mode === "login" ? "Don't have an account?" : "Already have an account?"}{" "}
                <button
                  type="button"
                  onClick={() => {
                    setMode(mode === "login" ? "register" : "login");
                    setError("");
                    setSuccess("");
                  }}
                >
                  {mode === "login" ? "Register" : "Sign in"}
                </button>
              </>
            )}
            {(mode === "forgot" || mode === "otp" || mode === "reset") && (
              <button
                type="button"
                onClick={() => {
                  setMode("login");
                  setError("");
                  setSuccess("");
                  setOtp("");
                  setNewPassword("");
                  setConfirmNewPassword("");
                }}
              >
                Back to Sign in
              </button>
            )}
          </p>
        </form>
      </div>
    </div>
  );
}

function AdminDashboard({ onBack, onLogout }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/admin/dashboard/`, {
          headers: authHeaders(),
        });
        const data = await res.json();
        if (!res.ok) {
          setError(data.error || "Failed to load dashboard");
          return;
        }
        setStats(data);
      } catch {
        setError("Cannot connect to the server");
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  return (
    <div className="admin-dashboard">
      <header className="admin-header">
        <div className="admin-header-left">
          <div className="brand-mark" aria-hidden="true">
            <span>ID</span>
          </div>
          <h1>Admin Dashboard</h1>
        </div>
        <div className="admin-header-right">
          <button type="button" className="secondary-button" onClick={onBack}>
            <Icon name="chat" size={16} /> Back to App
          </button>
          <button type="button" className="secondary-button" onClick={onLogout}>
            Logout
          </button>
        </div>
      </header>

      {loading && <div className="admin-loading">Loading dashboard...</div>}
      {error && <div className="admin-error">{error}</div>}

      {stats && (
        <>
          <div className="admin-summary-cards">
            <div className="admin-card">
              <div className="admin-card-number">{stats.total_users}</div>
              <div className="admin-card-label">Total Users</div>
            </div>
            <div className="admin-card">
              <div className="admin-card-number">
                {stats.users.reduce((sum, u) => sum + u.upload_count, 0)}
              </div>
              <div className="admin-card-label">Total Uploads</div>
            </div>
            <div className="admin-card">
              <div className="admin-card-number">
                {stats.users.reduce((sum, u) => sum + u.conversation_count, 0)}
              </div>
              <div className="admin-card-label">Total Conversations</div>
            </div>
            <div className="admin-card">
              <div className="admin-card-number">
                {stats.users.reduce((sum, u) => sum + u.message_count, 0)}
              </div>
              <div className="admin-card-label">Total Messages</div>
            </div>
          </div>

          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Joined</th>
                  <th>Last Login</th>
                  <th>Uploads</th>
                  <th>Conversations</th>
                  <th>Messages</th>
                  <th>Role</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {stats.users.map((u) => (
                  <tr key={u.id}>
                    <td className="admin-cell-name">{u.name}</td>
                    <td>{u.email}</td>
                    <td>{new Date(u.date_joined).toLocaleDateString()}</td>
                    <td>{u.last_login ? new Date(u.last_login).toLocaleDateString() : "Never"}</td>
                    <td className="admin-cell-number">{u.upload_count}</td>
                    <td className="admin-cell-number">{u.conversation_count}</td>
                    <td className="admin-cell-number">{u.message_count}</td>
                    <td>
                      <span className={`admin-badge ${u.is_admin ? "admin-badge-admin" : "admin-badge-user"}`}>
                        {u.is_admin ? "Admin" : "User"}
                      </span>
                    </td>
                    <td>
                      <span className={`admin-badge ${u.is_active ? "admin-badge-active" : "admin-badge-inactive"}`}>
                        {u.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function App() {
  // Clear auth only on first visit (new tab/window), not on refresh
  useEffect(() => {
    if (!sessionStorage.getItem("session_active")) {
      clearAuth();
      sessionStorage.setItem("session_active", "1");
    }
  }, []);

  const [authedUser, setAuthedUser] = useState(() => {
    return sessionStorage.getItem("session_active") ? getUsername() : "";
  });
  const [isAdmin, setIsAdmin] = useState(() => {
    return sessionStorage.getItem("session_active") ? getIsAdmin() : false;
  });
  const [showAdmin, setShowAdmin] = useState(false);
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
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [renamingConversation, setRenamingConversation] = useState(null);
  const [renameTitle, setRenameTitle] = useState("");
  const chatScrollRef = useRef(null);
  const toastTimerRef = useRef(null);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "light");
    localStorage.setItem("theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  // Sync admin flag from server on mount
  useEffect(() => {
    if (!authedUser) return;
    fetch(`${API_BASE}/auth/me/`, { headers: authHeaders() })
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
        if (data && data.is_admin !== undefined) {
          localStorage.setItem("auth_is_admin", data.is_admin ? "true" : "false");
          setIsAdmin(data.is_admin);
        }
      })
      .catch(() => {});
  }, [authedUser]);

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

  // ---- Conversations API ----
  const fetchConversations = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/conversations/`, {
        headers: authHeaders(),
      });
      if (response.status === 401) return;
      if (!response.ok) return;
      const data = await response.json();
      setConversations(data.conversations || []);
    } catch (err) {
      // silent
    }
  }, []);

  const createConversation = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/conversations/create/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ title: "New Chat" }),
      });
      if (!response.ok) return;
      const data = await response.json();
      setConversations((prev) => [data, ...prev]);
      setActiveConversation(data);
      setMessages([]);
    } catch (err) {
      // silent
    }
  }, []);

  const loadConversation = useCallback(async (conversation) => {
    setActiveConversation(conversation);
    try {
      const response = await fetch(`${API_BASE}/conversations/${conversation.id}/`, {
        headers: authHeaders(),
      });
      if (!response.ok) return;
      const data = await response.json();
      const loaded = (data.messages || []).map((m, i, arr) => {
        const msg = {
          id: m.id ? `db-${m.id}` : `loaded-${i}`,
          dbId: m.id || null,
          role: m.role === "user" ? "user" : "bot",
          text: m.text,
          sources: m.sources || [],
          highlights: m.highlights || [],
          streaming: false,
          globalDismissed: true,
        };
        return msg;
      });
      setMessages(loaded);
    } catch (err) {
      // silent
    }
  }, []);

  const handleRenameConversation = useCallback(async () => {
    if (!renamingConversation || !renameTitle.trim()) {
      setRenamingConversation(null);
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/conversations/${renamingConversation.id}/rename/`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ title: renameTitle.trim() }),
      });
      if (!response.ok) return;
      setConversations((prev) =>
        prev.map((c) => (c.id === renamingConversation.id ? { ...c, title: renameTitle.trim() } : c))
      );
      if (activeConversation?.id === renamingConversation.id) {
        setActiveConversation((prev) => ({ ...prev, title: renameTitle.trim() }));
      }
    } catch (err) {
      // silent
    }
    setRenamingConversation(null);
  }, [renamingConversation, renameTitle, activeConversation]);

  const handleDeleteConversation = useCallback(async (conversationId) => {
    try {
      const response = await fetch(`${API_BASE}/conversations/${conversationId}/delete/`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!response.ok) return;
      setConversations((prev) => prev.filter((c) => c.id !== conversationId));
      if (activeConversation?.id === conversationId) {
        setActiveConversation(null);
        setMessages([]);
      }
      showToast("Conversation deleted.", "success");
    } catch (err) {
      // silent
    }
  }, [activeConversation, showToast]);

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => {
      fetchUploadedFiles();
      fetchConversations();
    }, 0);
    const interval = window.setInterval(() => {
      fetchUploadedFiles({ silent: true });
    }, 60000);

    return () => {
      window.clearTimeout(initialRefresh);
      window.clearInterval(interval);
    };
  }, [fetchUploadedFiles, fetchConversations]);

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

    let currentConversation = activeConversation;
    try {
      // Auto-create conversation if none is active
      if (!currentConversation) {
        try {
          const createRes = await fetch(`${API_BASE}/conversations/create/`, {
            method: "POST",
            headers: { "Content-Type": "application/json", ...authHeaders() },
            body: JSON.stringify({ title: "New Chat" }),
          });
          if (createRes.ok) {
            const convData = await createRes.json();
            currentConversation = convData;
            setActiveConversation(convData);
            setConversations((prev) => [convData, ...prev]);
          }
        } catch (err) {
          // Continue without saving if creation fails
        }
      }

      const convParam = currentConversation ? `&conversation_id=${currentConversation.id}` : "";
      const response = await fetch(`${API_BASE}/chat-stream/?query=${encodeURIComponent(scopedQuestion)}${convParam}`, {
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
      // Refresh conversations to pick up title change from first message
      fetchConversations();
      // Reload messages to get server-assigned dbIds (needed for highlights to persist)
      if (currentConversation) {
        try {
          const res = await fetch(`${API_BASE}/conversations/${currentConversation.id}/`, {
            headers: authHeaders(),
          });
          if (res.ok) {
            const data = await res.json();
            const loadedMessages = (data.messages || []).map((m, i, arr) => {
              const isOffer = m.role !== "user" && isGlobalSearchOffer(m.text);
              // Find the preceding user message to reconstruct globalQuestion
              let globalQ = "";
              if (isOffer) {
                for (let j = i - 1; j >= 0; j--) {
                  if (arr[j].role === "user") {
                    globalQ = arr[j].text || "";
                    break;
                  }
                }
              }
              return {
                id: m.id ? `db-${m.id}` : `loaded-${i}`,
                dbId: m.id || null,
                role: m.role === "user" ? "user" : "bot",
                text: m.text,
                sources: m.sources || [],
                highlights: m.highlights || [],
                streaming: false,
                globalDismissed: !isOffer,
                globalQuestion: globalQ,
              };
            });
            setMessages(loadedMessages);
          }
        } catch {
          // silent — messages still show, just without dbIds
        }
      }
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
      let url = `${API_BASE}/global-search/?query=${encodeURIComponent(question)}`;
      if (activeConversation?.id) {
        url += `&conversation_id=${activeConversation.id}`;
      }
      const response = await fetch(url, {
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
    setIsAdmin(false);
    setShowAdmin(false);
    setMessages([]);
    setUploadedFiles([]);
    setConversations([]);
    setActiveConversation(null);
    if (recognitionRef.current) {
      recognitionRef.current.abort();
      recognitionRef.current = null;
    }
    setIsListening(false);
  };

  const toggleVoiceInput = useCallback(() => {
    // Stop listening
    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
      setIsListening(false);
      return;
    }

    // Check browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      showToast("Voice input is not supported in this browser. Try Chrome or Edge.", "error");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;

    let finalTranscript = "";

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interim += transcript;
        }
      }
      setInput(finalTranscript + interim);
    };

    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };

    recognition.onerror = (event) => {
      setIsListening(false);
      recognitionRef.current = null;
      if (event.error !== "aborted" && event.error !== "no-speech") {
        showToast(`Voice error: ${event.error}`, "error");
      }
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [isListening, showToast]);

  const saveHighlightsToServer = useCallback(async (dbId, highlights) => {
    if (!dbId) return;
    const numericId = String(dbId).replace(/^db-/, "");
    try {
      await fetch(`${API_BASE}/messages/${numericId}/highlights/`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ highlights }),
      });
    } catch {
      // silent
    }
  }, []);

  const addHighlight = useCallback((messageId, text, color) => {
    setMessages((prev) => {
      const updated = prev.map((m) => {
        if (m.id !== messageId) return m;
        const existing = m.highlights || [];
        // Don't add duplicate
        if (existing.some((h) => h.text === text)) return m;
        const newHighlights = [...existing, { text, color }];
        // Save to server
        if (m.dbId) saveHighlightsToServer(m.dbId, newHighlights);
        return { ...m, highlights: newHighlights };
      });
      return updated;
    });
  }, [saveHighlightsToServer]);

  const removeHighlight = useCallback((messageId, text) => {
    setMessages((prev) => {
      const updated = prev.map((m) => {
        if (m.id !== messageId) return m;
        const newHighlights = (m.highlights || []).filter((h) => h.text !== text);
        if (m.dbId) saveHighlightsToServer(m.dbId, newHighlights);
        return { ...m, highlights: newHighlights };
      });
      return updated;
    });
  }, [saveHighlightsToServer]);

  if (!authedUser) {
    return (
      <AuthScreen
        onAuth={(username) => {
          setAuthedUser(username);
          setIsAdmin(getIsAdmin());
        }}
      />
    );
  }

  if (showAdmin && isAdmin) {
    return (
      <AdminDashboard
        onBack={() => setShowAdmin(false)}
        onLogout={handleLogout}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Document library">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            <span>ID</span>
          </div>
        </div>

        {/* Conversations Section */}
        <div className="conversations-section">
          <div className="conversations-header">
            <span className="conversations-title">Chats</span>
            <button
              type="button"
              className="icon-button new-chat-btn"
              onClick={createConversation}
              title="New Chat"
              aria-label="New Chat"
            >
              <Icon name="plus" size={16} />
            </button>
          </div>
          <div className="conversations-list">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`conversation-row ${activeConversation?.id === conv.id ? "is-active" : ""}`}
              >
                {renamingConversation?.id === conv.id ? (
                  <form
                    className="rename-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      handleRenameConversation();
                    }}
                  >
                    <input
                      type="text"
                      value={renameTitle}
                      onChange={(e) => setRenameTitle(e.target.value)}
                      onBlur={handleRenameConversation}
                      autoFocus
                      className="rename-input"
                    />
                  </form>
                ) : (
                  <button
                    type="button"
                    className="conversation-select"
                    onClick={() => loadConversation(conv)}
                    title={conv.title}
                  >
                    <Icon name="chat" size={14} />
                    <span className="conversation-name">{conv.title}</span>
                  </button>
                )}
                <div className="conversation-actions">
                  <button
                    type="button"
                    className="conv-action-btn"
                    title="Rename"
                    onClick={(e) => {
                      e.stopPropagation();
                      setRenamingConversation(conv);
                      setRenameTitle(conv.title);
                    }}
                  >
                    <Icon name="edit" size={13} />
                  </button>
                  <button
                    type="button"
                    className="conv-action-btn conv-delete-btn"
                    title="Delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteConversation(conv.id);
                    }}
                  >
                    <Icon name="trash" size={13} />
                  </button>
                </div>
              </div>
            ))}
            {conversations.length === 0 && (
              <div className="empty-conversations">
                <small>No conversations yet</small>
              </div>
            )}
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
            {isAdmin && (
              <button type="button" className="admin-button" onClick={() => setShowAdmin(true)}>
                Admin Panel
              </button>
            )}
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
                          highlights={message.highlights || []}
                          onAddHighlight={(text, color) => addHighlight(message.id, text, color)}
                          onRemoveHighlight={(text) => removeHighlight(message.id, text)}
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
                  isListening
                    ? "Listening..."
                    : activeDocument
                      ? `Ask about ${compactName(activeDocument.name)}`
                      : "Ask about your knowledge base"
                }
                disabled={loading}
              />
            </div>
            <button
              className={`mic-button ${isListening ? "is-listening" : ""}`}
              type="button"
              onClick={toggleVoiceInput}
              disabled={loading}
              title={isListening ? "Stop listening" : "Voice input"}
              aria-label={isListening ? "Stop listening" : "Voice input"}
            >
              <Icon name={isListening ? "micOff" : "mic"} size={18} />
            </button>
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
