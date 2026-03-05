// ==================== API Communication ====================

// ==================== Fetch Wrapper with Timeout & Offline Detection ====================
async function apiFetch(url, options = {}, timeoutMs = 30000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(url, { ...options, signal: controller.signal });
        clearTimeout(timeoutId);
        if (!response.ok && response.status === 429) {
            throw new Error('Too many requests. Please wait a moment. / リクエストが多すぎます。しばらくお待ちください。');
        }
        if (!response.ok && response.status >= 500) {
            throw new Error(`Server error (${response.status}) / サーバーエラー (${response.status})`);
        }
        return response;
    } catch (err) {
        clearTimeout(timeoutId);
        if (err.name === 'AbortError') {
            throw new Error('Request timed out. The calculation may be too complex. / タイムアウトしました。計算が複雑すぎる可能性があります。');
        }
        if (typeof navigator !== 'undefined' && !navigator.onLine) {
            throw new Error('No internet connection. / インターネット接続がありません。');
        }
        throw err;
    }
}

// Load substance list from API
async function loadSubstances() {
    try {
        const res = await apiFetch(`${API_BASE}/substances`, {}, 10000);
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
    const res = await apiFetch(`${API_BASE}/calculate/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cases }),
    }, 300000); // 5min for batch
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
