const kpiGrid = document.getElementById("kpiGrid");
const chartsGrid = document.getElementById("chartsGrid");
const insightsList = document.getElementById("insightsList");
const aiSummary = document.getElementById("aiSummary");
const summaryEmpty = document.getElementById("summaryEmpty");
const insightsEmpty = document.getElementById("insightsEmpty");
const insightsModeTag = document.getElementById("insightsModeTag");
const chatWindow = document.getElementById("chatWindow");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatTyping = document.getElementById("chatTyping");
const roleSelect = document.getElementById("roleSelect");
const uploadForm = document.getElementById("uploadForm");
const datasetFile = document.getElementById("datasetFile");
const dropzone = document.getElementById("dropzone");
const selectedFileName = document.getElementById("selectedFileName");
const uploadSubmitBtn = document.getElementById("uploadSubmitBtn");
const urlForm = document.getElementById("urlForm");
const datasetUrl = document.getElementById("datasetUrl");
const runIngestionBtn = document.getElementById("runIngestionBtn");
const dataStatus = document.getElementById("dataStatus");
const statRecords = document.getElementById("statRecords");
const statColumns = document.getElementById("statColumns");
const statMode = document.getElementById("statMode");
const datasetBadge = document.getElementById("datasetBadge");
const datasetBadgeText = document.getElementById("datasetBadgeText");
const dashboardDesc = document.getElementById("dashboardDesc");
const blueprintEditor = document.getElementById("blueprintEditor");
const loadBlueprintBtn = document.getElementById("loadBlueprintBtn");
const saveBlueprintBtn = document.getElementById("saveBlueprintBtn");
const refreshDashboardBtn = document.getElementById("refreshDashboardBtn");
const refreshInsightsBtn = document.getElementById("refreshInsightsBtn");
const clearChatBtn = document.getElementById("clearChatBtn");
const promptChips = document.getElementById("promptChips");
const tabButtons = document.querySelectorAll(".tab-link");
const tabPanels = document.querySelectorAll(".tab-panel");
const chartInstances = new Map();
let sessionId = null;
let chatWelcomed = false;

const TAB_IDS = ["dashboard", "data", "insights", "assistant"];
const KPI_MAX = 8;
const CHART_PALETTE = [
    { border: "#8b5cf6", bg: "rgba(139, 92, 246, 0.35)" },
    { border: "#06b6d4", bg: "rgba(6, 182, 212, 0.35)" },
    { border: "#22c55e", bg: "rgba(34, 197, 94, 0.35)" },
    { border: "#f59e0b", bg: "rgba(245, 158, 11, 0.35)" },
    { border: "#ec4899", bg: "rgba(236, 72, 153, 0.35)" },
    { border: "#6366f1", bg: "rgba(99, 102, 241, 0.35)" },
];
const DOUGHNUT_COLORS = ["#8b5cf6", "#06b6d4", "#22c55e", "#f59e0b", "#ec4899", "#6366f1"];
const INSIGHT_ICONS = { info: "💡", warning: "⚠️", success: "✅" };

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return decodeURIComponent(parts.pop().split(";").shift());
    }
    return "";
}

function apiFetch(url, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = { ...(options.headers || {}) };
    if (method !== "GET" && method !== "HEAD") {
        const csrfToken = getCookie("csrftoken");
        if (csrfToken) {
            headers["X-CSRFToken"] = csrfToken;
        }
    }
    return fetch(url, { ...options, headers });
}

function switchTab(tabId) {
    if (!TAB_IDS.includes(tabId)) return;

    tabButtons.forEach((btn) => {
        const isActive = btn.dataset.tab === tabId;
        btn.classList.toggle("active", isActive);
        btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    tabPanels.forEach((panel) => {
        const isActive = panel.id === `tab-${tabId}`;
        panel.classList.toggle("active", isActive);
    });

    if (tabId === "dashboard" && chartInstances.size) {
        requestAnimationFrame(() => {
            chartInstances.forEach((instance) => instance.resize());
        });
    }

    if (tabId === "assistant" && !chatWelcomed) {
        chatWelcomed = true;
        addMessage("bot", "Ask me about your metrics, trends, or optimization ideas.", "Assistant");
    }

    history.replaceState(null, "", `#${tabId}`);
}

function money(value) {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
    }).format(value);
}

function setDataStatus(message, type = "info") {
    if (!dataStatus) return;
    if (!message) {
        dataStatus.hidden = true;
        dataStatus.textContent = "";
        dataStatus.className = "status-banner";
        return;
    }
    dataStatus.hidden = false;
    dataStatus.textContent = message;
    dataStatus.className = `status-banner ${type}`;
}

function updateDatasetMeta(data) {
    const records = data?.records ?? 0;
    const columns = data?.columns?.length ?? 0;
    const mode = data?.dataset_mode || "generic";
    const importMeta = data?.import_meta || {};

    if (statRecords) statRecords.textContent = records ? records.toLocaleString() : "—";
    if (statColumns) statColumns.textContent = columns || "—";
    if (statMode) {
        let modeLabel = mode === "ads" ? "Ads Analytics" : "Generic";
        if (importMeta.strategy === "merged" && importMeta.sheets_used?.length) {
            modeLabel += ` · ${importMeta.sheets_used.length} sheets`;
        } else if (importMeta.sheets_used?.length) {
            modeLabel += ` · ${importMeta.sheets_used[0]}`;
        }
        statMode.textContent = modeLabel;
    }

    if (datasetBadge && datasetBadgeText) {
        if (records > 0) {
            datasetBadge.hidden = false;
            datasetBadgeText.textContent = `${records.toLocaleString()} rows · ${mode} mode`;
        } else {
            datasetBadge.hidden = true;
        }
    }

    if (dashboardDesc) {
        dashboardDesc.textContent =
            records > 0
                ? `Analyzing ${records.toLocaleString()} records across ${columns} fields.`
                : "Key metrics and visual analysis from your active dataset.";
    }

    if (insightsModeTag) {
        insightsModeTag.textContent = mode === "ads" ? "Ads dataset" : "Generic dataset";
    }
}

function setChatLoading(isLoading) {
    if (chatTyping) chatTyping.hidden = !isLoading;
    if (chatInput) chatInput.disabled = isLoading;
    if (chatForm) {
        const submitBtn = chatForm.querySelector("button[type='submit']");
        if (submitBtn) submitBtn.disabled = isLoading;
    }
}

function addMessage(type, text, label = "") {
    const isNearBottom =
        chatWindow.scrollHeight - chatWindow.scrollTop - chatWindow.clientHeight < 48;

    const row = document.createElement("div");
    row.className = `msg-row ${type}`;

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = type === "user" ? "You" : "AI";

    const item = document.createElement("div");
    item.className = `msg ${type}`;

    if (type === "bot" && label) {
        const meta = document.createElement("span");
        meta.className = "msg-meta";
        meta.textContent = label;
        item.appendChild(meta);
    }

    if (type === "bot" && window.marked && window.DOMPurify) {
        const body = document.createElement("div");
        body.innerHTML = DOMPurify.sanitize(
            marked.parse(text, { breaks: true, gfm: true })
        );
        item.appendChild(body);
    } else {
        const body = document.createElement("div");
        body.textContent = text;
        item.appendChild(body);
    }

    row.appendChild(avatar);
    row.appendChild(item);
    chatWindow.appendChild(row);

    if (isNearBottom || type === "user") {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }
}

function formatKpiValue(card) {
    const value = card.value;
    if (typeof value !== "number") return value;
    if (card.format === "percent") {
        const normalized = value <= 1 ? value * 100 : value;
        return `${normalized.toFixed(2)}%`;
    }
    if (card.format === "currency") {
        return value > 999 ? money(value) : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
    if (card.format === "decimal") {
        return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
    return value.toLocaleString();
}

function filterKpiCardsForRole(cards, widgets) {
    if (!Array.isArray(cards) || !cards.length) return cards;
    if (!Array.isArray(widgets) || !widgets.length) return cards;
    const nonKpi = new Set(["trend_summary", "top_channels", "campaign_actions"]);
    const widgetKeys = new Set(widgets.filter((key) => !nonKpi.has(key)));
    if (!widgetKeys.size) return cards;
    const filtered = cards.filter((card) => widgetKeys.has(card.key));
    return filtered.length ? filtered : cards;
}

function normalizeKpiCards(data) {
    let cards;
    if (Array.isArray(data.kpi_cards) && data.kpi_cards.length) {
        cards = data.kpi_cards.slice(0, KPI_MAX);
    } else {
        cards = Object.entries(data.kpis || {})
            .map(([key, value]) => ({
                key,
                label: key.replaceAll("_", " ").replace(/\b\w/g, (ch) => ch.toUpperCase()),
                value,
                format:
                    key.includes("rate") || key.includes("ratio")
                        ? "percent"
                        : key.includes("revenue") || key.includes("sales") || key.includes("spend") || key.includes("profit")
                          ? "currency"
                          : "number",
            }))
            .slice(0, KPI_MAX);
    }
    return filterKpiCardsForRole(cards, data.widgets);
}

function renderKpis(data) {
    const cards = normalizeKpiCards(data);
    if (!cards.length) {
        kpiGrid.innerHTML = `<article class="kpi-card"><div class="label">Status</div><div class="value">No data</div></article>`;
        return;
    }
    kpiGrid.innerHTML = cards
        .map(
            (card) =>
                `<article class="kpi-card"><div class="label">${card.label}</div><div class="value">${formatKpiValue(card)}</div></article>`
        )
        .join("");
}

function destroyCharts() {
    chartInstances.forEach((instance) => instance.destroy());
    chartInstances.clear();
}

function buildChartConfig(chartDef, colorIndex) {
    const spec = chartDef.spec || {};
    const xKey = spec.x_key;
    const yKey = spec.y_key;
    const labels = (chartDef.data || []).map((row) => row[xKey]);
    const values = (chartDef.data || []).map((row) => row[yKey]);
    const palette = CHART_PALETTE[colorIndex % CHART_PALETTE.length];

    if (chartDef.type === "doughnut") {
        return {
            type: "doughnut",
            data: {
                labels,
                datasets: [{
                    label: spec.y_label || yKey,
                    data: values,
                    backgroundColor: labels.map((_, idx) => DOUGHNUT_COLORS[idx % DOUGHNUT_COLORS.length]),
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: {
                    legend: { position: "bottom", labels: { color: "#94a3b8", boxWidth: 12 } },
                },
            },
        };
    }

    if (chartDef.type === "bar") {
        return {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: spec.y_label || yKey,
                    data: values,
                    backgroundColor: palette.bg,
                    borderColor: palette.border,
                    borderWidth: 1,
                    borderRadius: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: "#94a3b8", maxRotation: 45, minRotation: 0 } },
                    y: { ticks: { color: "#94a3b8" } },
                },
            },
        };
    }

    return {
        type: "line",
        data: {
            labels,
            datasets: [{
                label: spec.y_label || yKey,
                data: values,
                borderColor: palette.border,
                backgroundColor: palette.bg,
                fill: true,
                tension: 0.3,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: "#94a3b8", maxRotation: 45, minRotation: 0 } },
                y: { ticks: { color: "#94a3b8" } },
            },
        },
    };
}

function renderCharts(charts) {
    destroyCharts();
    const chartList = Array.isArray(charts) ? charts : [];

    if (!chartList.length) {
        chartsGrid.innerHTML = `<div class="charts-empty">Upload a dataset in the <strong>Data Upload</strong> tab to generate analysis charts.</div>`;
        return;
    }

    chartsGrid.innerHTML = chartList
        .map(
            (chartDef, index) => `
        <article class="panel chart-panel">
            <div class="panel-head">
                <h3>${chartDef.title || "Analysis Chart"}</h3>
                <span class="panel-note">${chartDef.subtitle || ""}</span>
            </div>
            <div class="chart-wrap">
                <canvas id="chart-${index}"></canvas>
            </div>
        </article>`
        )
        .join("");

    chartList.forEach((chartDef, index) => {
        const spec = chartDef.spec || {};
        if (!spec.x_key || !spec.y_key || !chartDef.data?.length) return;
        const canvas = document.getElementById(`chart-${index}`);
        if (!canvas) return;
        chartInstances.set(`chart-${index}`, new Chart(canvas, buildChartConfig(chartDef, index)));
    });
}

function renderInsights(insights) {
    const items = insights || [];
    if (insightsEmpty) insightsEmpty.hidden = items.length > 0;
    if (!items.length) {
        insightsList.innerHTML = "";
        return;
    }

    insightsList.innerHTML = items
        .map((insight) => {
            const severity = insight.severity || "info";
            const icon = INSIGHT_ICONS[severity] || INSIGHT_ICONS.info;
            return `
        <article class="insight-item ${severity}">
            <div class="insight-icon" aria-hidden="true">${icon}</div>
            <div class="insight-body">
                <h3>${insight.headline}</h3>
                <p>${insight.detail}</p>
            </div>
        </article>`;
        })
        .join("");
}

function renderAiSummary(summaryText) {
    const hasSummary = Boolean(summaryText?.trim());
    if (summaryEmpty) summaryEmpty.hidden = hasSummary;
    if (!aiSummary) return;

    if (!hasSummary) {
        aiSummary.innerHTML = "";
        return;
    }

    if (window.marked && window.DOMPurify) {
        aiSummary.innerHTML = DOMPurify.sanitize(marked.parse(summaryText, { breaks: true, gfm: true }));
    } else {
        aiSummary.textContent = summaryText;
    }
}

function renderTrendChart(trends, trendSpec) {
    if (Array.isArray(trends) && trends.length && trendSpec?.x_key && trendSpec?.y_key) {
        renderCharts([{
            id: "legacy-trend",
            title: trendSpec.y_label || "Trend",
            subtitle: "Performance over time",
            type: "line",
            data: trends,
            spec: trendSpec,
        }]);
    } else {
        renderCharts([]);
    }
}

function applyDashboardData(data) {
    updateDatasetMeta(data);
    renderKpis(data);
    renderCharts(data.charts);
    renderAiSummary(data.ai_summary);
    renderInsights(data.ai_insights);
    if (!data.charts?.length) {
        renderTrendChart(data.trends, data.trend_spec);
    }
}

async function loadDashboard() {
    try {
        const role = roleSelect?.value || "team_member";
        const response = await apiFetch(`/api/analytics/summary/?role=${encodeURIComponent(role)}`);
        if (!response.ok) throw new Error(`Summary API failed (${response.status})`);
        const data = await response.json();
        applyDashboardData(data);
    } catch (error) {
        setDataStatus(`Could not refresh analytics: ${error.message}`, "error");
        if (document.getElementById("tab-assistant")?.classList.contains("active")) {
            addMessage("bot", `Unable to load analytics data: ${error.message}`, "System");
        }
    }
}

async function loadBlueprint() {
    const response = await apiFetch("/api/dashboard/blueprint/");
    const data = await response.json();
    if (!response.ok) {
        setDataStatus(data.detail || "Unable to load blueprint.", "error");
        return;
    }
    blueprintEditor.value = JSON.stringify(data.effective_blueprint || {}, null, 2);
}

function updateSelectedFileName(file) {
    if (!selectedFileName) return;
    selectedFileName.textContent = file ? file.name : "No file selected";
}

function setUploadLoading(isLoading) {
    if (uploadSubmitBtn) uploadSubmitBtn.disabled = isLoading;
    if (uploadSubmitBtn) uploadSubmitBtn.textContent = isLoading ? "Uploading…" : "Upload Dataset";
}

// Drag & drop
dropzone?.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("dragover");
});

dropzone?.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
});

dropzone?.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragover");
    const file = event.dataTransfer?.files?.[0];
    if (!file || !datasetFile) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    datasetFile.files = transfer.files;
    updateSelectedFileName(file);
});

datasetFile?.addEventListener("change", () => {
    updateSelectedFileName(datasetFile.files?.[0] || null);
});

roleSelect?.addEventListener("change", () => {
    sessionId = null;
    chatWelcomed = false;
    chatWindow.innerHTML = "";
    loadDashboard();
});

tabButtons.forEach((btn) => {
    btn.addEventListener("click", (event) => {
        event.preventDefault();
        switchTab(btn.dataset.tab);
    });
});

refreshDashboardBtn?.addEventListener("click", loadDashboard);
refreshInsightsBtn?.addEventListener("click", loadDashboard);

clearChatBtn?.addEventListener("click", () => {
    sessionId = null;
    chatWelcomed = false;
    chatWindow.innerHTML = "";
    chatWelcomed = true;
    addMessage("bot", "Chat cleared. What would you like to explore?", "Assistant");
});

promptChips?.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip?.dataset.prompt || !chatInput) return;
    chatInput.value = chip.dataset.prompt;
    chatInput.focus();
});

loadBlueprintBtn?.addEventListener("click", async () => {
    await loadBlueprint();
    setDataStatus("Blueprint loaded from server.", "success");
});

saveBlueprintBtn?.addEventListener("click", async () => {
    let parsed;
    try {
        parsed = JSON.parse(blueprintEditor.value || "{}");
    } catch {
        setDataStatus("Blueprint JSON is invalid. Check brackets and quotes.", "error");
        return;
    }
    const response = await apiFetch("/api/dashboard/blueprint/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blueprint: parsed }),
    });
    const data = await response.json();
    if (!response.ok) {
        setDataStatus(data.detail || "Unable to save blueprint.", "error");
        return;
    }
    setDataStatus(data.detail || "Blueprint saved. Dashboard will refresh.", "success");
    loadDashboard();
});

uploadForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!datasetFile?.files?.length) {
        setDataStatus("Please choose a CSV or Excel file first.", "error");
        return;
    }
    const formData = new FormData();
    formData.append("file", datasetFile.files[0]);
    setUploadLoading(true);
    setDataStatus("Uploading and analyzing dataset…", "info");
    try {
        const response = await apiFetch("/api/data/upload/", { method: "POST", body: formData });
        const data = await response.json();
        if (!response.ok) {
            setDataStatus(data.detail || "Upload failed.", "error");
            return;
        }
        setDataStatus(data.detail || `Dataset activated — ${data.rows?.toLocaleString()} rows · ${data.dataset_mode} mode`, "success");
        await loadDashboard();
        switchTab("dashboard");
    } catch (error) {
        setDataStatus(`Upload failed: ${error.message}`, "error");
    } finally {
        setUploadLoading(false);
    }
});

urlForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const url = datasetUrl.value.trim();
    if (!url) {
        setDataStatus("Please enter a public dataset URL.", "error");
        return;
    }
    setDataStatus("Fetching dataset from URL…", "info");
    try {
        const response = await apiFetch("/api/data/upload-link/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });
        const data = await response.json();
        if (!response.ok) {
            setDataStatus(data.detail || "URL ingestion failed.", "error");
            return;
        }
        setDataStatus(data.detail || `URL ingested — ${data.rows?.toLocaleString()} rows · ${data.dataset_mode} mode`, "success");
        await loadDashboard();
        switchTab("dashboard");
    } catch (error) {
        setDataStatus(`URL ingestion failed: ${error.message}`, "error");
    }
});

runIngestionBtn?.addEventListener("click", async () => {
    setDataStatus("Running ingestion sync job…", "info");
    try {
        const response = await apiFetch("/api/ingestion/run/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ source: "dashboard_manual" }),
        });
        const data = await response.json();
        if (!response.ok) {
            setDataStatus(data.detail || "Ingestion failed.", "error");
            return;
        }
        setDataStatus(`Sync complete — ${data.records?.toLocaleString()} records processed`, "success");
        loadDashboard();
    } catch (error) {
        setDataStatus(`Ingestion failed: ${error.message}`, "error");
    }
});

chatForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    addMessage("user", message);
    chatInput.value = "";
    setChatLoading(true);

    try {
        const response = await apiFetch("/api/chat/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                role: roleSelect?.value || "team_member",
                session_id: sessionId,
            }),
        });
        if (!response.ok) throw new Error(`Chat API failed (${response.status})`);
        const data = await response.json();
        sessionId = data.session_id;
        const sourceTag = data.powered_by_nvidia ? "NVIDIA" : "Fallback";
        addMessage("bot", data.reply, `${sourceTag} · ${data.role}`);
    } catch (error) {
        addMessage("bot", `Assistant request failed: ${error.message}`, "System");
    } finally {
        setChatLoading(false);
    }
});

function initApp() {
    const initialTab = TAB_IDS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "dashboard";
    switchTab(initialTab);
    loadDashboard();
    loadBlueprint();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
} else {
    initApp();
}
