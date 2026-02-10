// ==================== Charts (Chart.js) ====================

// ==================== Property Chart ====================
function initPropertyChart() {
    document.getElementById('gen-chart').onclick = async () => {
        if (!lastResult) return toast('Run calculation first', 'warning');
        const tMin = parseFloat(document.getElementById('chart-tmin').value) || 280;
        const tMax = parseFloat(document.getElementById('chart-tmax').value) || 400;
        const { params } = lastResult;
        toast('Generating chart data...');

        const temps = [], vals = [];
        const step = (tMax - tMin) / 20;
        for (let t = tMin; t <= tMax; t += step) {
            temps.push(t);
            try {
                const res = await fetch(`${API_BASE}/calculate/property_estimation`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ parameters: { substance: params.substance, property: params.property, temperature: t, pressure: params.pressure }})
                });
                const data = await res.json();
                const p = PROPERTIES[params.property] || { factor: 1 };
                vals.push(data.success ? data.outputs.value * p.factor : null);
            } catch { vals.push(null); }
        }

        const ctx = document.getElementById('prop-chart').getContext('2d');
        const p = PROPERTIES[params.property] || { name: params.property, unit: '' };
        if (propChart) propChart.destroy();

        const isDark = !document.documentElement.hasAttribute('data-theme') || document.documentElement.getAttribute('data-theme') === 'dark';
        const gridColor = isDark ? 'rgba(80, 160, 180, 0.15)' : 'rgba(60, 120, 160, 0.1)';
        const textColor = isDark ? '#7a9aa8' : '#5a7a8a';

        propChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: temps.map(t => t.toFixed(0)),
                datasets: [{ label: `${p.name} (${p.unit})`, data: vals, borderColor: '#00d4ff', backgroundColor: 'rgba(0, 212, 255, 0.1)', tension: 0.4, fill: true, borderWidth: 2, pointRadius: 0 }]
            },
            options: {
                responsive: true,
                interaction: { intersect: false, mode: 'index' },
                plugins: { legend: { labels: { color: textColor, font: { family: 'DM Mono' }}}},
                scales: {
                    x: { title: { display: true, text: 'Temperature (K)', color: textColor }, ticks: { color: textColor }, grid: { color: gridColor }},
                    y: { title: { display: true, text: p.unit, color: textColor }, ticks: { color: textColor }, grid: { color: gridColor }}
                }
            }
        });
        toast('Chart generated');
    };
}

// ==================== T-x-y Diagram ====================
let txyChart = null;

function initTxyDiagram() {
    document.getElementById('show-txy-btn').onclick = async () => {
        const form = document.getElementById('distillation-form');
        const fd = new FormData(form);
        const lightComp = fd.get('light_component');
        const heavyComp = fd.get('heavy_component');

        if (!lightComp || !heavyComp) {
            toast('Please enter both components', 'warning');
            return;
        }

        showLoading();

        try {
            const res = await fetch(`${API_BASE}/txy-diagram?light_component=${encodeURIComponent(lightComp)}&heavy_component=${encodeURIComponent(heavyComp)}&pressure=101325&points=21`, {
                method: 'POST'
            });
            const data = await res.json();

            if (data.success) {
                // Show modal
                document.getElementById('txy-modal').classList.remove('hidden');

                // Create chart data
                const bubbleData = data.x.map((x, i) => ({ x: x, y: data.T_bubble[i] - 273.15 }));
                const dewData = data.x.map((x, i) => ({ x: data.y[i], y: data.T_bubble[i] - 273.15 }));

                // Destroy previous chart if exists
                if (txyChart) {
                    txyChart.destroy();
                }

                // Create new chart
                const ctx = document.getElementById('txy-chart').getContext('2d');
                txyChart = new Chart(ctx, {
                    type: 'scatter',
                    data: {
                        datasets: [
                            {
                                label: 'Bubble Point (液相線)',
                                data: bubbleData,
                                borderColor: '#00d4ff',
                                backgroundColor: 'rgba(0, 212, 255, 0.1)',
                                showLine: true,
                                fill: false,
                                tension: 0.3,
                                pointRadius: 3,
                            },
                            {
                                label: 'Dew Point (気相線)',
                                data: dewData,
                                borderColor: '#ff6b9d',
                                backgroundColor: 'rgba(255, 107, 157, 0.1)',
                                showLine: true,
                                fill: false,
                                tension: 0.3,
                                pointRadius: 3,
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {
                            title: {
                                display: true,
                                text: `${lightComp} - ${heavyComp} System @ 101.325 kPa`,
                                color: '#e8f4f8',
                                font: { size: 14 }
                            },
                            legend: {
                                labels: { color: '#7a9aa8' }
                            }
                        },
                        scales: {
                            x: {
                                type: 'linear',
                                min: 0,
                                max: 1,
                                title: {
                                    display: true,
                                    text: `x, y (${lightComp} mole fraction)`,
                                    color: '#7a9aa8'
                                },
                                grid: { color: 'rgba(80, 160, 180, 0.1)' },
                                ticks: { color: '#7a9aa8' }
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: 'Temperature (°C)',
                                    color: '#7a9aa8'
                                },
                                grid: { color: 'rgba(80, 160, 180, 0.1)' },
                                ticks: { color: '#7a9aa8' }
                            }
                        }
                    }
                });

                // Update info
                const bpLight = data.bp_light ? (data.bp_light - 273.15).toFixed(1) : '?';
                const bpHeavy = data.bp_heavy ? (data.bp_heavy - 273.15).toFixed(1) : '?';
                const safeLightComp = escapeHtml(lightComp);
                const safeHeavyComp = escapeHtml(heavyComp);
                document.getElementById('txy-info').innerHTML = `
                    <strong>${safeLightComp}</strong> bp: ${bpLight}°C |
                    <strong>${safeHeavyComp}</strong> bp: ${bpHeavy}°C
                `;

                toast('T-x-y diagram generated');
            } else {
                toast('Error: ' + (data.error || 'Unknown'), 'error');
            }
        } catch (err) {
            toast('Connection error: ' + err.message, 'error');
        }

        hideLoading();
    };

    // Close modal
    document.getElementById('close-txy-modal').onclick = () => {
        document.getElementById('txy-modal').classList.add('hidden');
    };

    document.getElementById('txy-modal').onclick = (e) => {
        if (e.target.id === 'txy-modal') {
            document.getElementById('txy-modal').classList.add('hidden');
        }
    };
}

// ==================== LCOH Breakdown Bar Chart ====================
function drawLcohBreakdownChart(breakdown, total) {
    const container = document.getElementById('lcoh-breakdown-chart');
    const items = [
        { label: 'CAPEX', value: breakdown.capex, color: 'var(--accent-teal)' },
        { label: 'Energy', value: breakdown.energy, color: 'var(--accent-amber)' },
        { label: 'OPEX', value: breakdown.opex, color: 'var(--accent-cyan)' },
        { label: 'Labor', value: breakdown.labor, color: 'var(--accent-rose)' },
        { label: 'Maintenance', value: breakdown.maintenance, color: 'var(--accent-violet)' },
        { label: 'Stack', value: breakdown.stack_replacement, color: 'var(--accent-cyan)' },
        { label: 'Water', value: breakdown.water, color: 'var(--accent-teal)' },
        { label: 'Carbon', value: breakdown.carbon, color: 'var(--accent-violet)' }
    ].filter(i => i.value > 0.001);

    let html = '<div style="display: flex; flex-direction: column; gap: 0.5rem; height: 100%;">';
    items.forEach(item => {
        const pct = (item.value / total) * 100;
        html += `
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <div style="width: 70px; font-size: 0.75rem; color: var(--text-muted);">${item.label}</div>
                <div style="flex: 1; height: 24px; background: var(--glass-bg); border-radius: 4px; overflow: hidden;">
                    <div style="width: ${pct}%; height: 100%; background: ${item.color}; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px;">
                        <span style="font-size: 0.7rem; color: white; font-weight: 500;">${item.value.toFixed(2)}</span>
                    </div>
                </div>
                <div style="width: 45px; text-align: right; font-size: 0.75rem; color: var(--text-dim);">${pct.toFixed(1)}%</div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

// ==================== LCOH Sensitivity Chart ====================
function drawLcohSensitivityChart() {
    if (!lcohSensitivityData) return;

    const container = document.getElementById('lcoh-sensitivity-chart');
    let data, xLabel, xUnit;

    if (currentSensChart === 'electricity' && lcohSensitivityData.electricity_price) {
        data = lcohSensitivityData.electricity_price;
        xLabel = 'Electricity Price';
        xUnit = 'EUR/MWh';
    } else if (currentSensChart === 'gas' && lcohSensitivityData.natural_gas_price) {
        data = lcohSensitivityData.natural_gas_price;
        xLabel = 'Gas Price';
        xUnit = 'EUR/MWh';
    } else if (currentSensChart === 'capex' && lcohSensitivityData.capex) {
        data = lcohSensitivityData.capex;
        xLabel = 'CAPEX';
        xUnit = 'EUR/kW';
    } else if (currentSensChart === 'hours' && lcohSensitivityData.operating_hours) {
        data = lcohSensitivityData.operating_hours;
        xLabel = 'Operating Hours';
        xUnit = 'h/year';
    } else {
        // Fallback
        const available = Object.keys(lcohSensitivityData)[0];
        if (available) {
            data = lcohSensitivityData[available];
            xLabel = available;
            xUnit = '';
        }
    }

    if (!data || data.length === 0) {
        container.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-muted);">No sensitivity data</div>';
        return;
    }

    // Get min/max for scaling
    const lcohValues = data.map(d => d.lcoh);
    const minLcoh = Math.min(...lcohValues) * 0.9;
    const maxLcoh = Math.max(...lcohValues) * 1.1;

    // Draw SVG chart
    const width = Math.max(200, (container.clientWidth || 0) - 20);
    const height = 180;
    const padding = { left: 50, right: 20, top: 20, bottom: 30 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    let svg = `<svg width="${width}" height="${height}" style="overflow: visible;">`;

    // Y-axis labels
    const yTicks = 5;
    for (let i = 0; i <= yTicks; i++) {
        const y = padding.top + (chartHeight * i / yTicks);
        const val = maxLcoh - (maxLcoh - minLcoh) * i / yTicks;
        svg += `<text x="${padding.left - 5}" y="${y + 4}" text-anchor="end" font-size="10" fill="var(--text-muted)">${val.toFixed(1)}</text>`;
        svg += `<line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="var(--glass-border)" stroke-dasharray="2,2"/>`;
    }

    // X-axis and data points
    const xStep = chartWidth / (data.length - 1);
    let pathD = '';

    data.forEach((point, i) => {
        const x = padding.left + i * xStep;
        const y = padding.top + chartHeight * (1 - (point.lcoh - minLcoh) / (maxLcoh - minLcoh));
        const xVal = point.price || point.capex || point.hours || Object.values(point)[0];

        if (i === 0) pathD = `M ${x} ${y}`;
        else pathD += ` L ${x} ${y}`;

        // X label
        svg += `<text x="${x}" y="${height - 5}" text-anchor="middle" font-size="9" fill="var(--text-muted)">${xVal}</text>`;
        // Data point
        svg += `<circle cx="${x}" cy="${y}" r="4" fill="var(--accent-teal)"/>`;
        // Value label
        svg += `<text x="${x}" y="${y - 8}" text-anchor="middle" font-size="9" fill="var(--text-dim)">${point.lcoh.toFixed(2)}</text>`;
    });

    // Line
    svg += `<path d="${pathD}" fill="none" stroke="var(--accent-teal)" stroke-width="2"/>`;

    // Axis labels
    svg += `<text x="${padding.left - 35}" y="${height/2}" text-anchor="middle" font-size="10" fill="var(--text-muted)" transform="rotate(-90 ${padding.left - 35} ${height/2})">LCOH (EUR/kg)</text>`;
    svg += `<text x="${width/2}" y="${height + 10}" text-anchor="middle" font-size="10" fill="var(--text-muted)">${xLabel} (${xUnit})</text>`;

    svg += '</svg>';
    container.innerHTML = svg;
}

function initSensitivityChartButtons() {
    // Sensitivity chart buttons
    document.querySelectorAll('[data-sens]').forEach(btn => {
        btn.onclick = function() {
            document.querySelectorAll('[data-sens]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            const sens = this.dataset.sens;
            if (sens === 'electricity') currentSensChart = lcohSensitivityData?.electricity_price ? 'electricity' : 'gas';
            else if (sens === 'capex') currentSensChart = 'capex';
            else if (sens === 'hours') currentSensChart = 'hours';
            drawLcohSensitivityChart();
        };
    });
}

// ==================== Dashboard Chart ====================
let dashboardChart = null;

// Update dashboard chart
function updateDashboardChart(cases, chartType = 'bar') {
    const ctx = document.getElementById('dashboard-chart').getContext('2d');

    // Destroy existing chart
    if (dashboardChart) {
        dashboardChart.destroy();
    }

    // Prepare data for LCOH cases (most common use case)
    const lcohCases = cases.filter(c => c.type === 'lcoh');
    if (lcohCases.length > 0) {
        const labels = lcohCases.map(c => c.name.replace(/LCOH: /, '').substring(0, 30));
        const breakdownKeys = ['capex', 'energy', 'opex', 'stack_replacement', 'water', 'carbon_cost'];
        const breakdownLabels = ['CAPEX', 'Energy', 'OPEX', 'Stack', 'Water', 'Carbon'];
        const colors = ['#00d4ff', '#0fa', '#ffa726', '#a78bfa', '#ff6b9d', '#94a3b8'];

        const datasets = breakdownKeys.map((key, i) => ({
            label: breakdownLabels[i],
            data: lcohCases.map(c => c.result?.lcoh_breakdown?.[key] || 0),
            backgroundColor: colors[i],
            borderColor: colors[i],
            borderWidth: 1
        }));

        dashboardChart = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: 'rgba(255,255,255,0.8)', font: { size: 10 } }
                    },
                    title: {
                        display: true,
                        text: 'LCOH Cost Breakdown (EUR/kg H₂)',
                        color: 'rgba(255,255,255,0.9)'
                    }
                },
                scales: {
                    x: {
                        stacked: chartType === 'stacked',
                        ticks: { color: 'rgba(255,255,255,0.7)', font: { size: 9 } },
                        grid: { color: 'rgba(255,255,255,0.1)' }
                    },
                    y: {
                        stacked: chartType === 'stacked',
                        ticks: { color: 'rgba(255,255,255,0.7)' },
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        title: { display: true, text: 'EUR/kg H₂', color: 'rgba(255,255,255,0.7)' }
                    }
                }
            }
        });
    } else {
        // Generic bar chart for other types
        const labels = cases.map(c => c.name.substring(0, 25));
        const values = cases.map(c => parseFloat(c.mainValue) || 0);

        dashboardChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Value',
                    data: values,
                    backgroundColor: '#a78bfa',
                    borderColor: '#a78bfa',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        ticks: { color: 'rgba(255,255,255,0.7)', font: { size: 9 } },
                        grid: { color: 'rgba(255,255,255,0.1)' }
                    },
                    y: {
                        ticks: { color: 'rgba(255,255,255,0.7)' },
                        grid: { color: 'rgba(255,255,255,0.1)' }
                    }
                }
            }
        });
    }
}

// Set dashboard chart type
function setDashboardChartType(type) {
    document.querySelectorAll('.chart-type-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.chartType === type);
    });
    const cases = loadDashboardCases().filter(c => selectedCases.has(c.id));
    updateDashboardChart(cases, type);
}

// Export dashboard chart as PNG
function exportDashboardPNG() {
    if (!dashboardChart) {
        toast('No chart to export', 'warning');
        return;
    }
    const url = dashboardChart.toBase64Image();
    const a = document.createElement('a');
    a.href = url;
    a.download = `chemeng_dashboard_chart_${new Date().toISOString().slice(0,10)}.png`;
    a.click();
    toast('Chart exported successfully', 'success');
}

// Initialize all chart-related handlers
function initAllCharts() {
    initPropertyChart();
    initTxyDiagram();
    initSensitivityChartButtons();
}
