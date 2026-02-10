// ==================== Configuration ====================
const API_BASE = '/api/v1';

// Substance data (loaded from API)
let SUBSTANCES_DATA = [];

// Fallback substance list
const SUBSTANCES_FALLBACK = [
    { id: 'water', name_ja: '水', name_en: 'Water', formula: 'H2O' },
    { id: 'ethanol', name_ja: 'エタノール', name_en: 'Ethanol', formula: 'C2H5OH' },
    { id: 'methanol', name_ja: 'メタノール', name_en: 'Methanol', formula: 'CH3OH' },
    { id: 'acetone', name_ja: 'アセトン', name_en: 'Acetone', formula: 'C3H6O' },
    { id: 'benzene', name_ja: 'ベンゼン', name_en: 'Benzene', formula: 'C6H6' },
    { id: 'toluene', name_ja: 'トルエン', name_en: 'Toluene', formula: 'C7H8' },
    { id: 'ammonia', name_ja: 'アンモニア', name_en: 'Ammonia', formula: 'NH3' },
    { id: 'nitrogen', name_ja: '窒素', name_en: 'Nitrogen', formula: 'N2' },
    { id: 'oxygen', name_ja: '酸素', name_en: 'Oxygen', formula: 'O2' },
    { id: 'hydrogen', name_ja: '水素', name_en: 'Hydrogen', formula: 'H2' },
];

const PROPERTIES = {
    'vapor_pressure': { name: 'Vapor Pressure', unit: 'kPa', factor: 0.001 },
    'liquid_density': { name: 'Liquid Density', unit: 'kg/m³', factor: 1 },
    'liquid_viscosity': { name: 'Liquid Viscosity', unit: 'mPa·s', factor: 1000 },
    'heat_of_vaporization': { name: 'Heat of Vaporization', unit: 'kJ/mol', factor: 0.001 },
    'surface_tension': { name: 'Surface Tension', unit: 'mN/m', factor: 1000 },
    'boiling_point': { name: 'Boiling Point', unit: 'K', factor: 1 }
};

const UNITS = {
    temperature: {
        K: { toBase: v => v, fromBase: v => v },
        C: { toBase: v => v + 273.15, fromBase: v => v - 273.15 },
        F: { toBase: v => (v - 32) * 5/9 + 273.15, fromBase: v => (v - 273.15) * 9/5 + 32 }
    },
    pressure: {
        Pa: { toBase: v => v, fromBase: v => v },
        kPa: { toBase: v => v * 1000, fromBase: v => v / 1000 },
        atm: { toBase: v => v * 101325, fromBase: v => v / 101325 },
        bar: { toBase: v => v * 100000, fromBase: v => v / 100000 }
    }
};

const activeUnits = { 'prop-temp': 'K', 'prop-press': 'Pa' };

// Shared state variables
let lastResult = null;
let propChart = null;
let lastCalculationData = {};
let pendingImportData = null;

// ==================== Prompt Template Constants ====================
const SKILL_NAMES = {
    property_estimation: { ja: '物性推算', en: 'Property Estimation' },
    distillation: { ja: '蒸留塔設計', en: 'Distillation Column Design' },
    mass_balance: { ja: '物質収支', en: 'Mass Balance' },
    heat_balance: { ja: '熱収支', en: 'Heat Balance' },
    extraction: { ja: '液液抽出', en: 'Liquid-Liquid Extraction' },
    absorption: { ja: 'ガス吸収', en: 'Gas Absorption' },
    lcoh: { ja: '水素原価計算', en: 'Levelized Cost of Hydrogen' }
};

const SKILL_PARAMS = {
    property_estimation: [
        { name: 'substance', ja: '物質名', en: 'Substance name', required: true, example: 'ethanol', choices: 'water, ethanol, methanol, benzene, toluene, acetone, etc.' },
        { name: 'property', ja: '物性', en: 'Property', required: true, example: 'vapor_pressure', choices: 'vapor_pressure, liquid_density, gas_density, liquid_viscosity, gas_viscosity, heat_capacity_liquid, heat_capacity_gas, thermal_conductivity_liquid, thermal_conductivity_gas, surface_tension, heat_of_vaporization, critical_temperature, critical_pressure, acentric_factor, molecular_weight' },
        { name: 'temperature', ja: '温度', en: 'Temperature', required: false, unit: 'K', default: 298.15, range: '50-2000' },
        { name: 'pressure', ja: '圧力', en: 'Pressure', required: false, unit: 'Pa', default: 101325, range: '100-100000000' }
    ],
    distillation: [
        { name: 'light_component', ja: '軽沸成分', en: 'Light component', required: true, example: 'ethanol' },
        { name: 'heavy_component', ja: '重沸成分', en: 'Heavy component', required: true, example: 'water' },
        { name: 'feed_flow_rate', ja: '原料流量', en: 'Feed flow rate', required: true, unit: 'kmol/h', example: 100 },
        { name: 'feed_composition', ja: '原料中軽沸成分モル分率', en: 'Light component mole fraction in feed', required: true, range: '0.001-0.999', example: 0.4 },
        { name: 'distillate_purity', ja: '留出液目標純度', en: 'Target distillate purity', required: true, range: '0.5-0.9999', example: 0.95 },
        { name: 'bottoms_purity', ja: '缶出液目標純度（重沸成分）', en: 'Target bottoms purity (heavy component)', required: true, range: '0.5-0.9999', example: 0.98 },
        { name: 'feed_temperature', ja: '原料温度', en: 'Feed temperature', required: false, unit: 'K', default: 350, range: '200-600' },
        { name: 'feed_condition', ja: '原料熱状態 q', en: 'Feed thermal condition q', required: false, default: 1.0, range: '-0.5-1.5' },
        { name: 'column_pressure', ja: '塔頂圧力', en: 'Column pressure', required: false, unit: 'Pa', default: 101325 },
        { name: 'reflux_ratio_factor', ja: '還流比係数（最小還流比に対する倍率）', en: 'Reflux ratio factor', required: false, default: 1.3, range: '1.05-5.0' }
    ],
    mass_balance: [
        { name: 'components', ja: '成分リスト', en: 'Components (comma-separated)', required: true, example: 'ethanol, water' },
        { name: 'feed_flow_rate', ja: '原料流量', en: 'Feed flow rate', required: true, unit: 'mol/s', example: 100 },
        { name: 'feed_composition', ja: '原料組成（第1成分モル分率）', en: 'Feed composition (first component mole fraction)', required: true, range: '0-1', example: 0.4 },
        { name: 'distillate_composition', ja: '留出液組成', en: 'Distillate composition', required: true, range: '0-1', example: 0.95 },
        { name: 'bottoms_composition', ja: '缶出液組成', en: 'Bottoms composition', required: true, range: '0-1', example: 0.05 }
    ],
    heat_balance: [
        { name: 'substance', ja: '物質名', en: 'Substance name', required: true, example: 'water' },
        { name: 'flow_rate', ja: '流量', en: 'Flow rate', required: true, unit: 'mol/s', example: 100 },
        { name: 'inlet_temperature', ja: '入口温度', en: 'Inlet temperature', required: true, unit: 'K', example: 300 },
        { name: 'outlet_temperature', ja: '出口温度', en: 'Outlet temperature', required: true, unit: 'K', example: 400 },
        { name: 'pressure', ja: '圧力', en: 'Pressure', required: false, unit: 'Pa', default: 101325 },
        { name: 'phase_change', ja: '相変化考慮', en: 'Consider phase change', required: false, default: true, type: 'boolean' }
    ],
    extraction: [
        { name: 'solute', ja: '溶質', en: 'Solute', required: true, example: 'acetic_acid' },
        { name: 'carrier', ja: '原溶媒', en: 'Carrier solvent', required: true, example: 'water' },
        { name: 'solvent', ja: '抽剤', en: 'Extraction solvent', required: true, example: 'ethyl_acetate' },
        { name: 'feed_flow_rate', ja: '原料流量', en: 'Feed flow rate', required: true, unit: 'kmol/h', example: 100 },
        { name: 'feed_composition', ja: '原料中溶質モル分率', en: 'Solute mole fraction in feed', required: true, range: '0.001-0.5', example: 0.1 },
        { name: 'solvent_flow_rate', ja: '抽剤流量', en: 'Solvent flow rate', required: true, unit: 'kmol/h', example: 50 },
        { name: 'temperature', ja: '温度', en: 'Temperature', required: false, unit: 'K', default: 298.15 },
        { name: 'recovery', ja: '目標抽出率', en: 'Target recovery', required: false, default: 0.9, range: '0-1' }
    ],
    absorption: [
        { name: 'gas_component', ja: '被吸収成分', en: 'Gas component to absorb', required: true, example: 'ammonia' },
        { name: 'carrier_gas', ja: 'キャリアガス', en: 'Carrier gas', required: true, example: 'air' },
        { name: 'solvent', ja: '吸収液', en: 'Absorbent', required: true, example: 'water' },
        { name: 'gas_flow_rate', ja: 'ガス流量', en: 'Gas flow rate', required: true, unit: 'kmol/h', example: 100 },
        { name: 'inlet_gas_composition', ja: '入口ガス組成', en: 'Inlet gas composition', required: false, default: 0.05, range: '0-1' },
        { name: 'liquid_flow_rate', ja: '液流量', en: 'Liquid flow rate', required: false, unit: 'kmol/h', example: 200 },
        { name: 'temperature', ja: '温度', en: 'Temperature', required: false, unit: 'K', default: 298.15 },
        { name: 'pressure', ja: '圧力', en: 'Pressure', required: false, unit: 'Pa', default: 101325 },
        { name: 'removal_efficiency', ja: '目標除去率', en: 'Target removal efficiency', required: false, default: 0.9, range: '0-0.9999' }
    ],
    lcoh: [
        { name: 'production_method', ja: '製造方法', en: 'Production method', required: true, choices: 'pem_electrolysis, alkaline_electrolysis, soec_electrolysis, smr, smr_ccs, atr_ccs', example: 'pem_electrolysis' },
        { name: 'capacity', ja: '設備容量', en: 'Capacity', required: true, unit: 'MW', range: '0.1-1000', example: 10 },
        { name: 'electricity_price', ja: '電力単価', en: 'Electricity price', required: false, unit: 'EUR/MWh', default: 50 },
        { name: 'natural_gas_price', ja: 'ガス単価', en: 'Natural gas price', required: false, unit: 'EUR/MWh', default: 30 },
        { name: 'operating_hours', ja: '年間稼働時間', en: 'Operating hours', required: false, unit: 'h/year', default: 4000, range: '1000-8760' },
        { name: 'capex_per_kw', ja: 'CAPEX単価', en: 'CAPEX per kW', required: false, unit: 'EUR/kW', range: '100-5000' },
        { name: 'opex_percent', ja: 'OPEX率', en: 'OPEX percentage', required: false, unit: '%', default: 3.0 },
        { name: 'discount_rate', ja: '割引率', en: 'Discount rate', required: false, unit: '%', default: 6.0 },
        { name: 'project_lifetime', ja: 'プロジェクト寿命', en: 'Project lifetime', required: false, unit: 'years', default: 20 },
        { name: 'carbon_price', ja: '炭素価格', en: 'Carbon price', required: false, unit: 'EUR/ton', default: 0 },
        { name: 'capex_subsidy_percent', ja: 'CAPEX補助率', en: 'CAPEX subsidy percent', required: false, unit: '%', default: 0 },
        { name: 'capex_subsidy_amount', ja: 'CAPEX補助額', en: 'CAPEX subsidy amount', required: false, unit: 'EUR', default: 0 },
        { name: 'maintenance_days', ja: '計画停止日数', en: 'Maintenance downtime days', required: false, unit: 'days/year', default: 0 },
        { name: 'labor_cost', ja: '人件費', en: 'Labor cost', required: false, unit: 'EUR/year', default: 0 },
        { name: 'maintenance_cost', ja: '保守費用', en: 'Maintenance cost', required: false, unit: 'EUR/year', default: 0 },
        { name: 'subsidies', ja: '補助金', en: 'Subsidy per kg', required: false, unit: 'EUR/kg H2', default: 0 },
        { name: 'water_price', ja: '水価格', en: 'Water price', required: false, unit: 'EUR/m3', default: 2.0 },
    ]
};

// ==================== Help Content ====================
const HELP_CONTENT = {
    overview: {
        title: 'ChemEngとは?',
        content: `
            <p><strong>ChemEng</strong>は、化学工学の計算を簡単に行えるWebアプリケーションです。</p>
            <p>主な機能:</p>
            <ul>
                <li><strong>物性推算</strong> - 蒸気圧、密度、粘度などの物性値を計算</li>
                <li><strong>蒸留塔設計</strong> - McCabe-Thiele法による段数計算</li>
                <li><strong>物質収支</strong> - 分離プロセスの物質収支計算</li>
                <li><strong>熱収支</strong> - 加熱/冷却に必要な熱量計算</li>
            </ul>
            <p>左のパネルでパラメータを入力し、計算を実行すると右のパネルに結果が表示されます。</p>
        `
    },
    property: {
        title: '物性推算の使い方',
        content: `
            <p><strong>物性推算</strong>では、化学物質の物理的性質を計算できます。</p>
            <p><strong>入力項目:</strong></p>
            <ul>
                <li><strong>物質名</strong> - ethanol, water, benzene などを入力（オートコンプリート対応）</li>
                <li><strong>物性</strong> - 蒸気圧、液密度、粘度、蒸発熱、表面張力、沸点から選択</li>
                <li><strong>温度</strong> - K, °C, °F で入力可能（チップで単位切替）</li>
                <li><strong>圧力</strong> - Pa, kPa, atm, bar で入力可能</li>
            </ul>
            <p><strong>ヒント:</strong> <kbd>Ctrl</kbd>+<kbd>Enter</kbd> で計算を実行できます。</p>
        `
    },
    distillation: {
        title: '蒸留塔設計の使い方',
        content: `
            <p><strong>蒸留塔設計</strong>では、McCabe-Thiele法を用いた二成分蒸留塔の設計ができます。</p>
            <p><strong>入力項目:</strong></p>
            <ul>
                <li><strong>軽沸/重沸成分</strong> - 分離する2成分を指定</li>
                <li><strong>原料流量</strong> - kmol/h で入力</li>
                <li><strong>組成</strong> - 軽沸成分のモル分率（0〜1）</li>
                <li><strong>還流比係数</strong> - R/Rmin（通常1.2〜1.5）</li>
            </ul>
            <p><strong>出力:</strong> 理論段数、フィード段、塔径、コンデンサー/リボイラー熱負荷</p>
        `
    },
    mass_balance: {
        title: '物質収支の使い方',
        content: `
            <p><strong>物質収支</strong>では、分離プロセスの物質収支を計算します。</p>
            <p><strong>入力項目:</strong></p>
            <ul>
                <li><strong>成分リスト</strong> - カンマ区切りで入力（例: ethanol, water）</li>
                <li><strong>原料流量</strong> - mol/s で入力</li>
                <li><strong>各組成</strong> - 第一成分のモル分率</li>
            </ul>
            <p><strong>出力:</strong> 各ストリームの流量とクロージャー（収支誤差）</p>
        `
    },
    heat_balance: {
        title: '熱収支の使い方',
        content: `
            <p><strong>熱収支</strong>では、加熱・冷却に必要な熱量を計算します。</p>
            <p><strong>入力項目:</strong></p>
            <ul>
                <li><strong>物質名</strong> - 対象物質を指定</li>
                <li><strong>流量</strong> - mol/s で入力</li>
                <li><strong>入口/出口温度</strong> - K で入力</li>
                <li><strong>圧力</strong> - Pa で入力</li>
                <li><strong>熱効率</strong> - 0〜1 の値</li>
            </ul>
            <p><strong>出力:</strong> 顕熱、潜熱、総熱負荷、実熱負荷、相変化情報</p>
        `
    }
};
