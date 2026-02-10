// ==================== API Communication ====================

// Load substance list from API
async function loadSubstances() {
    try {
        const res = await fetch(`${API_BASE}/substances`);
        const data = await res.json();
        if (data.success && data.substances.length > 0) {
            SUBSTANCES_DATA = data.substances;
        } else {
            SUBSTANCES_DATA = SUBSTANCES_FALLBACK;
        }
    } catch (e) {
        console.warn('Failed to load substances from API, using fallback', e);
        SUBSTANCES_DATA = SUBSTANCES_FALLBACK;
    }
}

// Substance search (Japanese, English, formula)
function searchSubstances(query) {
    if (!query || query.length < 1) return [];
    const q = query.toLowerCase();
    return SUBSTANCES_DATA.filter(s => {
        const searchFields = [
            s.id?.toLowerCase() || '',
            s.name_ja?.toLowerCase() || '',
            s.name_en?.toLowerCase() || '',
            s.formula?.toLowerCase() || '',
            ...(s.aliases || []).map(a => a.toLowerCase())
        ];
        return searchFields.some(f => f.includes(q));
    }).slice(0, 10);
}

// ==================== Batch Calculation ====================
async function calculateBatch(cases) {
    const res = await fetch(`${API_BASE}/calculate/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cases }),
    });
    return res.json();
}

// ==================== API Status ====================
async function checkStatus() {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    try {
        const res = await fetch('/api');
        const data = await res.json();
        dot.className = 'status-dot online';
        text.textContent = data.mode || 'Online';
    } catch {
        dot.className = 'status-dot offline';
        text.textContent = 'Offline';
    }
}
