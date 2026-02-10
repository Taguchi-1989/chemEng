// ==================== History ====================
function getHistory() {
    return JSON.parse(localStorage.getItem('chemeng_history') || '[]');
}

function saveHistory(type, params, result) {
    // Save for report generation
    lastCalculationData[type] = { params, result, timestamp: new Date().toISOString() };

    const h = getHistory();
    const summary = type === 'property' ? `${params.substance}: ${params.property}`
        : type === 'distillation' ? `${params.light_component}/${params.heavy_component}`
        : type === 'mass_balance' ? params.components?.join('/')
        : type === 'extraction' ? `${params.solute}: ${params.carrier}→${params.solvent}`
        : type === 'absorption' ? `${params.gas_component}: into ${params.solvent}`
        : type === 'lcoh' ? `${params.production_method}: ${params.capacity}MW`
        : `${params.substance}: ${params.inlet_temperature}→${params.outlet_temperature}K`;
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
            document.querySelectorAll('.calc-tab').forEach(t => t.classList.remove('active'));
            document.querySelector(`[data-tab="${entry.type}"]`)?.classList.add('active');
            document.querySelectorAll('.form-section').forEach(f => f.classList.remove('active'));
            const form = document.getElementById(`${entry.type}-form`);
            form?.classList.add('active');
            if (form && entry.params) {
                Object.entries(entry.params).forEach(([k, v]) => {
                    const inp = form.querySelector(`[name="${k}"]`);
                    if (inp) inp.value = Array.isArray(v) ? v.join(', ') : v;
                });
            }
            toast('Loaded from history');
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
            return result.lcoh ? `${result.lcoh.toFixed(2)} EUR/kg H₂` : '-';
        case 'property':
            return result.value ? `${result.value.toFixed(4)} ${result.unit || ''}` : '-';
        case 'distillation':
            return result.actual_stages ? `${result.actual_stages} stages` : '-';
        case 'extraction':
            return result.extraction_efficiency ? `${(result.extraction_efficiency * 100).toFixed(1)}% eff.` : '-';
        case 'absorption':
            return result.required_stages ? `${result.required_stages} stages` : '-';
        case 'mass_balance':
            return result.distillate_flow ? `D=${result.distillate_flow.toFixed(2)}` : '-';
        case 'heat_balance':
            return result.heat_duty ? `${result.heat_duty.toFixed(2)} kW` : '-';
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
                <p>No saved cases</p>
                <p class="dashboard-empty-hint">Run calculations and click "Save to Dashboard" to compare results</p>
            </div>
        `;
        document.getElementById('compare-btn').disabled = true;
        return;
    }

    const html = filteredCases.map(c => `
        <div class="dashboard-case-item ${selectedCases.has(c.id) ? 'selected' : ''}" data-id="${c.id}">
            <input type="checkbox" class="case-checkbox" ${selectedCases.has(c.id) ? 'checked' : ''} onchange="toggleCaseSelection('${c.id}')">
            <div class="case-info">
                <div class="case-name">${c.name}</div>
                <div class="case-meta">
                    <span class="case-type-badge">${c.type.toUpperCase()}</span>
                    <span>${new Date(c.timestamp).toLocaleDateString('ja-JP')}</span>
                </div>
            </div>
            <div class="case-value">${c.mainValue}</div>
            <button class="case-delete" onclick="deleteDashboardCase('${c.id}')" title="Delete case">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
            </button>
        </div>
    `).join('');

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
        ? `Select ${2 - selectedCases.size} more case(s)`
        : `Compare ${selectedCases.size} Cases`;
}

// Delete a dashboard case
function deleteDashboardCase(caseId) {
    const cases = loadDashboardCases();
    const updated = cases.filter(c => c.id !== caseId);
    saveDashboardCases(updated);
    selectedCases.delete(caseId);
    renderDashboardCaseList();
    toast('Case deleted', 'success');
}

// Clear all dashboard cases
function clearAllDashboardCases() {
    if (confirm('Delete all saved cases? This cannot be undone.')) {
        saveDashboardCases([]);
        selectedCases.clear();
        renderDashboardCaseList();
        toast('All cases cleared', 'success');
    }
}

// Compare selected cases
function compareDashboardCases() {
    const cases = loadDashboardCases();
    const selected = cases.filter(c => selectedCases.has(c.id));

    if (selected.length < 2) {
        toast('Select at least 2 cases to compare', 'warning');
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

    // Find best case (lowest for LCOH, highest for efficiency, etc.)
    const lcohCases = cases.filter(c => c.type === 'lcoh');
    if (lcohCases.length > 0) {
        const best = lcohCases.reduce((a, b) => (a.result?.lcoh || Infinity) < (b.result?.lcoh || Infinity) ? a : b);
        document.getElementById('dash-best-case').textContent = best.result?.lcoh ? `${best.result.lcoh.toFixed(2)} EUR/kg` : '-';

        const avg = lcohCases.reduce((sum, c) => sum + (c.result?.lcoh || 0), 0) / lcohCases.length;
        document.getElementById('dash-average').textContent = `${avg.toFixed(2)} EUR/kg`;

        const values = lcohCases.map(c => c.result?.lcoh || 0);
        const range = Math.max(...values) - Math.min(...values);
        document.getElementById('dash-range').textContent = `±${(range/2).toFixed(2)} EUR/kg`;
    } else {
        document.getElementById('dash-best-case').textContent = '-';
        document.getElementById('dash-average').textContent = '-';
        document.getElementById('dash-range').textContent = '-';
    }

    document.getElementById('dashboard-subtitle').textContent = `Comparing ${cases.length} cases`;
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
        return `
            <tr>
                <td>${c.name}</td>
                <td><span class="case-type-badge">${c.type.toUpperCase()}</span></td>
                <td style="font-family: var(--mono); color: var(--accent-teal);">${c.mainValue}</td>
                <td style="font-size: 0.75rem;">${details}</td>
                <td>
                    <button class="case-delete" onclick="deleteDashboardCase('${c.id}')" title="Delete">
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

    const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${v}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chemeng_dashboard_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast('CSV exported successfully', 'success');
}
