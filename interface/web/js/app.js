// ==================== Main Application Initialization ====================

// ==================== API Status Check (start immediately) ====================
checkStatus();
setInterval(checkStatus, 30000);

// ==================== Theme (initialize immediately) ====================
initTheme();

document.getElementById('theme-toggle').onclick = () => {
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    if (isLight) {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('theme', 'dark');
        updateThemeIcon(true);
    } else {
        document.documentElement.setAttribute('data-theme', 'light');
        localStorage.setItem('theme', 'light');
        updateThemeIcon(false);
    }
};

function initGlobalActionHandlers() {
    document.addEventListener('click', (e) => {
        const actionEl = e.target.closest('[data-action]');
        if (actionEl) {
            const { action, skill, type, value, caseId } = actionEl.dataset;
            if (action === 'toggle-language') {
                setLanguage(currentLang === 'ja' ? 'en' : 'ja');
            } else if (action === 'clear-dashboard') {
                clearAllDashboardCases();
            } else if (action === 'compare-dashboard') {
                compareDashboardCases();
            } else if (action === 'download-template' && skill) {
                downloadPromptTemplate(skill);
            } else if (action === 'download-report' && type) {
                downloadReport(type);
            } else if (action === 'save-dashboard' && type) {
                saveToDashboard(type);
            } else if (action === 'export-json' && skill) {
                exportJSON(skill);
            } else if (action === 'export-csv' && skill) {
                exportCSV(skill);
            } else if (action === 'set-dashboard-chart-type' && value) {
                setDashboardChartType(value);
            } else if (action === 'export-dashboard-csv') {
                exportDashboardCSV();
            } else if (action === 'export-dashboard-png') {
                exportDashboardPNG();
            } else if (action === 'delete-dashboard-case' && caseId) {
                deleteDashboardCase(caseId);
            }
        }

        const caseCheckbox = e.target.closest('.case-checkbox');
        if (caseCheckbox && caseCheckbox.dataset.caseId) {
            toggleCaseSelection(caseCheckbox.dataset.caseId);
        }
    });
}

// ==================== Tabs ====================
const allTabs = document.querySelectorAll('.calc-tab');

function activateTab(tab) {
    allTabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
        t.setAttribute('tabindex', '-1');
    });
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    tab.setAttribute('tabindex', '0');
    tab.focus();
    const name = tab.dataset.tab;
    document.querySelectorAll('.form-section').forEach(f => f.classList.remove('active'));
    document.getElementById(`${name}-form`).classList.add('active');
    if (name === 'dashboard') {
        showResult('dashboard');
        renderDashboardCaseList();
    }
}

allTabs.forEach((tab, idx) => {
    tab.onclick = () => activateTab(tab);
    tab.onkeydown = (e) => {
        let target = null;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            e.preventDefault();
            target = allTabs[(idx + 1) % allTabs.length];
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            e.preventDefault();
            target = allTabs[(idx - 1 + allTabs.length) % allTabs.length];
        } else if (e.key === 'Home') {
            e.preventDefault();
            target = allTabs[0];
        } else if (e.key === 'End') {
            e.preventDefault();
            target = allTabs[allTabs.length - 1];
        }
        if (target) activateTab(target);
    };
    if (tab.classList.contains('active')) {
        tab.setAttribute('tabindex', '0');
    } else {
        tab.setAttribute('tabindex', '-1');
    }
});

// ==================== Autocomplete ====================
function initAutocomplete() {
    document.querySelectorAll('.substance-input').forEach((input, i) => {
        const dropdown = document.getElementById(`autocomplete-${i + 1}`) || input.parentElement.querySelector('.autocomplete-dropdown');
        if (!dropdown) return;

        let selectedIndex = -1;

        function updateSelection() {
            const items = dropdown.querySelectorAll('.autocomplete-item');
            items.forEach((item, idx) => {
                item.classList.toggle('selected', idx === selectedIndex);
            });
            if (selectedIndex >= 0 && items[selectedIndex]) {
                items[selectedIndex].scrollIntoView({ block: 'nearest' });
            }
        }

        function selectItem(item) {
            input.value = item.dataset.id;
            dropdown.classList.add('hidden');
            selectedIndex = -1;
        }

        input.oninput = () => {
            const val = input.value;
            selectedIndex = -1;
            if (val.length < 1) { dropdown.classList.add('hidden'); return; }
            const matches = searchSubstances(val);
            if (!matches.length) { dropdown.classList.add('hidden'); return; }

            dropdown.innerHTML = matches.map(s => `
                <div class="autocomplete-item" data-id="${escapeHtml(s.id)}">
                    <span class="ac-name">${escapeHtml(s.name_ja || s.id)}</span>
                    <span class="ac-en">${escapeHtml(s.name_en || '')}</span>
                    <span class="ac-formula">${escapeHtml(s.formula || '')}</span>
                </div>
            `).join('');
            dropdown.classList.remove('hidden');

            dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
                item.onclick = () => selectItem(item);
                item.onmouseenter = () => {
                    selectedIndex = [...dropdown.querySelectorAll('.autocomplete-item')].indexOf(item);
                    updateSelection();
                };
            });
        };

        input.onkeydown = (e) => {
            const items = dropdown.querySelectorAll('.autocomplete-item');
            if (dropdown.classList.contains('hidden') || !items.length) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
                updateSelection();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, 0);
                updateSelection();
            } else if (e.key === 'Enter' && selectedIndex >= 0) {
                e.preventDefault();
                selectItem(items[selectedIndex]);
            } else if (e.key === 'Escape') {
                dropdown.classList.add('hidden');
                selectedIndex = -1;
            }
        };

        input.onblur = () => setTimeout(() => {
            dropdown.classList.add('hidden');
            selectedIndex = -1;
        }, 150);

        input.onfocus = () => {
            if (input.value.length >= 1) input.oninput();
        };
    });
}

loadSubstances().then(() => initAutocomplete());

// ==================== Unit Conversion Chips ====================
document.querySelectorAll('.unit-chip').forEach(chip => {
    chip.onclick = () => {
        const target = chip.dataset.target;
        const newUnit = chip.dataset.unit;
        const input = document.getElementById(target);
        const currentVal = parseFloat(input.value) || 0;
        const currentUnit = activeUnits[target];
        const isTemp = ['K', 'C', 'F'].includes(newUnit);
        const type = isTemp ? 'temperature' : 'pressure';
        const base = UNITS[type][currentUnit].toBase(currentVal);
        const newVal = UNITS[type][newUnit].fromBase(base);
        input.value = newVal.toFixed(isTemp ? 2 : 0);
        activeUnits[target] = newUnit;
        chip.parentElement.querySelectorAll('.unit-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
    };
});

// ==================== History ====================
initHistoryToggle();

// ==================== Forms ====================
initAllForms();

// ==================== Charts ====================
initAllCharts();

// ==================== Export Buttons ====================
document.getElementById('export-json').onclick = () => {
    if (!lastResult) return toast('No data to export', 'warning');
    exportJSON('property_estimation');
};

document.getElementById('export-csv').onclick = () => {
    if (!lastResult) return toast('No data to export', 'warning');
    exportCSV('property_estimation');
};

// ==================== Import ====================
document.getElementById('import-btn').onclick = () => {
    document.getElementById('import-modal').classList.remove('hidden');
};

document.getElementById('close-import-modal').onclick = () => {
    document.getElementById('import-modal').classList.add('hidden');
    resetImportModal();
};

document.getElementById('cancel-import').onclick = () => {
    document.getElementById('import-modal').classList.add('hidden');
    resetImportModal();
};

const importDropzone = document.getElementById('import-dropzone');
const importFileInput = document.getElementById('import-file');

importDropzone.onclick = () => importFileInput.click();
importFileInput.onchange = (e) => handleImportFile(e.target.files[0]);

importDropzone.ondragover = (e) => {
    e.preventDefault();
    importDropzone.classList.add('dragover');
};
importDropzone.ondragleave = () => importDropzone.classList.remove('dragover');
importDropzone.ondrop = (e) => {
    e.preventDefault();
    importDropzone.classList.remove('dragover');
    handleImportFile(e.dataTransfer.files[0]);
};

document.getElementById('confirm-import').onclick = async () => {
    if (!pendingImportData) return;

    if (pendingImportData._batch) {
        const cases = pendingImportData.cases;
        document.getElementById('import-modal').classList.add('hidden');
        resetImportModal();

        toast(`Executing ${cases.length} cases... / ${cases.length}件を一括実行中...`, 'info');

        try {
            const resp = await calculateBatch(cases);
            const dashCases = loadDashboardCases();

            (resp.results || []).forEach((r) => {
                const skillType = r.skill_id === 'property_estimation' ? 'property' : r.skill_id;
                const caseName = r.case_name || getCaseName(skillType, r.inputs || {}, r.outputs || {});
                dashCases.unshift({
                    id: generateCaseId(),
                    type: skillType,
                    name: caseName,
                    params: r.inputs || {},
                    result: r.outputs || {},
                    mainValue: r.success ? getMainValue(skillType, r.outputs || {}) : 'Error',
                    timestamp: r.timestamp || new Date().toISOString()
                });
            });

            saveDashboardCases(dashCases);

            const dashTab = document.querySelector('[data-tab="dashboard"]');
            if (dashTab && typeof activateTab === 'function') activateTab(dashTab);

            toast(`Batch complete: ${resp.succeeded}/${resp.total} succeeded (${resp.execution_time_ms}ms) / 一括実行完了`, 'success');
        } catch (e) {
            toast('Batch execution failed: ' + e.message, 'error');
        }
        return;
    }

    const { skill_id, parameters } = pendingImportData;
    const tabName = skill_id === 'property_estimation' ? 'property' : skill_id;
    const targetTab = document.querySelector(`[data-tab="${tabName}"]`);
    if (targetTab && typeof activateTab === 'function') activateTab(targetTab);

    populateForm(skill_id, parameters);

    document.getElementById('import-modal').classList.add('hidden');
    resetImportModal();

    toast('Parameters imported! / パラメータをインポートしました', 'success');
};

// ==================== Keyboard Shortcut ====================
document.addEventListener('keydown', e => {
    if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        const active = document.querySelector('.calc-tab.active');
        if (active) {
            const form = document.getElementById(`${active.dataset.tab}-form`);
            if (form) form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        }
    }
});

// ==================== Steps Toggles ====================
['prop', 'dist', 'mb', 'hb', 'ext', 'abs', 'lcoh'].forEach(prefix => {
    const btn = document.getElementById(`${prefix}-steps-toggle`);
    if (btn) {
        btn.onclick = () => {
            const steps = document.getElementById(`${prefix}-steps`);
            const hidden = steps.classList.toggle('hidden');
            btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="${hidden ? 'M12 5v14M5 12h14' : 'M5 12h14'}"/></svg> ${hidden ? 'Show' : 'Hide'} Calculation Steps`;
        };
    }
});

// ==================== Dashboard ====================
document.getElementById('dashboard-type-filter')?.addEventListener('change', renderDashboardCaseList);
renderDashboardCaseList();

// ==================== AI Suggest Buttons ====================
const skillTabMap = {
    'property': 'property_estimation',
    'distillation': 'distillation',
    'mass_balance': 'mass_balance',
    'heat_balance': 'heat_balance',
    'extraction': 'extraction',
    'absorption': 'absorption',
    'lcoh': 'lcoh',
};

document.querySelectorAll('.submit-btn[type="submit"]').forEach(btn => {
    const form = btn.closest('form');
    if (!form) return;

    const tabName = form.id?.replace('-form', '');
    const skillId = skillTabMap[tabName];
    if (!skillId) return;

    const suggestBtn = document.createElement('button');
    suggestBtn.type = 'button';
    suggestBtn.className = 'submit-btn secondary ai-suggest-btn';
    suggestBtn.style.cssText = 'background: var(--accent-violet); margin-left: 0.5rem;';
    suggestBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 16.8l-6.2 4.5 2.4-7.4L2 9.4h7.6z"/></svg> AI提案`;
    suggestBtn.onclick = async () => {
        suggestBtn.disabled = true;
        suggestBtn.textContent = '提案中...';

        const formData = new FormData(form);
        const params = {};
        for (const [k, v] of formData.entries()) {
            if (v) params[k] = isNaN(Number(v)) ? v : Number(v);
        }

        try {
            const data = await requestSuggestions(skillId, params);
            if (data.success && data.suggestions && data.suggestions.length > 0) {
                showSuggestionPopover(data.suggestions, form, suggestBtn);
            } else {
                toast(data.error || 'No suggestions available / 提案はありません', 'info');
            }
        } catch (err) {
            toast('AI提案エラー: ' + (err.message || 'Unknown error'), 'error');
        } finally {
            suggestBtn.disabled = false;
            suggestBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 16.8l-6.2 4.5 2.4-7.4L2 9.4h7.6z"/></svg> AI提案`;
        }
    };

    btn.parentNode.insertBefore(suggestBtn, btn.nextSibling);
});

function showSuggestionPopover(suggestions, form, anchor) {
    document.querySelectorAll('.suggestion-popover').forEach(el => el.remove());

    const popover = document.createElement('div');
    popover.className = 'suggestion-popover';
    popover.style.cssText = `
        position: absolute; z-index: 1000; background: var(--bg-panel);
        border: 1px solid var(--accent-violet); border-radius: 12px;
        padding: 1rem; max-width: 360px; box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        backdrop-filter: blur(20px);
    `;

    let html = '<div style="font-weight:600;color:var(--accent-violet);margin-bottom:0.75rem;">AI Parameter Suggestions</div>';
    suggestions.forEach((s, i) => {
        html += `<div style="padding:0.5rem 0;border-bottom:1px solid var(--glass-border);">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span><strong>${escapeHtml(s.param)}</strong>: ${escapeHtml(String(s.value))}</span>
                <button class="suggest-apply-btn" data-idx="${i}" style="
                    background:var(--accent-violet);color:#fff;border:none;
                    border-radius:6px;padding:0.2rem 0.6rem;cursor:pointer;font-size:0.8rem;
                ">Apply</button>
            </div>
            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.25rem;">${escapeHtml(s.reason || '')}</div>
        </div>`;
    });
    html += `<button class="suggest-apply-all" style="
        margin-top:0.75rem;width:100%;background:var(--accent-violet);color:#fff;
        border:none;border-radius:8px;padding:0.5rem;cursor:pointer;
    ">Apply All / すべて適用</button>`;

    popover.innerHTML = html;

    anchor.style.position = 'relative';
    anchor.parentNode.style.position = 'relative';
    anchor.parentNode.appendChild(popover);

    popover.querySelectorAll('.suggest-apply-btn').forEach(btn => {
        btn.onclick = () => {
            const s = suggestions[Number(btn.dataset.idx)];
            if (!/^[a-zA-Z0-9_-]+$/.test(s.param)) return;
            const input = form.querySelector(`[name="${s.param}"]`);
            if (input) {
                input.value = s.value;
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
            btn.textContent = 'Applied';
            btn.disabled = true;
        };
    });

    popover.querySelector('.suggest-apply-all').onclick = () => {
        suggestions.forEach(s => {
            if (!/^[a-zA-Z0-9_-]+$/.test(s.param)) return;
            const input = form.querySelector(`[name="${s.param}"]`);
            if (input) {
                input.value = s.value;
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
        popover.remove();
        toast('All suggestions applied / すべて適用しました', 'success');
    };

    setTimeout(() => {
        document.addEventListener('click', function closePopover(e) {
            if (!popover.contains(e.target) && e.target !== anchor) {
                popover.remove();
                document.removeEventListener('click', closePopover);
            }
        });
    }, 100);
}

// ==================== Help System ====================
initHelpSystem();
initFeedbackSystem();
initGlobalActionHandlers();
