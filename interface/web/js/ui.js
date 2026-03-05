// ==================== UI Utilities ====================

// ==================== Escape HTML ====================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== Toast System ====================
function toast(msg, type = 'success', duration) {
    if (!duration) duration = type === 'error' ? 8000 : 4000;
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : '⚠';
    el.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${escapeHtml(msg)}</span>
        <button class="toast-close" aria-label="Close">×</button>
    `;
    container.appendChild(el);
    el.querySelector('.toast-close').onclick = () => el.remove();
    setTimeout(() => el.remove(), duration);
}

// ==================== Error Message Formatter ====================
function formatApiErrors(errors, warnings) {
    if (!errors || errors.length === 0) {
        return 'An unexpected error occurred / 予期しないエラーが発生しました';
    }
    const TRANSLATIONS = {
        'Skill not found': '計算タイプが見つかりません / Calculation type not found',
        'No calculation engine available': '計算エンジンが利用できません / No engine available',
        'No template or engine available': 'この計算はまだサポートされていません / Not yet supported',
        'Calculation timed out': '計算がタイムアウトしました / Calculation timed out',
        'Relative volatility': '相対揮発度が1以下です。この系では蒸留分離ができません / Relative volatility ≤ 1',
        'Feed composition': '原料組成が留出/缶出仕様と整合しません / Feed composition inconsistent',
        'Invalid material balance': '物質収支が成立しません。仕様を確認してください / Invalid material balance',
        'Henry constant': 'ヘンリー定数が正でなければなりません / Henry constant must be positive',
        'Distribution coefficient': '分配係数が正でなければなりません / Distribution coefficient must be positive',
        'Physically impossible': '物理的に不可能な結果です。パラメータを確認してください',
    };
    return errors.map(e => {
        for (const [key, translation] of Object.entries(TRANSLATIONS)) {
            if (e.includes(key)) return translation;
        }
        if (e.includes('ref:')) {
            return '内部計算エラー。異なるパラメータをお試しください / Internal error. Try different parameters.';
        }
        return e;
    }).join('\n');
}

// ==================== Confirmation Dialog ====================
function confirmAction(message, onConfirm) {
    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    overlay.innerHTML = `
        <div class="confirm-dialog">
            <p>${escapeHtml(message)}</p>
            <div class="confirm-actions">
                <button class="confirm-cancel">Cancel / キャンセル</button>
                <button class="confirm-ok">OK / 確認</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('.confirm-cancel').onclick = () => overlay.remove();
    overlay.querySelector('.confirm-ok').onclick = () => { overlay.remove(); onConfirm(); };
    overlay.addEventListener('keydown', e => {
        if (e.key === 'Escape') overlay.remove();
    });
    overlay.querySelector('.confirm-cancel').focus();
}

// ==================== Theme ====================
function initTheme() {
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (saved === 'light' || (!saved && !prefersDark)) {
        document.documentElement.setAttribute('data-theme', 'light');
        updateThemeIcon(false);
    } else {
        updateThemeIcon(true);
    }
}

function updateThemeIcon(isDark) {
    const icon = document.getElementById('theme-icon');
    icon.innerHTML = isDark
        ? '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'
        : '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
}

// ==================== Loading / Result Display ====================
function showLoading(message, showProgress) {
    document.getElementById('empty-state').classList.add('hidden');
    const loadingEl = document.getElementById('loading-state');
    loadingEl.classList.add('active');
    document.querySelectorAll('.result-section').forEach(s => s.classList.remove('active'));
    const msgEl = document.getElementById('loading-text');
    if (msgEl && message) msgEl.textContent = message;
    const progressEl = document.getElementById('loading-progress');
    if (progressEl) {
        progressEl.classList.toggle('active', !!showProgress);
    }
}

function hideLoading() {
    document.getElementById('loading-state').classList.remove('active');
    const progressEl = document.getElementById('loading-progress');
    if (progressEl) progressEl.classList.remove('active');
}

function updateLoadingProgress(current, total) {
    const fill = document.getElementById('loading-progress-fill');
    if (fill) {
        const pct = Math.round((current / total) * 100);
        fill.style.width = `${pct}%`;
    }
    const textEl = document.getElementById('loading-progress-text');
    if (textEl) textEl.textContent = `${current} / ${total}`;
    const msgEl = document.getElementById('loading-text');
    if (msgEl) msgEl.textContent = `Processing ${current}/${total}...`;
}

function showResult(type) {
    hideLoading();
    // Clear all result sections first
    document.querySelectorAll('.result-section').forEach(s => s.classList.remove('active'));
    // Hide empty state
    document.getElementById('empty-state').classList.add('hidden');
    // Show the specified result
    document.getElementById(`${type}-result`).classList.add('active');
}

// ==================== Render Calculation Steps ====================
function renderSteps(steps) {
    return steps.map(s => {
        const stepNo = escapeHtml(s?.step);
        const title = escapeHtml(s?.title);
        const desc = s?.description ? `<div class="step-desc">${escapeHtml(s.description)}</div>` : '';
        const formulas = Array.isArray(s?.formulas)
            ? s.formulas.map(escapeHtml).join('<br>')
            : escapeHtml(s?.formulas ?? '');
        return `
            <div class="step-item">
                <div class="step-title">Step ${stepNo}: ${title}</div>
                ${desc}
                <div class="step-formula">${formulas}</div>
            </div>
        `;
    }).join('');
}

// ==================== Report Generation ====================
function generateReport(type) {
    const data = lastCalculationData[type];
    if (!data) {
        toast('No calculation data available', 'error');
        return;
    }

    const timestamp = new Date().toLocaleString('ja-JP');
    const typeLabels = {
        'property': '物性推算 / Property Estimation',
        'distillation': '蒸留塔設計 / Distillation Column Design',
        'mass_balance': '物質収支 / Mass Balance',
        'heat_balance': '熱収支 / Heat Balance',
        'extraction': '液液抽出 / Liquid-Liquid Extraction',
        'absorption': 'ガス吸収 / Gas Absorption',
        'lcoh': '水素製造原価 / LCOH (Levelized Cost of Hydrogen)'
    };

    let html = `<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ChemEng Report - ${typeLabels[type] || type}</title>
    <style>
        :root {
            --primary: #14b8a6;
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text: #e2e8f0;
            --text-muted: #94a3b8;
            --border: #334155;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', 'Hiragino Sans', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }
        .report-container {
            max-width: 900px;
            margin: 0 auto;
        }
        .report-header {
            text-align: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid var(--primary);
        }
        .report-header h1 {
            color: var(--primary);
            font-size: 1.8rem;
            margin-bottom: 0.5rem;
        }
        .report-header .subtitle {
            color: var(--text-muted);
            font-size: 0.9rem;
        }
        .section {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }
        .section-title {
            color: var(--primary);
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 0.5rem 0;
        }
        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        th {
            color: var(--text-muted);
            font-weight: 500;
            font-size: 0.85rem;
        }
        td {
            font-family: 'Consolas', monospace;
        }
        .highlight {
            background: linear-gradient(135deg, var(--primary), #06b6d4);
            color: white;
            padding: 1.5rem;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 1.5rem;
        }
        .highlight-value {
            font-size: 2.5rem;
            font-weight: 700;
        }
        .highlight-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        .step {
            background: rgba(20, 184, 166, 0.1);
            border-left: 3px solid var(--primary);
            padding: 1rem;
            margin: 0.75rem 0;
            border-radius: 0 8px 8px 0;
        }
        .step-title {
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 0.5rem;
        }
        .step-formula {
            font-family: 'Consolas', monospace;
            color: var(--text-muted);
            font-size: 0.9rem;
        }
        .step-result {
            color: var(--primary);
            font-weight: 500;
            margin-top: 0.5rem;
        }
        .footer {
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8rem;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
        }
        @media print {
            body { background: white; color: #1e293b; }
            .section { border: 1px solid #e2e8f0; }
            .highlight { background: #14b8a6; }
        }
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <h1>ChemEng 計算レポート</h1>
            <div class="subtitle">${typeLabels[type] || type}</div>
            <div class="subtitle">Generated: ${timestamp}</div>
        </div>
`;
    // Add type-specific content
    html += generateReportContent(type, data);

    html += `
        <div class="footer">
            <p>Generated by ChemEng - Chemical Engineering Laboratory</p>
            <p>Powered by thermo/chemicals library</p>
        </div>
    </div>
</body>
</html>`;

    return html;
}

function generateReportContent(type, data) {
    const { params, result } = data;
    let html = '';

    // Input Parameters Section
    html += '<div class="section"><div class="section-title">📥 入力パラメータ / Input Parameters</div><table>';
    const paramLabels = getParamLabels(type);
    for (const [key, value] of Object.entries(params)) {
        const label = paramLabels[key] || key;
        html += `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(formatValue(value))}</td></tr>`;
    }
    html += '</table></div>';

    // Main Result (type-specific)
    html += generateMainResult(type, result);

    // Output Parameters Section
    if (result) {
        html += '<div class="section"><div class="section-title">📊 計算結果詳細 / Detailed Results</div><table>';
        const outputLabels = getOutputLabels(type);
        for (const [key, value] of Object.entries(result)) {
            if (key === 'calculation_steps' || key === 'sensitivity_data' || key === 'lcoh_breakdown' || key === 'annual_costs') continue;
            if (typeof value === 'object') continue;
            const label = outputLabels[key] || key;
            html += `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(formatValue(value))}</td></tr>`;
        }
        html += '</table></div>';
    }


    // Object Outputs Section (e.g., annual_costs)
    if (result) {
        const outputLabels = getOutputLabels(type);
        const objectEntries = Object.entries(result).filter(([key, value]) => {
            if (!value || typeof value !== 'object') return false;
            if (key === 'calculation_steps' || key === 'sensitivity_data') return false;
            if (key === 'lcoh_breakdown') return false; // handled in main result
            return true;
        });
        if (objectEntries.length) {
            html += '<div class="section"><div class="section-title">Structured Outputs</div>';
            objectEntries.forEach(([key, value]) => {
                const label = outputLabels[key] || key;
                html += `<div class="section-title" style="margin-top:1rem;">${escapeHtml(label)}</div>`;
                if (Array.isArray(value)) {
                    html += `<pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
                } else {
                    html += '<table>';
                    for (const [k, v] of Object.entries(value)) {
                        let displayVal = '-';
                        if (v !== null && v !== undefined) {
                            if (typeof v === 'number') {
                                displayVal = formatValue(v);
                            } else if (typeof v === 'object') {
                                displayVal = JSON.stringify(v);
                            } else {
                                displayVal = String(v);
                            }
                        }
                        html += `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(displayVal)}</td></tr>`;
                    }
                    html += '</table>';
                }
            });
            html += '</div>';
        }
    }

    // Calculation Steps
    if (result?.calculation_steps?.length) {
        html += '<div class="section"><div class="section-title">📝 計算過程 / Calculation Steps</div>';
        result.calculation_steps.forEach((step, i) => {
            html += `<div class="step">
                <div class="step-title">Step ${i + 1}: ${escapeHtml(step.step || step.title || '')}</div>
                ${step.description ? `<div>${escapeHtml(step.description)}</div>` : ''}
                ${step.formula ? `<div class="step-formula">${escapeHtml(step.formula)}</div>` : ''}
                ${step.formulas ? `<div class="step-formula">${step.formulas.map(escapeHtml).join('<br>')}</div>` : ''}
                ${step.values ? `<div class="step-formula">${Object.entries(step.values).map(([k,v]) => `${escapeHtml(k)}: ${escapeHtml(v)}`).join(', ')}</div>` : ''}
                ${step.result ? `<div class="step-result">→ ${escapeHtml(step.result)}</div>` : ''}
            </div>`;
        });
        html += '</div>';
    }

    return html;
}

function generateMainResult(type, result) {
    if (!result) return '';
    let html = '';

    switch(type) {
        case 'property':
            html += `<div class="highlight">
                <div class="highlight-label">${escapeHtml(result.property || 'Result')}</div>
                <div class="highlight-value">${escapeHtml(formatValue(result.value))} ${escapeHtml(result.unit || '')}</div>
            </div>`;
            break;
        case 'distillation':
            html += `<div class="highlight">
                <div class="highlight-label">理論段数 / Theoretical Stages</div>
                <div class="highlight-value">${escapeHtml(String(result.actual_stages || result.theoretical_stages || '-'))}</div>
            </div>`;
            break;
        case 'extraction':
            html += `<div class="highlight">
                <div class="highlight-label">抽出率 / Recovery</div>
                <div class="highlight-value">${((result.recovery || 0) * 100).toFixed(1)}%</div>
            </div>`;
            break;
        case 'absorption':
            html += `<div class="highlight">
                <div class="highlight-label">除去率 / Removal Efficiency</div>
                <div class="highlight-value">${((result.removal_efficiency || 0) * 100).toFixed(1)}%</div>
            </div>`;
            break;
        case 'lcoh':
            html += `<div class="highlight">
                <div class="highlight-label">Levelized Cost of Hydrogen</div>
                <div class="highlight-value">${escapeHtml(result.lcoh?.toFixed(2) || '-')} EUR/kg H2</div>
            </div>`;
            // Cost breakdown
            if (result.lcoh_breakdown) {
                html += '<div class="section"><div class="section-title">💰 コスト内訳 / Cost Breakdown</div><table>';
                const breakdownLabels = {
                    capex: 'CAPEX (設備投資)',
                    energy: 'Energy (エネルギー)',
                    opex: 'OPEX (運転費)',
                    labor: 'Labor (Labor Cost)',
                    maintenance: 'Maintenance (Maintenance Cost)',
                    stack_replacement: 'Stack Replacement (スタック交換)',
                    water: 'Water (水)',
                    carbon: 'Carbon Cost (炭素コスト)',
                    revenue_offset: 'Revenue Offset (収入控除)'
                };
                for (const [key, value] of Object.entries(result.lcoh_breakdown)) {
                    if (key === 'total') continue;
                    html += `<tr><th>${escapeHtml(breakdownLabels[key] || key)}</th><td>${escapeHtml(String(value?.toFixed(3) || 0))} EUR/kg H2</td></tr>`;
                }
                html += '</table></div>';
            }
            break;
        default:
            break;
    }
    return html;
}

function getParamLabels(type) {
    const common = {
        substance: '物質名 / Substance',
        temperature: '温度 / Temperature (K)',
        pressure: '圧力 / Pressure (Pa)',
        components: '成分 / Components'
    };
    const specific = {
        property: { property: '物性 / Property' },
        distillation: {
            light_component: '軽沸成分 / Light Component',
            heavy_component: '重沸成分 / Heavy Component',
            feed_composition: '原料組成 / Feed Composition',
            distillate_composition: '留出液組成 / Distillate Composition',
            bottoms_composition: '缶出液組成 / Bottoms Composition',
            feed_flow_rate: '原料流量 / Feed Flow Rate',
            reflux_ratio: '還流比 / Reflux Ratio'
        },
        extraction: {
            solute: '溶質 / Solute',
            carrier: 'キャリア / Carrier',
            solvent: '溶媒 / Solvent',
            feed_flow: '原料流量 / Feed Flow',
            solvent_flow: '溶媒流量 / Solvent Flow'
        },
        absorption: {
            gas_component: 'ガス成分 / Gas Component',
            carrier_gas: 'キャリアガス / Carrier Gas',
            solvent: '吸収液 / Solvent',
            gas_flow_rate: 'ガス流量 / Gas Flow Rate'
        },
        lcoh: {
            production_method: '製造方法 / Production Method',
            capacity: '設備容量 / Capacity (MW)',
            electricity_price: '電力単価 / Electricity Price (EUR/MWh)',
            natural_gas_price: 'ガス単価 / Gas Price (EUR/MWh)',
            operating_hours: '稼働時間 / Operating Hours (h/year)',
            capex_per_kw: 'CAPEX単価 / CAPEX (EUR/kW)',
            opex_percent: 'OPEX率 / OPEX (%)',
            discount_rate: '割引率 / Discount Rate (%)',
            project_lifetime: 'プロジェクト寿命 / Project Lifetime (years)',
            carbon_price: 'Carbon Price (EUR/ton)',
            subsidies: 'Subsidy (EUR/kg)',
            water_price: 'Water Price (EUR/m3)',
            capex_subsidy_percent: 'CAPEX Subsidy (%)',
            capex_subsidy_amount: 'CAPEX Subsidy (EUR)',
            maintenance_days: 'Maintenance Days (days/year)',
            labor_cost: 'Labor Cost (EUR/year)',
            maintenance_cost: 'Maintenance Cost (EUR/year)'
        }
    };
    return { ...common, ...(specific[type] || {}) };
}

function getOutputLabels(type) {
    return {
        lcoh: 'LCOH (EUR/kg H2)',
        annual_costs: 'Annual Costs (EUR/year)',
        annual_h2_production: '年間生産量 / Annual Production (kg/year)',
        total_capex: '総CAPEX / Total CAPEX (EUR)',
        energy_efficiency: 'エネルギー効率 / Energy Efficiency (%)',
        carbon_intensity: 'CO₂原単位 / Carbon Intensity (kg CO₂/kg H₂)',
        production_method: '製造方法 / Production Method',
        capacity_mw: '設備容量 / Capacity (MW)',
        operating_hours: '稼働時間 / Operating Hours (h/year)',
        theoretical_stages: '理論段数 / Theoretical Stages',
        actual_stages: '実際段数 / Actual Stages',
        minimum_reflux_ratio: '最小還流比 / Minimum Reflux Ratio',
        actual_reflux_ratio: '実際還流比 / Actual Reflux Ratio',
        recovery: '抽出率 / Recovery',
        stages: '段数 / Stages',
        removal_efficiency: '除去率 / Removal Efficiency',
        absorption_factor: '吸収係数 / Absorption Factor',
        liquid_gas_ratio: '液ガス比 / L/G Ratio',
        ntu: 'NTU',
        value: '値 / Value'
    };
}

function formatValue(val) {
    if (val === null || val === undefined) return '-';
    if (typeof val === 'number') {
        if (Number.isInteger(val)) return val.toLocaleString();
        return val.toFixed(4).replace(/\.?0+$/, '');
    }
    if (Array.isArray(val)) return val.join(', ');
    return String(val);
}

function downloadReport(type) {
    const html = generateReport(type);
    if (!html) return;

    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
    a.download = `chemeng_${type}_report_${timestamp}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast('Report downloaded');
}

// ==================== Export ====================
function download(content, filename, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
    toast(`Downloaded ${filename}`);
}

// Universal JSON Export (importable format)
function exportJSON(skillId) {
    const data = lastCalculationData[skillId.replace('_estimation', '').replace('property_estimation', 'property')];
    if (!data) return toast('No data to export. Run calculation first.', 'warning');

    const exportData = {
        skill_id: skillId,
        parameters: data.params,
        results: data.result,
        timestamp: data.timestamp || new Date().toISOString()
    };

    download(JSON.stringify(exportData, null, 2),
             `chemeng_${skillId}_${Date.now()}.json`,
             'application/json');
}

// Universal CSV Export
function exportCSV(skillId) {
    const typeKey = skillId.replace('_estimation', '').replace('property_estimation', 'property');
    const data = lastCalculationData[typeKey];
    if (!data) return toast('No data to export. Run calculation first.', 'warning');

    const { params, result } = data;
    let csv = '';

    // Build CSV based on skill type
    if (skillId === 'property_estimation' || skillId === 'property') {
        const p = PROPERTIES[params.property] || { name: params.property, unit: '', factor: 1 };
        csv = `Substance,Property,Value,Unit,Temperature (K),Pressure (Pa)\n`;
        csv += `${params.substance},${p.name},${(result.value * p.factor).toFixed(4)},${p.unit},${params.temperature},${params.pressure}`;
    } else {
        // Generic CSV for other skill types
        csv = `Parameter,Value\n`;
        Object.entries(params).forEach(([key, val]) => {
            csv += `[Input] ${key},${formatCSVValue(val)}\n`;
        });
        csv += `\nResult,Value\n`;
        Object.entries(result).forEach(([key, val]) => {
            if (key !== 'calculation_steps' && key !== 'lcoh_breakdown' && key !== 'sensitivity_data') {
                csv += `[Output] ${key},${formatCSVValue(val)}\n`;
            }
        });
    }

    download(csv, `chemeng_${skillId}_${Date.now()}.csv`, 'text/csv');
}

function formatCSVValue(val) {
    if (val === null || val === undefined) return '';
    if (typeof val === 'number') return val.toString();
    let str;
    if (typeof val === 'object') {
        str = JSON.stringify(val);
    } else {
        str = String(val);
    }
    // Escape double quotes by doubling them, then wrap in quotes
    str = str.replace(/"/g, '""');
    // Prevent CSV formula injection (=, +, -, @, tab, CR)
    if (/^[=+\-@\t\r]/.test(str)) {
        str = "'" + str;
    }
    return `"${str}"`;
}

// ==================== Prompt Template Generation ====================
async function downloadPromptTemplate(skillId) {
    const template = generatePromptTemplate(skillId);
    download(template, `chemeng_${skillId}_template.txt`, 'text/plain');
}

function generatePromptTemplate(skillId) {
    const skillName = SKILL_NAMES[skillId] || { ja: skillId, en: skillId };
    const params = SKILL_PARAMS[skillId] || [];

    let template = `${'='.repeat(80)}\n`;
    template += `ChemEng - ${skillName.ja} / ${skillName.en} - Prompt Template\n`;
    template += `${'='.repeat(80)}\n\n`;

    template += `【使い方 / How to Use】\n`;
    template += `1. 下の「YOUR DATA」セクションにパラメータを入力してください\n`;
    template += `   Fill in your parameters in the "YOUR DATA" section below\n`;
    template += `2. このテンプレートをClaude等のLLMに送信してください\n`;
    template += `   Send this template to an LLM (like Claude)\n`;
    template += `3. 出力されたJSONをChemEngにインポートしてください\n`;
    template += `   Import the output JSON into ChemEng\n\n`;

    template += `${'='.repeat(80)}\n`;
    template += `【パラメータ説明 / Parameter Description】\n`;
    template += `${'='.repeat(80)}\n\n`;

    params.forEach((p, idx) => {
        template += `${idx + 1}. ${p.name} ${p.required ? '(必須/Required)' : '(オプション/Optional)'}\n`;
        template += `   - ${p.ja} / ${p.en}\n`;
        if (p.unit) template += `   - 単位/Unit: ${p.unit}\n`;
        if (p.default !== undefined) template += `   - デフォルト/Default: ${p.default}\n`;
        if (p.range) template += `   - 範囲/Range: ${p.range}\n`;
        if (p.choices) template += `   - 選択肢/Choices: ${p.choices}\n`;
        if (p.example !== undefined) template += `   - 例/Example: ${JSON.stringify(p.example)}\n`;
        template += `\n`;
    });

    template += `${'='.repeat(80)}\n`;
    template += `【YOUR DATA / あなたのデータ】\n`;
    template += `${'='.repeat(80)}\n\n`;

    params.forEach(p => {
        template += `${p.name}: _______________\n`;
    });

    template += `\n${'='.repeat(80)}\n`;
    template += `【LLMへの指示 / Instructions for LLM】\n`;
    template += `${'='.repeat(80)}\n\n`;
    template += `上記のデータを以下のJSON形式で出力してください。\n`;
    template += `空欄のフィールドは省略してください。\n\n`;
    template += `Please convert the above data to this JSON format.\n`;
    template += `Omit fields that are empty.\n\n`;

    const exampleParams = {};
    params.forEach(p => {
        if (p.example !== undefined) {
            exampleParams[p.name] = p.example;
        } else if (p.default !== undefined) {
            exampleParams[p.name] = p.default;
        }
    });

    template += `{\n`;
    template += `  "skill_id": "${skillId}",\n`;
    template += `  "parameters": ${JSON.stringify(exampleParams, null, 4).split('\n').map((line, i) => i === 0 ? line : '  ' + line).join('\n')}\n`;
    template += `}\n\n`;

    template += `${'='.repeat(80)}\n`;
    template += `ChemEng v1.0.0 | Chemical Engineering Calculator\n`;
    template += `${'='.repeat(80)}\n`;

    return template;
}

// ==================== Import ====================
async function handleImportFile(file) {
    if (!file || !file.name.endsWith('.json')) {
        showImportError('Please select a valid JSON file / 有効なJSONファイルを選択してください');
        return;
    }

    try {
        const text = await file.text();
        const data = JSON.parse(text);

        // Batch format detection: { cases: [...] }
        if (Array.isArray(data.cases) && data.cases.length > 0) {
            const validSkills = Object.keys(SKILL_NAMES);
            const errors = [];
            data.cases.forEach((c, i) => {
                if (!c.skill_id || !c.parameters) {
                    errors.push(`Case ${i + 1}: missing skill_id or parameters`);
                } else if (!validSkills.includes(c.skill_id)) {
                    errors.push(`Case ${i + 1}: unknown skill "${c.skill_id}"`);
                }
            });
            if (errors.length > 0) {
                showImportError(errors.join('\n'));
                return;
            }
            if (data.cases.length > 50) {
                showImportError('Maximum 50 cases per batch / 一括実行は最大50件です');
                return;
            }
            pendingImportData = { _batch: true, cases: data.cases };
            showBatchPreview(data.cases);
            document.getElementById('confirm-import').disabled = false;
            return;
        }

        if (!data.skill_id || !data.parameters) {
            showImportError('Invalid format. Missing skill_id or parameters. / 無効なフォーマット。skill_idまたはparametersがありません。');
            return;
        }

        const validSkills = Object.keys(SKILL_NAMES);
        if (!validSkills.includes(data.skill_id)) {
            showImportError(`Unknown skill: ${data.skill_id}. Valid: ${validSkills.join(', ')}`);
            return;
        }

        const validation = validateImportParams(data.skill_id, data.parameters);
        if (!validation.valid) {
            showImportError(`Validation error: ${validation.errors.join(', ')}`);
            return;
        }

        pendingImportData = data;
        showImportPreview(data);
        document.getElementById('confirm-import').disabled = false;

    } catch (e) {
        showImportError('Failed to parse JSON: ' + e.message);
    }
}

function validateImportParams(skillId, params) {
    const schema = SKILL_PARAMS[skillId] || [];
    const errors = [];

    schema.filter(p => p.required).forEach(p => {
        if (params[p.name] === undefined || params[p.name] === null || params[p.name] === '') {
            errors.push(`Missing required: ${p.name}`);
        }
    });

    return { valid: errors.length === 0, errors };
}

function showImportPreview(data) {
    const skillName = SKILL_NAMES[data.skill_id] || { ja: data.skill_id, en: data.skill_id };
    document.getElementById('import-skill-badge').textContent = `${skillName.ja} / ${skillName.en}`;

    const paramsList = document.getElementById('import-params-list');
    paramsList.innerHTML = Object.entries(data.parameters)
        .map(([key, val]) => `<div class="import-param-row">
            <span class="import-param-name">${escapeHtml(key)}:</span>
            <span class="import-param-value">${escapeHtml(JSON.stringify(val))}</span>
        </div>`)
        .join('');

    document.getElementById('import-preview').classList.remove('hidden');
    document.getElementById('import-dropzone').classList.add('hidden');
    document.getElementById('import-error').classList.add('hidden');
}

function showBatchPreview(cases) {
    const skillName = (id) => {
        const s = SKILL_NAMES[id];
        return s ? `${s.ja} / ${s.en}` : id;
    };
    document.getElementById('import-skill-badge').textContent = `Batch / 一括実行 (${cases.length} cases)`;

    const paramsList = document.getElementById('import-params-list');
    paramsList.innerHTML = cases.map((c, i) => {
        const name = c.case_name || `Case ${i + 1}`;
        return `<div class="import-param-row">
            <span class="import-param-name">${escapeHtml(name)}</span>
            <span class="import-param-value">${escapeHtml(skillName(c.skill_id))}</span>
        </div>`;
    }).join('');

    document.getElementById('import-preview').classList.remove('hidden');
    document.getElementById('import-dropzone').classList.add('hidden');
    document.getElementById('import-error').classList.add('hidden');
}

function showImportError(message) {
    const errorEl = document.getElementById('import-error');
    errorEl.textContent = message;
    errorEl.classList.remove('hidden');
}

function resetImportModal() {
    pendingImportData = null;
    document.getElementById('import-preview').classList.add('hidden');
    document.getElementById('import-dropzone').classList.remove('hidden');
    document.getElementById('import-error').classList.add('hidden');
    document.getElementById('confirm-import').disabled = true;
    document.getElementById('import-file').value = '';
}

function populateForm(skillId, params) {
    const tabName = skillId === 'property_estimation' ? 'property' : skillId;
    const form = document.getElementById(`${tabName}-form`);
    if (!form) return;

    Object.entries(params).forEach(([name, value]) => {
        if (!/^[a-zA-Z0-9_-]+$/.test(name)) return;
        const input = form.querySelector(`[name="${name}"]`);
        if (input) {
            if (input.type === 'checkbox') {
                input.checked = !!value;
            } else if (Array.isArray(value)) {
                input.value = value.join(', ');
            } else {
                input.value = value;
            }
        }
    });
}

// ==================== Help System ====================
let helpPanelOpen = false;

function initHelpSystem() {
    const fab = document.getElementById('help-fab');
    const panel = document.getElementById('help-panel');
    const closeBtn = document.getElementById('help-panel-close');
    const messagesContainer = document.getElementById('help-messages');
    const input = document.getElementById('help-input');
    const sendBtn = document.getElementById('help-send-btn');

    // Toggle panel
    fab.onclick = () => {
        helpPanelOpen = !helpPanelOpen;
        panel.classList.toggle('hidden', !helpPanelOpen);
        fab.classList.toggle('active', helpPanelOpen);
        if (helpPanelOpen) {
            input.focus();
        }
    };

    // Close button
    closeBtn.onclick = () => {
        helpPanelOpen = false;
        panel.classList.add('hidden');
        fab.classList.remove('active');
    };

    // Quick action buttons
    document.querySelectorAll('.help-quick-btn').forEach(btn => {
        btn.onclick = () => {
            const topic = btn.dataset.topic;
            showHelpTopic(topic);
        };
    });

    // Close on Escape key
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && helpPanelOpen) {
            helpPanelOpen = false;
            panel.classList.add('hidden');
            fab.classList.remove('active');
        }
    });

    // Future: Enable input when AI is integrated
    input.oninput = () => {
        // sendBtn.disabled = !input.value.trim();
    };

    // Future: Send message
    sendBtn.onclick = () => {
        if (sendBtn.disabled) return;
        const text = input.value.trim();
        if (!text) return;
        addUserMessage(text);
        input.value = '';
        sendBtn.disabled = true;
        setTimeout(() => {
            addSystemMessage('AI機能は現在開発中です。上のトピックボタンをご利用ください。');
        }, 500);
    };

    // Enter to send (future)
    input.onkeydown = e => {
        if (e.key === 'Enter' && !e.shiftKey && !sendBtn.disabled) {
            e.preventDefault();
            sendBtn.click();
        }
    };
}

function showHelpTopic(topic) {
    const content = HELP_CONTENT[topic];
    if (!content) return;

    const messagesContainer = document.getElementById('help-messages');

    // Clear quick actions and add response
    const quickActions = document.getElementById('help-quick-actions');
    if (quickActions) {
        quickActions.remove();
    }

    // Add system response
    const msgEl = document.createElement('div');
    msgEl.className = 'help-message system';
    msgEl.innerHTML = `
        <div class="help-message-avatar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            </svg>
        </div>
        <div class="help-message-content">
            <p style="font-weight: 600; color: var(--accent-cyan); margin-bottom: 0.75rem;">${content.title}</p>
            ${content.content}
        </div>
    `;
    messagesContainer.appendChild(msgEl);

    // Add back button
    const backBtn = document.createElement('button');
    backBtn.className = 'help-quick-btn';
    backBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
        </svg>
        他のトピックを見る
    `;
    backBtn.onclick = () => resetHelpPanel();
    messagesContainer.appendChild(backBtn);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addUserMessage(text) {
    const messagesContainer = document.getElementById('help-messages');
    const msgEl = document.createElement('div');
    msgEl.className = 'help-message user';
    msgEl.innerHTML = `
        <div class="help-message-avatar">U</div>
        <div class="help-message-content">${escapeHtml(text)}</div>
    `;
    messagesContainer.appendChild(msgEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addSystemMessage(text) {
    const messagesContainer = document.getElementById('help-messages');
    const msgEl = document.createElement('div');
    msgEl.className = 'help-message system';
    msgEl.innerHTML = `
        <div class="help-message-avatar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            </svg>
        </div>
        <div class="help-message-content">${escapeHtml(text)}</div>
    `;
    messagesContainer.appendChild(msgEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function resetHelpPanel() {
    const messagesContainer = document.getElementById('help-messages');
    messagesContainer.innerHTML = `
        <div class="help-message system">
            <div class="help-message-avatar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                </svg>
            </div>
            <div class="help-message-content">
                <p>ChemEngへようこそ! 何かお手伝いできますか?</p>
                <p class="help-message-hint">下のトピックを選択するか、質問を入力してください。</p>
            </div>
        </div>
        <div class="help-quick-actions" id="help-quick-actions">
            <button class="help-quick-btn" data-topic="overview">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="16" x2="12" y2="12"/>
                    <line x1="12" y1="8" x2="12.01" y2="8"/>
                </svg>
                ChemEngとは?
            </button>
            <button class="help-quick-btn" data-topic="property">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                物性推算の使い方
            </button>
            <button class="help-quick-btn" data-topic="distillation">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="8" y="2" width="8" height="20" rx="1"/>
                    <line x1="8" y1="10" x2="16" y2="10"/>
                    <line x1="8" y1="14" x2="16" y2="14"/>
                </svg>
                蒸留塔設計の使い方
            </button>
            <button class="help-quick-btn" data-topic="mass_balance">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="16"/>
                    <line x1="8" y1="12" x2="16" y2="12"/>
                </svg>
                物質収支の使い方
            </button>
            <button class="help-quick-btn" data-topic="heat_balance">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="5"/>
                    <line x1="12" y1="1" x2="12" y2="3"/>
                    <line x1="12" y1="21" x2="12" y2="23"/>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                    <line x1="1" y1="12" x2="3" y2="12"/>
                    <line x1="21" y1="12" x2="23" y2="12"/>
                </svg>
                熱収支の使い方
            </button>
        </div>
    `;

    // Re-attach event listeners
    document.querySelectorAll('.help-quick-btn').forEach(btn => {
        btn.onclick = () => {
            const topic = btn.dataset.topic;
            showHelpTopic(topic);
        };
    });
}
