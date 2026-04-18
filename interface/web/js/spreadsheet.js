// ==================== Spreadsheet Grid View ====================
// Excel-like grid for chemical engineering calculations using jspreadsheet CE

let spreadsheetInstance = null;
let spreadsheetStepsInstance = null;
let currentSpreadsheetSkill = null;

// Skill parameter definitions for grid layout
const SPREADSHEET_SKILLS = {
    heat_balance: {
        inputs: [
            { name: 'substance', label: '物質 / Substance', type: 'text', default: 'water' },
            { name: 'flow_rate', label: '流量 / Flow Rate', unit: 'mol/s', type: 'numeric', default: 100 },
            { name: 'inlet_temperature', label: '入口温度 / Inlet Temp', unit: 'K', type: 'numeric', default: 300 },
            { name: 'outlet_temperature', label: '出口温度 / Outlet Temp', unit: 'K', type: 'numeric', default: 400 },
            { name: 'pressure', label: '圧力 / Pressure', unit: 'Pa', type: 'numeric', default: 101325 },
            { name: 'phase_change', label: '相変化 / Phase Change', type: 'checkbox', default: true },
            { name: 'heat_of_reaction', label: '反応熱 / Rxn Heat', unit: 'J/mol', type: 'numeric', default: 0 },
            { name: 'efficiency', label: '熱効率 / Efficiency', unit: '-', type: 'numeric', default: 1.0 },
        ],
        outputs: [
            { name: 'sensible_heat', label: '顕熱 / Sensible Heat', unit: 'kW' },
            { name: 'latent_heat', label: '潜熱 / Latent Heat', unit: 'kW' },
            { name: 'reaction_heat', label: '反応熱 / Reaction Heat', unit: 'kW' },
            { name: 'total_heat_duty', label: '合計熱負荷 / Total Duty', unit: 'kW' },
            { name: 'actual_heat_duty', label: '実際熱負荷 / Actual Duty', unit: 'kW' },
        ],
    },
    mass_balance: {
        inputs: [
            { name: 'process_type', label: 'プロセスタイプ / Process Type', type: 'text', default: 'simple_mixing' },
            { name: 'components', label: '成分リスト / Components', type: 'text', default: 'A,B' },
            { name: 'inlet_count', label: '入口数 / Inlet Count', unit: '-', type: 'numeric', default: 2 },
            { name: 'outlet_count', label: '出口数 / Outlet Count', unit: '-', type: 'numeric', default: 1 },
        ],
        outputs: [
            { name: 'total_inlet_flow', label: '入口合計流量 / Total Inlet', unit: 'mol/s' },
            { name: 'total_outlet_flow', label: '出口合計流量 / Total Outlet', unit: 'mol/s' },
            { name: 'closure_error', label: '収支誤差 / Closure Error', unit: '%' },
        ],
    },
    distillation: {
        inputs: [
            { name: 'light_component', label: '軽沸成分 / Light Comp', type: 'text', default: 'benzene' },
            { name: 'heavy_component', label: '重沸成分 / Heavy Comp', type: 'text', default: 'toluene' },
            { name: 'feed_flow', label: '原料流量 / Feed Flow', unit: 'mol/s', type: 'numeric', default: 100 },
            { name: 'feed_composition', label: '原料組成 / Feed Comp', unit: 'mol frac', type: 'numeric', default: 0.5 },
            { name: 'distillate_composition', label: '留出組成 / Dist Comp', unit: 'mol frac', type: 'numeric', default: 0.95 },
            { name: 'bottoms_composition', label: '缶出組成 / Bot Comp', unit: 'mol frac', type: 'numeric', default: 0.05 },
            { name: 'pressure', label: '操作圧力 / Pressure', unit: 'Pa', type: 'numeric', default: 101325 },
            { name: 'reflux_ratio', label: '還流比 / Reflux Ratio', unit: '-', type: 'numeric', default: 2.0 },
        ],
        outputs: [
            { name: 'theoretical_stages', label: '理論段数 / Stages', unit: '-' },
            { name: 'minimum_reflux_ratio', label: '最小還流比 / Min RR', unit: '-' },
            { name: 'distillate_flow', label: '留出流量 / Dist Flow', unit: 'mol/s' },
            { name: 'bottoms_flow', label: '缶出流量 / Bot Flow', unit: 'mol/s' },
            { name: 'condenser_duty', label: '凝縮器負荷 / Cond Duty', unit: 'kW' },
            { name: 'reboiler_duty', label: 'リボイラー負荷 / Reb Duty', unit: 'kW' },
        ],
    },
};

function initSpreadsheetView(skillId) {
    const config = SPREADSHEET_SKILLS[skillId];
    if (!config) return;

    currentSpreadsheetSkill = skillId;
    const container = document.getElementById('spreadsheet-container');
    if (!container) return;

    // Clear previous
    container.innerHTML = '';
    if (spreadsheetInstance) {
        try { jspreadsheet.destroy(document.getElementById('spreadsheet-grid')); } catch(e) {}
    }

    // Create grid container
    const gridDiv = document.createElement('div');
    gridDiv.id = 'spreadsheet-grid';
    container.appendChild(gridDiv);

    // Build data rows
    const data = [];
    const inputStartRow = 0;

    // Header row
    data.push(['--- INPUT PARAMETERS ---', '', '', '']);

    // Input rows
    config.inputs.forEach(param => {
        data.push([param.label, param.default ?? '', param.unit || '', 'input']);
    });

    // Separator
    data.push(['--- OUTPUT RESULTS ---', '', '', '']);

    // Output rows (initially empty)
    config.outputs.forEach(param => {
        data.push([param.label, '', param.unit || '', 'output']);
    });

    const totalRows = data.length;
    const inputEnd = 1 + config.inputs.length;  // after header + inputs
    const outputStart = inputEnd + 1;  // after separator

    spreadsheetInstance = jspreadsheet(gridDiv, {
        data: data,
        columns: [
            { title: 'パラメータ / Parameter', width: 250, readOnly: true },
            { title: '値 / Value', width: 180 },
            { title: '単位 / Unit', width: 100, readOnly: true },
            { title: 'Type', width: 1 },  // hidden column for row type
        ],
        style: buildSpreadsheetStyles(data, inputEnd, outputStart),
        columnSorting: false,
        allowInsertRow: false,
        allowInsertColumn: false,
        allowDeleteRow: false,
        allowDeleteColumn: false,
        allowRenameColumn: false,
        about: false,
        onchange: function(instance, cell, x, y, value) {
            // Only auto-calculate when input values change
            if (y >= 1 && y < inputEnd && x === 1) {
                debounceCalculate(skillId);
            }
        },
    });

    // Make output cells read-only
    for (let r = outputStart; r < totalRows; r++) {
        spreadsheetInstance.setReadOnly(r, 1, true);
    }
    // Make header/separator rows fully read-only
    [0, inputEnd].forEach(r => {
        for (let c = 0; c < 4; c++) {
            spreadsheetInstance.setReadOnly(r, c, true);
        }
    });

    // Hide type column
    spreadsheetInstance.hideColumn(3);

    // Initial calculation
    debounceCalculate(skillId);
}

function buildSpreadsheetStyles(data, inputEnd, outputStart) {
    const styles = {};
    data.forEach((row, r) => {
        if (r === 0 || r === inputEnd) {
            // Header rows
            for (let c = 0; c < 4; c++) {
                styles[`${String.fromCharCode(65 + c)}${r + 1}`] = 'font-weight: bold; background-color: #1a1a2e; color: #00d4ff;';
            }
        } else if (r >= outputStart) {
            // Output rows - shaded
            styles[`B${r + 1}`] = 'background-color: #0d1117; color: #7ee787; font-weight: 500;';
        }
    });
    return styles;
}

let calcDebounceTimer = null;
function debounceCalculate(skillId) {
    if (calcDebounceTimer) clearTimeout(calcDebounceTimer);
    calcDebounceTimer = setTimeout(() => runSpreadsheetCalculation(skillId), 600);
}

async function runSpreadsheetCalculation(skillId) {
    const config = SPREADSHEET_SKILLS[skillId];
    if (!config || !spreadsheetInstance) return;

    // Gather input values from spreadsheet
    const params = {};
    config.inputs.forEach((param, i) => {
        const row = i + 1; // skip header
        const rawValue = spreadsheetInstance.getValueFromCoords(1, row);

        if (param.type === 'numeric') {
            const num = parseFloat(rawValue);
            if (!isNaN(num)) params[param.name] = num;
        } else if (param.type === 'checkbox') {
            params[param.name] = rawValue === true || rawValue === 'true' || rawValue === '1';
        } else {
            params[param.name] = rawValue;
        }
    });

    try {
        const response = await fetch(`/api/v1/calculate/${skillId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ parameters: params }),
        });
        const result = await response.json();

        if (result.success) {
            // Update output cells
            const outputStart = 1 + config.inputs.length + 1; // header + inputs + separator
            config.outputs.forEach((param, i) => {
                const row = outputStart + i;
                const value = result.outputs[param.name];
                const displayValue = formatValue(value);
                spreadsheetInstance.setValueFromCoords(1, row, displayValue, true);
            });

            // Show calculation steps if available
            if (result.outputs.calculation_steps) {
                renderStepsGrid(result.outputs.calculation_steps);
            }
        } else {
            toast(formatApiErrors(result.errors, result.warnings), 'error');
        }
    } catch (err) {
        console.error('Spreadsheet calculation error:', err);
    }
}

function formatValue(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'number') {
        if (Math.abs(value) >= 1e6 || (Math.abs(value) < 0.01 && value !== 0)) {
            return value.toExponential(4);
        }
        return Number(value.toFixed(4)).toString();
    }
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
}

function renderStepsGrid(steps) {
    const container = document.getElementById('spreadsheet-steps');
    if (!container || !steps || !Array.isArray(steps)) return;

    container.innerHTML = '<h4 class="steps-title">計算ステップ / Calculation Steps</h4>';

    const stepsDiv = document.createElement('div');
    stepsDiv.id = 'spreadsheet-steps-grid';
    container.appendChild(stepsDiv);

    const data = [];
    steps.forEach(step => {
        data.push([`Step ${step.step}`, step.title || '', '', '']);
        if (step.description) {
            data.push(['', step.description, '', '']);
        }
        if (step.formulas) {
            step.formulas.forEach(f => data.push(['', '', f, '']));
        }
        if (step.values) {
            Object.entries(step.values).forEach(([k, v]) => {
                data.push(['', k, formatValue(v), '']);
            });
        }
    });

    if (data.length === 0) return;

    spreadsheetStepsInstance = jspreadsheet(stepsDiv, {
        data: data,
        columns: [
            { title: 'Step', width: 100, readOnly: true },
            { title: 'Description', width: 250, readOnly: true },
            { title: 'Formula / Value', width: 250, readOnly: true },
            { title: '', width: 1, readOnly: true },
        ],
        columnSorting: false,
        allowInsertRow: false,
        allowInsertColumn: false,
        allowDeleteRow: false,
        allowDeleteColumn: false,
        editable: false,
        about: false,
    });
}

function destroySpreadsheet() {
    if (spreadsheetInstance) {
        try {
            const el = document.getElementById('spreadsheet-grid');
            if (el) jspreadsheet.destroy(el);
        } catch(e) {}
        spreadsheetInstance = null;
    }
    if (spreadsheetStepsInstance) {
        try {
            const el = document.getElementById('spreadsheet-steps-grid');
            if (el) jspreadsheet.destroy(el);
        } catch(e) {}
        spreadsheetStepsInstance = null;
    }
}
