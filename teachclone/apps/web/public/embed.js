/**
 * TeachClone Embed Widget — Self-contained chat widget for external websites.
 *
 * Usage:
 *   <script src="https://teachclone.com/embed.js" data-token="your_embed_token"></script>
 *
 * The widget renders a floating chat button that opens a panel showing
 * available teacher profiles. Students can start a chat session directly.
 */
(function () {
  "use strict";

  const API_BASE = "http://localhost:8000"; // configurable
  const scriptEl = document.currentScript;
  const EMBED_TOKEN = scriptEl?.getAttribute("data-token") || "";
  const API_BASE_ATTR = scriptEl?.getAttribute("data-api-url");

  if (!EMBED_TOKEN) {
    console.warn("[TeachClone] No data-token found. Widget cannot load.");
    return;
  }

  const BASE = API_BASE_ATTR || API_BASE;

  // --- Inject styles ---
  const style = document.createElement("style");
  style.textContent = `
    .tc-widget-btn {
      position: fixed; bottom: 24px; right: 24px; z-index: 99999;
      width: 60px; height: 60px; border-radius: 50%;
      background: #6366F1; color: #fff; border: none; cursor: pointer;
      font-size: 28px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      display: flex; align-items: center; justify-content: center;
      transition: transform 0.2s;
    }
    .tc-widget-btn:hover { transform: scale(1.1); }
    .tc-widget-panel {
      position: fixed; bottom: 100px; right: 24px; z-index: 99998;
      width: 360px; max-height: 520px; background: #1a1a2e;
      border-radius: 16px; box-shadow: 0 8px 40px rgba(0,0,0,0.4);
      display: none; flex-direction: column; overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: #e2e8f0;
    }
    .tc-widget-panel.open { display: flex; }
    .tc-panel-header {
      padding: 16px; background: #16213e; border-bottom: 1px solid #334155;
      display: flex; justify-content: space-between; align-items: center;
    }
    .tc-panel-header h3 { margin: 0; font-size: 15px; font-weight: 600; }
    .tc-close-btn { background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 18px; }
    .tc-profiles { padding: 8px; overflow-y: auto; flex: 1; }
    .tc-profile-card {
      padding: 12px; margin: 4px 0; background: #0f172a; border-radius: 10px;
      cursor: pointer; transition: background 0.15s;
    }
    .tc-profile-card:hover { background: #1e293b; }
    .tc-profile-card h4 { margin: 0 0 4px; font-size: 14px; color: #e2e8f0; }
    .tc-profile-card p { margin: 0; font-size: 12px; color: #94a3b8; }
    .tc-chat-area { display: none; flex-direction: column; height: 400px; }
    .tc-chat-area.active { display: flex; }
    .tc-messages { flex: 1; overflow-y: auto; padding: 12px; }
    .tc-msg { margin: 8px 0; padding: 10px 14px; border-radius: 12px; font-size: 13px; line-height: 1.5; max-width: 85%; }
    .tc-msg.user { background: #6366F1; color: #fff; align-self: flex-end; margin-left: auto; border-bottom-right-radius: 4px; }
    .tc-msg.assistant { background: #1e293b; color: #e2e8f0; border-bottom-left-radius: 4px; }
    .tc-input-row { display: flex; padding: 8px 12px; gap: 8px; border-top: 1px solid #334155; }
    .tc-input-row input {
      flex: 1; background: #0f172a; border: 1px solid #334155; border-radius: 8px;
      padding: 10px 12px; color: #e2e8f0; font-size: 13px; outline: none;
    }
    .tc-input-row button {
      background: #6366F1; color: #fff; border: none; border-radius: 8px;
      padding: 10px 16px; cursor: pointer; font-size: 13px;
    }
    .tc-loading { text-align: center; padding: 24px; color: #64748b; }
    .tc-back-btn {
      background: none; border: none; color: #94a3b8; cursor: pointer;
      font-size: 13px; padding: 8px 16px;
    }
  `;
  document.head.appendChild(style);

  // --- Build DOM ---
  const btn = document.createElement("button");
  btn.className = "tc-widget-btn";
  btn.textContent = "💬";
  btn.setAttribute("aria-label", "Open TeachClone chat");

  const panel = document.createElement("div");
  panel.className = "tc-widget-panel";

  let sessionId = null;
  let currentProfile = null;

  function renderProfiles(profiles) {
    panel.innerHTML = `
      <div class="tc-panel-header">
        <h3>🎓 Choose a Teacher</h3>
        <button class="tc-close-btn" aria-label="Close">&times;</button>
      </div>
      <div class="tc-profiles">
        ${profiles.length === 0 ? '<div class="tc-loading">No profiles available</div>' : ""}
      </div>
    `;
    panel.querySelector(".tc-close-btn").onclick = () => panel.classList.remove("open");

    const container = panel.querySelector(".tc-profiles");
    profiles.forEach((p) => {
      const card = document.createElement("div");
      card.className = "tc-profile-card";
      card.innerHTML = `<h4>${escHtml(p.name)}</h4><p>${escHtml(p.subject || "")} ${p.description ? "— " + escHtml(p.description) : ""}</p>`;
      card.onclick = () => startChat(p);
      container.appendChild(card);
    });
  }

  function renderChat(profile) {
    panel.innerHTML = `
      <div class="tc-panel-header">
        <h3>💬 ${escHtml(profile.name)}</h3>
        <button class="tc-close-btn" aria-label="Close">&times;</button>
      </div>
      <div class="tc-chat-area active">
        <div class="tc-messages">
          <div class="tc-msg assistant">Hi! I'm ${escHtml(profile.name)}. Ask me anything!</div>
        </div>
        <div class="tc-input-row">
          <input type="text" placeholder="Type your question..." />
          <button>Send</button>
        </div>
      </div>
    `;
    panel.querySelector(".tc-close-btn").onclick = () => panel.classList.remove("open");

    const input = panel.querySelector("input");
    const sendBtn = panel.querySelector("button:not(.tc-close-btn)");
    const messages = panel.querySelector(".tc-messages");

    async function sendMessage() {
      const text = input.value.trim();
      if (!text) return;
      input.value = "";

      appendMsg("user", text);

      try {
        if (!sessionId) {
          // Create session first
          const chatRes = await fetch(`${BASE}/embed/chat?token=${encodeURIComponent(EMBED_TOKEN)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "Origin": location.origin },
            body: JSON.stringify({ profile_id: profile.id, content: text, student_level: "intermediate" }),
          });
          if (!chatRes.ok) throw new Error("Failed to start chat");
          const chatData = await chatRes.json();
          sessionId = chatData.session_id;
        }

        // Send message via SSE
        const res = await fetch(`${BASE}/chat/${sessionId}/message`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text, want_audio: false }),
        });

        if (!res.ok) throw new Error(`Chat error ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let assistantEl = appendMsg("assistant", "");

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";
          for (const part of parts) {
            let data = "";
            for (const line of part.split("\n")) {
              if (line.startsWith("data:")) data += line.slice(5).trim();
            }
            if (!data) continue;
            try {
              const parsed = JSON.parse(data);
              if (parsed.token) assistantEl.textContent += parsed.token;
            } catch {}
          }
        }
      } catch (err) {
        appendMsg("assistant", "Sorry, something went wrong. Please try again.");
        console.error("[TeachClone]", err);
      }
    }

    sendBtn.onclick = sendMessage;
    input.onkeydown = (e) => { if (e.key === "Enter") sendMessage(); };
    input.focus();
  }

  function appendMsg(role, text) {
    const messages = panel.querySelector(".tc-messages");
    const el = document.createElement("div");
    el.className = `tc-msg ${role}`;
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  function escHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  async function loadProfiles() {
    panel.innerHTML = '<div class="tc-loading">Loading teachers…</div>';
    panel.classList.add("open");
    try {
      const res = await fetch(`${BASE}/embed/profiles?token=${encodeURIComponent(EMBED_TOKEN)}`, {
        headers: { "Origin": location.origin },
      });
      if (!res.ok) throw new Error("Failed to load profiles");
      const profiles = await res.json();
      renderProfiles(profiles);
    } catch (err) {
      panel.innerHTML = '<div class="tc-loading">Failed to load teachers.</div>';
      console.error("[TeachClone]", err);
    }
  }

  btn.onclick = () => {
    if (panel.classList.contains("open")) {
      panel.classList.remove("open");
    } else {
      loadProfiles();
    }
  };

  document.body.appendChild(btn);
  document.body.appendChild(panel);
})();
