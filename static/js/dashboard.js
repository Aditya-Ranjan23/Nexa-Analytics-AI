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
const deactivateDatasetBtn = document.getElementById("deactivateDatasetBtn");
const libraryList = document.getElementById("libraryList");
const chartInstances = new Map();
let sessionId = null;
let chatWelcomed = false;
let activeDatasetId = null;
let activeDatasetSource = null;
let activeDatasetVersion = 1;

// Versioning and Modal DOM Elements
let activeModalDatasetId = null;
const versionsModal = document.getElementById("versionsModal");
const versionsModalTitle = document.getElementById("versionsModalTitle");
const versionsTableBody = document.getElementById("versionsTableBody");
const closeVersionsModalBtn = document.getElementById("closeVersionsModalBtn");
const versionUploadForm = document.getElementById("versionUploadForm");
const versionFileInput = document.getElementById("versionFileInput");
const versionFileSelectBtn = document.getElementById("versionFileSelectBtn");
const versionFileName = document.getElementById("versionFileName");
const versionUrlForm = document.getElementById("versionUrlForm");
const versionUrlInput = document.getElementById("versionUrlInput");
const versionUploadStatus = document.getElementById("versionUploadStatus");
const compareBtn = document.getElementById("compareBtn");
const compareResultsSection = document.getElementById("compareResultsSection");
const closeCompareBtn = document.getElementById("closeCompareBtn");
const compareV1Num = document.getElementById("compareV1Num");
const compareV1Rows = document.getElementById("compareV1Rows");
const compareV2Num = document.getElementById("compareV2Num");
const compareV2Rows = document.getElementById("compareV2Rows");
const compareRowDiffVal = document.getElementById("compareRowDiffVal");
const compareAddedCount = document.getElementById("compareAddedCount");
const compareAddedCols = document.getElementById("compareAddedCols");
const compareRemovedCount = document.getElementById("compareRemovedCount");
const compareRemovedCols = document.getElementById("compareRemovedCols");
const compareStatsBody = document.getElementById("compareStatsBody");

const TAB_IDS = ["dashboard", "data", "insights", "assistant", "profile", "settings"];
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

    if (tabId === "data") {
        loadDatasetLibrary();
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

    activeDatasetId = data?.dataset_id || null;
    activeDatasetSource = data?.source_type || null;
    activeDatasetVersion = data?.active_version_number || 1;

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

    const heroActiveBadge = document.getElementById("heroActiveBadge");
    const heroActiveText = document.getElementById("heroActiveText");
    if (heroActiveBadge && heroActiveText) {
        if (records > 0) {
            heroActiveBadge.hidden = false;
            let label = `Active: ${data.dataset_name || "Dataset"} · v${data.dataset_version || 1} (${records.toLocaleString()} rows · ${mode} mode)`;
            if (data.last_sync_at) {
                const syncTime = new Date(data.last_sync_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                label += ` · Refreshed ${syncTime}`;
            }
            heroActiveText.textContent = label;
        } else {
            heroActiveBadge.hidden = true;
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
    return cards;
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

async function renderProactiveInsights(insights, data) {
    if (!insights) return;
    
    // 1. Render Top KPIs Row
    const kpiRow = document.getElementById("insightsKpiRow");
    if (kpiRow) {
        const topKpis = insights.top_kpis || [];
        if (topKpis.length === 0) {
            kpiRow.style.display = "none";
            kpiRow.innerHTML = "";
        } else {
            kpiRow.style.display = "grid";
            kpiRow.innerHTML = topKpis.map(k => {
                const label = k.metric.replaceAll("_", " ").replace(/\b\w/g, ch => ch.toUpperCase());
                let totalVal = k.total;
                let avgVal = k.average;
                
                let totalFormatted = "";
                if (k.format === "currency") {
                    totalFormatted = money(totalVal);
                } else if (k.format === "percent") {
                    totalFormatted = `${(totalVal <= 1 ? totalVal * 100 : totalVal).toFixed(1)}%`;
                } else {
                    totalFormatted = totalVal.toLocaleString(undefined, { maximumFractionDigits: 1 });
                }
                
                return `
                    <article class="kpi-card mini" style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); padding: 0.85rem; border-radius: 8px; display: flex; flex-direction: column; gap: 0.35rem;">
                        <span class="label" style="font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em;">Total ${label}</span>
                        <span class="value" style="font-size: 1.25rem; font-weight: 700; color: var(--accent);">${totalFormatted}</span>
                        <span class="sub" style="font-size: 0.7rem; color: var(--muted);">Avg: ${avgVal.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                    </article>
                `;
            }).join('');
        }
    }

    // 2. Render Data Quality Summary
    const dqSummary = document.getElementById("dataQualitySummary");
    if (dqSummary) {
        const dq = insights.data_quality || {};
        const scorePct = Math.round((dq.health_score || 0) * 100);
        let scoreClass = "success";
        if (dq.health_grade === "Warning") scoreClass = "danger";
        else if (dq.health_grade === "Fair") scoreClass = "warning";
        
        dqSummary.innerHTML = `
            <div style="background: rgba(255, 255, 255, 0.02); padding: 0.85rem; border-radius: 8px; display: flex; flex-direction: column; gap: 0.6rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 0.82rem; color: var(--muted);">Completeness Score</span>
                    <strong style="color: ${scoreClass === 'success' ? '#86efac' : scoreClass === 'warning' ? '#fde047' : '#fca5a5'}; font-size: 0.9rem;">${dq.health_grade} (${scorePct}%)</strong>
                </div>
                <div class="confidence-track" style="height: 6px; background: rgba(255, 255, 255, 0.08); border-radius: 4px; overflow: hidden;">
                    <div class="confidence-fill" style="width: ${scorePct}%; height: 100%; background: ${scoreClass === 'success' ? 'var(--accent)' : scoreClass === 'warning' ? '#f59e0b' : '#ef4899'}; border-radius: 4px;"></div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; font-size: 0.78rem; margin-top: 0.35rem; color: var(--muted);">
                    <div>
                        <div>Rows: <strong style="color: var(--text);">${dq.total_rows?.toLocaleString() || 0}</strong></div>
                        <div>Columns: <strong style="color: var(--text);">${dq.total_columns || 0}</strong></div>
                    </div>
                    <div>
                        <div>Missing Cells: <strong style="color: var(--text);">${dq.missing_cells?.toLocaleString() || 0}</strong></div>
                        <div>Duplicates: <strong style="color: var(--text);">${dq.duplicate_rows?.toLocaleString() || 0}</strong></div>
                    </div>
                </div>
            </div>
        `;
    }

    // 3. Render Business Highlights & Shifts
    const listShifts = document.getElementById("shiftsHighlightList");
    if (listShifts) {
        const highlights = insights.business_highlights || [];
        const changes = insights.largest_changes || [];
        const combined = [...highlights, ...changes];
        if (combined.length === 0) {
            listShifts.innerHTML = '<li class="empty-state" style="color: var(--muted); font-size: 0.88rem;">No key shifts or highlights identified in this data scope.</li>';
        } else {
            listShifts.innerHTML = combined.map(item => `
                <li style="line-height: 1.4; color: var(--text); margin-bottom: 0.25rem;">
                    ${item}
                </li>
            `).join('');
        }
    }

    // Narratives
    const narratives = insights.narratives || {};
    const txtExec = document.getElementById("narrativeExec");
    const txtMgt = document.getElementById("narrativeMgt");
    const txtOps = document.getElementById("narrativeOps");
    const txtRisk = document.getElementById("narrativeRisk");
    const txtOpp = document.getElementById("narrativeOpp");
    
    if (txtExec) txtExec.textContent = narratives.executive_summary || "No executive briefing generated.";
    if (txtMgt) txtMgt.textContent = narratives.management_summary || "No management focus points generated.";
    if (txtOps) txtOps.textContent = narratives.operational_summary || "No operational status generated.";
    if (txtRisk) txtRisk.textContent = narratives.risk_summary || "No critical risk flags detected.";
    if (txtOpp) txtOpp.textContent = narratives.opportunity_summary || "No growth opportunities calculated.";

    // Anomalies
    const listAnomalies = document.getElementById("anomaliesList");
    if (listAnomalies) {
        const items = insights.anomalies || [];
        if (items.length === 0) {
            listAnomalies.innerHTML = '<p class="empty-state" style="padding: 1rem 0; margin: 0; color: var(--muted); font-size: 0.88rem;">No anomalies or outliers detected in the active data series.</p>';
        } else {
            listAnomalies.innerHTML = items.map(a => {
                let icon = "💡";
                if (a.type === "missing_values") icon = "❓";
                else if (a.type === "duplicates") icon = "👥";
                else if (a.type === "drop") icon = "📉";
                else if (a.type === "spike") icon = "📈";
                else if (a.type === "outliers") icon = "🚨";
                
                const confPct = Math.round((a.confidence || 0) * 100);
                return `
                    <div class="anomaly-row ${a.type}">
                        <div class="anomaly-icon">${icon}</div>
                        <div class="anomaly-content">
                            <span class="anomaly-msg">${a.message}</span>
                            <div class="anomaly-meta">
                                <span>Confidence: ${confPct}%</span>
                                <div class="confidence-bar-wrap">
                                    <div class="confidence-track">
                                        <div class="confidence-fill" style="width: ${confPct}%;"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
    }

    // Root Cause Attribution
    const listAttribution = document.getElementById("attributionList");
    if (listAttribution) {
        const items = insights.contributors || [];
        if (items.length === 0) {
            listAttribution.innerHTML = '<p class="empty-state" style="padding: 1rem 0; margin: 0; color: var(--muted); font-size: 0.88rem;">No dimensional contribution attribution available.</p>';
        } else {
            listAttribution.innerHTML = items.map(c => `
                <div class="attribution-item">
                    <div class="attr-left">
                        <span class="attr-title">${c.category}</span>
                        <span class="attr-sub">Dimension: ${c.dimension}</span>
                    </div>
                    <div class="attr-right">
                        <span class="attr-share">${c.share_pct}%</span>
                        <span class="attr-sub">Share of ${c.metric}</span>
                    </div>
                </div>
            `).join('');
        }
    }

    // Recommendations
    const listRecs = document.getElementById("recommendationsList");
    if (listRecs) {
        const recs = narratives.recommendations || [];
        if (recs.length === 0) {
            listRecs.innerHTML = '<li class="empty-state" style="color: var(--muted); font-size: 0.88rem;">No business actions recommended for this dataset.</li>';
        } else {
            listRecs.innerHTML = recs.map(r => `<li>${r}</li>`).join('');
        }
    }

    // Suggested Questions
    const listQuestions = document.getElementById("suggestedQuestionsList");
    if (listQuestions) {
        const questions = narratives.suggested_questions || [];
        if (questions.length === 0) {
            listQuestions.innerHTML = '<p class="empty-state" style="color: var(--muted); font-size: 0.88rem;">No dynamic questions proposed.</p>';
        } else {
            listQuestions.innerHTML = questions.map(q => `
                <button type="button" class="suggested-question-btn" data-question="${q.replace(/"/g, '&quot;')}">
                    <span>${q}</span>
                    <span class="question-arrow">→</span>
                </button>
            `).join('');
            
            // Bind click triggers
            listQuestions.querySelectorAll(".suggested-question-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    const q = btn.dataset.question;
                    const input = document.getElementById("chatInput");
                    if (input) {
                        input.value = q;
                        switchTab("assistant");
                        const form = document.getElementById("chatForm");
                        if (form) {
                            form.dispatchEvent(new Event("submit"));
                        }
                    }
                });
            });
        }
    }

    // Populate timeline versions select dropdown
    const selectVer = document.getElementById("insightsVersionSelect");
    const containerTimeline = document.getElementById("insightTimelineContainer");
    if (selectVer && containerTimeline) {
        if (!data.dataset_id) {
            containerTimeline.style.display = "none";
        } else {
            containerTimeline.style.display = "flex";
            try {
                const response = await apiFetch(`/api/data/datasets/${data.dataset_id}/versions/`);
                if (response.ok) {
                    const versions = await response.json();
                    selectVer.innerHTML = versions.map(v => {
                        const selected = v.version_number === data.dataset_version ? "selected" : "";
                        return `<option value="${v.version_number}" ${selected}>Version ${v.version_number} (${new Date(v.created_at).toLocaleDateString()})</option>`;
                    }).join('');
                }
            } catch (err) {
                console.error("Failed to load timeline versions:", err);
            }
        }
    }
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
    renderProactiveInsights(data.proactive_insights, data);
    if (!data.charts?.length) {
        renderTrendChart(data.trends, data.trend_spec);
    }
}

async function loadDashboard() {
    try {
        const response = await apiFetch("/api/analytics/summary/");
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
        await loadDatasetLibrary();
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
        await loadDatasetLibrary();
        switchTab("dashboard");
    } catch (error) {
        setDataStatus(`URL ingestion failed: ${error.message}`, "error");
    }
});

runIngestionBtn?.addEventListener("click", async () => {
    if (!activeDatasetId) {
        setDataStatus("No active dataset is loaded to refresh.", "warning");
        return;
    }
    if (activeDatasetSource === "seed") {
        setDataStatus("Seed dataset cannot be synchronized. Ingest a database table, file or URL to run sync jobs.", "warning");
        return;
    }
    setDataStatus("Syncing dataset from source…", "info");
    try {
        const response = await apiFetch(`/api/data/datasets/${activeDatasetId}/sync/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const data = await response.json();
        if (!response.ok) {
            setDataStatus(data.error || "Sync failed.", "error");
            return;
        }
        let msg = `Sync complete — version ${data.version_number} activated (${data.rows?.toLocaleString()} rows)`;
        if (data.schema_changed) {
            msg += " · ⚠️ Schema changes detected";
        }
        setDataStatus(msg, data.schema_changed ? "warning" : "success");
        await loadDashboard();
        await loadDatasetLibrary();
    } catch (error) {
        setDataStatus(`Sync failed: ${error.message}`, "error");
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
                session_id: sessionId,
            }),
        });
        if (!response.ok) throw new Error(`Chat API failed (${response.status})`);
        const data = await response.json();
        sessionId = data.session_id;
        const sourceTag = data.powered_by_nvidia ? "NVIDIA" : "Fallback";
        addMessage("bot", data.reply, sourceTag);
    } catch (error) {
        addMessage("bot", `Assistant request failed: ${error.message}`, "System");
    } finally {
        setChatLoading(false);
    }
});

async function loadDatasetLibrary() {
    if (!libraryList) return;
    try {
        const response = await apiFetch("/api/data/datasets/");
        if (!response.ok) throw new Error("Failed to fetch dataset list");
        const datasets = await response.json();
        
        if (!datasets.length) {
            libraryList.innerHTML = '<div class="empty-state centered">No datasets uploaded yet.</div>';
            return;
        }

        libraryList.innerHTML = datasets.map(ds => {
            const activeClass = ds.is_active ? 'active' : '';
            const activeBadge = ds.is_active ? ' <span class="library-status-badge processed">Active</span>' : '';
            const statusLabel = ds.is_archived ? 'Archived' : ds.status;
            const statusClass = ds.is_archived ? 'archived' : ds.status;
            const formattedDate = new Date(ds.created_at).toLocaleString();
            
            return `
                <div class="library-item ${activeClass}" data-id="${ds.id}">
                    <div class="library-item-header">
                        <div class="library-item-title">
                            📁 ${ds.name || ds.display_name}
                            ${activeBadge}
                        </div>
                        <span class="library-status-badge ${statusClass}">${statusLabel}</span>
                    </div>
                    <div class="library-item-meta">
                        <span>Records: <strong>${ds.row_count.toLocaleString()}</strong></span>
                        <span>Type: <strong>${ds.source_type}</strong></span>
                        <span>Uploaded: ${formattedDate}</span>
                    </div>
                    ${ds.description ? `<div class="library-item-desc">${ds.description}</div>` : ''}
                    ${ds.error_message ? `<div class="status-banner error" style="margin-top: 0.5rem; padding: 0.4rem 0.6rem; font-size: 0.76rem;">${ds.error_message}</div>` : ''}
                    <div class="library-item-actions">
                        ${!ds.is_active && ds.status === 'processed' ? `<button type="button" class="ghost-btn small activate-ds-btn" data-id="${ds.id}">Activate</button>` : ''}
                        <button type="button" class="ghost-btn small manage-versions-btn" data-id="${ds.id}" data-name="${ds.name || ds.display_name}">Versions</button>
                        <button type="button" class="ghost-btn small sync-ds-action-btn" data-id="${ds.id}">Sync</button>
                        <button type="button" class="ghost-btn small rename-ds-btn" data-id="${ds.id}" data-name="${ds.name || ds.display_name}">Rename</button>
                        <button type="button" class="ghost-btn small archive-ds-btn" data-id="${ds.id}">${ds.is_archived ? 'Unarchive' : 'Archive'}</button>
                        <button type="button" class="ghost-btn small danger delete-ds-btn" style="border-color: rgba(239, 68, 68, 0.35); color: #fca5a5;" data-id="${ds.id}">Delete</button>
                    </div>
                </div>
            `;
        }).join('');

        // Bind dynamic action buttons
        libraryList.querySelectorAll(".activate-ds-btn").forEach(btn => {
            btn.addEventListener("click", (e) => activateDataset(e.target.dataset.id));
        });
        libraryList.querySelectorAll(".manage-versions-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const id = e.target.dataset.id;
                const name = e.target.dataset.name;
                openVersionsModal(id, name);
            });
        });
        libraryList.querySelectorAll(".sync-ds-action-btn").forEach(btn => {
            btn.addEventListener("click", async (e) => {
                const id = e.target.dataset.id;
                setDataStatus("Syncing dataset...", "info");
                try {
                    const response = await apiFetch(`/api/data/datasets/${id}/sync/`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" }
                    });
                    const data = await response.json();
                    if (!response.ok) {
                        setDataStatus(data.error || "Sync failed.", "error");
                        return;
                    }
                    let msg = `Sync complete — version ${data.version_number} activated (${data.rows?.toLocaleString()} rows)`;
                    if (data.schema_changed) {
                        msg += " · ⚠️ Schema changes detected";
                    }
                    setDataStatus(msg, data.schema_changed ? "warning" : "success");
                    await loadDashboard();
                    await loadDatasetLibrary();
                } catch (error) {
                    setDataStatus(`Sync failed: ${error.message}`, "error");
                }
            });
        });
        libraryList.querySelectorAll(".rename-ds-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const id = e.target.dataset.id;
                const currentName = e.target.dataset.name;
                renameDataset(id, currentName);
            });
        });
        libraryList.querySelectorAll(".archive-ds-btn").forEach(btn => {
            btn.addEventListener("click", (e) => toggleArchiveDataset(e.target.dataset.id));
        });
        libraryList.querySelectorAll(".delete-ds-btn").forEach(btn => {
            btn.addEventListener("click", (e) => deleteDataset(e.target.dataset.id));
        });

    } catch (error) {
        libraryList.innerHTML = `<div class="status-banner error">Error loading library: ${error.message}</div>`;
    }
}

async function activateDataset(id) {
    setDataStatus("Activating dataset…", "info");
    try {
        const response = await apiFetch(`/api/data/datasets/${id}/activate/`, {
            method: "POST"
        });
        const data = await response.json();
        if (!response.ok) {
            setDataStatus(data.detail || "Activation failed.", "error");
            return;
        }
        setDataStatus("Dataset activated successfully.", "success");
        await loadDashboard();
        await loadBlueprint();
        await loadDatasetLibrary();
    } catch (error) {
        setDataStatus(`Activation failed: ${error.message}`, "error");
    }
}

async function renameDataset(id, currentName) {
    const newName = prompt("Enter a new name for the dataset:", currentName);
    if (newName === null) return;
    const trimmed = newName.trim();
    if (!trimmed) {
        alert("Dataset name cannot be empty.");
        return;
    }
    
    setDataStatus("Renaming dataset…", "info");
    try {
        const response = await apiFetch(`/api/data/datasets/${id}/`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: trimmed })
        });
        const data = await response.json();
        if (!response.ok) {
            setDataStatus(data.detail || "Rename failed.", "error");
            return;
        }
        setDataStatus("Dataset renamed.", "success");
        await loadDashboard();
        await loadDatasetLibrary();
    } catch (error) {
        setDataStatus(`Rename failed: ${error.message}`, "error");
    }
}

async function toggleArchiveDataset(id) {
    setDataStatus("Updating archive status…", "info");
    try {
        const response = await apiFetch(`/api/data/datasets/${id}/archive/`, {
            method: "POST"
        });
        const data = await response.json();
        if (!response.ok) {
            setDataStatus(data.detail || "Archive toggle failed.", "error");
            return;
        }
        setDataStatus(data.detail, "success");
        await loadDashboard();
        await loadDatasetLibrary();
    } catch (error) {
        setDataStatus(`Archive failed: ${error.message}`, "error");
    }
}

async function deleteDataset(id) {
    if (!confirm("Are you sure you want to permanently delete this dataset? This action cannot be undone.")) {
        return;
    }
    setDataStatus("Deleting dataset…", "info");
    try {
        const response = await apiFetch(`/api/data/datasets/${id}/`, {
            method: "DELETE"
        });
        const data = await response.json();
        if (!response.ok) {
            setDataStatus(data.detail || "Deletion failed.", "error");
            return;
        }
        setDataStatus("Dataset deleted successfully.", "success");
        await loadDashboard();
        await loadBlueprint();
        await loadDatasetLibrary();
    } catch (error) {
        setDataStatus(`Deletion failed: ${error.message}`, "error");
    }
}

deactivateDatasetBtn?.addEventListener("click", async () => {
    setDataStatus("Resetting dashboard to default seed dataset…", "info");
    try {
        const response = await apiFetch("/api/data/datasets/deactivate/", {
            method: "POST"
        });
        const data = await response.json();
        if (!response.ok) {
            setDataStatus(data.detail || "Reset failed.", "error");
            return;
        }
        setDataStatus("Dashboard reset to seed dataset.", "success");
        await loadDashboard();
        await loadBlueprint();
        await loadDatasetLibrary();
    } catch (error) {
        setDataStatus(`Reset failed: ${error.message}`, "error");
    }
});

function initApp() {
    const initialTab = TAB_IDS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "dashboard";
    switchTab(initialTab);
    loadDashboard();
    loadBlueprint();
    initConnectors();
    initAuthModal();
    initProactiveInsightsTimeline();
    if (initialTab === "data") {
        loadDatasetLibrary();
    }
}

// Modal & Version Control logic
function openVersionsModal(id, name) {
    activeModalDatasetId = id;
    if (versionsModalTitle) {
        versionsModalTitle.textContent = `Version History: ${name}`;
    }
    setVersionUploadStatus("");
    if (compareResultsSection) compareResultsSection.hidden = true;
    if (versionsModal) versionsModal.hidden = false;
    
    // Clear inputs
    if (versionFileName) versionFileName.textContent = "No file chosen";
    if (versionFileInput) versionFileInput.value = "";
    if (versionUrlInput) versionUrlInput.value = "";
    
    loadVersionsTable(id);
}

function closeVersionsModal() {
    if (versionsModal) versionsModal.hidden = true;
    activeModalDatasetId = null;
}

if (closeVersionsModalBtn) {
    closeVersionsModalBtn.addEventListener("click", closeVersionsModal);
}

// Handle file selection click
if (versionFileSelectBtn && versionFileInput) {
    versionFileSelectBtn.addEventListener("click", () => versionFileInput.click());
    versionFileInput.addEventListener("change", () => {
        const file = versionFileInput.files[0];
        if (versionFileName) {
            versionFileName.textContent = file ? file.name : "No file chosen";
        }
    });
}

function setVersionUploadStatus(msg, type = "info") {
    if (!versionUploadStatus) return;
    if (!msg) {
        versionUploadStatus.hidden = true;
        versionUploadStatus.textContent = "";
        versionUploadStatus.className = "status-banner";
        return;
    }
    versionUploadStatus.hidden = false;
    versionUploadStatus.textContent = msg;
    versionUploadStatus.className = `status-banner ${type}`;
}

// Upload version file
versionUploadForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!activeModalDatasetId || !versionFileInput) return;
    const file = versionFileInput.files[0];
    if (!file) {
        setVersionUploadStatus("Please choose a file first.", "error");
        return;
    }
    
    setVersionUploadStatus("Uploading file version…", "info");
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const response = await apiFetch(`/api/data/datasets/${activeModalDatasetId}/versions/upload/`, {
            method: "POST",
            body: formData,
        });
        const data = await response.json();
        if (!response.ok) {
            setVersionUploadStatus(data.detail || "Upload failed.", "error");
            return;
        }
        setVersionUploadStatus(data.detail || "New version uploaded successfully.", "success");
        if (versionFileName) versionFileName.textContent = "No file chosen";
        versionFileInput.value = "";
        
        // Refresh
        await loadDashboard();
        await loadDatasetLibrary();
        loadVersionsTable(activeModalDatasetId);
    } catch (err) {
        setVersionUploadStatus(`Upload failed: ${err.message}`, "error");
    }
});

// Ingest version URL
versionUrlForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!activeModalDatasetId || !versionUrlInput) return;
    const url = versionUrlInput.value.trim();
    if (!url) return;
    
    setVersionUploadStatus("Ingesting URL version…", "info");
    try {
        const response = await apiFetch(`/api/data/datasets/${activeModalDatasetId}/versions/url/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });
        const data = await response.json();
        if (!response.ok) {
            setVersionUploadStatus(data.detail || "Ingestion failed.", "error");
            return;
        }
        setVersionUploadStatus(data.detail || "New version URL ingested.", "success");
        versionUrlInput.value = "";
        
        // Refresh
        await loadDashboard();
        await loadDatasetLibrary();
        loadVersionsTable(activeModalDatasetId);
    } catch (err) {
        setVersionUploadStatus(`Ingestion failed: ${err.message}`, "error");
    }
});

async function loadVersionsTable(datasetId) {
    if (!versionsTableBody) return;
    versionsTableBody.innerHTML = '<tr><td colspan="7" class="centered">Loading versions…</td></tr>';
    
    try {
        const response = await apiFetch(`/api/data/datasets/${datasetId}/versions/`);
        if (!response.ok) throw new Error("Failed to load versions list");
        const versions = await response.json();
        
        if (!versions.length) {
            versionsTableBody.innerHTML = '<tr><td colspan="7" class="centered">No historical versions stored.</td></tr>';
            return;
        }
        
        versionsTableBody.innerHTML = versions.map(v => {
            const activeBadge = v.is_active ? '<span class="library-status-badge processed">Active</span>' : '<span class="library-status-badge archived">Historic</span>';
            const actionBtn = v.is_active ? '' : `<button type="button" class="ghost-btn small restore-version-btn" data-ver="${v.version_number}">Restore</button>`;
            const formattedDate = new Date(v.created_at).toLocaleString();
            
            return `
                <tr>
                    <td><input type="checkbox" class="version-select-cb" data-ver="${v.version_number}" /></td>
                    <td><strong>v${v.version_number}</strong></td>
                    <td class="filename-span" title="${v.name || v.source_url}">${v.name || v.source_url}</td>
                    <td>${v.row_count.toLocaleString()}</td>
                    <td>${formattedDate}</td>
                    <td>${activeBadge}</td>
                    <td style="text-align: right;">${actionBtn}</td>
                </tr>
            `;
        }).join('');
        
        // Bind restore buttons
        versionsTableBody.querySelectorAll(".restore-version-btn").forEach(btn => {
            btn.addEventListener("click", (e) => restoreVersion(datasetId, e.target.dataset.ver));
        });
        
        // Bind checkbox listeners for comparison
        versionsTableBody.querySelectorAll(".version-select-cb").forEach(cb => {
            cb.addEventListener("change", updateCompareButtonState);
        });
        
        updateCompareButtonState();
    } catch (err) {
        versionsTableBody.innerHTML = `<tr><td colspan="7" class="centered error">Error: ${err.message}</td></tr>`;
    }
}

function updateCompareButtonState() {
    if (!compareBtn) return;
    const checked = Array.from(versionsTableBody.querySelectorAll(".version-select-cb:checked"));
    
    // Enforce max 2 checkboxes
    if (checked.length > 2) {
        // Uncheck the latest selection
        this.checked = false;
        return;
    }
    
    const count = checked.length;
    compareBtn.disabled = (count !== 2);
    compareBtn.textContent = `Compare Selected (${count}/2)`;
}

async function restoreVersion(datasetId, versionNumber) {
    if (!confirm(`Are you sure you want to restore to version ${versionNumber}?`)) return;
    setVersionUploadStatus(`Restoring to version ${versionNumber}…`, "info");
    try {
        const response = await apiFetch(`/api/data/datasets/${datasetId}/versions/${versionNumber}/restore/`, {
            method: "POST"
        });
        const data = await response.json();
        if (!response.ok) {
            setVersionUploadStatus(data.detail || "Restore failed.", "error");
            return;
        }
        setVersionUploadStatus(data.detail || `Restored to version ${versionNumber}.`, "success");
        await loadDashboard();
        await loadBlueprint();
        await loadDatasetLibrary();
        loadVersionsTable(datasetId);
    } catch (err) {
        setVersionUploadStatus(`Restore failed: ${err.message}`, "error");
    }
}

// Compare click
compareBtn?.addEventListener("click", async () => {
    if (!activeModalDatasetId) return;
    const checked = Array.from(versionsTableBody.querySelectorAll(".version-select-cb:checked"));
    if (checked.length !== 2) return;
    
    const v1 = checked[0].dataset.ver;
    const v2 = checked[1].dataset.ver;
    
    setVersionUploadStatus("Generating version comparison report…", "info");
    try {
        const response = await apiFetch(`/api/data/datasets/${activeModalDatasetId}/versions/compare/?v1=${v1}&v2=${v2}`);
        const data = await response.json();
        if (!response.ok) {
            setVersionUploadStatus(data.detail || "Comparison failed.", "error");
            return;
        }
        setVersionUploadStatus("", "info"); // Clear status
        displayComparisonReport(data);
    } catch (err) {
        setVersionUploadStatus(`Comparison failed: ${err.message}`, "error");
    }
});

function displayComparisonReport(data) {
    if (!compareResultsSection) return;
    compareResultsSection.hidden = false;
    
    if (compareV1Num) compareV1Num.textContent = data.v1_metadata.version_number;
    if (compareV1Rows) compareV1Rows.textContent = data.v1_metadata.row_count.toLocaleString();
    if (compareV2Num) compareV2Num.textContent = data.v2_metadata.version_number;
    if (compareV2Rows) compareV2Rows.textContent = data.v2_metadata.row_count.toLocaleString();
    
    if (compareRowDiffVal) {
        const diff = data.row_count_diff;
        compareRowDiffVal.textContent = diff >= 0 ? `+${diff.toLocaleString()}` : diff.toLocaleString();
        if (compareRowDiffContainer) {
            compareRowDiffContainer.style.background = diff >= 0 ? "rgba(34, 197, 94, 0.08)" : "rgba(239, 68, 68, 0.08)";
            compareRowDiffContainer.style.color = diff >= 0 ? "#86efac" : "#fca5a5";
        }
    }
    
    if (compareAddedCount) compareAddedCount.textContent = data.columns_diff.added.length;
    if (compareAddedCols) {
        compareAddedCols.innerHTML = data.columns_diff.added.length 
            ? data.columns_diff.added.map(c => `<span class="schema-diff-tag added">${c}</span>`).join('')
            : '<span class="schema-diff-tag" style="color: var(--muted);">None</span>';
    }
    
    if (compareRemovedCount) compareRemovedCount.textContent = data.columns_diff.removed.length;
    if (compareRemovedCols) {
        compareRemovedCols.innerHTML = data.columns_diff.removed.length 
            ? data.columns_diff.removed.map(c => `<span class="schema-diff-tag removed">${c}</span>`).join('')
            : '<span class="schema-diff-tag" style="color: var(--muted);">None</span>';
    }
    
    if (compareStatsBody) {
        const stats = data.numeric_stats_compare;
        const columns = Object.keys(stats);
        
        if (!columns.length) {
            compareStatsBody.innerHTML = '<tr><td colspan="6" class="centered">No common numeric columns found for profiling.</td></tr>';
            return;
        }
        
        compareStatsBody.innerHTML = columns.map(col => {
            const s = stats[col];
            const diffClass = s.mean_diff >= 0 ? 'added' : 'removed';
            const diffSign = s.mean_diff >= 0 ? `+` : '';
            return `
                <tr>
                    <td><strong>${col}</strong></td>
                    <td>${s.v1_mean.toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
                    <td>${s.v2_mean.toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
                    <td class="schema-diff-label ${diffClass}" style="margin-bottom:0;">
                        ${diffSign}${s.mean_diff.toLocaleString(undefined, {maximumFractionDigits: 2})}
                    </td>
                    <td>${s.v1_min.toLocaleString(undefined, {maximumFractionDigits: 2})} - ${s.v1_max.toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
                    <td>${s.v2_min.toLocaleString(undefined, {maximumFractionDigits: 2})} - ${s.v2_max.toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
                </tr>
            `;
        }).join('');
    }
}

closeCompareBtn?.addEventListener("click", () => {
    if (compareResultsSection) compareResultsSection.hidden = true;
    versionsTableBody.querySelectorAll(".version-select-cb").forEach(cb => cb.checked = false);
    updateCompareButtonState();
});

/* ─── Profile & Settings Handlers ─────────────────────────── */
function showStatusBanner(el, message, type) {
    if (!el) return;
    el.hidden = false;
    el.textContent = message;
    el.className = `status-banner ${type}`;
    setTimeout(() => { el.hidden = true; }, 4000);
}

// Profile save
const profileForm = document.getElementById("profileForm");
const profileStatus = document.getElementById("profileStatus");
const avatarInput = document.getElementById("avatarInput");

if (profileForm) {
    profileForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const payload = {
            display_name: document.getElementById("profileDisplayName").value,
            email: document.getElementById("profileEmail").value,
            bio: document.getElementById("profileBio").value,
            timezone: document.getElementById("profileTimezone").value,
        };
        apiFetch("/api/profile/update/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((r) => r.json())
            .then((data) => {
                if (data.error) {
                    showStatusBanner(profileStatus, data.error, "error");
                } else {
                    showStatusBanner(profileStatus, "Profile updated.", "success");
                    const nameEl = document.getElementById("profileDisplayNameText");
                    if (nameEl) nameEl.textContent = data.display_name || data.username;
                }
            })
            .catch(() => showStatusBanner(profileStatus, "Network error.", "error"));
    });
}

// Avatar upload
if (avatarInput) {
    avatarInput.addEventListener("change", () => {
        const file = avatarInput.files[0];
        if (!file) return;
        const fd = new FormData();
        fd.append("avatar", file);
        apiFetch("/api/profile/update/", { method: "POST", body: fd })
            .then((r) => r.json())
            .then((data) => {
                if (data.avatar_url) {
                    const prev = document.getElementById("avatarPreview");
                    if (prev) {
                        if (prev.tagName === "IMG") {
                            prev.src = data.avatar_url;
                        } else {
                            const img = document.createElement("img");
                            img.src = data.avatar_url;
                            img.alt = "Avatar";
                            img.className = "avatar-img";
                            img.id = "avatarPreview";
                            prev.replaceWith(img);
                        }
                    }
                    showStatusBanner(profileStatus, "Avatar updated.", "success");
                }
            })
            .catch(() => showStatusBanner(profileStatus, "Avatar upload failed.", "error"));
    });
}

// Theme toggle
const settingsStatus = document.getElementById("settingsStatus");
document.querySelectorAll(".theme-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
        const theme = chip.dataset.theme;
        apiFetch("/api/settings/update/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ theme_preference: theme }),
        })
            .then((r) => r.json())
            .then((data) => {
                if (data.theme_preference) {
                    document.querySelectorAll(".theme-chip").forEach((c) => c.classList.remove("theme-chip-active"));
                    chip.classList.add("theme-chip-active");
                    showStatusBanner(settingsStatus, `Theme set to ${data.theme_preference}.`, "success");
                }
            })
            .catch(() => showStatusBanner(settingsStatus, "Failed to save theme.", "error"));
    });
});

// Data export
const exportDataBtn = document.getElementById("exportDataBtn");
if (exportDataBtn) {
    exportDataBtn.addEventListener("click", () => {
        apiFetch("/api/settings/export-data/")
            .then((r) => r.json())
            .then((data) => {
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "nexa_account_export.json";
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
            })
            .catch(() => alert("Export failed."));
    });
}

// Account deletion
const deleteAccountBtn = document.getElementById("deleteAccountBtn");
const deleteConfirmRow = document.getElementById("deleteConfirmRow");
const deleteAccountConfirmBtn = document.getElementById("deleteAccountConfirmBtn");

if (deleteAccountBtn) {
    deleteAccountBtn.addEventListener("click", () => {
        if (deleteConfirmRow) deleteConfirmRow.hidden = false;
        deleteAccountBtn.hidden = true;
    });
}
if (deleteAccountConfirmBtn) {
    deleteAccountConfirmBtn.addEventListener("click", () => {
        const input = document.getElementById("deleteConfirmInput");
        if (!input || input.value !== "DELETE") {
            alert('Please type "DELETE" to confirm.');
            return;
        }
        apiFetch("/api/settings/delete-account/", { method: "POST" })
            .then((r) => r.json())
            .then((data) => {
                if (data.deleted) {
                    window.location.href = "/login/";
                } else {
                    alert(data.error || "Deletion failed.");
                }
            })
            .catch(() => alert("Network error during account deletion."));
    });
}

function initConnectors() {
    const optButtons = document.querySelectorAll(".connector-option-btn");
    optButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            if (btn.classList.contains("disabled")) return;
            optButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            const target = btn.dataset.connector;
            document.querySelectorAll(".connector-form-pane").forEach(pane => {
                pane.hidden = (pane.id !== `pane-${target}`);
            });
        });
    });

    const pgTestBtn = document.getElementById("pgTestBtn");
    const pgListTablesBtn = document.getElementById("pgListTablesBtn");
    const pgIngestSection = document.getElementById("pgIngestSection");
    const pgTableSelect = document.getElementById("pgTableSelect");
    const postgresStatus = document.getElementById("postgresStatus");
    const postgresForm = document.getElementById("postgresForm");

    function setPgStatus(msg, type) {
        if (!postgresStatus) return;
        postgresStatus.hidden = !msg;
        postgresStatus.textContent = msg || "";
        postgresStatus.className = `status-banner ${type || ""}`;
    }

    pgTestBtn?.addEventListener("click", async () => {
        const host = document.getElementById("pgHost").value.trim();
        const port = document.getElementById("pgPort").value.trim();
        const username = document.getElementById("pgUser").value.trim();
        const password = document.getElementById("pgPassword").value;
        const database = document.getElementById("pgDatabase").value.trim();

        if (!host || !username || !database) {
            setPgStatus("Host, username, and database name are required to test connection.", "error");
            return;
        }

        setPgStatus("Testing database connection...", "info");
        pgTestBtn.disabled = true;

        try {
            const res = await apiFetch("/api/data/connectors/test/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ host, port, username, password, database })
            });
            const data = await res.json();
            if (!res.ok) {
                setPgStatus(data.error || data.message || "Connection failed.", "error");
                pgListTablesBtn.disabled = true;
            } else {
                setPgStatus("Connection test successful!", "success");
                pgListTablesBtn.disabled = false;
            }
        } catch (err) {
            setPgStatus(`Error: ${err.message}`, "error");
        } finally {
            pgTestBtn.disabled = false;
        }
    });

    pgListTablesBtn?.addEventListener("click", async () => {
        const host = document.getElementById("pgHost").value.trim();
        const port = document.getElementById("pgPort").value.trim();
        const username = document.getElementById("pgUser").value.trim();
        const password = document.getElementById("pgPassword").value;
        const database = document.getElementById("pgDatabase").value.trim();

        setPgStatus("Discovering tables...", "info");
        pgListTablesBtn.disabled = true;

        try {
            const res = await apiFetch("/api/data/connectors/schema/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ host, port, username, password, database })
            });
            const data = await res.json();
            if (!res.ok) {
                setPgStatus(data.error || "Schema discovery failed.", "error");
            } else if (data.tables && data.tables.length > 0) {
                pgTableSelect.innerHTML = data.tables.map(tbl => `<option value="${tbl}">${tbl}</option>`).join("");
                pgIngestSection.hidden = false;
                setPgStatus(`Found ${data.tables.length} tables. Select one to ingest.`, "success");
            } else {
                setPgStatus("No tables found in public schema.", "warning");
            }
        } catch (err) {
            setPgStatus(`Error: ${err.message}`, "error");
        } finally {
            pgListTablesBtn.disabled = false;
        }
    });

    postgresForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const host = document.getElementById("pgHost").value.trim();
        const port = document.getElementById("pgPort").value.trim();
        const username = document.getElementById("pgUser").value.trim();
        const password = document.getElementById("pgPassword").value;
        const database = document.getElementById("pgDatabase").value.trim();
        const table = pgTableSelect.value;
        const name = document.getElementById("pgDatasetName").value.trim() || table;

        if (!table) {
            setPgStatus("Please select a table to ingest.", "error");
            return;
        }

        setPgStatus("Ingesting table data...", "info");
        const submitBtn = postgresForm.querySelector("button[type='submit']");
        if (submitBtn) submitBtn.disabled = true;

        try {
            const res = await apiFetch("/api/data/connectors/ingest/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ host, port, username, password, database, table, name })
            });
            const data = await res.json();
            if (!res.ok) {
                setPgStatus(data.error || "Table ingestion failed.", "error");
            } else {
                setPgStatus("Ingestion successful!", "success");
                postgresForm.reset();
                pgIngestSection.hidden = true;
                pgListTablesBtn.disabled = true;
                
                await loadDashboard();
                await loadDatasetLibrary();
                switchTab("dashboard");
            }
        } catch (err) {
            setPgStatus(`Error: ${err.message}`, "error");
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });
}

function initAuthModal() {
    const authModal = document.getElementById("authModal");
    const openLoginBtn = document.getElementById("openLoginBtn");
    const openRegisterBtn = document.getElementById("openRegisterBtn");
    const heroPrimaryCtaRegister = document.getElementById("heroPrimaryCtaRegister");
    const heroSecondaryCtaLogin = document.getElementById("heroSecondaryCtaLogin");
    const closeAuthModalBtn = document.getElementById("closeAuthModalBtn");

    const tabBtnLogin = document.getElementById("tabBtnLogin");
    const tabBtnRegister = document.getElementById("tabBtnRegister");
    const modalLoginForm = document.getElementById("modalLoginForm");
    const modalRegisterForm = document.getElementById("modalRegisterForm");

    const loginFormError = document.getElementById("loginFormError");
    const registerFormError = document.getElementById("registerFormError");

    function showModal(tab = "login") {
        if (!authModal) return;
        authModal.hidden = false;
        switchAuthTab(tab);
    }

    function hideModal() {
        if (!authModal) return;
        authModal.hidden = true;
        if (loginFormError) loginFormError.hidden = true;
        if (registerFormError) registerFormError.hidden = true;
        modalLoginForm?.reset();
        modalRegisterForm?.reset();
        const url = new URL(window.location);
        url.searchParams.delete("auth");
        window.history.replaceState({}, document.title, url.pathname + url.search + url.hash);
    }

    function switchAuthTab(tab) {
        if (tab === "login") {
            tabBtnLogin?.classList.add("active");
            tabBtnRegister?.classList.remove("active");
            if (modalLoginForm) modalLoginForm.hidden = false;
            if (modalRegisterForm) modalRegisterForm.hidden = true;
        } else {
            tabBtnRegister?.classList.add("active");
            tabBtnLogin?.classList.remove("active");
            if (modalLoginForm) modalLoginForm.hidden = true;
            if (modalRegisterForm) modalRegisterForm.hidden = false;
        }
    }

    openLoginBtn?.addEventListener("click", () => showModal("login"));
    openRegisterBtn?.addEventListener("click", () => showModal("register"));
    heroPrimaryCtaRegister?.addEventListener("click", () => showModal("register"));
    heroSecondaryCtaLogin?.addEventListener("click", () => showModal("login"));
    closeAuthModalBtn?.addEventListener("click", hideModal);

    authModal?.addEventListener("click", (e) => {
        if (e.target === authModal) hideModal();
    });

    tabBtnLogin?.addEventListener("click", () => switchAuthTab("login"));
    tabBtnRegister?.addEventListener("click", () => switchAuthTab("register"));

    document.querySelectorAll(".toggle-password-visibility").forEach(btn => {
        btn.addEventListener("click", () => {
            const input = btn.previousElementSibling;
            if (input) {
                if (input.type === "password") {
                    input.type = "text";
                    btn.textContent = "🙈";
                } else {
                    input.type = "password";
                    btn.textContent = "👁️";
                }
            }
        });
    });

    modalLoginForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = document.getElementById("loginUsername").value.trim();
        const password = document.getElementById("loginPassword").value;
        const rememberMe = document.getElementById("loginRememberMe").checked;

        if (loginFormError) loginFormError.hidden = true;
        const submitBtn = document.getElementById("loginSubmitBtn");
        if (submitBtn) submitBtn.disabled = true;

        try {
            const res = await apiFetch("/api/auth/login/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password, remember_me: rememberMe })
            });
            const data = await res.json();
            if (!res.ok) {
                if (loginFormError) {
                    loginFormError.textContent = data.error || "Login failed.";
                    loginFormError.hidden = false;
                }
            } else {
                window.location.href = window.location.pathname;
            }
        } catch (err) {
            if (loginFormError) {
                loginFormError.textContent = `Error: ${err.message}`;
                loginFormError.hidden = false;
            }
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });

    modalRegisterForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = document.getElementById("registerUsername").value.trim();
        const email = document.getElementById("registerEmail").value.trim();
        const password1 = document.getElementById("registerPassword1").value;
        const password2 = document.getElementById("registerPassword2").value;

        if (registerFormError) registerFormError.hidden = true;
        const submitBtn = document.getElementById("registerSubmitBtn");
        if (submitBtn) submitBtn.disabled = true;

        try {
            const res = await apiFetch("/api/auth/register/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, email, password1, password2 })
            });
            const data = await res.json();
            if (!res.ok) {
                if (registerFormError) {
                    registerFormError.textContent = data.error || "Registration failed.";
                    registerFormError.hidden = false;
                }
            } else {
                window.location.href = window.location.pathname;
            }
        } catch (err) {
            if (registerFormError) {
                registerFormError.textContent = `Error: ${err.message}`;
                registerFormError.hidden = false;
            }
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });

    const params = new URLSearchParams(window.location.search);
    const authAction = params.get("auth");
    if (authAction) {
        if (openLoginBtn) {
            if (authAction === "login") {
                showModal("login");
            } else if (authAction === "register") {
                showModal("register");
            }
        } else {
            // Clean up url parameters if already authenticated
            const url = new URL(window.location);
            url.searchParams.delete("auth");
            window.history.replaceState({}, document.title, url.pathname + url.search + url.hash);
        }
    }
}

function initProactiveInsightsTimeline() {
    const compareBtn = document.getElementById("compareTimelineInsightsBtn");
    const closeCompareBtn = document.getElementById("closeInsightCompareBtn");
    const selectVer = document.getElementById("insightsVersionSelect");
    const box = document.getElementById("insightComparisonBox");

    compareBtn?.addEventListener("click", async () => {
        if (!activeDatasetId || !selectVer) return;
        const selectedVerVal = selectVer.value;
        if (!selectedVerVal) return;

        compareBtn.disabled = true;
        compareBtn.textContent = "Comparing…";

        try {
            const response = await apiFetch(`/api/data/datasets/${activeDatasetId}/versions/compare_insights/?v1=${activeDatasetVersion}&v2=${selectedVerVal}`);
            if (!response.ok) {
                alert("Comparison failed: one or both version snapshots could not be analyzed.");
                return;
            }
            const compareData = await response.json();
            
            const title1 = document.getElementById("compV1Title");
            const text1 = document.getElementById("compV1Text");
            const title2 = document.getElementById("compV2Title");
            const text2 = document.getElementById("compV2Text");
            
            if (box && title1 && text1 && title2 && text2) {
                title1.textContent = `Current Active Version (v${compareData.v1_number})`;
                text1.textContent = compareData.v1?.narratives?.executive_summary || "No insights recorded.";
                
                title2.textContent = `Selected Comparison Target (v${compareData.v2_number})`;
                text2.textContent = compareData.v2?.narratives?.executive_summary || "No insights recorded.";
                
                box.hidden = false;
            }
        } catch (err) {
            alert(`Error comparing version insights: ${err.message}`);
        } finally {
            compareBtn.disabled = false;
            compareBtn.textContent = "Compare Version";
        }
    });

    closeCompareBtn?.addEventListener("click", () => {
        if (box) box.hidden = true;
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
} else {
    initApp();
}
