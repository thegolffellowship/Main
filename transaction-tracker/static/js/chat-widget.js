/* =========================================================
   TGF Support Chat Widget
   Floating AI assistant available to authenticated users.
   Include AFTER auth.js on every page.
   ========================================================= */

(function () {
    "use strict";

    // ---- State ----
    let chatOpen = false;
    let chatMode = null;       // "ask" | "bug" | "feature"
    let conversationHistory = [];
    let streaming = false;

    // ---- Helpers ----
    function esc(str) {
        const d = document.createElement("div");
        d.textContent = str || "";
        return d.innerHTML;
    }

    function currentPage() {
        const path = window.location.pathname;
        if (path === "/") return "Transactions";
        if (path.startsWith("/events")) return "Events";
        if (path.startsWith("/customers")) return "Customers";
        if (path.startsWith("/rsvps")) return "RSVP Log";
        if (path.startsWith("/matrix")) return "Matrix";
        if (path.startsWith("/audit")) return "Audit";
        if (path.startsWith("/changelog")) return "Changelog";
        return path;
    }

    // Simple markdown: **bold**, `code`, newlines
    function miniMarkdown(text) {
        return esc(text)
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/`([^`]+)`/g, '<code style="background:#f1f5f9;padding:0.1em 0.3em;border-radius:3px;font-size:0.85em;">$1</code>')
            .replace(/\n/g, "<br>");
    }

    // ---- Build DOM ----
    function injectWidget() {
        // FAB button
        const fab = document.createElement("button");
        fab.id = "tgf-chat-fab";
        fab.innerHTML = "?";
        fab.title = "TGF Support";
        document.body.appendChild(fab);

        // Chat panel
        const panel = document.createElement("div");
        panel.id = "tgf-chat-panel";
        panel.innerHTML = `
            <div class="tgf-chat-header">
                <span class="tgf-chat-title">TGF Support</span>
                <button class="tgf-chat-close" title="Close">&times;</button>
            </div>
            <div class="tgf-chat-body">
                <div class="tgf-chat-modes">
                    <button class="tgf-mode-btn" data-mode="ask">Ask a Question</button>
                    <button class="tgf-mode-btn" data-mode="bug">Report a Bug</button>
                    <button class="tgf-mode-btn" data-mode="feature">Request a Feature</button>
                </div>
                <div class="tgf-chat-messages" id="tgf-chat-messages"></div>
            </div>
            <div class="tgf-chat-input-area" style="display:none;">
                <textarea id="tgf-chat-input" placeholder="Type your message..." rows="2"></textarea>
                <button id="tgf-chat-send" title="Send">&#9654;</button>
            </div>
        `;
        document.body.appendChild(panel);

        // Events
        fab.addEventListener("click", toggleChat);
        panel.querySelector(".tgf-chat-close").addEventListener("click", toggleChat);

        panel.querySelectorAll(".tgf-mode-btn").forEach(btn => {
            btn.addEventListener("click", () => selectMode(btn.dataset.mode));
        });

        document.getElementById("tgf-chat-send").addEventListener("click", sendMessage);
        document.getElementById("tgf-chat-input").addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    function toggleChat() {
        chatOpen = !chatOpen;
        const panel = document.getElementById("tgf-chat-panel");
        const fab = document.getElementById("tgf-chat-fab");
        if (chatOpen) {
            panel.classList.add("open");
            fab.classList.add("open");
            fab.innerHTML = "&times;";
        } else {
            panel.classList.remove("open");
            fab.classList.remove("open");
            fab.innerHTML = "?";
        }
    }

    function selectMode(mode) {
        chatMode = mode;
        conversationHistory = [];
        streaming = false;

        const msgs = document.getElementById("tgf-chat-messages");
        const inputArea = document.querySelector(".tgf-chat-input-area");
        const input = document.getElementById("tgf-chat-input");

        // Highlight selected button
        document.querySelectorAll(".tgf-mode-btn").forEach(b => b.classList.remove("active"));
        document.querySelector(`.tgf-mode-btn[data-mode="${mode}"]`).classList.add("active");

        inputArea.style.display = "flex";
        msgs.innerHTML = "";

        if (mode === "ask") {
            addBotMessage("Hi! I'm the TGF Assistant. Ask me anything about the Transaction Tracker — features, workflows, or how to do something.");
            input.placeholder = "Ask your question...";
        } else if (mode === "bug") {
            addBotMessage("Describe the bug you found. Include what page you were on and what you expected to happen. I'll log it for the admin team.");
            input.placeholder = "Describe the bug...";
        } else if (mode === "feature") {
            addBotMessage("What feature would you like to see? Describe it and I'll log the request for the admin team.");
            input.placeholder = "Describe your feature idea...";
        }

        input.focus();
    }

    function addBotMessage(text) {
        const msgs = document.getElementById("tgf-chat-messages");
        const div = document.createElement("div");
        div.className = "tgf-msg tgf-msg-bot";
        div.innerHTML = miniMarkdown(text);
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
    }

    function addUserMessage(text) {
        const msgs = document.getElementById("tgf-chat-messages");
        const div = document.createElement("div");
        div.className = "tgf-msg tgf-msg-user";
        div.textContent = text;
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
    }

    function addStreamingBubble() {
        const msgs = document.getElementById("tgf-chat-messages");
        const div = document.createElement("div");
        div.className = "tgf-msg tgf-msg-bot tgf-msg-streaming";
        div.innerHTML = '<span class="tgf-typing">...</span>';
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
        return div;
    }

    async function sendMessage() {
        if (streaming) return;
        const input = document.getElementById("tgf-chat-input");
        const text = input.value.trim();
        if (!text) return;

        input.value = "";
        addUserMessage(text);

        if (chatMode === "bug" || chatMode === "feature") {
            await submitFeedback(text);
            return;
        }

        // Ask a Question — stream from AI
        streaming = true;
        const sendBtn = document.getElementById("tgf-chat-send");
        sendBtn.disabled = true;

        const bubble = addStreamingBubble();

        try {
            const res = await fetch("/api/support/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    history: conversationHistory,
                    page: currentPage(),
                }),
            });

            if (!res.ok) {
                const err = await res.json();
                bubble.innerHTML = miniMarkdown("Sorry, something went wrong: " + (err.error || "Unknown error"));
                streaming = false;
                sendBtn.disabled = false;
                return;
            }

            // Read SSE stream
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let fullText = "";
            bubble.innerHTML = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split("\n");
                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    try {
                        const payload = JSON.parse(line.slice(6));
                        if (payload.text) {
                            fullText += payload.text;
                            bubble.innerHTML = miniMarkdown(fullText);
                            document.getElementById("tgf-chat-messages").scrollTop =
                                document.getElementById("tgf-chat-messages").scrollHeight;
                        }
                        if (payload.error) {
                            fullText += "\n\n[Error: " + payload.error + "]";
                            bubble.innerHTML = miniMarkdown(fullText);
                        }
                    } catch (_) { /* skip malformed lines */ }
                }
            }

            bubble.classList.remove("tgf-msg-streaming");

            // Update conversation history
            conversationHistory.push({ role: "user", content: text });
            conversationHistory.push({ role: "assistant", content: fullText });

            // Keep history manageable (last 10 exchanges)
            if (conversationHistory.length > 20) {
                conversationHistory = conversationHistory.slice(-20);
            }
        } catch (err) {
            bubble.innerHTML = miniMarkdown("Connection error. Please try again.");
            bubble.classList.remove("tgf-msg-streaming");
        }

        streaming = false;
        sendBtn.disabled = false;
    }

    async function submitFeedback(text) {
        const fbType = chatMode === "bug" ? "bug" : "feature";
        try {
            const res = await fetch("/api/support/feedback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    type: fbType,
                    message: text,
                    page: currentPage(),
                }),
            });

            if (!res.ok) {
                const err = await res.json();
                addBotMessage("Failed to submit: " + (err.error || "Unknown error"));
                return;
            }

            const label = fbType === "bug" ? "Bug report" : "Feature request";
            addBotMessage(`${label} submitted! The admin team will review it. You can submit another or switch modes above.`);
        } catch (err) {
            addBotMessage("Connection error. Please try again.");
        }
    }

    // ---- Inject CSS ----
    function injectStyles() {
        const style = document.createElement("style");
        style.textContent = `
            #tgf-chat-fab {
                position: fixed;
                bottom: 1.25rem;
                right: 1.25rem;
                width: 48px;
                height: 48px;
                border-radius: 50%;
                background: #1e40af;
                color: #fff;
                border: none;
                font-size: 1.4rem;
                font-weight: 700;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(0,0,0,0.25);
                z-index: 9998;
                transition: transform 0.2s, background 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
                line-height: 1;
            }
            #tgf-chat-fab:hover { background: #1d4ed8; transform: scale(1.08); }
            #tgf-chat-fab.open { background: #6b7280; }

            #tgf-chat-panel {
                position: fixed;
                bottom: 5rem;
                right: 1.25rem;
                width: 370px;
                max-width: calc(100vw - 2rem);
                max-height: 520px;
                background: #fff;
                border-radius: 12px;
                box-shadow: 0 8px 30px rgba(0,0,0,0.18);
                z-index: 9999;
                display: flex;
                flex-direction: column;
                overflow: hidden;
                transform: scale(0.9) translateY(20px);
                opacity: 0;
                pointer-events: none;
                transition: transform 0.25s ease, opacity 0.25s ease;
            }
            #tgf-chat-panel.open {
                transform: scale(1) translateY(0);
                opacity: 1;
                pointer-events: auto;
            }

            .tgf-chat-header {
                background: #1e40af;
                color: #fff;
                padding: 0.75rem 1rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-shrink: 0;
            }
            .tgf-chat-title { font-weight: 700; font-size: 0.95rem; }
            .tgf-chat-close {
                background: none;
                border: none;
                color: #fff;
                font-size: 1.4rem;
                cursor: pointer;
                line-height: 1;
                padding: 0;
                opacity: 0.8;
            }
            .tgf-chat-close:hover { opacity: 1; }

            .tgf-chat-body {
                flex: 1;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
            }

            .tgf-chat-modes {
                display: flex;
                gap: 0.4rem;
                padding: 0.75rem 0.75rem 0.5rem;
                flex-wrap: wrap;
                flex-shrink: 0;
            }
            .tgf-mode-btn {
                flex: 1;
                min-width: 0;
                padding: 0.45rem 0.5rem;
                border: 1.5px solid #d1d5db;
                border-radius: 8px;
                background: #f9fafb;
                font-size: 0.72rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.15s;
                white-space: nowrap;
                text-align: center;
            }
            .tgf-mode-btn:hover { border-color: #1e40af; color: #1e40af; }
            .tgf-mode-btn.active { background: #1e40af; color: #fff; border-color: #1e40af; }

            .tgf-chat-messages {
                flex: 1;
                overflow-y: auto;
                padding: 0.5rem 0.75rem;
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
                min-height: 180px;
            }

            .tgf-msg {
                max-width: 88%;
                padding: 0.55rem 0.75rem;
                border-radius: 10px;
                font-size: 0.82rem;
                line-height: 1.45;
                word-break: break-word;
            }
            .tgf-msg-bot {
                background: #f1f5f9;
                color: #1e293b;
                align-self: flex-start;
                border-bottom-left-radius: 3px;
            }
            .tgf-msg-user {
                background: #1e40af;
                color: #fff;
                align-self: flex-end;
                border-bottom-right-radius: 3px;
            }
            .tgf-msg-streaming .tgf-typing {
                display: inline-block;
                animation: tgf-blink 1s infinite;
            }
            @keyframes tgf-blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.3; }
            }

            .tgf-chat-input-area {
                display: flex;
                gap: 0.4rem;
                padding: 0.5rem 0.75rem 0.65rem;
                border-top: 1px solid #e5e7eb;
                background: #fff;
                flex-shrink: 0;
            }
            #tgf-chat-input {
                flex: 1;
                border: 1.5px solid #d1d5db;
                border-radius: 8px;
                padding: 0.5rem 0.65rem;
                font-size: 0.82rem;
                resize: none;
                font-family: inherit;
                outline: none;
            }
            #tgf-chat-input:focus { border-color: #1e40af; }
            #tgf-chat-send {
                width: 38px;
                height: 38px;
                border-radius: 8px;
                border: none;
                background: #1e40af;
                color: #fff;
                font-size: 1rem;
                cursor: pointer;
                flex-shrink: 0;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            #tgf-chat-send:hover { background: #1d4ed8; }
            #tgf-chat-send:disabled { opacity: 0.5; cursor: not-allowed; }

            @media (max-width: 480px) {
                #tgf-chat-panel {
                    bottom: 4.5rem;
                    right: 0.5rem;
                    left: 0.5rem;
                    width: auto;
                    max-height: 70vh;
                }
                #tgf-chat-fab {
                    bottom: 0.75rem;
                    right: 0.75rem;
                    width: 44px;
                    height: 44px;
                    font-size: 1.2rem;
                }
            }
        `;
        document.head.appendChild(style);
    }

    // ---- Init ----
    // Poll for currentRole to be set by auth.js (avoids interfering with
    // page-specific onAuthReady callbacks).
    let _chatInjected = false;
    function tryInit() {
        if (_chatInjected) return;
        if (typeof currentRole !== "undefined" && currentRole) {
            _chatInjected = true;
            injectStyles();
            injectWidget();
        }
    }

    // Check immediately in case auth already resolved, then poll briefly
    document.addEventListener("DOMContentLoaded", () => {
        tryInit();
        if (!_chatInjected) {
            const iv = setInterval(() => {
                tryInit();
                if (_chatInjected) clearInterval(iv);
            }, 200);
            // Stop polling after 30s
            setTimeout(() => clearInterval(iv), 30000);
        }
    });
})();
