// PolPilot — API Layer
// Flag to switch between mock data and real backend
const USE_MOCK = true;
const API_BASE = 'http://localhost:8000/api';
const EMPRESA_ID = 'empresa_demo';

// ═══════════════════════════════════════════════════════════════
// MOCK DATA (built from polpilot/backend/seed/*.json)
// ═══════════════════════════════════════════════════════════════

const MOCK = {
  profile: {
    name: "Calatayud Brakes & Clutches SRL",
    cuit: "30-71584923-4",
    sector: "Retail",
    sub_sector: "Automotive brake & clutch parts distribution",
    location: "Venado Tuerto",
    province: "Santa Fe",
    employees_count: 8,
    years_in_business: 42,
    annual_revenue: 678000000,
    revenue_target: 800000000,
    description: "Family business founded in 1984 dedicated to the sale and distribution of automotive brake and clutch parts."
  },

  financials: [
    { year: 2025, month: 10, revenue: 48000000, expenses: 46500000, net_cash_flow: 1500000, cash_balance: 4200000, accounts_receivable: 11000000, accounts_payable: 18500000, inventory_value: 40000000, notes: "Stable month, pre-summer season start" },
    { year: 2025, month: 11, revenue: 51200000, expenses: 48800000, net_cash_flow: 2400000, cash_balance: 6600000, accounts_receivable: 12500000, accounts_payable: 19200000, inventory_value: 41500000, notes: "Wholesale demand up due to season" },
    { year: 2025, month: 12, revenue: 58500000, expenses: 54200000, net_cash_flow: 4300000, cash_balance: 10900000, accounts_receivable: 13800000, accounts_payable: 20000000, inventory_value: 38000000, notes: "Peak December sales" },
    { year: 2026, month: 1, revenue: 42000000, expenses: 45000000, net_cash_flow: -3000000, cash_balance: 7900000, accounts_receivable: 10500000, accounts_payable: 21000000, inventory_value: 42000000, notes: "Low January due to holidays" },
    { year: 2026, month: 2, revenue: 49800000, expenses: 47200000, net_cash_flow: 2600000, cash_balance: 5500000, accounts_receivable: 13200000, accounts_payable: 21500000, inventory_value: 43500000, notes: "Post-holiday recovery" },
    { year: 2026, month: 3, revenue: 56500000, expenses: 55588600, net_cash_flow: -2068600, cash_balance: 1131400, accounts_receivable: 14200000, accounts_payable: 22300000, inventory_value: 45000000, notes: "Negative flow due to import supplier payments" }
  ],

  indicators: [
    { period: "2026-03", gross_margin: 0.317, net_margin: 0.016, roa: 0.011, roe: 0.015, current_ratio: 0.91, quick_ratio: 0.23, working_capital: -8100000, debt_to_equity: 0.38, days_receivable: 28, days_payable: 42, inventory_turnover: 35, cash_cycle: 21, health_score: 58 },
    { period: "2025-Q4", gross_margin: 0.33, net_margin: 0.045, roa: 0.03, roe: 0.04, current_ratio: 1.15, quick_ratio: 0.35, working_capital: 5200000, debt_to_equity: 0.32, days_receivable: 25, days_payable: 38, inventory_turnover: 30, cash_cycle: 17, health_score: 72 }
  ],

  clients: [
    { name: "Venado Tuerto Workshop Network (12 shops)", client_type: "fleet", annual_revenue: 144000000, avg_payment_days: 30, outstanding_balance: 4500000, risk_level: "low" },
    { name: "South Santa Fe Lube Centers (8 locations)", client_type: "fleet", annual_revenue: 102000000, avg_payment_days: 35, outstanding_balance: 3200000, risk_level: "low" },
    { name: "Walk-in retail", client_type: "individual", annual_revenue: 222000000, avg_payment_days: 0, outstanding_balance: 0, risk_level: "low" },
    { name: "MercadoLibre (online store)", client_type: "workshop", annual_revenue: 50400000, avg_payment_days: 14, outstanding_balance: 2100000, risk_level: "low" },
    { name: "Regional used-car dealerships", client_type: "fleet", annual_revenue: 63600000, avg_payment_days: 45, outstanding_balance: 5300000, risk_level: "medium" },
    { name: "San Martín Lube Center", client_type: "workshop", annual_revenue: 8400000, avg_payment_days: 95, outstanding_balance: 450000, risk_level: "high" },
    { name: "Rossi Auto Repair", client_type: "workshop", annual_revenue: 5200000, avg_payment_days: 120, outstanding_balance: 320000, risk_level: "high" },
    { name: "Frenos del Sur", client_type: "workshop", annual_revenue: 3600000, avg_payment_days: 105, outstanding_balance: 230000, risk_level: "high" }
  ],

  suppliers: [
    { name: "Frasle Argentina SA", avg_price_level: "$$", payment_terms_days: 30, delivery_time_hours: 48, reliability_pct: 95.0, is_primary: true, notes: "Brake pads and linings. Domestic. Primary supplier." },
    { name: "Sachs Automotive", avg_price_level: "$$$", payment_terms_days: 60, delivery_time_hours: 72, reliability_pct: 92.0, is_primary: true, notes: "Clutch kits. Domestic." },
    { name: "Fremax Brasil", avg_price_level: "$$", payment_terms_days: 30, delivery_time_hours: 168, reliability_pct: 88.0, is_primary: false, notes: "Imported brake discs from Brazil." },
    { name: "Turk Fren Sanayi", avg_price_level: "$", payment_terms_days: 0, delivery_time_hours: 720, reliability_pct: 82.0, is_primary: false, notes: "Brake cylinders and pumps from Turkey." },
    { name: "Distri Repuestos Rosario", avg_price_level: "$$", payment_terms_days: 15, delivery_time_hours: 24, reliability_pct: 90.0, is_primary: false, notes: "Complementary distributor." }
  ],

  products: [
    { name: "Ferodo Brake Pads", category: "Brakes", monthly_revenue: 10880000, margin_pct: 42.2, current_stock: 340, min_stock: 100, supplier_id: 1 },
    { name: "VW Gol Vented Brake Disc", category: "Brakes", monthly_revenue: 8160000, margin_pct: 38.2, current_stock: 120, min_stock: 40, supplier_id: 3 },
    { name: "Sachs Fiat Clutch Kit", category: "Clutches", monthly_revenue: 19175000, margin_pct: 37.3, current_stock: 65, min_stock: 20, supplier_id: 2 },
    { name: "Toyota Master Brake Cylinder", category: "Brakes", monthly_revenue: 6975000, margin_pct: 38.7, current_stock: 45, min_stock: 15, supplier_id: 4 },
    { name: "Universal Brake Hose", category: "Brakes", monthly_revenue: 4200000, margin_pct: 43.3, current_stock: 280, min_stock: 80, supplier_id: 5 },
    { name: "Clutch Cylinder Repair Kit", category: "Clutches", monthly_revenue: 3200000, margin_pct: 45.0, current_stock: 90, min_stock: 30, supplier_id: 2 }
  ],

  employees: [
    { name: "Martín Ruiz", role: "Counter Sales Manager", area: "Sales", salary: 850000, workload_pct: 100 },
    { name: "Carlos Pereyra", role: "Counter Sales Rep", area: "Sales", salary: 720000, workload_pct: 95 },
    { name: "Lucía Gómez", role: "Admin & Billing", area: "Administration", salary: 680000, workload_pct: 110 },
    { name: "Diego Fernández", role: "Warehouse & Logistics", area: "Logistics", salary: 620000, workload_pct: 90 },
    { name: "Pablo Acosta", role: "Wholesale Sales Rep", area: "Sales", salary: 750000, workload_pct: 105 },
    { name: "Ana Torres", role: "Collections", area: "Administration", salary: 650000, workload_pct: 85 },
    { name: "Ramiro Díaz", role: "Driver & Deliveries", area: "Logistics", salary: 580000, workload_pct: 100 },
    { name: "Sofía Méndez", role: "Customer Service / Social", area: "Marketing", salary: 550000, workload_pct: 80 }
  ],

  credits: [
    { bank_name: "Banco Nación", credit_name: "SME Productive Investment Loan", credit_type: "investment", annual_rate: 0.29, max_amount: 80000000, min_amount: 5000000, max_term_months: 48, requirements: '["Active SME Certificate (AFIP)","Minimum 2 years in business","No BCRA debt","Projected cash flow statement"]', requires_mipyme_cert: true, url: "https://www.bna.com.ar/Empresas/Pymes", matches_profile: true, qualification_reasons_ok: ["Has SME certificate","Amount within revenue range","Current ratio 0.91 (adjusted)"], qualification_reasons_fail: [] },
    { bank_name: "Banco Provincia", credit_name: "SME Import Credit Line", credit_type: "investment", annual_rate: 0.26, max_amount: 60000000, min_amount: 3000000, max_term_months: 36, requirements: '["SME Certificate","Documented foreign trade operation","No tax debt"]', requires_mipyme_cert: true, url: "https://www.bancoprovincia.com.ar/web/pymes", matches_profile: true, qualification_reasons_ok: ["Has SME certificate","Amount within revenue range"], qualification_reasons_fail: [] },
    { bank_name: "Banco Galicia", credit_name: "Working Capital Loan", credit_type: "working_capital", annual_rate: 0.38, max_amount: 30000000, min_amount: 1000000, max_term_months: 12, requirements: '["Checking account with 6 months history","Verifiable revenue"]', requires_mipyme_cert: false, url: "https://www.galicia.ar/empresas", matches_profile: true, qualification_reasons_ok: ["No SME cert required","Amount within range"], qualification_reasons_fail: [] },
    { bank_name: "Ministry of Production", credit_name: "FONDEP Program", credit_type: "investment", annual_rate: 0.15, max_amount: 50000000, min_amount: 5000000, max_term_months: 60, requirements: '["Approved productive project","SME Certificate","20% matching funds"]', requires_mipyme_cert: true, url: "https://www.argentina.gob.ar/produccion/fondep", matches_profile: true, qualification_reasons_ok: ["Has SME certificate"], qualification_reasons_fail: ["Requires approved project and 20% matching funds"] },
    { bank_name: "Banco ICBC", credit_name: "Trade Finance Loan", credit_type: "investment", annual_rate: 0.08, max_amount: 120000000, min_amount: 10000000, max_term_months: 6, requirements: '["Import track record","Letter of credit or purchase order","Bank guarantee"]', requires_mipyme_cert: false, url: "https://www.icbc.com.ar/empresas", matches_profile: false, qualification_reasons_ok: ["Lowest rate in market (8%)"], qualification_reasons_fail: ["Max amount high vs revenue","Requires bank guarantee"] }
  ],

  creditProfile: {
    cuit: "30-71584923-4", situation: 1, total_debt: 0, days_overdue: 0,
    last_24_months: [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    rejected_checks: []
  },

  macro: {
    inflacion_mensual: 0.028, inflacion_interanual: 0.42,
    usd_oficial: 1200.0, usd_blue: 1350.0,
    tasa_badlar: 0.32, tasa_plazo_fijo_30d: 0.30,
    riesgo_pais: 780, pbi_variacion_anual: 0.045, desempleo: 0.068
  },

  regulations: [
    { title: "AFIP Resolution 5432/2025: Simplified SME Import Regime", summary: "New simplified import regime for SMEs in Tier 1 and 2 categories.", source: "official_gazette", status: "confirmed", relevance_score: 0.95, published_date: "2025-11-15" },
    { title: "Decree 124/2026: SME Import Rate Subsidy", summary: "5-point interest rate subsidy for productive SME loans.", source: "official_gazette", status: "confirmed", relevance_score: 0.98, published_date: "2026-02-01" },
    { title: "BCRA Communication A-7890: Preferential Lines Without Reciprocity", summary: "SMEs can access preferential credit lines without bank reciprocity requirements.", source: "bcra", status: "confirmed", relevance_score: 0.85, published_date: "2026-03-10" }
  ],

  sectorSignals: [
    { signal_type: "demand_shift", description: "Increased demand for imported parts due to import deregulation.", sector: "Automotive parts", impact_level: "high" },
    { signal_type: "price_change", description: "Price drop on imported discs and pads (-15% average).", sector: "Automotive parts", impact_level: "medium" }
  ],

  benchmark: {
    gross_margin: { company: 0.317, sector_avg: 0.30, diff: 0.017, status: "above" },
    payment_days: { company: 28, sector_avg: 35, diff: -7, status: "better" }
  }
};

// ═══════════════════════════════════════════════════════════════
// COMPUTED MOCK DATA (replicas of data_service.py logic)
// ═══════════════════════════════════════════════════════════════

function computeAlerts() {
  const fin = MOCK.financials[MOCK.financials.length - 1];
  const ind = MOCK.indicators[0];
  const overdue = MOCK.clients.filter(c => c.risk_level === 'high');
  const alerts = [];

  if (fin.net_cash_flow < 0) {
    alerts.push({ type: 'cash_flow', severity: 'critical', title: 'Negative cash flow', description: `March 2026: ${formatCurrency(fin.net_cash_flow)}. Large payment to import suppliers.`, action_suggested: 'Review available working capital loans' });
  }
  if (ind.current_ratio < 1.0) {
    alerts.push({ type: 'liquidity', severity: 'warning', title: 'Current ratio below 1.0', description: `Current ratio: ${ind.current_ratio}. Negative working capital: ${formatCurrency(ind.working_capital)}`, action_suggested: 'Evaluate refinancing current liabilities' });
  }
  if (overdue.length > 0) {
    const totalOverdue = overdue.reduce((s, c) => s + c.outstanding_balance, 0);
    alerts.push({ type: 'delinquency', severity: 'warning', title: `${overdue.length} overdue clients`, description: `Outstanding debt: ${formatCurrency(totalOverdue)}. Average 107 days past due.`, action_suggested: 'Activate intensive collection management' });
  }
  if (fin.cash_balance < 2000000) {
    alerts.push({ type: 'cash_reserve', severity: 'critical', title: 'Minimum cash reserve', description: `Current balance: ${formatCurrency(fin.cash_balance)}. Less than 1 day of operations.`, action_suggested: 'Urgent: seek liquidity injection' });
  }
  return alerts;
}

function computeCashPosition() {
  const fin = MOCK.financials[MOCK.financials.length - 1];
  const ind = MOCK.indicators[0];
  const overdue = MOCK.clients.filter(c => c.risk_level === 'high');
  return {
    cash_balance: fin.cash_balance,
    net_cash_flow: fin.net_cash_flow,
    accounts_receivable: fin.accounts_receivable,
    accounts_payable: fin.accounts_payable,
    current_ratio: ind.current_ratio,
    health_score: ind.health_score,
    total_overdue: overdue.reduce((s, c) => s + c.outstanding_balance, 0),
    delinquent_count: overdue.length
  };
}

// ═══════════════════════════════════════════════════════════════
// PUBLIC API FUNCTIONS
// ═══════════════════════════════════════════════════════════════

async function fetchDashboard(empresaId = EMPRESA_ID) {
  if (USE_MOCK) {
    await fakeLag(300);
    return {
      profile: MOCK.profile,
      financials: MOCK.financials,
      indicators: MOCK.indicators[0],
      cashPosition: computeCashPosition(),
      morosos: MOCK.clients.filter(c => c.risk_level === 'high'),
      benchmark: MOCK.benchmark,
      alerts: computeAlerts()
    };
  }
  const res = await fetch(`${API_BASE}/dashboard/${empresaId}`);
  return res.json();
}

async function fetchFinanzas(empresaId = EMPRESA_ID) {
  if (USE_MOCK) {
    await fakeLag(250);
    return {
      financials: MOCK.financials,
      indicators: MOCK.indicators,
      clients: MOCK.clients,
      morosos: MOCK.clients.filter(c => c.risk_level === 'high'),
      products: MOCK.products,
      suppliers: MOCK.suppliers,
      employees: MOCK.employees
    };
  }
  const res = await fetch(`${API_BASE}/finanzas/${empresaId}`);
  return res.json();
}

async function fetchCreditos(empresaId = EMPRESA_ID) {
  if (USE_MOCK) {
    await fakeLag(350);
    return {
      credits: MOCK.credits,
      creditProfile: MOCK.creditProfile,
      macro: MOCK.macro,
      regulations: MOCK.regulations,
      sectorSignals: MOCK.sectorSignals
    };
  }
  const res = await fetch(`${API_BASE}/creditos/${empresaId}`);
  return res.json();
}

// ═══════════════════════════════════════════════════════════════
// ANGELA CHAT — SSE Mock / Real
// ═══════════════════════════════════════════════════════════════

// ── Moment 1: Chaotic audio ingestion ──
const MOCK_AUDIO_RESPONSE = `Gonzalo, I processed your audio. Here's the March 2026 summary:

**Monthly P&L**

| Item | Amount |
|------|--------|
| Counter sales | $18,500,000 |
| Wholesale sales | $32,000,000 |
| Other income | $6,000,000 |
| **Total revenue** | **$56,500,000** |
| Cost of goods | -$38,000,000 |
| Payroll + taxes | -$11,200,000 |
| Rent | -$1,800,000 |
| Other operating expenses | -$4,400,000 |
| **Operating income** | **$1,100,000** |

**Cash on hand:** $1,131,400
**Gross margin:** 31.7%
**Health Score:** 58/100 (adjusted)

**Alerts:**
- Current ratio 0.91 — below the 1.0 threshold
- Overdue accounts: $3,450,000 pending (Rosario $3M + San Martín Lube Center $450K)
- Negative cash flow this month: -$2,068,600

Once you send the Excel I'll fine-tune the numbers. Want me to build a collection plan for the overdue accounts?`;

// ── Moment 2: Proactive alert ──
const MOCK_ALERTA_RESPONSE = `**Opportunity Alert**

Gonzalo, I detected something important:

Auto parts imports have been deregulated (AFIP Resolution 5432/2025). I found that importing directly from **Turk Fren Sanayi** in Turkey costs **20% less** than buying through Frasle or Fremax as distributors.

**Impact on your business:**
- Unit cost for brake pads: drops from $18,500 to $14,800
- Unit cost for vented discs: drops from $42,000 to $33,600
- **Your gross margin goes from 31.7% to 39.8% (+8.1 points)**

Plus, Decree 124/2026 gives you a 5-point interest rate subsidy if you use a loan to import.

Want me to analyze if it's worth bringing in a container?`;

// ── Moment 3: Loans + Bank Folder ──
const MOCK_CREDITOS_RESPONSE = `Gonzalo, I analyzed your situation:

**Your cash today:** $1,131,400
**Container cost:** USD 35,000 (~$42,000,000)
**You can't cover it with cash.** But your credit profile is solid.

**Your profile:**
- 42 years in business
- No BCRA debt (status 1 — spotless)
- Net worth: $59.5M
- Revenue trending up

I searched all available loans on the market and filtered for your eligibility. Found 3:

**#1 — SME Productive Investment Loan (Banco Nación)**
- Rate: 29% annual → **drops to 24% with import subsidy**
- Amount: up to $80M
- Term: 48 months
- Est. payment: **$1,380,000/mo**
- Requirements you meet: SME Cert, 2+ years in business, No BCRA debt
- Missing: projected cash flow statement (I can generate it)

**#2 — SME Import Credit Line (Banco Provincia)**
- Rate: 26% → **drops to 21% with subsidy**
- Up to USD 50,000 | Term: 36 months
- Est. payment: **$1,620,000/mo**
- Missing: documented foreign trade operation

**#3 — Trade Finance Loan (Banco ICBC)**
- Rate: 8% annual in USD (lowest)
- Term: 6 months (short)
- Est. payment: **$6,100,000/mo**
- Risk: short term, you need to sell the container fast

**My recommendation:** Go with Banco Nación. The $1.4M/mo payment is manageable with your $56.5M revenue. With 2 stock rotations (3 months each), you recover the investment in 6 months.

**I've prepared your complete bank application folder.** PDF attached, ready to submit.`;

// ── Fallback: generic credits (legacy) ──
const MOCK_DEMO_RESPONSE = MOCK_CREDITOS_RESPONSE;

function detectMoment(message) {
  const lw = message.toLowerCase();
  if (lw.includes('audio') || lw.includes('we sold') || lw.includes('counter sales') || lw.includes('process my audio') || lw.includes('parse') || lw.includes('recorded') || lw.includes('voice memo') || lw.includes('revenue this month') || lw.includes('56 million')) return 'audio';
  if (lw.includes('opportunity') || lw.includes('alert') || lw.includes('detect') || lw.includes('proactiv') || lw.includes('direct import') || lw.includes('turk fren') || lw.includes('deregulat')) return 'alerta';
  if (lw.includes('loan') || lw.includes('credit') || lw.includes('financ') || lw.includes('bank') || lw.includes('rate') || lw.includes('cash for') || lw.includes('container') || lw.includes('bank folder') || lw.includes('worth it') || lw.includes('afford')) return 'creditos';
  return null;
}

function sendQueryMock(message, context, onStep, onComplete) {
  const moment = detectMoment(message);
  let steps, response, cards, navigate_to, extra;

  if (moment === 'audio') {
    steps = [
      { step: 'classifying', message: 'Receiving WhatsApp audio...', delay: 500 },
      { step: 'expanding', message: 'Transcribing audio (22 seconds)...', delay: 1100 },
      { step: 'agent_finance', message: 'Parsing financial data from audio...', delay: 1400 },
      { step: 'meshing', message: 'Building income statement...', delay: 1000 },
      { step: 'agent_research', message: 'Calculating Health Score and alerts...', delay: 800 },
      { step: 'validating', message: 'Generating structured summary...', delay: 500 }
    ];
    response = MOCK_AUDIO_RESPONSE;
    cards = null;
    navigate_to = 'home';
    extra = {
      health_score: 58,
      alerts: [
        { type: 'warning', text: 'Current ratio 0.91 < 1.0' },
        { type: 'danger', text: 'Negative cash flow: -$2,068,600' },
        { type: 'warning', text: 'Overdue: $3,450,000 (2 clients)' }
      ]
    };

  } else if (moment === 'alerta') {
    steps = [
      { step: 'agent_research', message: 'Monitoring regulations and official gazette...', delay: 700 },
      { step: 'classifying', message: 'Detected: AFIP Resolution 5432/2025...', delay: 1000 },
      { step: 'agent_economy', message: 'Cross-referencing with current suppliers...', delay: 1200 },
      { step: 'agent_finance', message: 'Calculating impact on gross margin...', delay: 1100 },
      { step: 'meshing', message: 'Evaluating Decree 124/2026 — rate subsidy...', delay: 900 },
      { step: 'validating', message: 'Verifying opportunity at 95% confidence...', delay: 500 }
    ];
    response = MOCK_ALERTA_RESPONSE;
    cards = [
      { type: 'opportunity', bank: 'Current cost', name: 'National distributor', rate: '$18,500/u', amount: 'Margin 31.7%', match: false },
      { type: 'opportunity', bank: 'Direct import', name: 'Turk Fren Sanayi', rate: '$14,800/u', amount: 'Margin 39.8%', match: true }
    ];
    navigate_to = null;

  } else {
    steps = [
      { step: 'classifying', message: 'Classifying your query...', delay: 600 },
      { step: 'agent_finance', message: 'Analyzing cash and payment capacity...', delay: 1200 },
      { step: 'agent_economy', message: 'Searching available loans on the market...', delay: 1500 },
      { step: 'expanding', message: 'Simulating Credit Committee...', delay: 2000 },
      { step: 'agent_research', message: 'Ranking loans by suitability...', delay: 1000 },
      { step: 'meshing', message: 'Generating bank application folder (PDF)...', delay: 1200 },
      { step: 'validating', message: 'Verifying response quality...', delay: 500 }
    ];
    response = MOCK_CREDITOS_RESPONSE;
    cards = [
      { type: 'credit', bank: 'Banco Nación', name: 'SME Investment Loan', rate: '24%', amount: '$80M · 48 mo', match: true },
      { type: 'credit', bank: 'Banco Provincia', name: 'SME Import Line', rate: '21%', amount: '$60M · 36 mo', match: true },
      { type: 'credit', bank: 'Banco ICBC', name: 'Trade Finance', rate: '8% USD', amount: '$120M · 6 mo', match: false }
    ];
    navigate_to = 'creditos';
    extra = {
      pdf: 'Financial_Profile_Calatayud_SRL_April_2026.pdf'
    };
  }

  let totalDelay = 0;
  const timers = [];

  for (const s of steps) {
    totalDelay += s.delay;
    timers.push(setTimeout(() => onStep(s), totalDelay));
  }

  totalDelay += 600;
  timers.push(setTimeout(() => {
    onComplete({
      step: 'complete',
      response: response,
      cards: cards,
      navigate_to: navigate_to,
      extra: extra || null
    });
  }, totalDelay));

  return () => timers.forEach(clearTimeout);
}

async function sendQuery(message, context = {}) {
  if (USE_MOCK) {
    return new Promise((resolve) => {
      const steps = [];
      sendQueryMock(message, context,
        (step) => steps.push(step),
        (result) => resolve({ steps, ...result })
      );
    });
  }
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ empresa_id: EMPRESA_ID, message, context })
  });
  return res.json();
}

function sendQueryStreaming(message, context, onStep, onComplete) {
  if (USE_MOCK) {
    return sendQueryMock(message, context, onStep, onComplete);
  }
  const evtSource = new EventSource(`${API_BASE}/query/stream?empresa_id=${EMPRESA_ID}&message=${encodeURIComponent(message)}`);
  evtSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.step === 'complete') {
      onComplete(data);
      evtSource.close();
    } else {
      onStep(data);
    }
  };
  evtSource.onerror = () => evtSource.close();
  return () => evtSource.close();
}

async function ingestFile(file) {
  if (USE_MOCK) {
    await fakeLag(1500);
    const ext = file.name.split('.').pop().toLowerCase();
    const topicMap = { xlsx: 'finances', xls: 'finances', csv: 'finances', pdf: 'documents', jpg: 'documents', png: 'documents', jpeg: 'documents', txt: 'general', doc: 'documents', docx: 'documents' };
    return {
      filename: file.name,
      status: 'processed',
      chunks_created: Math.floor(Math.random() * 8) + 2,
      topic: topicMap[ext] || 'general',
      angela_comment: `Processed "${file.name}" successfully. Extracted ${Math.floor(Math.random() * 8) + 2} information chunks and integrated them into your knowledge base. This improves my context about your business.`
    };
  }
  const form = new FormData();
  form.append('empresa_id', EMPRESA_ID);
  form.append('file', file);
  const res = await fetch(`${API_BASE}/ingest`, { method: 'POST', body: form });
  return res.json();
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function fakeLag(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function formatCurrency(n) {
  if (n == null) return '-';
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(1) + 'B';
  if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return sign + '$' + (abs / 1e3).toFixed(0) + 'K';
  return sign + '$' + abs.toFixed(0);
}

function formatPct(n) {
  if (n == null) return '-';
  return (n * 100).toFixed(1) + '%';
}

function monthLabel(year, month) {
  const labels = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${labels[month]} ${String(year).slice(2)}`;
}
