document.addEventListener("DOMContentLoaded", () => {
    const tg = window.Telegram.WebApp;
    tg.expand();

    const urlParams = new URLSearchParams(window.location.search);
    const queryId = urlParams.get("query_id");
    const session = urlParams.get("session");
    const container = document.getElementById("questions-container");
    const form = document.getElementById("captcha-form");
    const statusDiv = document.getElementById("status");

    const paramStr = queryId ? `query_id=${queryId}` : `session=${session}`;
    const emojiSelections = {}; // questionId -> selected emoji index

    if (!queryId && !session) {
        showStatus("Невірне посилання для верифікації.", "error");
        return;
    }

    fetch(`/api/questions?${paramStr}`)
        .then(res => res.json())
        .then(data => {
            if (data.questions && data.questions.length > 0) {
                data.questions.forEach((q) => {
                    if (q.type === "emoji") {
                        renderEmojiQuestion(q);
                    } else if (q.type === "choice") {
                        renderChoiceQuestion(q);
                    } else {
                        renderTextQuestion(q);
                    }
                });
            } else if (data.detail) {
                showStatus("Невірна або застаріла сесія.", "error");
            } else {
                showStatus("Не вдалося завантажити питання капчі", "error");
            }
        })
        .catch(() => showStatus("Помилка з'єднання з сервером", "error"));

    function renderTextQuestion(q) {
        const group = document.createElement("div");
        group.className = "form-group";
        group.innerHTML = `
            <label for="q-${q.id}">${q.q}</label>
            <input type="text" id="q-${q.id}" name="${q.id}" required placeholder="Ваша відповідь..." autocomplete="off">
        `;
        container.appendChild(group);
    }

    function renderChoiceQuestion(q) {
        const group = document.createElement("div");
        group.className = "form-group";

        const label = document.createElement("label");
        label.textContent = q.q;
        group.appendChild(label);

        const grid = document.createElement("div");
        grid.className = "emoji-grid";

        q.choices.forEach((choice) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "emoji-btn";
            btn.textContent = choice;
            btn.addEventListener("click", () => {
                grid.querySelectorAll(".emoji-btn").forEach(b => b.classList.remove("selected"));
                btn.classList.add("selected");
                emojiSelections[q.id] = choice;
            });
            grid.appendChild(btn);
        });

        group.appendChild(grid);
        container.appendChild(group);
    }

    function renderEmojiQuestion(q) {
        const group = document.createElement("div");
        group.className = "form-group";

        const label = document.createElement("label");
        label.textContent = q.q;
        group.appendChild(label);

        const grid = document.createElement("div");
        grid.className = "emoji-grid";

        q.emojis.forEach((emoji, idx) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "emoji-btn";
            btn.textContent = emoji;
            btn.dataset.idx = idx;
            btn.addEventListener("click", () => {
                // Deselect all in this grid
                grid.querySelectorAll(".emoji-btn").forEach(b => b.classList.remove("selected"));
                btn.classList.add("selected");
                emojiSelections[q.id] = idx;
            });
            grid.appendChild(btn);
        });

        group.appendChild(grid);
        container.appendChild(group);
    }

    // --- Fingerprint collection ---
    function getCanvasFingerprint() {
        try {
            const canvas = document.createElement("canvas");
            canvas.width = 200;
            canvas.height = 50;
            const ctx = canvas.getContext("2d");
            ctx.textBaseline = "top";
            ctx.font = "14px 'Arial'";
            ctx.fillStyle = "#f60";
            ctx.fillRect(125, 1, 62, 20);
            ctx.fillStyle = "#069";
            ctx.fillText("ClassicGuard", 2, 15);
            ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
            ctx.fillText("fp", 4, 17);
            return canvas.toDataURL();
        } catch (e) {
            return "canvas_error";
        }
    }

    function getWebGLFingerprint() {
        try {
            const canvas = document.createElement("canvas");
            const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
            if (!gl) return "no_webgl";
            const debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
            if (debugInfo) {
                return gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) + "|" +
                       gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
            }
            return "no_debug_info";
        } catch (e) {
            return "webgl_error";
        }
    }

    function collectFingerprint() {
        const user = tg.initDataUnsafe?.user || {};
        return {
            // Telegram data
            is_premium: user.is_premium || false,
            language_code: user.language_code || "",
            // Device data
            user_agent: navigator.userAgent,
            platform: navigator.platform || "",
            language: navigator.language || "",
            screen: `${screen.width}x${screen.height}x${screen.colorDepth}`,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
            timezone_offset: new Date().getTimezoneOffset(),
            // Fingerprint
            canvas: getCanvasFingerprint(),
            webgl: getWebGLFingerprint(),
        };
    }

    form.addEventListener("submit", (e) => {
        e.preventDefault();

        const answers = {};

        // Text inputs
        const inputs = form.querySelectorAll("input[type='text']");
        inputs.forEach(input => {
            answers[input.name] = input.value;
        });

        // Emoji selections
        Object.entries(emojiSelections).forEach(([qId, idx]) => {
            answers[qId] = idx;
        });

        const fingerprint = collectFingerprint();
        showStatus("Перевірка відповідей...", "");

        const payload = {
            answers,
            device_info: fingerprint.user_agent,
            fingerprint: fingerprint
        };
        if (queryId) payload.query_id = queryId;
        if (session) payload.session = session;

        fetch("/api/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showStatus("✅ Успішно! Вас допущено до чату.", "success");
                setTimeout(() => tg.close(), 3000);
            } else {
                showStatus(data.reason || "Перевірку не пройдено.", "error");
            }
        })
        .catch(() => showStatus("Помилка надсилання перевірки.", "error"));
    });

    function showStatus(text, type) {
        statusDiv.className = `status ${type}`;
        statusDiv.textContent = text;
    }
});