// ==================== Form Submission Handlers ====================

// ==================== Property Form ====================
function initPropertyForm() {
    document.getElementById('property-form').onsubmit = async e => {
        e.preventDefault();
        showLoading();
        const fd = new FormData(e.target);
        const tempU = activeUnits['prop-temp'] || 'K';
        const pressU = activeUnits['prop-press'] || 'Pa';
        const params = {
            substance: fd.get('substance'),
            property: fd.get('property'),
            temperature: UNITS.temperature[tempU].toBase(parseFloat(fd.get('temperature'))),
            pressure: UNITS.pressure[pressU].toBase(parseFloat(fd.get('pressure')))
        };
        try {
            const res = await fetch(`${API_BASE}/calculate/property_estimation`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parameters: params })
            });
            const data = await res.json();
            if (data.success) {
                const out = data.outputs;
                const p = PROPERTIES[params.property] || { name: params.property, unit: '', factor: 1 };
                document.getElementById('prop-substance').textContent = out.substance || params.substance;
                document.getElementById('prop-name').textContent = p.name;
                document.getElementById('prop-value').textContent = (out.value * p.factor).toFixed(4);
                document.getElementById('prop-unit').textContent = p.unit;
                document.getElementById('prop-temp-result').textContent = params.temperature.toFixed(1);
                document.getElementById('prop-press-result').textContent = (params.pressure / 1000).toFixed(1);
                if (out.calculation_steps?.length) document.getElementById('prop-steps').innerHTML = renderSteps(out.calculation_steps);
                lastResult = { params, outputs: out };
                document.getElementById('chart-tmin').value = Math.max(250, params.temperature - 50);
                document.getElementById('chart-tmax').value = Math.min(500, params.temperature + 50);
                saveHistory('property', params, out);
                showResult('property');
                toast('Calculation complete');
            } else {
                toast('Error: ' + (data.errors?.join(', ') || 'Unknown'), 'error');
                hideLoading();
            }
        } catch (err) {
            toast('Connection error: ' + err.message, 'error');
            hideLoading();
        }
    };
}

// ==================== Distillation Form ====================
function initDistillationForm() {
    document.getElementById('distillation-form').onsubmit = async e => {
        e.preventDefault();
        showLoading();
        const fd = new FormData(e.target);
        const params = {
            light_component: fd.get('light_component'),
            heavy_component: fd.get('heavy_component'),
            feed_flow_rate: parseFloat(fd.get('feed_flow_rate')),
            feed_composition: parseFloat(fd.get('feed_composition')),
            distillate_purity: parseFloat(fd.get('distillate_purity')),
            bottoms_purity: parseFloat(fd.get('bottoms_purity')),
            reflux_ratio_factor: parseFloat(fd.get('reflux_ratio_factor'))
        };
        try {
            const res = await fetch(`${API_BASE}/calculate/distillation`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parameters: params })
            });
            const data = await res.json();
            if (data.success) {
                const out = data.outputs;
                document.getElementById('dist-system').textContent = `${params.light_component} / ${params.heavy_component}`;
                document.getElementById('dist-stages').textContent = out.actual_stages;
                document.getElementById('dist-feed-stage').textContent = out.feed_stage;
                document.getElementById('dist-reflux').textContent = out.actual_reflux_ratio.toFixed(2);
                document.getElementById('dist-diam').textContent = out.column_diameter.toFixed(2);
                const fmt = kw => kw > 1000 ? `${(kw/1000).toFixed(1)} MW` : `${kw.toFixed(0)} kW`;
                document.getElementById('dist-qc').textContent = fmt(out.condenser_duty);
                document.getElementById('dist-qr').textContent = fmt(out.reboiler_duty);
                document.getElementById('dist-feed-label').textContent = `F = ${params.feed_flow_rate}`;
                document.getElementById('dist-d-label').textContent = `D = ${out.distillate_flow_rate.toFixed(1)}`;
                document.getElementById('dist-b-label').textContent = `B = ${out.bottoms_flow_rate.toFixed(1)}`;
                const trays = document.getElementById('dist-trays');
                trays.innerHTML = '';
                const num = out.actual_stages - 1;
                const spacing = 260 / (num + 1);
                for (let i = 1; i <= num; i++) {
                    const y = 70 + i * spacing;
                    trays.innerHTML += `<line x1="120" y1="${y}" x2="200" y2="${y}" stroke="var(--glass-border)" stroke-width="1"/>`;
                }
                document.getElementById('dist-feed-dot').setAttribute('cy', 70 + out.feed_stage * spacing);
                const warn = document.getElementById('dist-warnings');
                if (data.warnings?.length) {
                    warn.classList.remove('hidden');
                    document.getElementById('dist-warn-list').innerHTML = data.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('');
                } else warn.classList.add('hidden');
                if (out.calculation_steps?.length) document.getElementById('dist-steps').innerHTML = renderSteps(out.calculation_steps);
                saveHistory('distillation', params, out);
                showResult('distillation');
                toast('Column design complete');
            } else {
                toast('Error: ' + (data.errors?.join(', ') || 'Unknown'), 'error');
                hideLoading();
            }
        } catch (err) {
            toast('Connection error: ' + err.message, 'error');
            hideLoading();
        }
    };
}

// ==================== Mass Balance Form ====================
function initMassBalanceForm() {
    document.getElementById('mass_balance-form').onsubmit = async e => {
        e.preventDefault();
        showLoading();
        const fd = new FormData(e.target);
        const comps = fd.get('components').split(',').map(c => c.trim());
        const feedComp = parseFloat(fd.get('feed_composition'));
        const distComp = parseFloat(fd.get('distillate_composition'));
        const bottComp = parseFloat(fd.get('bottoms_composition'));
        const params = {
            components: comps,
            inlet_streams: [{ name: 'Feed', flow_rate: parseFloat(fd.get('feed_flow_rate')), composition: { [comps[0]]: feedComp, [comps[1]]: 1 - feedComp }}],
            outlet_streams: [
                { name: 'Distillate', composition: { [comps[0]]: distComp, [comps[1]]: 1 - distComp }},
                { name: 'Bottoms', composition: { [comps[0]]: bottComp, [comps[1]]: 1 - bottComp }}
            ]
        };
        try {
            const res = await fetch(`${API_BASE}/calculate/mass_balance`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parameters: params })
            });
            const data = await res.json();
            if (data.success) {
                const out = data.outputs;
                document.getElementById('mb-comps').textContent = comps.join(' / ');
                document.getElementById('mb-in-label').textContent = `${out.inlet_total.flow_rate.toFixed(1)} mol/s`;
                document.getElementById('mb-closure-svg').textContent = `Closure: ${out.closure.toFixed(1)}%`;
                if (out.outlet_streams[0]) document.getElementById('mb-out1-label').textContent = `${out.outlet_streams[0].flow_rate.toFixed(1)} mol/s`;
                if (out.outlet_streams[1]) document.getElementById('mb-out2-label').textContent = `${out.outlet_streams[1].flow_rate.toFixed(1)} mol/s`;
                document.getElementById('mb-closure').textContent = out.closure.toFixed(2);
                if (out.calculation_steps?.length) document.getElementById('mb-steps').innerHTML = renderSteps(out.calculation_steps);
                saveHistory('mass_balance', { components: comps, feed_flow_rate: params.inlet_streams[0].flow_rate }, out);
                showResult('mass_balance');
                toast('Balance calculation complete');
            } else {
                toast('Error: ' + (data.errors?.join(', ') || 'Unknown'), 'error');
                hideLoading();
            }
        } catch (err) {
            toast('Connection error: ' + err.message, 'error');
            hideLoading();
        }
    };
}

// ==================== Heat Balance Form ====================
function initHeatBalanceForm() {
    document.getElementById('heat_balance-form').onsubmit = async e => {
        e.preventDefault();
        showLoading();
        const fd = new FormData(e.target);
        const params = {
            substance: fd.get('substance'),
            flow_rate: parseFloat(fd.get('flow_rate')),
            inlet_temperature: parseFloat(fd.get('inlet_temperature')),
            outlet_temperature: parseFloat(fd.get('outlet_temperature')),
            pressure: parseFloat(fd.get('pressure')),
            efficiency: parseFloat(fd.get('efficiency')),
            phase_change: true
        };
        try {
            const res = await fetch(`${API_BASE}/calculate/heat_balance`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parameters: params })
            });
            const data = await res.json();
            if (data.success) {
                const out = data.outputs;
                const phaseJa = { liquid: '液相', vapor: '気相', unknown: '不明' };
                document.getElementById('hb-sub').textContent = `${params.substance} (${params.flow_rate} mol/s)`;
                document.getElementById('hb-sens').textContent = out.sensible_heat.toFixed(1);
                document.getElementById('hb-lat').textContent = out.latent_heat.toFixed(1);
                document.getElementById('hb-total').textContent = out.total_heat_duty.toFixed(1);
                document.getElementById('hb-actual').textContent = out.actual_heat_duty.toFixed(1);
                document.getElementById('hb-t-in').textContent = `T = ${params.inlet_temperature} K`;
                document.getElementById('hb-t-out').textContent = `T = ${params.outlet_temperature} K`;
                document.getElementById('hb-q-label').textContent = out.total_heat_duty > 1000 ? `Q = ${(out.total_heat_duty/1000).toFixed(1)} MW` : `Q = ${out.total_heat_duty.toFixed(0)} kW`;
                document.getElementById('hb-phase-in').textContent = `${phaseJa[out.phase_info.inlet_phase] || out.phase_info.inlet_phase} / ${out.phase_info.inlet_phase}`;
                document.getElementById('hb-phase-out').textContent = `${phaseJa[out.phase_info.outlet_phase] || out.phase_info.outlet_phase} / ${out.phase_info.outlet_phase}`;
                document.getElementById('hb-bp').textContent = out.phase_info.boiling_point ? `${out.phase_info.boiling_point.toFixed(1)} K` : '-';
                document.getElementById('hb-pc').textContent = out.phase_info.has_phase_change ? 'Yes' : 'No';
                const warn = document.getElementById('hb-warnings');
                if (data.warnings?.length) {
                    warn.classList.remove('hidden');
                    document.getElementById('hb-warn-list').innerHTML = data.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('');
                } else warn.classList.add('hidden');
                if (out.calculation_steps?.length) document.getElementById('hb-steps').innerHTML = renderSteps(out.calculation_steps);
                saveHistory('heat_balance', params, out);
                showResult('heat_balance');
                toast('Heat duty calculation complete');
            } else {
                toast('Error: ' + (data.errors?.join(', ') || 'Unknown'), 'error');
                hideLoading();
            }
        } catch (err) {
            toast('Connection error: ' + err.message, 'error');
            hideLoading();
        }
    };
}

// ==================== Extraction Form ====================
function initExtractionForm() {
    document.getElementById('extraction-form').onsubmit = async e => {
        e.preventDefault();
        showLoading();
        const fd = new FormData(e.target);
        const stagesVal = fd.get('stages');
        const params = {
            solute: fd.get('solute'),
            carrier: fd.get('carrier'),
            solvent: fd.get('solvent'),
            feed_flow_rate: parseFloat(fd.get('feed_flow_rate')),
            feed_composition: parseFloat(fd.get('feed_composition')),
            solvent_flow_rate: parseFloat(fd.get('solvent_flow_rate')),
            temperature: parseFloat(fd.get('temperature')),
            recovery: parseFloat(fd.get('recovery'))
        };
        if (stagesVal && stagesVal.trim() !== '') {
            params.stages = parseInt(stagesVal);
        }
        try {
            const res = await fetch(`${API_BASE}/calculate/extraction`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parameters: params })
            });
            const data = await res.json();
            if (data.success) {
                const out = data.outputs;
                // System description
                document.getElementById('ext-system').textContent = `${params.solute} from ${params.carrier} using ${params.solvent}`;
                // Main results
                document.getElementById('ext-recovery').textContent = (out.recovery * 100).toFixed(1);
                document.getElementById('ext-stages').textContent = out.actual_stages;
                document.getElementById('ext-factor').textContent = out.extraction_factor.toFixed(3);
                document.getElementById('ext-m').textContent = out.distribution_coefficient.toFixed(3);
                // Diagram labels
                document.getElementById('ext-feed-label').textContent = `${params.feed_flow_rate} kmol/h`;
                document.getElementById('ext-solv-label').textContent = `${params.solvent_flow_rate} kmol/h`;
                document.getElementById('ext-raff-label').textContent = `${out.raffinate_flow_rate.toFixed(1)} kmol/h`;
                document.getElementById('ext-extract-label').textContent = `${out.extract_flow_rate.toFixed(1)} kmol/h`;
                // Draw stages in SVG
                const stagesSvg = document.getElementById('ext-stages-svg');
                stagesSvg.innerHTML = '';
                const nStages = out.actual_stages;
                const stageHeight = 200 / Math.min(nStages, 10);
                for (let i = 0; i < Math.min(nStages, 10); i++) {
                    const y = 50 + i * stageHeight + stageHeight / 2;
                    stagesSvg.innerHTML += `<line x1="185" y1="${y}" x2="295" y2="${y}" stroke="var(--glass-border)" stroke-width="1" stroke-dasharray="4,4"/>`;
                    stagesSvg.innerHTML += `<text x="300" y="${y+4}" font-size="9" fill="var(--text-dim)">${i+1}</text>`;
                }
                if (nStages > 10) {
                    stagesSvg.innerHTML += `<text x="240" y="270" text-anchor="middle" font-size="9" fill="var(--text-muted)">...${nStages} stages total</text>`;
                }
                // Table data
                document.getElementById('ext-tbl-feed').textContent = params.feed_flow_rate.toFixed(1);
                document.getElementById('ext-tbl-xf').textContent = params.feed_composition.toFixed(4);
                document.getElementById('ext-tbl-solv').textContent = params.solvent_flow_rate.toFixed(1);
                document.getElementById('ext-tbl-ys').textContent = '0.0000';
                document.getElementById('ext-tbl-raff').textContent = out.raffinate_flow_rate.toFixed(2);
                document.getElementById('ext-tbl-xr').textContent = out.raffinate_composition.toFixed(6);
                document.getElementById('ext-tbl-extract').textContent = out.extract_flow_rate.toFixed(2);
                document.getElementById('ext-tbl-ye').textContent = out.extract_composition.toFixed(6);
                // Warnings
                const warn = document.getElementById('ext-warnings');
                if (data.warnings?.length) {
                    warn.classList.remove('hidden');
                    document.getElementById('ext-warn-list').innerHTML = data.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('');
                } else warn.classList.add('hidden');
                // Steps
                if (out.calculation_steps?.length) document.getElementById('ext-steps').innerHTML = renderSteps(out.calculation_steps);
                saveHistory('extraction', params, out);
                showResult('extraction');
                toast('Extraction calculation complete');
            } else {
                toast('Error: ' + (data.errors?.join(', ') || 'Unknown'), 'error');
                hideLoading();
            }
        } catch (err) {
            toast('Connection error: ' + err.message, 'error');
            hideLoading();
        }
    };
}

// ==================== Absorption Form ====================
function initAbsorptionForm() {
    document.getElementById('absorption-form').onsubmit = async e => {
        e.preventDefault();
        showLoading();
        const fd = new FormData(e.target);
        const liquidFlowVal = fd.get('liquid_flow_rate');
        const params = {
            gas_component: fd.get('gas_component'),
            carrier_gas: fd.get('carrier_gas'),
            solvent: fd.get('solvent'),
            gas_flow_rate: parseFloat(fd.get('gas_flow_rate')),
            inlet_gas_composition: parseFloat(fd.get('inlet_gas_composition')),
            temperature: parseFloat(fd.get('temperature')),
            pressure: parseFloat(fd.get('pressure')),
            removal_efficiency: parseFloat(fd.get('removal_efficiency'))
        };
        if (liquidFlowVal && liquidFlowVal.trim() !== '') {
            params.liquid_flow_rate = parseFloat(liquidFlowVal);
        }
        try {
            const res = await fetch(`${API_BASE}/calculate/absorption`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parameters: params })
            });
            const data = await res.json();
            if (data.success) {
                const out = data.outputs;
                // System description
                document.getElementById('abs-system').textContent = `${params.gas_component} into ${params.solvent}`;
                // Main results
                document.getElementById('abs-removal').textContent = (out.removal_efficiency * 100).toFixed(1);
                document.getElementById('abs-stages').textContent = out.actual_stages;
                document.getElementById('abs-factor').textContent = out.absorption_factor.toFixed(3);
                document.getElementById('abs-lg').textContent = out.liquid_gas_ratio.toFixed(3);
                // Diagram labels
                document.getElementById('abs-gas-in-label').textContent = `${params.gas_flow_rate} kmol/h`;
                document.getElementById('abs-gas-out-label').textContent = `${out.outlet_gas_flow.toFixed(1)} kmol/h`;
                document.getElementById('abs-liq-out-label').textContent = `${out.outlet_liquid_flow.toFixed(1)} kmol/h`;
                // Draw stages in SVG
                const stagesSvg = document.getElementById('abs-stages-svg');
                stagesSvg.innerHTML = '';
                const nStages = out.actual_stages;
                const stageHeight = 220 / Math.min(nStages, 10);
                for (let i = 0; i < Math.min(nStages, 10); i++) {
                    const y = 50 + i * stageHeight + stageHeight / 2;
                    stagesSvg.innerHTML += `<line x1="155" y1="${y}" x2="265" y2="${y}" stroke="var(--glass-border)" stroke-width="1" stroke-dasharray="4,4"/>`;
                    stagesSvg.innerHTML += `<text x="275" y="${y+4}" font-size="9" fill="var(--text-dim)">${i+1}</text>`;
                }
                if (nStages > 10) {
                    stagesSvg.innerHTML += `<text x="210" y="285" text-anchor="middle" font-size="9" fill="var(--text-muted)">...${nStages} stages total</text>`;
                }
                // Table data
                document.getElementById('abs-tbl-gin').textContent = params.gas_flow_rate.toFixed(1);
                document.getElementById('abs-tbl-yin').textContent = params.inlet_gas_composition.toFixed(4);
                document.getElementById('abs-tbl-gout').textContent = out.outlet_gas_flow.toFixed(2);
                document.getElementById('abs-tbl-yout').textContent = out.outlet_gas_composition.toFixed(8);
                const L_in = out.outlet_liquid_flow - out.absorbed_amount;
                document.getElementById('abs-tbl-lin').textContent = L_in.toFixed(1);
                document.getElementById('abs-tbl-xin').textContent = '0.0000';
                document.getElementById('abs-tbl-lout').textContent = out.outlet_liquid_flow.toFixed(2);
                document.getElementById('abs-tbl-xout').textContent = out.outlet_liquid_composition.toFixed(6);
                // Absorbed amount
                document.getElementById('abs-absorbed').textContent = out.absorbed_amount.toFixed(3);
                // Warnings
                const warn = document.getElementById('abs-warnings');
                if (data.warnings?.length) {
                    warn.classList.remove('hidden');
                    document.getElementById('abs-warn-list').innerHTML = data.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('');
                } else warn.classList.add('hidden');
                // Steps
                if (out.calculation_steps?.length) document.getElementById('abs-steps').innerHTML = renderSteps(out.calculation_steps);
                saveHistory('absorption', params, out);
                showResult('absorption');
                toast('Absorption calculation complete');
            } else {
                toast('Error: ' + (data.errors?.join(', ') || 'Unknown'), 'error');
                hideLoading();
            }
        } catch (err) {
            toast('Connection error: ' + err.message, 'error');
            hideLoading();
        }
    };
}

// ==================== LCOH Form ====================
// Store sensitivity data globally for chart updates
let lcohSensitivityData = null;
let currentSensChart = 'electricity';

function initLcohForm() {
    // Method-dependent field visibility
    document.getElementById('lcoh-method').onchange = function() {
        const method = this.value;
        const isElec = method.includes('electrolysis');
        document.getElementById('lcoh-elec-group').classList.toggle('hidden', !isElec);
        document.getElementById('lcoh-gas-group').classList.toggle('hidden', isElec);
    };

    document.getElementById('lcoh-form').onsubmit = async e => {
        e.preventDefault();
        showLoading();
        const fd = new FormData(e.target);
        const method = fd.get('production_method');
            const params = {
                production_method: method,
                capacity: parseFloat(fd.get('capacity')),
                operating_hours: parseFloat(fd.get('operating_hours')),
                opex_percent: parseFloat(fd.get('opex_percent')),
                discount_rate: parseFloat(fd.get('discount_rate')),
                project_lifetime: parseInt(fd.get('project_lifetime')),
                carbon_price: parseFloat(fd.get('carbon_price')),
                maintenance_days: parseFloat(fd.get('maintenance_days') || 0),
                labor_cost: parseFloat(fd.get('labor_cost') || 0),
                maintenance_cost: parseFloat(fd.get('maintenance_cost') || 0),
                capex_subsidy_percent: parseFloat(fd.get('capex_subsidy_percent') || 0),
                capex_subsidy_amount: parseFloat(fd.get('capex_subsidy_amount') || 0),
                subsidies: parseFloat(fd.get('subsidies') || 0)
            };

        // Optional CAPEX
        const capexVal = fd.get('capex_per_kw');
        if (capexVal && capexVal.trim() !== '') {
            params.capex_per_kw = parseFloat(capexVal);
        }

        // Method-specific parameters
        if (method.includes('electrolysis')) {
            params.electricity_price = parseFloat(fd.get('electricity_price'));
        } else {
            params.natural_gas_price = parseFloat(fd.get('natural_gas_price'));
        }

        try {
            const res = await fetch(`${API_BASE}/calculate/lcoh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parameters: params })
            });
            const data = await res.json();
            if (data.success) {
                const out = data.outputs;
                lcohSensitivityData = out.sensitivity_data;

                // Method label
                const methodLabels = {
                    'pem_electrolysis': 'PEM Electrolysis',
                    'alkaline_electrolysis': 'Alkaline Electrolysis',
                    'soec_electrolysis': 'SOEC Electrolysis',
                    'smr': 'SMR (Gray H₂)',
                    'smr_ccs': 'SMR + CCS (Blue H₂)',
                    'atr_ccs': 'ATR + CCS (Blue H₂)'
                };
                document.getElementById('lcoh-method-label').textContent = methodLabels[method] || method;

                // Main LCOH value
                document.getElementById('lcoh-value').textContent = out.lcoh.toFixed(2);

                // Summary cards
                document.getElementById('lcoh-production').textContent = (out.annual_h2_production / 1000).toFixed(1);
                document.getElementById('lcoh-capex').textContent = (out.total_capex / 1000000).toFixed(2);
                document.getElementById('lcoh-efficiency').textContent = out.energy_efficiency.toFixed(1);
                document.getElementById('lcoh-carbon').textContent = out.carbon_intensity.toFixed(2);

                // Cost breakdown
                const bd = out.lcoh_breakdown;
                const labor = bd.labor || 0;
                const maintenance = bd.maintenance || 0;
                const water = bd.water || 0;
                const revenue = bd.revenue_offset || 0;
                const totalPositive = bd.capex + bd.energy + bd.opex + labor + maintenance + bd.stack_replacement + bd.carbon + water;
                document.getElementById('lcoh-tbl-capex').textContent = bd.capex.toFixed(3);
                document.getElementById('lcoh-tbl-capex-pct').textContent = ((bd.capex / totalPositive) * 100).toFixed(1) + '%';
                document.getElementById('lcoh-tbl-energy').textContent = bd.energy.toFixed(3);
                document.getElementById('lcoh-tbl-energy-pct').textContent = ((bd.energy / totalPositive) * 100).toFixed(1) + '%';
                document.getElementById('lcoh-tbl-opex').textContent = bd.opex.toFixed(3);
                document.getElementById('lcoh-tbl-opex-pct').textContent = ((bd.opex / totalPositive) * 100).toFixed(1) + '%';
                document.getElementById('lcoh-tbl-labor').textContent = labor.toFixed(3);
                document.getElementById('lcoh-tbl-labor-pct').textContent = ((labor / totalPositive) * 100).toFixed(1) + '%';
                document.getElementById('lcoh-tbl-maint').textContent = maintenance.toFixed(3);
                document.getElementById('lcoh-tbl-maint-pct').textContent = ((maintenance / totalPositive) * 100).toFixed(1) + '%';
                document.getElementById('lcoh-tbl-stack').textContent = bd.stack_replacement.toFixed(3);
                document.getElementById('lcoh-tbl-stack-pct').textContent = ((bd.stack_replacement / totalPositive) * 100).toFixed(1) + '%';
                document.getElementById('lcoh-tbl-water').textContent = water.toFixed(3);
                document.getElementById('lcoh-tbl-water-pct').textContent = ((water / totalPositive) * 100).toFixed(1) + '%';
                document.getElementById('lcoh-tbl-carbon').textContent = bd.carbon.toFixed(3);
                document.getElementById('lcoh-tbl-carbon-pct').textContent = ((bd.carbon / totalPositive) * 100).toFixed(1) + '%';
                document.getElementById('lcoh-tbl-revenue').textContent = revenue.toFixed(3);
                document.getElementById('lcoh-tbl-revenue-pct').textContent = totalPositive > 0 ? ((revenue / totalPositive) * 100).toFixed(1) + '%' : '-';

                // Draw breakdown chart
                drawLcohBreakdownChart(bd, totalPositive);

                // Draw sensitivity chart
                currentSensChart = method.includes('electrolysis') ? 'electricity' : 'gas';
                drawLcohSensitivityChart();

                // Steps (LCOH has different step format)
                if (out.calculation_steps?.length) {
                    const stepsHtml = out.calculation_steps.map(s => `
                        <div class="step-item">
                            <div class="step-title">${escapeHtml(s.step)}</div>
                            ${s.description ? `<div class="step-desc">${escapeHtml(s.description)}</div>` : ''}
                            ${s.formula ? `<div class="step-formula">${escapeHtml(s.formula)}</div>` : ''}
                            ${s.values ? `<div class="step-values" style="font-size: 0.8rem; color: var(--text-muted); margin: 0.25rem 0;">${Object.entries(s.values).map(([k,v]) => `${escapeHtml(k)}: ${escapeHtml(v)}`).join(', ')}</div>` : ''}
                            ${s.result ? `<div class="step-result" style="font-weight: 500; color: var(--accent-teal);">→ ${escapeHtml(s.result)}</div>` : ''}
                        </div>
                    `).join('');
                    document.getElementById('lcoh-steps').innerHTML = stepsHtml;
                }

                saveHistory('lcoh', params, out);
                showResult('lcoh');
                toast('LCOH calculation complete');
            } else {
                toast('Error: ' + (data.errors?.join(', ') || 'Unknown'), 'error');
                hideLoading();
            }
        } catch (err) {
            toast('Connection error: ' + err.message, 'error');
            hideLoading();
        }
    };
}

// Initialize all form handlers
function initAllForms() {
    initPropertyForm();
    initDistillationForm();
    initMassBalanceForm();
    initHeatBalanceForm();
    initExtractionForm();
    initAbsorptionForm();
    initLcohForm();
}
