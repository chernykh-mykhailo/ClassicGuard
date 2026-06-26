document.addEventListener("DOMContentLoaded", () => {
    const tg = window.Telegram.WebApp;
    tg.expand();

    const urlParams = new URLSearchParams(window.location.search);
    const chatId = urlParams.get("chat_id") || "0";
    const questionsList = document.getElementById("questions-list");
    const form = document.getElementById("settings-form");
    const selectorContainer = document.getElementById("chat-selector-container");
    const chatSelect = document.getElementById("chat-select");
    const selectChatBtn = document.getElementById("select-chat-btn");
    const customLangContainer = document.getElementById("custom-lang-tags");
    const customLangInput = document.getElementById("custom-lang-input");
    const addCustomLangBtn = document.getElementById("add-custom-lang-btn");
    let customLanguages = [];
    let activeChatId = chatId;

    // ─── Chat selector ────────────────────────────────────────────────
    if (activeChatId === "0") {
        form.style.display = "none";
        selectorContainer.style.display = "block";
        const userId = tg.initDataUnsafe?.user?.id || 0;
        fetch(`/api/admin/chats?user_id=${userId}`)
            .then(r => r.json())
            .then(data => {
                chatSelect.innerHTML = "";
                if (data.chats && data.chats.length > 0) {
                    data.chats.forEach(c => {
                        const opt = document.createElement("option");
                        opt.value = c.id;
                        opt.textContent = c.title;
                        chatSelect.appendChild(opt);
                    });
                } else {
                    const opt = document.createElement("option");
                    opt.value = "";
                    opt.textContent = "Не знайдено підключених груп, де ви є адміном";
                    chatSelect.appendChild(opt);
                }
            });
        selectChatBtn.addEventListener("click", () => {
            const val = chatSelect.value;
            if (val) {
                activeChatId = val;
                selectorContainer.style.display = "none";
                form.style.display = "block";
                loadSettings(activeChatId);
                updateSpammerLink(activeChatId);
            } else {
                alert("Будь ласка, оберіть дійсний чат.");
            }
        });
    } else {
        loadSettings(activeChatId);
        updateSpammerLink(activeChatId);
    }

    function updateSpammerLink(cid) {
        const link = document.getElementById('spammer-db-link');
        if (link && cid && cid !== '0') {
            link.href = `/static/spammer-db.html?chat_id=${cid}`;
        }
    }

    // ─── Custom language tags ─────────────────────────────────────────
    function renderCustomLangTag(lang) {
        const tag = document.createElement("span");
        tag.className = "lang-tag";
        tag.innerHTML = `${lang.toUpperCase()} <button type="button" title="Видалити">&times;</button>`;
        tag.querySelector("button").addEventListener("click", () => {
            customLanguages = customLanguages.filter(l => l !== lang);
            tag.remove();
        });
        customLangContainer.appendChild(tag);
    }

    addCustomLangBtn.addEventListener("click", () => {
        const val = customLangInput.value.trim().toLowerCase();
        if (val && !customLanguages.includes(val) && !document.querySelector(`.lang-cb[value="${val}"]`)) {
            customLanguages.push(val);
            renderCustomLangTag(val);
            customLangInput.value = "";
        }
    });

    function getLogLanguages() {
        const checked = [];
        document.querySelectorAll(".lang-cb:checked").forEach(cb => checked.push(cb.value));
        return [...checked, ...customLanguages];
    }

    // ─── Presets ──────────────────────────────────────────────────────
    const PRESETS = {
        simple: {
            "guard-mode": true, "action": "decline",
            "check-ip": true, "check-avatar": true, "avatar-min-count": 1,
            "check-fingerprint": true, "check-account-age": true, "min-account-age-months": 3,
            "check-cas": true, "cas-action": "block",
            "check-device": false, "check-premium": false, "check-language": false,
            "check-osint": false, "osint-action": "log",
            "check-ban-commands": true, "passive-ban-monitoring": true, "check-global-spammer-db": false
        },
        balanced: {
            "guard-mode": true, "action": "decline",
            "check-ip": true, "check-avatar": true, "avatar-min-count": 1,
            "check-fingerprint": true, "check-account-age": true, "min-account-age-months": 3,
            "check-cas": true, "cas-action": "block",
            "check-device": false, "check-premium": false, "check-language": false,
            "check-osint": false, "osint-action": "log",
            "check-ban-commands": true, "passive-ban-monitoring": true, "check-global-spammer-db": false
        },
        strict: {
            "guard-mode": true, "action": "decline",
            "check-ip": true, "check-avatar": true, "avatar-min-count": 1,
            "check-fingerprint": true, "check-account-age": true, "min-account-age-months": 6,
            "check-cas": true, "cas-action": "block",
            "check-device": true, "check-premium": true, "check-language": true,
            "check-osint": false, "osint-action": "log",
            "check-ban-commands": true, "passive-ban-monitoring": true, "check-global-spammer-db": true
        },
        ultra: {
            "guard-mode": true, "action": "ban",
            "check-ip": true, "check-avatar": true, "avatar-min-count": 2,
            "check-fingerprint": true, "check-account-age": true, "min-account-age-months": 12,
            "check-cas": true, "cas-action": "block",
            "check-device": true, "check-premium": true, "check-language": true,
            "check-osint": true, "osint-action": "block",
            "check-ban-commands": true, "passive-ban-monitoring": true, "check-global-spammer-db": true
        }
    };

    function applyPreset(name) {
        const p = PRESETS[name];
        if (!p) return;
        Object.keys(p).forEach(key => {
            const el = document.getElementById(key);
            if (!el) return;
            if (el.type === "checkbox") el.checked = p[key];
            else el.value = p[key];
        });
    }

    const presetSelect = document.getElementById("preset");
    let currentPreset = "balanced";
    presetSelect.addEventListener("change", () => {
        currentPreset = presetSelect.value;
        applyPreset(presetSelect.value);
    });

    const trackedIds = [
        "action", "guard-mode", "check-ip", "check-device", "check-avatar",
        "avatar-min-count", "check-premium", "check-language", "check-fingerprint",
        "check-account-age", "min-account-age-months", "check-cas", "cas-action",
        "check-global-spammer-db", "check-ban-commands", "passive-ban-monitoring",
        "check-osint", "osint-action", "questions-count"
    ];
    trackedIds.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("change", () => { if (currentPreset !== "custom") { currentPreset = "custom"; presetSelect.value = "custom"; } });
        el.addEventListener("input",  () => { if (currentPreset !== "custom") { currentPreset = "custom"; presetSelect.value = "custom"; } });
    });

    // ─── Default questions (mirror of config.py) ───────────────────────
    const DEFAULT_QUESTIONS = [
        {type:"emoji", q:"Де паляниця? 🧐", correct:"🫓", distractors:["🍓","🍓","🍓","🍓","🍓","🍓","🍓","🍓"]},
        {type:"choice", q:"Чий Крим?", a:["український","україна","україни"], choices:["Україна","Росія","Нічий","Спірний"]},
        {type:"choice", q:"Батько наш - ...?", a:["бандера"], choices:["Бандера","Шевченко","Франко","Мазепа"]},
        {type:"text", q:"Україна - це ...?", a:["європа","понад усе"]},
        {type:"choice", q:"Столиця України?", a:["київ","kyiv"], choices:["Київ","Москва","Мінськ","Варшава"]},
        {type:"text", q:"Якою мовою розмовляють в Україні?", a:["українською","українська"]},
        {type:"emoji", q:"Яка тварина символ України? 🐺", correct:"🐺", distractors:["🦊","🐻","🐗","🦌","🦅","🐱","🐶","🐰"]},
        {type:"choice", q:"Якого кольору прапор України?", a:["синьо-жовтий","синій і жовтий","blue and yellow","жовто-блакитний"], choices:["Синьо-жовтий","Червоно-чорний","Біло-червоний","Зелено-жовтий"]}
    ];

    // ─── Load settings ────────────────────────────────────────────────
    function loadSettings(cid) {
        fetch(`/api/settings?chat_id=${cid}`)
            .then(r => r.json())
            .then(data => {
                document.getElementById("action").value = data.action || "decline";
                document.getElementById("guard-mode").checked = data.guard_mode !== false;
                document.getElementById("check-ip").checked = data.check_ip;
                document.getElementById("check-device").checked = data.check_device;
                document.getElementById("check-avatar").checked = data.check_avatar;
                document.getElementById("avatar-min-count").value = data.avatar_min_count ?? 1;
                document.getElementById("check-premium").checked = data.check_premium !== false;
                document.getElementById("check-language").checked = data.check_language !== false;
                document.getElementById("check-fingerprint").checked = data.check_fingerprint !== false;
                document.getElementById("check-account-age").checked = data.check_account_age !== false;
                document.getElementById("min-account-age-months").value = data.min_account_age_months ?? 3;
                document.getElementById("check-cas").checked = data.check_cas === true;
                document.getElementById("cas-action").value = data.cas_action || "block";
                document.getElementById("check-global-spammer-db").checked = data.check_global_spammer_db === true;
                document.getElementById("check-ban-commands").checked = data.check_ban_commands !== false;
                document.getElementById("passive-ban-monitoring").checked = data.passive_ban_monitoring !== false;
                document.getElementById("check-osint").checked = data.check_osint === true;
                document.getElementById("osint-action").value = data.osint_action || "log";
                document.getElementById("questions-count").value = data.questions_count ?? 1;
                document.getElementById("log-channel").value = data.log_channel || "";
                document.getElementById("contact-link").value = data.contact_link || "";
                document.getElementById("decline-msg-captcha").value = data.decline_msg_captcha || "";
                document.getElementById("decline-msg-twink").value = data.decline_msg_twink || "";

                // Language checkboxes
                const logLangs = data.log_languages || [];
                document.querySelectorAll(".lang-cb").forEach(cb => { cb.checked = logLangs.includes(cb.value); });
                customLanguages = logLangs.filter(l => !document.querySelector(`.lang-cb[value="${l}"]`));
                customLangContainer.innerHTML = "";
                customLanguages.forEach(l => renderCustomLangTag(l));

                // Questions — if empty, copy defaults
                questionsList.innerHTML = "";
                let questions = data.questions || [];
                let needsSave = false;

                if (questions.length === 0) {
                    questions = DEFAULT_QUESTIONS;
                    needsSave = true; // will auto-save defaults to DB on first "save"
                    const notice = document.createElement("div");
                    notice.style.cssText = "font-size:12px; color:#fbbf24; margin-bottom:10px; padding:8px 12px; background:rgba(251,191,36,0.1); border:1px solid rgba(251,191,36,0.3); border-radius:6px;";
                    notice.textContent = "⚠️ Питань у базі не знайдено — завантажено стандартні. Збережіть щоб зафіксувати.";
                    questionsList.parentElement.insertBefore(notice, questionsList);
                }

                questions.forEach(q => renderQuestionItem(q));
            });
    }

    // ─── Render question items (with all fields editable) ────────────
    function renderQuestionItem(q = null) {
        const type = q ? q.type || "text" : null;
        if (!q) {
            // called by add-button — will be overridden
        }
        if (type === "emoji") {
            renderEmojiQuestion(q.q, q.correct, (q.distractors || []).join(", "));
        } else if (type === "choice") {
            renderChoiceQuestion(q.q, (q.a || []).join(", "), (q.choices || []).join(", "));
        } else {
            renderTextQuestion(q ? q.q : "", q ? (q.a || []).join(", ") : "");
        }
    }

    function makeRemoveBtn() {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-danger btn-sm";
        btn.textContent = "Видалити";
        return btn;
    }

    function renderTextQuestion(questionText = "", answersText = "") {
        const item = document.createElement("div");
        item.className = "question-item";
        item.dataset.type = "text";
        item.innerHTML = `
            <div class="question-item-header">
                <span class="question-badge">📝 Текстове</span>
            </div>
            <div class="question-field">
                <label>Запитання</label>
                <input type="text" class="q-text" placeholder="напр. Чий Крим?" value="${esc(questionText)}">
            </div>
            <div class="question-field">
                <label>Правильні відповіді (через кому)</label>
                <input type="text" class="q-ans" placeholder="напр. України, український" value="${esc(answersText)}">
            </div>
        `;
        const rm = makeRemoveBtn();
        rm.addEventListener("click", () => item.remove());
        item.appendChild(rm);
        questionsList.appendChild(item);
    }

    function renderChoiceQuestion(questionText = "", answersText = "", choicesText = "") {
        const item = document.createElement("div");
        item.className = "question-item";
        item.dataset.type = "choice";
        item.innerHTML = `
            <div class="question-item-header">
                <span class="question-badge choice">📋 З вибором</span>
            </div>
            <div class="question-field">
                <label>Запитання</label>
                <input type="text" class="q-text" placeholder="напр. Чий Крим?" value="${esc(questionText)}">
            </div>
            <div class="question-field">
                <label>Правильні відповіді (через кому)</label>
                <input type="text" class="q-ans" placeholder="напр. Україна, українська" value="${esc(answersText)}">
            </div>
            <div class="question-field">
                <label>Варіанти вибору (через кому, мін. 2)</label>
                <input type="text" class="q-choices" placeholder="напр. Україна, Росія, Нічий, Спірний" value="${esc(choicesText)}">
            </div>
        `;
        const rm = makeRemoveBtn();
        rm.addEventListener("click", () => item.remove());
        item.appendChild(rm);
        questionsList.appendChild(item);
    }

    function renderEmojiQuestion(questionText = "", correctEmoji = "", distractorsText = "") {
        const item = document.createElement("div");
        item.className = "question-item";
        item.dataset.type = "emoji";
        item.innerHTML = `
            <div class="question-item-header">
                <span class="question-badge emoji">🎯 Emoji</span>
            </div>
            <div class="question-field">
                <label>Текст питання</label>
                <input type="text" class="q-text" placeholder="напр. Де паляниця? 🧐" value="${esc(questionText)}">
            </div>
            <div class="question-field">
                <label>Правильне емодзі</label>
                <input type="text" class="q-correct" placeholder="напр. 🫓" value="${esc(correctEmoji)}" style="width:120px;">
            </div>
            <div class="question-field">
                <label>Відволікаючі емодзі (через кому)</label>
                <input type="text" class="q-distractors" placeholder="напр. 🍓, 🍕, 🍔, 🌮" value="${esc(distractorsText)}">
            </div>
        `;
        const rm = makeRemoveBtn();
        rm.addEventListener("click", () => item.remove());
        item.appendChild(rm);
        questionsList.appendChild(item);
    }

    function esc(str) {
        return String(str).replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    document.getElementById("add-question").addEventListener("click", () => renderTextQuestion());
    document.getElementById("add-choice-question").addEventListener("click", () => renderChoiceQuestion());
    document.getElementById("add-emoji-question").addEventListener("click", () => renderEmojiQuestion());

    // ─── Submit ───────────────────────────────────────────────────────
    form.addEventListener("submit", (e) => {
        e.preventDefault();

        const questions = [];
        questionsList.querySelectorAll(".question-item").forEach(item => {
            const q = item.querySelector(".q-text").value.trim();
            if (!q) return;
            if (item.dataset.type === "emoji") {
                const correct = item.querySelector(".q-correct")?.value.trim();
                const distractors = (item.querySelector(".q-distractors")?.value || "")
                    .split(",").map(s => s.trim()).filter(Boolean);
                if (correct) questions.push({ type: "emoji", q, correct, distractors });
            } else if (item.dataset.type === "choice") {
                const aRaw = (item.querySelector(".q-ans")?.value || "").split(",").map(s => s.trim()).filter(Boolean);
                const choices = (item.querySelector(".q-choices")?.value || "").split(",").map(s => s.trim()).filter(Boolean);
                if (aRaw.length && choices.length >= 2) questions.push({ type: "choice", q, a: aRaw, choices });
            } else {
                const a = (item.querySelector(".q-ans")?.value || "").split(",").map(s => s.trim()).filter(Boolean);
                if (a.length) questions.push({ q, a });
            }
        });

        const settings = {
            action: document.getElementById("action").value,
            guard_mode: document.getElementById("guard-mode").checked,
            check_ip: document.getElementById("check-ip").checked,
            check_device: document.getElementById("check-device").checked,
            check_avatar: document.getElementById("check-avatar").checked,
            avatar_min_count: parseInt(document.getElementById("avatar-min-count").value, 10),
            check_premium: document.getElementById("check-premium").checked,
            check_language: document.getElementById("check-language").checked,
            log_languages: getLogLanguages(),
            check_fingerprint: document.getElementById("check-fingerprint").checked,
            check_account_age: document.getElementById("check-account-age").checked,
            min_account_age_months: parseInt(document.getElementById("min-account-age-months").value, 10),
            check_cas: document.getElementById("check-cas").checked,
            cas_action: document.getElementById("cas-action").value,
            check_global_spammer_db: document.getElementById("check-global-spammer-db").checked,
            check_ban_commands: document.getElementById("check-ban-commands").checked,
            passive_ban_monitoring: document.getElementById("passive-ban-monitoring").checked,
            check_osint: document.getElementById("check-osint").checked,
            osint_action: document.getElementById("osint-action").value,
            questions_count: parseInt(document.getElementById("questions-count").value, 10),
            log_channel: document.getElementById("log-channel").value.trim(),
            contact_link: document.getElementById("contact-link").value.trim(),
            decline_msg_captcha: document.getElementById("decline-msg-captcha").value.trim(),
            decline_msg_twink: document.getElementById("decline-msg-twink").value.trim(),
            questions
        };

        const saveBtn = form.querySelector("[type=submit]");
        saveBtn.disabled = true;
        saveBtn.textContent = "Збереження…";

        fetch(`/api/settings?chat_id=${activeChatId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settings)
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                saveBtn.textContent = "✅ Збережено!";
                saveBtn.style.background = "#22c55e";
                setTimeout(() => tg.close(), 900);
            } else {
                alert("Помилка збереження налаштувань.");
                saveBtn.disabled = false;
                saveBtn.textContent = "💾 Зберегти налаштування";
            }
        })
        .catch(() => {
            alert("Помилка підключення до сервера.");
            saveBtn.disabled = false;
            saveBtn.textContent = "💾 Зберегти налаштування";
        });
    });
});