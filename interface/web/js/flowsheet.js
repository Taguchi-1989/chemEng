// ==================== Process Flowsheet Builder ====================
// Interactive process flow diagram editor using Drawflow

let flowsheetEditor = null;
let flowsheetData = null;

// ==================== Initialization ====================

function initFlowsheetEditor() {
    const container = document.getElementById('flowsheet-canvas');
    if (!container || typeof Drawflow === 'undefined') return;

    flowsheetEditor = new Drawflow(container);
    flowsheetEditor.reroute = true;
    flowsheetEditor.start();

    // Load saved flowsheet from localStorage
    const saved = localStorage.getItem('chemeng_flowsheet');
    if (saved) {
        try {
            flowsheetEditor.import(JSON.parse(saved));
        } catch(e) {
            console.warn('Failed to load saved flowsheet:', e);
        }
    }

    // Event handlers
    flowsheetEditor.on('nodeCreated', (id) => saveFlowsheet());
    flowsheetEditor.on('nodeRemoved', (id) => saveFlowsheet());
    flowsheetEditor.on('connectionCreated', (conn) => saveFlowsheet());
    flowsheetEditor.on('connectionRemoved', (conn) => saveFlowsheet());
    flowsheetEditor.on('nodeMoved', (id) => saveFlowsheet());

    // Double-click to edit block parameters
    container.addEventListener('dblclick', (e) => {
        const nodeEl = e.target.closest('.drawflow-node');
        if (nodeEl) {
            const nodeId = nodeEl.id.replace('node-', '');
            openBlockEditor(parseInt(nodeId));
        }
    });

    // Init drag from palette
    initBlockPalette();
}

// ==================== Block Palette ====================

const BLOCK_TYPES = {
    mixer: {
        name: 'ミキサー / Mixer',
        icon: `<svg viewBox="0 0 40 40" width="40" height="40"><polygon points="20,5 35,20 20,35 5,20" fill="none" stroke="currentColor" stroke-width="2"/><text x="20" y="24" text-anchor="middle" font-size="10">M</text></svg>`,
        inputs: 2, outputs: 1,
        defaultParams: {},
    },
    splitter: {
        name: 'スプリッター / Splitter',
        icon: `<svg viewBox="0 0 40 40" width="40" height="40"><polygon points="20,5 35,20 20,35 5,20" fill="none" stroke="currentColor" stroke-width="2"/><text x="20" y="24" text-anchor="middle" font-size="10">S</text></svg>`,
        inputs: 1, outputs: 2,
        defaultParams: { split_ratio: 0.5 },
    },
    heat_exchanger: {
        name: '熱交換器 / Heat Exchanger',
        icon: `<svg viewBox="0 0 40 40" width="40" height="40"><rect x="5" y="8" width="30" height="24" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><line x1="5" y1="20" x2="35" y2="20" stroke="currentColor" stroke-width="1" stroke-dasharray="3,2"/><text x="20" y="17" text-anchor="middle" font-size="8">HX</text></svg>`,
        inputs: 1, outputs: 1,
        defaultParams: { outlet_temperature: 350, cp: 75.0 },
    },
    reactor: {
        name: '反応器 / Reactor',
        icon: `<svg viewBox="0 0 40 40" width="40" height="40"><circle cx="20" cy="20" r="15" fill="none" stroke="currentColor" stroke-width="2"/><text x="20" y="24" text-anchor="middle" font-size="10">R</text></svg>`,
        inputs: 1, outputs: 1,
        defaultParams: { key_component: '', conversion: 0.8, stoichiometry: {}, outlet_temperature: 350 },
    },
    flash: {
        name: 'フラッシュ / Flash Drum',
        icon: `<svg viewBox="0 0 40 40" width="40" height="40"><rect x="10" y="5" width="20" height="30" rx="10" fill="none" stroke="currentColor" stroke-width="2"/><line x1="10" y1="20" x2="30" y2="20" stroke="currentColor" stroke-width="1" stroke-dasharray="2,2"/><text x="20" y="17" text-anchor="middle" font-size="7">F</text></svg>`,
        inputs: 1, outputs: 2,
        defaultParams: { vapor_fraction: 0.5, k_values: {} },
    },
};

function initBlockPalette() {
    const palette = document.getElementById('block-palette');
    if (!palette) return;

    palette.innerHTML = '<h4 class="palette-title">ブロック / Blocks</h4>';

    Object.entries(BLOCK_TYPES).forEach(([type, config]) => {
        const item = document.createElement('div');
        item.className = 'palette-item';
        item.draggable = true;
        item.dataset.blockType = type;
        item.innerHTML = `
            <div class="palette-icon">${config.icon}</div>
            <span class="palette-label">${config.name}</span>
        `;

        item.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('block-type', type);
        });

        // Also support click-to-add
        item.addEventListener('click', () => {
            addBlockToFlowsheet(type);
        });

        palette.appendChild(item);
    });

    // Drop zone
    const canvas = document.getElementById('flowsheet-canvas');
    if (canvas) {
        canvas.addEventListener('dragover', (e) => e.preventDefault());
        canvas.addEventListener('drop', (e) => {
            e.preventDefault();
            const type = e.dataTransfer.getData('block-type');
            if (type) {
                addBlockToFlowsheet(type, e.clientX, e.clientY);
            }
        });
    }
}

function addBlockToFlowsheet(blockType, clientX, clientY) {
    if (!flowsheetEditor) return;

    const config = BLOCK_TYPES[blockType];
    if (!config) return;

    // Calculate position
    const canvas = document.getElementById('flowsheet-canvas');
    const rect = canvas ? canvas.getBoundingClientRect() : { left: 0, top: 0 };
    const posX = clientX ? clientX - rect.left : 250;
    const posY = clientY ? clientY - rect.top : 200;

    const blockCount = Object.keys(flowsheetEditor.drawflow.drawflow.Home.data).length;
    const blockName = `${blockType.toUpperCase()}-${blockCount + 1}`;

    const html = `
        <div class="flowsheet-block" data-block-type="${blockType}">
            <div class="block-icon">${config.icon}</div>
            <div class="block-name">${blockName}</div>
            <div class="block-type-label">${config.name.split('/')[0].trim()}</div>
        </div>
    `;

    flowsheetEditor.addNode(
        blockName,
        config.inputs,
        config.outputs,
        posX, posY,
        `block-${blockType}`,
        { blockType: blockType, params: { ...config.defaultParams }, name: blockName },
        html
    );

    saveFlowsheet();
}

// ==================== Block Parameter Editor ====================

function openBlockEditor(nodeId) {
    if (!flowsheetEditor) return;

    const nodeData = flowsheetEditor.getNodeFromId(nodeId);
    if (!nodeData) return;

    const blockType = nodeData.data.blockType;
    const params = nodeData.data.params || {};
    const blockName = nodeData.data.name || nodeData.name;

    // Create modal
    const overlay = document.createElement('div');
    overlay.className = 'block-editor-overlay';
    overlay.innerHTML = `
        <div class="block-editor-modal">
            <div class="block-editor-header">
                <h3>${blockName} - パラメータ編集</h3>
                <button class="block-editor-close">&times;</button>
            </div>
            <div class="block-editor-body">
                ${generateParamForm(blockType, params)}
            </div>
            <div class="block-editor-footer">
                <button class="btn-cancel">キャンセル</button>
                <button class="btn-save">保存 / Save</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    // Event handlers
    overlay.querySelector('.block-editor-close').onclick = () => overlay.remove();
    overlay.querySelector('.btn-cancel').onclick = () => overlay.remove();
    overlay.querySelector('.btn-save').onclick = () => {
        const form = overlay.querySelector('.block-editor-body');
        const newParams = collectParamValues(form, blockType);
        nodeData.data.params = newParams;
        flowsheetEditor.updateNodeDataFromId(nodeId, nodeData.data);
        saveFlowsheet();
        overlay.remove();
        toast('パラメータを保存しました / Parameters saved', 'success');
    };
    overlay.addEventListener('keydown', e => { if (e.key === 'Escape') overlay.remove(); });
}

function generateParamForm(blockType, currentParams) {
    const paramDefs = {
        mixer: [],
        splitter: [
            { name: 'split_ratio', label: '分割比 / Split Ratio', type: 'number', min: 0, max: 1, step: 0.01 },
        ],
        heat_exchanger: [
            { name: 'outlet_temperature', label: '出口温度 / Outlet Temp (K)', type: 'number', min: 0 },
            { name: 'duty', label: '熱負荷 / Duty (kW)', type: 'number' },
            { name: 'cp', label: 'Cp (J/mol/K)', type: 'number', min: 0 },
        ],
        reactor: [
            { name: 'key_component', label: 'キー成分 / Key Component', type: 'text' },
            { name: 'conversion', label: '転化率 / Conversion', type: 'number', min: 0, max: 1, step: 0.01 },
            { name: 'outlet_temperature', label: '出口温度 / Outlet Temp (K)', type: 'number', min: 0 },
        ],
        flash: [
            { name: 'vapor_fraction', label: '気相割合 / Vapor Fraction', type: 'number', min: 0, max: 1, step: 0.01 },
            { name: 'temperature', label: '温度 / Temperature (K)', type: 'number', min: 0 },
            { name: 'pressure', label: '圧力 / Pressure (Pa)', type: 'number', min: 0 },
        ],
    };

    const defs = paramDefs[blockType] || [];
    if (defs.length === 0) return '<p>パラメータなし / No parameters</p>';

    return defs.map(d => {
        const value = currentParams[d.name] ?? '';
        const attrs = [];
        if (d.min !== undefined) attrs.push(`min="${d.min}"`);
        if (d.max !== undefined) attrs.push(`max="${d.max}"`);
        if (d.step !== undefined) attrs.push(`step="${d.step}"`);
        return `
            <div class="param-row">
                <label>${d.label}</label>
                <input type="${d.type}" name="${d.name}" value="${value}" ${attrs.join(' ')} />
            </div>
        `;
    }).join('');
}

function collectParamValues(form, blockType) {
    const params = {};
    form.querySelectorAll('input').forEach(input => {
        const name = input.name;
        if (input.type === 'number') {
            const v = parseFloat(input.value);
            if (!isNaN(v)) params[name] = v;
        } else {
            if (input.value) params[name] = input.value;
        }
    });
    return params;
}

// ==================== Flowsheet Calculation ====================

async function calculateFlowsheet() {
    if (!flowsheetEditor) return;

    const flowsheetPayload = buildFlowsheetPayload();
    if (!flowsheetPayload) {
        toast('フローシートが空です / Flowsheet is empty', 'warning');
        return;
    }

    const calcBtn = document.getElementById('btn-calculate-flowsheet');
    if (calcBtn) {
        calcBtn.disabled = true;
        calcBtn.textContent = '計算中... / Calculating...';
    }

    try {
        const response = await fetch('/api/v1/flowsheet/calculate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(flowsheetPayload),
        });
        const result = await response.json();

        if (result.success) {
            updateFlowsheetResults(result);
            toast('計算完了 / Calculation complete', 'success');
        } else {
            const errMsg = result.warnings ? result.warnings.join('; ') : 'Calculation failed';
            toast(errMsg, 'error');
        }

        // Show convergence if available
        if (result.convergence) {
            renderFlowsheetConvergence(result.convergence);
        }
    } catch (err) {
        console.error('Flowsheet calculation error:', err);
        toast('計算エラー / Calculation error', 'error');
    } finally {
        if (calcBtn) {
            calcBtn.disabled = false;
            calcBtn.textContent = '計算実行 / Calculate';
        }
    }
}

function buildFlowsheetPayload() {
    if (!flowsheetEditor) return null;

    const drawflowData = flowsheetEditor.export();
    const nodes = drawflowData.drawflow.Home.data;

    if (Object.keys(nodes).length === 0) return null;

    const blocks = {};
    const streams = {};
    const components = [];
    let streamCounter = 0;

    // Build blocks
    Object.entries(nodes).forEach(([nodeId, node]) => {
        const blockId = `B${nodeId}`;
        blocks[blockId] = {
            id: blockId,
            block_type: node.data.blockType,
            name: node.data.name || node.name,
            parameters: node.data.params || {},
            inlet_streams: [],
            outlet_streams: [],
            position: { x: node.pos_x, y: node.pos_y },
        };
    });

    // Build streams from connections
    Object.entries(nodes).forEach(([nodeId, node]) => {
        const srcBlockId = `B${nodeId}`;

        Object.entries(node.outputs || {}).forEach(([outputKey, output]) => {
            (output.connections || []).forEach(conn => {
                streamCounter++;
                const streamId = `S${streamCounter}`;
                const tgtBlockId = `B${conn.node}`;

                streams[streamId] = {
                    id: streamId,
                    name: `Stream ${streamCounter}`,
                    source_block: srcBlockId,
                    target_block: tgtBlockId,
                    temperature: 298.15,
                    pressure: 101325,
                    total_flow: 100,
                    composition: {},
                    phase: 'liquid',
                };

                if (blocks[srcBlockId]) blocks[srcBlockId].outlet_streams.push(streamId);
                if (blocks[tgtBlockId]) blocks[tgtBlockId].inlet_streams.push(streamId);
            });
        });
    });

    // Find feed blocks (no inlets) and add feed streams
    Object.values(blocks).forEach(block => {
        if (block.inlet_streams.length === 0) {
            streamCounter++;
            const feedStreamId = `S${streamCounter}`;
            streams[feedStreamId] = {
                id: feedStreamId,
                name: `Feed to ${block.name}`,
                source_block: null,
                target_block: block.id,
                temperature: 298.15,
                pressure: 101325,
                total_flow: 100,
                composition: {},
                phase: 'liquid',
            };
            block.inlet_streams.push(feedStreamId);
        }
    });

    return {
        id: 'flowsheet-1',
        name: 'Process Flowsheet',
        components: components,
        blocks: blocks,
        streams: streams,
        tear_streams: [],
        convergence_config: {
            method: 'successive_substitution',
            max_iterations: 50,
            tolerance: 1e-6,
        },
    };
}

function updateFlowsheetResults(result) {
    if (!result.flowsheet || !flowsheetEditor) return;

    const blocks = result.flowsheet.blocks || {};
    const streams = result.flowsheet.streams || {};

    // Update node displays with results
    Object.entries(blocks).forEach(([blockId, block]) => {
        const nodeId = blockId.replace('B', '');
        const nodeEl = document.getElementById(`node-${nodeId}`);
        if (!nodeEl) return;

        // Remove old results
        const oldResult = nodeEl.querySelector('.block-result');
        if (oldResult) oldResult.remove();

        // Add result display
        if (block.calculation_result && !block.calculation_result.error) {
            const resultDiv = document.createElement('div');
            resultDiv.className = 'block-result';
            const resultEntries = Object.entries(block.calculation_result)
                .filter(([k]) => k !== 'outlet' && k !== 'outlet_1' && k !== 'outlet_2' && k !== 'vapor_outlet' && k !== 'liquid_outlet')
                .slice(0, 3);
            resultDiv.innerHTML = resultEntries
                .map(([k, v]) => `<div class="result-line">${k}: ${typeof v === 'number' ? v.toFixed(2) : v}</div>`)
                .join('');
            nodeEl.querySelector('.drawflow_content_node').appendChild(resultDiv);
        }
    });

    // Update stream labels
    const resultsPanel = document.getElementById('flowsheet-results');
    if (resultsPanel) {
        let html = '<h4>ストリーム結果 / Stream Results</h4><table class="stream-results-table"><thead><tr><th>Stream</th><th>Flow (mol/s)</th><th>T (K)</th><th>P (Pa)</th><th>Phase</th></tr></thead><tbody>';
        Object.values(streams).forEach(s => {
            html += `<tr><td>${s.name}</td><td>${s.total_flow?.toFixed(2) ?? '-'}</td><td>${s.temperature?.toFixed(1) ?? '-'}</td><td>${s.pressure?.toFixed(0) ?? '-'}</td><td>${s.phase}</td></tr>`;
        });
        html += '</tbody></table>';
        resultsPanel.innerHTML = html;
    }
}

function renderFlowsheetConvergence(convergence) {
    const container = document.getElementById('convergence-panel');
    if (!container) return;

    container.innerHTML = `
        <h4>収束状況 / Convergence</h4>
        <p>${convergence.converged ? '✓ 収束しました' : '✕ 未収束'} (${convergence.iterations_used} iterations)</p>
    `;

    if (convergence.history && convergence.history.length > 1) {
        const chartCanvas = document.createElement('canvas');
        chartCanvas.id = 'convergence-chart';
        chartCanvas.width = 400;
        chartCanvas.height = 200;
        container.appendChild(chartCanvas);

        const labels = convergence.history.map(h => h.iteration);
        const residuals = convergence.history.map(h => h.max_residual);

        new Chart(chartCanvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: '最大残差 / Max Residual',
                    data: residuals,
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                    tension: 0.3,
                }],
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        type: 'logarithmic',
                        title: { display: true, text: 'Residual' },
                    },
                    x: {
                        title: { display: true, text: 'Iteration' },
                    },
                },
                plugins: {
                    legend: { display: false },
                },
            },
        });
    }
}

// ==================== Goal Seek ====================

function openGoalSeekDialog() {
    const payload = buildFlowsheetPayload();
    if (!payload) {
        toast('フローシートが空です / Flowsheet is empty', 'warning');
        return;
    }

    const blocks = payload.blocks;
    const streams = payload.streams;

    const overlay = document.createElement('div');
    overlay.className = 'block-editor-overlay';
    overlay.innerHTML = `
        <div class="block-editor-modal goal-seek-modal">
            <div class="block-editor-header">
                <h3>ゴールシーク / Goal Seek</h3>
                <button class="block-editor-close">&times;</button>
            </div>
            <div class="block-editor-body">
                <div class="param-row">
                    <label>目標変数 / Target Variable</label>
                    <select id="gs-target">
                        ${Object.values(streams).map(s =>
                            `<option value="streams.${s.id}.temperature">${s.name} - 温度/Temperature</option>
                             <option value="streams.${s.id}.total_flow">${s.name} - 流量/Flow</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="param-row">
                    <label>目標値 / Target Value</label>
                    <input type="number" id="gs-target-value" value="350" />
                </div>
                <div class="param-row">
                    <label>操作変数 / Manipulated Variable</label>
                    <select id="gs-manipulated">
                        ${Object.values(blocks).map(b => {
                            const params = b.parameters || {};
                            return Object.keys(params).map(p =>
                                `<option value="blocks.${b.id}.parameters.${p}">${b.name} - ${p}</option>`
                            ).join('');
                        }).join('')}
                    </select>
                </div>
                <div class="param-row">
                    <label>下限 / Lower Bound</label>
                    <input type="number" id="gs-lower" value="200" />
                </div>
                <div class="param-row">
                    <label>上限 / Upper Bound</label>
                    <input type="number" id="gs-upper" value="500" />
                </div>
            </div>
            <div class="block-editor-footer">
                <button class="btn-cancel">キャンセル</button>
                <button class="btn-save" id="btn-run-goalseek">実行 / Run</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    overlay.querySelector('.block-editor-close').onclick = () => overlay.remove();
    overlay.querySelector('.btn-cancel').onclick = () => overlay.remove();
    overlay.querySelector('#btn-run-goalseek').onclick = async () => {
        const gsPayload = {
            flowsheet: payload,
            target_variable: document.getElementById('gs-target').value,
            target_value: parseFloat(document.getElementById('gs-target-value').value),
            manipulated_variable: document.getElementById('gs-manipulated').value,
            lower_bound: parseFloat(document.getElementById('gs-lower').value),
            upper_bound: parseFloat(document.getElementById('gs-upper').value),
        };

        overlay.querySelector('#btn-run-goalseek').disabled = true;
        overlay.querySelector('#btn-run-goalseek').textContent = '計算中...';

        try {
            const resp = await fetch('/api/v1/flowsheet/goal-seek', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(gsPayload),
            });
            const result = await resp.json();

            if (result.success) {
                toast(`ゴールシーク完了: ${result.manipulated_value?.toFixed(4)}`, 'success');
                updateFlowsheetResults(result);
                if (result.convergence) renderFlowsheetConvergence(result.convergence);
            } else {
                toast(result.error || 'Goal seek failed', 'error');
            }
        } catch (err) {
            toast('ゴールシーク エラー / Goal seek error', 'error');
        }

        overlay.remove();
    };
}

// ==================== Mermaid Export ====================

async function exportMermaid() {
    const payload = buildFlowsheetPayload();
    if (!payload) return;

    try {
        const resp = await fetch('/api/v1/flowsheet/export-mermaid', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await resp.json();

        if (result.mermaid) {
            renderMermaidDiagram(result.mermaid);
        }
    } catch (err) {
        console.error('Mermaid export error:', err);
    }
}

function renderMermaidDiagram(mermaidText) {
    const container = document.getElementById('mermaid-container');
    if (!container || typeof mermaid === 'undefined') return;

    const div = document.createElement('div');
    div.className = 'mermaid';
    div.textContent = mermaidText;
    container.innerHTML = '';
    container.appendChild(div);
    mermaid.run({ nodes: [div] });
    container.classList.remove('hidden');
}

// ==================== Save/Load ====================

function saveFlowsheet() {
    if (!flowsheetEditor) return;
    try {
        const data = flowsheetEditor.export();
        localStorage.setItem('chemeng_flowsheet', JSON.stringify(data));
    } catch(e) {
        console.warn('Failed to save flowsheet:', e);
    }
}

function clearFlowsheet() {
    if (!flowsheetEditor) return;
    flowsheetEditor.clear();
    localStorage.removeItem('chemeng_flowsheet');
    const resultsPanel = document.getElementById('flowsheet-results');
    if (resultsPanel) resultsPanel.innerHTML = '';
    const convergencePanel = document.getElementById('convergence-panel');
    if (convergencePanel) convergencePanel.innerHTML = '';
    toast('フローシートをクリアしました / Flowsheet cleared', 'success');
}

function exportFlowsheetJSON() {
    const payload = buildFlowsheetPayload();
    if (!payload) return;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chemeng_flowsheet_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
}
