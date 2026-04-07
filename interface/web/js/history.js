// ==================== History ====================
function getHistory() {
    return JSON.parse(localStorage.getItem('chemeng_history') || '[]');
}

function saveHistory(type, params, result) {
    // Save for report generation
    lastCalculationData[type] = { params, result, timestamp: new Date().toISOString() };

    const h = getHistory();
    let summary;
    try {
        if (type === 'property') summary = `${params.substance}: ${params.property}`;
        else if (type === 'distillation') summary = `${params.light_component}/${params.heavy_component}`;
        else if (type === 'mass_balance') summary = Array.isArray(params.components) ? params.components.join('/') : String(params.components || '');
        else if (type === 'extraction') summary = `${params.solute || '?'}: ${params.carrier || '?'} → ${params.solvent || '?'}`;
        else if (type === 'absorption') summary = `${params.gas_component || '?'}: into ${params.solvent || '?'}`;
        else if (type === 'lcoh') summary = `${params.production_method || '?'}: ${params.capacity || '?'}MW`;
        else if (type === 'heat_balance') summary = `${params.substance || '?'}: ${params.inlet_temperature || '?'} → ${params.outlet_temperature || '?'}K`;
        else summary = type;
    } catch { summary = type; }
    h.unshift({ type, params, summary, timestamp: new Date().toISOString() });
    if (h.length > 20) h.pop();
    localStorage.setItem('chemeng_history', JSON.stringify(h));
    updateHistoryUI();
}

function updateHistoryUI() {
    const h = getHistory();
    document.getElementById('history-count').textContent = h.length;
    const list = document.getElementById('history-list');
    list.innerHTML = h.map((item, i) => `
        <div class="history-item" data-idx="${i}">
            <div class="history-type">${escapeHtml(item.type)}</div>
            <div class="history-summary">${escapeHtml(item.summary)}</div>
        </div>
    `).join('');
    list.querySelectorAll('.history-item').forEach(el => {
        el.onclick = () => {
            const entry = h[parseInt(el.dataset.idx)];
            const targetTab = document.querySelector(`[data-tab="${entry.type}"]`);
            if (targetTab && typeof activateTab === 'function') {
                activateTab(targetTab);
            } else {
                document.querySelectorAll('.calc-tab').forEach(t => t.classList.remove('active'));
                targetTab?.classList.add('active');
                document.querySelectorAll('.form-section').forEach(f => f.classList.remove('active'));
                document.getElementById(`${entry.type}-form`)?.classList.add('active');
            }
            const form = document.getElementById(`${entry.type}-form`);
            if (form && entry.params) {
                Object.entries(entry.params).forEach(([k, v]) => {
                    if (!/^[a-zA-Z0-9_-]+$/.test(k)) return;
                    const inp = form.querySelector(`[name="${k}"]`);
                    if (inp) inp.value = Array.isArray(v) ? v.join(', ') : v;
                });
            }
            toast(t('msg.loaded_history'));
        };
    });
}

function initHistoryToggle() {
    document.getElementById('history-toggle').onclick = () => {
        document.getElementById('history-list').classList.toggle('hidden');
    };
    updateHistoryUI();
}

// ==================== Dashboard System ====================
const DASHBOARD_STORAGE_KEY = 'chemeng_dashboard_cases';
let selectedCases = new Set();

// Load dashboard cases from localStorage
function loadDashboardCases() {
    try {
        const stored = localStorage.getItem(DASHBOARD_STORAGE_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch (e) {
        console.error('Failed to load dashboard cases:', e);
        return [];
    }
}

// Save dashboard cases to localStorage
function saveDashboardCases(cases) {
    try {
        localStorage.setItem(DASHBOARD_STORAGE_KEY, JSON.stringify(cases));
    } catch (e) {
        console.error('Failed to save dashboard cases:', e);
        toast('Failed to save to dashboard', 'error');
    }
}

// Generate unique case ID
function generateCaseId() {
    return 'case_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Get case name from type and params
function getCaseName(type, params, result) {
    const timestamp = new Date().toLocaleString('ja-JP', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    switch (type) {
        case 'lcoh':
            const method = params.production_method?.replace(/_/g, ' ') || 'Unknown';
            return `LCOH: ${method} (${params.capacity || '?'}MW) - ${timestamp}`;
        case 'property':
            return `Property: ${params.substance} - ${params.property} - ${timestamp}`;
        case 'distillation':
            return `Distillation: ${params.light_component}/${params.heavy_component} - ${timestamp}`;
        case 'extraction':
            return `Extraction: ${params.solute || 'Unknown'} - ${timestamp}`;
        case 'absorption':
            return `Absorption: ${params.gas_component || 'Unknown'} - ${timestamp}`;
        case 'mass_balance':
            return `Mass Balance: ${params.components} - ${timestamp}`;
        case 'heat_balance':
            return `Heat Balance - ${timestamp}`;
        default:
            return `${type}: ${timestamp}`;
    }
}

// Get main value from result
function getMainValue(type, result) {
    switch (type) {
        case 'lcoh':
            return result.lcoh != null ? `${result.lcoh.toFixed(2)} EUR/kg H\u2082` : '-';
        case 'property':
            return result.value != null ? `${result.value.toFixed(4)} ${result.unit || ''}` : '-';
        case 'distillation':
            return result.actual_stages != null ? `${result.actual_stages} stages` : '-';
        case 'extraction':
            return result.recovery != null ? `${(result.recovery * 100).toFixed(1)}% recovery` : '-';
        case 'absorption':
            return result.actual_stages != null ? `${result.actual_stages} stages` : '-';
        case 'mass_balance':
            return result.closure != null ? `Closure: ${result.closure.toFixed(1)}%` : '-';
        case 'heat_balance':
            return result.total_heat_duty != null ? `${result.total_heat_duty.toFixed(1)} kW` : '-';
        default:
            return '-';
    }
}

// Save current calculation to dashboard
function saveToDashboard(type) {
    const data = lastCalculationData[type];
    if (!data) {
        toast('No calculation data to save. Run a calculation first.', 'warning');
        return;
    }

    const cases = loadDashboardCases();
    const newCase = {
        id: generateCaseId(),
        type: type,
        name: getCaseName(type, data.params, data.result),
        params: data.params,
        result: data.result,
        mainValue: getMainValue(type, data.result),
        timestamp: data.timestamp || new Date().toISOString()
    };

    cases.unshift(newCase);
    saveDashboardCases(cases);
    toast(`Saved to dashboard: ${newCase.name}`, 'success');
    renderDashboardCaseList();
}

// Render dashboard case list
function renderDashboardCaseList() {
    const container = document.getElementById('dashboard-case-list');
    const filterType = document.getElementById('dashboard-type-filter')?.value || 'all';
    const cases = loadDashboardCases();
    const filteredCases = filterType === 'all' ? cases : cases.filter(c => c.type === filterType);

    if (filteredCases.length === 0) {
        container.innerHTML = `
            <div class="dashboard-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1">
                    <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
                    <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
                </svg>
                <p>${escapeHtml(t('label.no_saved_cases'))}</p>
                <p class="dashboard-empty-hint">${escapeHtml(t('label.no_saved_cases_hint'))}</p>
            </div>
        `;
        document.getElementById('compare-btn').disabled = true;
        return;
    }

    const html = filteredCases.map(c => {
        const safeId = escapeHtml(c.id);
        return `
        <div class="dashboard-case-item ${selectedCases.has(c.id) ? 'selected' : ''}" data-id="${safeId}">
            <input type="checkbox" class="case-checkbox" ${selectedCases.has(c.id) ? 'checked' : ''} onchange="toggleCaseSelection('${safeId}')">
            <div class="case-info">
                <div class="case-name">${escapeHtml(c.name)}</div>
                <div class="case-meta">
                    <span class="case-type-badge">${escapeHtml(c.type.toUpperCase())}</span>
                    <span>${escapeHtml(new Date(c.timestamp).toLocaleDateString('ja-JP'))}</span>
                </div>
            </div>
            <div class="case-value">${escapeHtml(c.mainValue)}</div>
            <button class="case-delete" onclick="deleteDashboardCase('${safeId}')" title="Delete case">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
            </button>
        </div>
    `;
    }).join('');

    container.innerHTML = html;
    updateCompareButton();
}

// Toggle case selection
function toggleCaseSelection(caseId) {
    if (selectedCases.has(caseId)) {
        selectedCases.delete(caseId);
    } else {
        selectedCases.add(caseId);
    }
    renderDashboardCaseList();
}

// Update compare button state
function updateCompareButton() {
    const btn = document.getElementById('compare-btn');
    btn.disabled = selectedCases.size < 2;
    btn.textContent = selectedCases.size < 2
        ? t('btn.select_more').replace('{n}', 2 - selectedCases.size)
        : t('btn.compare_n').replace('{n}', selectedCases.size);
}

// Delete a dashboard case
function deleteDashboardCase(caseId) {
    confirmAction(t('confirm.delete_case'), () => {
        const cases = loadDashboardCases();
        const updated = cases.filter(c => c.id !== caseId);
        saveDashboardCases(updated);
        selectedCases.delete(caseId);
        renderDashboardCaseList();
        toast(t('msg.case_deleted'), 'success');
    });
}

// Clear all dashboard cases
function clearAllDashboardCases() {
    confirmAction(t('confirm.clear_all'), () => {
        saveDashboardCases([]);
        selectedCases.clear();
        renderDashboardCaseList();
        toast(t('msg.all_cleared'), 'success');
    });
}

// Compare selected cases
function compareDashboardCases() {
    const cases = loadDashboardCases();
    const selected = cases.filter(c => selectedCases.has(c.id));

    if (selected.length < 2) {
        toast(t('msg.select_2_cases'), 'warning');
        return;
    }

    // Show dashboard result panel
    showResult('dashboard');

    // Update summary
    updateDashboardSummary(selected);

    // Update chart
    updateDashboardChart(selected);

    // Update table
    updateDashboardTable(selected);
}

// Update dashboard summary cards
function updateDashboardSummary(cases) {
    document.getElementById('dash-case-count').textContent = cases.length;

    // Check if mixed types
    const types = new Set(cases.map(c => c.type));
    const isMixed = types.size > 1;
    const noteEl = document.getElementById('dash-mixed-note');

    // Type-specific summary extraction
    function extractNumericValues(cases) {
        if (types.size === 1) {
            const type = cases[0].type;
            if (type === 'lcoh') return { values: cases.map(c => c.result?.lcoh).filter(v => v != null), unit: 'EUR/kg H\u2082', lower_is_better: true };
            if (type === 'heat_balance') return { values: cases.map(c => c.result?.total_heat_duty).filter(v => v != null), unit: 'kW', lower_is_better: true };
            if (type === 'mass_balance') return { values: cases.map(c => c.result?.closure).filter(v => v != null), unit: '%', lower_is_better: false };
            if (type === 'extraction') return { values: cases.map(c => c.result?.recovery != null ? c.result.recovery * 100 : null).filter(v => v != null), unit: '%', lower_is_better: false };
            if (type === 'distillation' || type === 'absorption') return { values: cases.map(c => c.result?.actual_stages).filter(v => v != null), unit: t('label.stages'), lower_is_better: true };
        }
        // Fallback: parse mainValue
        const vals = cases.map(c => { const m = String(c.mainValue || '').match(/([\d.]+)/); return m ? parseFloat(m[1]) : null; }).filter(v => v != null);
        return { values: vals, unit: '', lower_is_better: true };
    }

    const { values, unit, lower_is_better } = extractNumericValues(cases);

    const bestEl = document.getElementById('dash-best-case');
    const avgEl = document.getElementById('dash-average');
    const rangeEl = document.getElementById('dash-range');

    if (values.length > 0) {
        const best = lower_is_better ? Math.min(...values) : Math.max(...values);
        const avg = values.reduce((a, b) => a + b, 0) / values.length;
        const range = Math.max(...values) - Math.min(...values);
        if (bestEl) bestEl.textContent = `${best.toFixed(2)} ${unit}`;
        if (avgEl) avgEl.textContent = `${avg.toFixed(2)} ${unit}`;
        if (rangeEl) rangeEl.textContent = `\u00b1${(range / 2).toFixed(2)} ${unit}`;
    } else {
        if (bestEl) bestEl.textContent = '-';
        if (avgEl) avgEl.textContent = '-';
        if (rangeEl) rangeEl.textContent = '-';
    }

    if (noteEl) {
        if (isMixed) {
            noteEl.textContent = t('label.mixed_type_note');
            noteEl.classList.remove('hidden');
        } else {
            noteEl.classList.add('hidden');
        }
    }

    document.getElementById('dashboard-subtitle').textContent = t('label.comparing_n').replace('{n}', cases.length);
}

// Update dashboard comparison table
function updateDashboardTable(cases) {
    const tbody = document.getElementById('dashboard-table-body');
    const html = cases.map(c => {
        let details = '-';
        if (c.type === 'lcoh') {
            details = `${c.params.capacity || '?'}MW, ${c.params.electricity_price || '?'} EUR/MWh, ${c.params.operating_hours || '?'}h/yr`;
        } else if (c.type === 'distillation') {
            details = `Feed: ${c.params.feed_flow_rate} kmol/h, xF: ${c.params.feed_composition}`;
        } else if (c.type === 'property') {
            details = `T: ${c.params.temperature}K, P: ${c.params.pressure}Pa`;
        }
        const safeId = escapeHtml(c.id);
        return `
            <tr>
                <td>${escapeHtml(c.name)}</td>
                <td><span class="case-type-badge">${escapeHtml(c.type.toUpperCase())}</span></td>
                <td style="font-family: var(--mono); color: var(--accent-teal);">${escapeHtml(c.mainValue)}</td>
                <td style="font-size: 0.75rem;">${escapeHtml(details)}</td>
                <td>
                    <button class="case-delete" onclick="deleteDashboardCase('${safeId}')" title="Delete">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                        </svg>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
    tbody.innerHTML = html;
}

// Export dashboard to CSV
function exportDashboardCSV() {
    const cases = loadDashboardCases().filter(c => selectedCases.has(c.id));
    if (cases.length === 0) {
        toast('No cases selected for export', 'warning');
        return;
    }

    const headers = ['Name', 'Type', 'Main Value', 'Timestamp'];
    const rows = cases.map(c => [
        c.name,
        c.type,
        c.mainValue,
        new Date(c.timestamp).toISOString()
    ]);

    const escCSV = v => {
        let s = String(v).replace(/"/g, '""');
        if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
        return `"${s}"`;
    };
    const csv = [headers.join(','), ...rows.map(r => r.map(escCSV).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chemeng_dashboard_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast('CSV exported successfully', 'success');
}
