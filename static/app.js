document.addEventListener("DOMContentLoaded", () => {

  // DOM Elements
  const form = document.getElementById("screener-form");
  const startupNameInput = document.getElementById("startup-name");
  const startupWebsiteInput = document.getElementById("startup-website");
  const additionalNotesInput = document.getElementById("additional-notes");
  const apiKeyInput = document.getElementById("api-key-input");
  const providerSelect = document.getElementById("provider-select");
  const runBtn = document.getElementById("run-screen-btn");
  const btnText = runBtn.querySelector(".btn-text");
  const btnLoader = runBtn.querySelector(".btn-loader");

  const toggleSettingsBtn = document.getElementById("toggle-settings-btn");
  const settingsPanel = document.getElementById("settings-panel");
  const keyStatusMsg = document.getElementById("key-status-msg");

  const emptyState = document.getElementById("output-empty-state");
  const loadingState = document.getElementById("output-loading-state");
  const reportContainer = document.getElementById("output-report-container");
  const loadingStatusText = document.getElementById("loading-status-text");

  let presetsData = [];

  // 1. Check Server Health & Provider Status
  async function checkServerHealth() {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const data = await res.json();
        if (data.gemini_key_configured) {
          keyStatusMsg.innerHTML = `🟢 Server active using <strong>Google Gemini API</strong> (<code>${data.gemini_model}</code>).`;
          if (providerSelect) providerSelect.value = "gemini";
        } else if (data.openai_key_configured) {
          keyStatusMsg.innerHTML = `🟢 Server active using <strong>OpenAI API</strong> (<code>${data.openai_model}</code>).`;
          if (providerSelect) providerSelect.value = "openai";
        } else {
          keyStatusMsg.innerHTML = `🟡 No server API key detected. App will run in <strong>Offline Demo Mode</strong> unless key is provided below.`;
        }
      }
    } catch (e) {
      keyStatusMsg.innerHTML = `🔴 Could not reach FastAPI backend server.`;
    }
  }

  // 2. Load Presets
  async function loadPresets() {
    try {
      const res = await fetch("/api/presets");
      if (res.ok) {
        const data = await res.json();
        presetsData = data.presets || [];
      }
    } catch (e) {
      console.warn("Could not load presets", e);
    }
  }

  // Handle Preset Click
  document.querySelectorAll(".preset-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const presetId = btn.getAttribute("data-preset");
      const preset = presetsData.find(p => p.id === presetId);
      if (preset) {
        startupNameInput.value = preset.name;
        startupWebsiteInput.value = preset.website;
        additionalNotesInput.value = preset.notes;
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // Toggle Settings Panel
  toggleSettingsBtn.addEventListener("click", () => {
    settingsPanel.classList.toggle("hidden");
  });

  // 3. Handle Form Submission
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const name = startupNameInput.value.trim();
    if (!name) return;

    const website = startupWebsiteInput.value.trim();
    const notes = additionalNotesInput.value.trim();
    const keyOverride = apiKeyInput.value.trim();
    const providerOverride = providerSelect ? providerSelect.value : null;

    // Show Loading UI State
    emptyState.classList.add("hidden");
    reportContainer.classList.add("hidden");
    loadingState.classList.remove("hidden");
    runBtn.disabled = true;
    btnText.classList.add("hidden");
    btnLoader.classList.remove("hidden");

    loadingStatusText.textContent = website 
      ? `Fetching ${website} & screening against VC thesis...` 
      : `Analyzing ${name} against VC thesis...`;

    try {
      const response = await fetch("/api/screen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          startup_name: name,
          startup_website: website,
          additional_notes: notes,
          api_key_override: keyOverride || null,
          provider_override: providerOverride
        })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Screening failed.");
      }

      const result = await response.json();
      renderReport(result);

    } catch (error) {
      alert(`Error running screen: ${error.message}`);
      loadingState.classList.add("hidden");
      emptyState.classList.remove("hidden");
    } finally {
      runBtn.disabled = false;
      btnText.classList.remove("hidden");
      btnLoader.classList.add("hidden");
    }
  });

  // 4. Render Screening Report Output
  function renderReport(data) {
    loadingState.classList.add("hidden");
    reportContainer.classList.remove("hidden");

    const report = data.report || {};

    // Header Info
    document.getElementById("report-startup-name").textContent = data.startup_name;
    const urlElem = document.getElementById("report-startup-url");
    if (data.startup_website) {
      urlElem.innerHTML = `<a href="${data.startup_website}" target="_blank" rel="noopener">${data.startup_website}</a>`;
    } else {
      urlElem.textContent = "Website: Not provided";
    }

    // Recommendation Badge
    const recBadge = document.getElementById("recommendation-badge");
    const recTitle = document.getElementById("recommendation-title");
    const rec = (report.recommendation || "INVESTIGATE").toUpperCase();

    recBadge.className = "rec-badge";
    if (rec === "HIGH PRIORITY") recBadge.classList.add("badge-high-priority");
    else if (rec === "INVESTIGATE") recBadge.classList.add("badge-investigate");
    else if (rec === "WATCH") recBadge.classList.add("badge-watch");
    else recBadge.classList.add("badge-pass");

    recTitle.textContent = rec;
    document.getElementById("recommendation-reason-text").textContent = report.recommendation_reason || "Based on thesis fit evaluation.";

    // API Warning / Offline Mode Notification
    const warningBanner = document.getElementById("api-warning-banner");
    if (report.api_error_warning) {
      warningBanner.textContent = report.api_error_warning;
      warningBanner.classList.remove("hidden");
    } else if (report.is_offline_fallback) {
      warningBanner.innerHTML = "ℹ️ Running in <strong>Offline Demo Mode</strong>. Scorecard generated using deterministic thesis criteria.";
      warningBanner.classList.remove("hidden");
    } else {
      warningBanner.classList.add("hidden");
    }

    // Executive Summary
    document.getElementById("report-exec-summary").textContent = report.executive_summary || "N/A";

    // Scorecard Table
    const tbody = document.getElementById("scorecard-tbody");
    tbody.innerHTML = "";
    const scorecard = report.scorecard || [];
    
    scorecard.forEach(item => {
      const tr = document.createElement("tr");
      const scoreNum = Math.min(5, Math.max(1, parseInt(item.score) || 1));

      tr.innerHTML = `
        <td><strong>${escapeHtml(item.criterion)}</strong></td>
        <td>
          <span class="score-badge score-${scoreNum}">${scoreNum}</span>
          <span style="font-size:0.8rem; color: #94a3b8;">/ 5</span>
        </td>
        <td>${escapeHtml(item.reason)}</td>
      `;
      tbody.appendChild(tr);
    });

    // Why It Fits
    document.getElementById("report-why-fits").textContent = report.why_it_fits || "N/A";

    // Positives List
    renderList("report-positives-list", report.investment_positives);

    // Risks List
    renderList("report-risks-list", report.risks_red_flags);

    // Key Unknowns List
    renderList("report-unknowns-list", report.key_unknowns);

    // Founder Questions List
    renderList("report-questions-list", report.founder_questions, true);

    // Sources & Provider Badge
    const sourcesContainer = document.getElementById("report-sources-container");
    sourcesContainer.innerHTML = "";

    const providerTag = document.createElement("span");
    providerTag.className = "source-pill";
    providerTag.style.background = "#1e3a8a";
    providerTag.style.color = "#93c5fd";
    providerTag.textContent = `Provider: ${report.provider_used || (report.is_offline_fallback ? "Offline Demo Engine" : "AI Provider")}`;
    sourcesContainer.appendChild(providerTag);

    const sources = report.sources || [];
    sources.forEach(src => {
      const pill = document.createElement("span");
      pill.className = "source-pill";
      pill.textContent = src;
      sourcesContainer.appendChild(pill);
    });

    // Scroll smoothly to report top
    reportContainer.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderList(elemId, items, isOrdered = false) {
    const list = document.getElementById(elemId);
    list.innerHTML = "";
    if (!items || items.length === 0) {
      list.innerHTML = "<li>None specified</li>";
      return;
    }
    items.forEach(item => {
      const li = document.createElement("li");
      li.textContent = item;
      list.appendChild(li);
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Initialize
  checkServerHealth();
  loadPresets();
});
