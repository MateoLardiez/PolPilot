// PolPilot — API Layer
// USE_MOCK = false → llama al backend real (cd backend && uvicorn main:app --reload)
const USE_MOCK = true;
const API_BASE = 'http://localhost:8000';
const EMPRESA_ID = 'emp_001';

// ═══════════════════════════════════════════════════════════════
// MOCK DATA (construido a partir de polpilot/backend/seed/*.json)
// ═══════════════════════════════════════════════════════════════

const MOCK = {
  profile: {
    name: "Calatayud Frenos y Embragues SRL",
    cuit: "30-71584923-4",
    sector: "Comercio",
    sub_sector: "Venta y distribución de repuestos automotores",
    location: "Venado Tuerto",
    province: "Santa Fe",
    employees_count: 8,
    years_in_business: 42,
    annual_revenue: 678000000,
    revenue_target: 800000000,
    description: "Empresa familiar fundada en 1984 dedicada a la venta y distribución de repuestos de frenos y embragues automotores."
  },

  financials: [
    { year: 2025, month: 10, revenue: 48000000, expenses: 46500000, net_cash_flow: 1500000, cash_balance: 4200000, accounts_receivable: 11000000, accounts_payable: 18500000, inventory_value: 40000000, notes: "Mes estable, inicio temporada pre-verano" },
    { year: 2025, month: 11, revenue: 51200000, expenses: 48800000, net_cash_flow: 2400000, cash_balance: 6600000, accounts_receivable: 12500000, accounts_payable: 19200000, inventory_value: 41500000, notes: "Sube demanda mayorista por temporada" },
    { year: 2025, month: 12, revenue: 58500000, expenses: 54200000, net_cash_flow: 4300000, cash_balance: 10900000, accounts_receivable: 13800000, accounts_payable: 20000000, inventory_value: 38000000, notes: "Pico de ventas diciembre" },
    { year: 2026, month: 1, revenue: 42000000, expenses: 45000000, net_cash_flow: -3000000, cash_balance: 7900000, accounts_receivable: 10500000, accounts_payable: 21000000, inventory_value: 42000000, notes: "Enero bajo por vacaciones" },
    { year: 2026, month: 2, revenue: 49800000, expenses: 47200000, net_cash_flow: 2600000, cash_balance: 5500000, accounts_receivable: 13200000, accounts_payable: 21500000, inventory_value: 43500000, notes: "Recuperación post-vacaciones" },
    { year: 2026, month: 3, revenue: 56500000, expenses: 55588600, net_cash_flow: -2068600, cash_balance: 1131400, accounts_receivable: 14200000, accounts_payable: 22300000, inventory_value: 45000000, notes: "Flujo negativo por pago a proveedores de importación" }
  ],

  indicators: [
    { period: "2026-03", gross_margin: 0.317, net_margin: 0.016, roa: 0.011, roe: 0.015, current_ratio: 0.91, quick_ratio: 0.23, working_capital: -8100000, debt_to_equity: 0.38, days_receivable: 28, days_payable: 42, inventory_turnover: 35, cash_cycle: 21, health_score: 58 },
    { period: "2025-Q4", gross_margin: 0.33, net_margin: 0.045, roa: 0.03, roe: 0.04, current_ratio: 1.15, quick_ratio: 0.35, working_capital: 5200000, debt_to_equity: 0.32, days_receivable: 25, days_payable: 38, inventory_turnover: 30, cash_cycle: 17, health_score: 72 }
  ],

  clients: [
    { name: "Red de Talleres Venado Tuerto (12 talleres)", client_type: "fleet", annual_revenue: 144000000, avg_payment_days: 30, outstanding_balance: 4500000, risk_level: "low" },
    { name: "Lubricentros zona sur Santa Fe (8 locales)", client_type: "fleet", annual_revenue: 102000000, avg_payment_days: 35, outstanding_balance: 3200000, risk_level: "low" },
    { name: "Mostrador particular", client_type: "individual", annual_revenue: 222000000, avg_payment_days: 0, outstanding_balance: 0, risk_level: "low" },
    { name: "MercadoLibre (tienda online)", client_type: "workshop", annual_revenue: 50400000, avg_payment_days: 14, outstanding_balance: 2100000, risk_level: "low" },
    { name: "Concesionarias usados región", client_type: "fleet", annual_revenue: 63600000, avg_payment_days: 45, outstanding_balance: 5300000, risk_level: "medium" },
    { name: "Lubricentro San Martín", client_type: "workshop", annual_revenue: 8400000, avg_payment_days: 95, outstanding_balance: 450000, risk_level: "high" },
    { name: "Taller Mecánico Rossi", client_type: "workshop", annual_revenue: 5200000, avg_payment_days: 120, outstanding_balance: 320000, risk_level: "high" },
    { name: "Frenos del Sur", client_type: "workshop", annual_revenue: 3600000, avg_payment_days: 105, outstanding_balance: 230000, risk_level: "high" }
  ],

  suppliers: [
    { name: "Frasle Argentina SA", avg_price_level: "$$", payment_terms_days: 30, delivery_time_hours: 48, reliability_pct: 95.0, is_primary: true, notes: "Pastillas y cintas de freno. Nacional. Proveedor principal." },
    { name: "Sachs Automotive", avg_price_level: "$$$", payment_terms_days: 60, delivery_time_hours: 72, reliability_pct: 92.0, is_primary: true, notes: "Embragues y kits. Nacional." },
    { name: "Fremax Brasil", avg_price_level: "$$", payment_terms_days: 30, delivery_time_hours: 168, reliability_pct: 88.0, is_primary: false, notes: "Discos de freno importados de Brasil." },
    { name: "Turk Fren Sanayi", avg_price_level: "$", payment_terms_days: 0, delivery_time_hours: 720, reliability_pct: 82.0, is_primary: false, notes: "Cilindros y bombas de freno de Turquía." },
    { name: "Distri Repuestos Rosario", avg_price_level: "$$", payment_terms_days: 15, delivery_time_hours: 24, reliability_pct: 90.0, is_primary: false, notes: "Distribuidor complementario." }
  ],

  products: [
    { name: "Pastillas de freno Ferodo", category: "Frenos", monthly_revenue: 10880000, margin_pct: 42.2, current_stock: 340, min_stock: 100, supplier_id: 1 },
    { name: "Disco de freno ventilado VW Gol", category: "Frenos", monthly_revenue: 8160000, margin_pct: 38.2, current_stock: 120, min_stock: 40, supplier_id: 3 },
    { name: "Kit embrague Sachs Fiat", category: "Embragues", monthly_revenue: 19175000, margin_pct: 37.3, current_stock: 65, min_stock: 20, supplier_id: 2 },
    { name: "Cilindro maestro freno Toyota", category: "Frenos", monthly_revenue: 6975000, margin_pct: 38.7, current_stock: 45, min_stock: 15, supplier_id: 4 },
    { name: "Manguera freno universal", category: "Frenos", monthly_revenue: 4200000, margin_pct: 43.3, current_stock: 280, min_stock: 80, supplier_id: 5 },
    { name: "Kit reparación cilindro embrague", category: "Embragues", monthly_revenue: 3200000, margin_pct: 45.0, current_stock: 90, min_stock: 30, supplier_id: 2 }
  ],

  employees: [
    { name: "Martín Ruiz", role: "Encargado de ventas mostrador", area: "Ventas", salary: 850000, workload_pct: 100 },
    { name: "Carlos Pereyra", role: "Vendedor mostrador", area: "Ventas", salary: 720000, workload_pct: 95 },
    { name: "Lucía Gómez", role: "Administración y facturación", area: "Administración", salary: 680000, workload_pct: 110 },
    { name: "Diego Fernández", role: "Depósito y logística", area: "Logística", salary: 620000, workload_pct: 90 },
    { name: "Pablo Acosta", role: "Vendedor mayorista", area: "Ventas", salary: 750000, workload_pct: 105 },
    { name: "Ana Torres", role: "Cobranzas", area: "Administración", salary: 650000, workload_pct: 85 },
    { name: "Ramiro Díaz", role: "Chofer y entregas", area: "Logística", salary: 580000, workload_pct: 100 },
    { name: "Sofía Méndez", role: "Atención al cliente / redes", area: "Marketing", salary: 550000, workload_pct: 80 }
  ],

  credits: [
    { bank_name: "Banco Nación", credit_name: "Crédito PyME Inversión Productiva", credit_type: "inversion", annual_rate: 0.29, max_amount: 80000000, min_amount: 5000000, max_term_months: 48, requirements: '["Certificado PyME AFIP vigente","Antigüedad mínima 2 años","Sin deuda BCRA","Presentar flujo de fondos proyectado"]', requires_mipyme_cert: true, url: "https://www.bna.com.ar/Empresas/Pymes", matches_profile: true, qualification_reasons_ok: ["Tiene certificado PyME","Monto dentro del rango de facturación","Liquidez corriente 0.91 (ajustado)"], qualification_reasons_fail: [] },
    { bank_name: "Banco Provincia", credit_name: "Línea Importaciones PyME", credit_type: "inversion", annual_rate: 0.26, max_amount: 60000000, min_amount: 3000000, max_term_months: 36, requirements: '["Certificado PyME","Operación de comercio exterior documentada","Sin deuda impositiva"]', requires_mipyme_cert: true, url: "https://www.bancoprovincia.com.ar/web/pymes", matches_profile: true, qualification_reasons_ok: ["Tiene certificado PyME","Monto dentro del rango de facturación"], qualification_reasons_fail: [] },
    { bank_name: "Banco Galicia", credit_name: "Crédito Capital de Trabajo", credit_type: "capital_trabajo", annual_rate: 0.38, max_amount: 30000000, min_amount: 1000000, max_term_months: 12, requirements: '["Cuenta corriente con 6 meses de antigüedad","Facturación demostrable"]', requires_mipyme_cert: false, url: "https://www.galicia.ar/empresas", matches_profile: true, qualification_reasons_ok: ["No requiere cert PyME","Monto dentro del rango"], qualification_reasons_fail: [] },
    { bank_name: "Ministerio de Producción", credit_name: "Programa FONDEP", credit_type: "inversion", annual_rate: 0.15, max_amount: 50000000, min_amount: 5000000, max_term_months: 60, requirements: '["Proyecto productivo aprobado","Certificado PyME","Matching funds 20%"]', requires_mipyme_cert: true, url: "https://www.argentina.gob.ar/produccion/fondep", matches_profile: true, qualification_reasons_ok: ["Tiene certificado PyME"], qualification_reasons_fail: ["Requiere proyecto aprobado y matching funds 20%"] },
    { bank_name: "Banco ICBC", credit_name: "Préstamo Comex", credit_type: "inversion", annual_rate: 0.08, max_amount: 120000000, min_amount: 10000000, max_term_months: 6, requirements: '["Historial importador","Carta de crédito o orden de compra","Garantía bancaria"]', requires_mipyme_cert: false, url: "https://www.icbc.com.ar/empresas", matches_profile: false, qualification_reasons_ok: ["Tasa más baja del mercado (8%)"], qualification_reasons_fail: ["Monto máximo alto vs facturación","Requiere garantía bancaria"] }
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
    { title: "Resolución AFIP 5432/2025: Régimen simplificado de importación PyME", summary: "Nuevo régimen simplificado de importación para PyMEs categoría Tramo 1 y 2.", source: "boletin_oficial", status: "confirmed", relevance_score: 0.95, published_date: "2025-11-15" },
    { title: "Decreto 124/2026: Bonificación tasa créditos PyME importación", summary: "Bonificación de 5 puntos en tasa de interés para créditos productivos PyME.", source: "boletin_oficial", status: "confirmed", relevance_score: 0.98, published_date: "2026-02-01" },
    { title: "Comunicación BCRA A-7890: Líneas preferenciales sin reciprocidad", summary: "Las PyMEs pueden acceder a líneas de crédito preferenciales sin requisito de reciprocidad bancaria.", source: "bcra", status: "confirmed", relevance_score: 0.85, published_date: "2026-03-10" }
  ],

  sectorSignals: [
    { signal_type: "demand_shift", description: "Aumento de demanda de repuestos importados por desregulación de importaciones.", sector: "Repuestos automotores", impact_level: "high" },
    { signal_type: "price_change", description: "Baja de precios en discos y pastillas importados (-15% promedio).", sector: "Repuestos automotores", impact_level: "medium" }
  ],

  benchmark: {
    gross_margin: { company: 0.317, sector_avg: 0.30, diff: 0.017, status: "above" },
    payment_days: { company: 28, sector_avg: 35, diff: -7, status: "better" }
  }
};

// ═══════════════════════════════════════════════════════════════
// COMPUTED MOCK DATA (replicas de data_service.py logic)
// ═══════════════════════════════════════════════════════════════

function computeAlerts() {
  const fin = MOCK.financials[MOCK.financials.length - 1];
  const ind = MOCK.indicators[0];
  const morosos = MOCK.clients.filter(c => c.risk_level === 'high');
  const alerts = [];

  if (fin.net_cash_flow < 0) {
    alerts.push({ type: 'cash_flow', severity: 'critical', title: 'Flujo de caja negativo', description: `Marzo 2026: ${formatCurrency(fin.net_cash_flow)}. Pago fuerte a proveedores de importación.`, action_suggested: 'Revisar créditos disponibles para capital de trabajo' });
  }
  if (ind.current_ratio < 1.0) {
    alerts.push({ type: 'liquidity', severity: 'warning', title: 'Liquidez corriente bajo 1.0', description: `Ratio actual: ${ind.current_ratio}. Capital de trabajo negativo: ${formatCurrency(ind.working_capital)}`, action_suggested: 'Evaluar refinanciación de pasivos corrientes' });
  }
  if (morosos.length > 0) {
    const totalMoroso = morosos.reduce((s, c) => s + c.outstanding_balance, 0);
    alerts.push({ type: 'delinquency', severity: 'warning', title: `${morosos.length} clientes morosos`, description: `Deuda acumulada: ${formatCurrency(totalMoroso)}. Promedio 107 días de atraso.`, action_suggested: 'Activar gestión de cobranza intensiva' });
  }
  if (fin.cash_balance < 2000000) {
    alerts.push({ type: 'cash_reserve', severity: 'critical', title: 'Reserva de caja mínima', description: `Saldo actual: ${formatCurrency(fin.cash_balance)}. Menos de 1 día de operación.`, action_suggested: 'Urgente: buscar inyección de liquidez' });
  }
  return alerts;
}

function computeCashPosition() {
  const fin = MOCK.financials[MOCK.financials.length - 1];
  const ind = MOCK.indicators[0];
  const morosos = MOCK.clients.filter(c => c.risk_level === 'high');
  return {
    cash_balance: fin.cash_balance,
    net_cash_flow: fin.net_cash_flow,
    accounts_receivable: fin.accounts_receivable,
    accounts_payable: fin.accounts_payable,
    current_ratio: ind.current_ratio,
    health_score: ind.health_score,
    total_overdue: morosos.reduce((s, c) => s + c.outstanding_balance, 0),
    delinquent_count: morosos.length
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
  try {
    const res = await fetch(`${API_BASE}/dashboard/${empresaId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch (e) {
    console.warn('Backend dashboard no disponible, usando mock:', e.message);
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
  try {
    const res = await fetch(`${API_BASE}/finanzas/${empresaId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch (e) {
    console.warn('Backend finanzas no disponible, usando mock:', e.message);
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
  try {
    const res = await fetch(`${API_BASE}/creditos/${empresaId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch (e) {
    console.warn('Backend créditos no disponible, usando mock:', e.message);
    return {
      credits: MOCK.credits,
      creditProfile: MOCK.creditProfile,
      macro: MOCK.macro,
      regulations: MOCK.regulations,
      sectorSignals: MOCK.sectorSignals
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// ANGELA CHAT — SSE Mock / Real
// ═══════════════════════════════════════════════════════════════

const MOCK_DEMO_RESPONSE = `Gonzalo, analicé tu situación financiera cruzando tus datos internos con las opciones de crédito disponibles en el mercado. Acá va mi análisis:

**Tu situación actual:**
- Facturación anual: $678M, con margen bruto de 31.7% (por encima del promedio del sector: 30%)
- Flujo de caja negativo en marzo (-$2.07M) por pagos a proveedores de importación
- Situación BCRA: **Categoría 1** (normal) — sin deuda reportada en 24 meses ✅
- Capital de trabajo negativo: -$8.1M — esto es lo que hay que resolver

**Top 3 créditos recomendados para importar discos de freno:**

🥇 **Banco Provincia — Línea Importaciones PyME**
- Tasa: 26% TNA (la más baja para tu perfil)
- Hasta $60M | 36 meses
- ✅ Específica para importación — calificás directamente

🥈 **Banco Nación — Crédito PyME Inversión Productiva**
- Tasa: 29% TNA
- Hasta $80M | 48 meses
- ✅ Mayor monto y plazo, ideal si querés stockear fuerte

🥉 **Programa FONDEP — Ministerio de Producción**
- Tasa: 15% TNA (subsidiada)
- Hasta $50M | 60 meses
- ⚠️ Requiere proyecto aprobado y matching funds 20%

**Mi recomendación:** Arrancá con Banco Provincia para la importación inmediata de discos Fremax. Con $60M podés cubrir 12 meses de stock importado y resolver el cuello de botella de caja.

¿Querés que te arme un flujo de fondos proyectado para presentar al banco?`;

function sendQueryMock(message, context, onStep, onComplete) {
  const steps = [
    { step: 'classifying', message: 'Clasificando tu consulta...', delay: 600 },
    { step: 'expanding', message: 'Generando sub-preguntas de análisis...', delay: 900 },
    { step: 'agent_finance', message: 'Consultando tus datos financieros internos...', delay: 1200 },
    { step: 'agent_economy', message: 'Buscando créditos y contexto macroeconómico...', delay: 1400 },
    { step: 'agent_research', message: 'Verificando tasas actualizadas en BCRA...', delay: 1000 },
    { step: 'meshing', message: 'Cruzando datos internos con externos...', delay: 800 },
    { step: 'validating', message: 'Verificando calidad de la respuesta...', delay: 500 }
  ];

  let i = 0;
  let totalDelay = 0;
  const timers = [];

  for (const s of steps) {
    totalDelay += s.delay;
    timers.push(setTimeout(() => onStep(s), totalDelay));
    i++;
  }

  totalDelay += 600;
  timers.push(setTimeout(() => {
    onComplete({
      step: 'complete',
      response: MOCK_DEMO_RESPONSE,
      cards: [
        { type: 'credit', bank: 'Banco Provincia', name: 'Línea Importaciones PyME', rate: '26%', amount: '$60M', match: true },
        { type: 'credit', bank: 'Banco Nación', name: 'Crédito PyME Inversión', rate: '29%', amount: '$80M', match: true },
        { type: 'credit', bank: 'FONDEP', name: 'Programa FONDEP', rate: '15%', amount: '$50M', match: false }
      ],
      navigate_to: 'creditos'
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
  // Real SSE — will be replaced when backend is ready
  // conversation_id persiste durante la sesión
  if (!window._polConvId) window._polConvId = crypto.randomUUID();
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      company_id: EMPRESA_ID,
      user_message: message,
      conversation_id: window._polConvId,
    })
  });
  const data = await res.json();
  // Normalizar respuesta al formato que espera index.html
  return {
    step: 'complete',
    response: data?.response?.message || '',
    cards: (data?.response?.recommendations || []).map(r => ({ type: 'rec', action: r.action, impact: r.impact, urgency: r.urgency })),
    metadata: data?.metadata,
  };
}

function sendQueryStreaming(message, context, onStep, onComplete) {
  if (USE_MOCK) {
    return sendQueryMock(message, context, onStep, onComplete);
  }
  // Llamada real al backend (sin SSE — polling simulado con fetch)
  if (!window._polConvId) window._polConvId = crypto.randomUUID();
  const steps = [
    { step: 'classifying',    message: 'Clasificando tu consulta...' },
    { step: 'expanding',      message: 'Generando sub-preguntas de análisis...' },
    { step: 'agent_finance',  message: 'Consultando datos financieros internos...' },
    { step: 'agent_economy',  message: 'Buscando créditos y contexto macro...' },
    { step: 'agent_research', message: 'Verificando datos en tiempo real (BCRA)...' },
    { step: 'meshing',        message: 'Cruzando y sintetizando respuestas...' },
  ];
  let i = 0;
  const interval = setInterval(() => {
    if (i < steps.length) onStep(steps[i++]);
  }, 600);

  fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      company_id: EMPRESA_ID,
      user_message: message,
      conversation_id: window._polConvId,
    }),
  })
    .then(r => r.json())
    .then(data => {
      clearInterval(interval);
      const msg = data?.response?.message || 'Sin respuesta del servidor.';
      const recs = data?.response?.recommendations || [];
      const cards = recs.map(r => ({ type: 'rec', action: r.action, impact: r.impact, urgency: r.urgency }));
      onComplete({ step: 'complete', response: msg, cards, metadata: data?.metadata });
    })
    .catch(err => {
      clearInterval(interval);
      onComplete({ step: 'complete', response: `Error al conectar con el backend: ${err.message}`, cards: [] });
    });

  return () => clearInterval(interval);
}

async function ingestFile(file) {
  if (USE_MOCK) {
    await fakeLag(1500);
    const ext = file.name.split('.').pop().toLowerCase();
    const topicMap = { xlsx: 'finanzas', xls: 'finanzas', csv: 'finanzas', pdf: 'documentos', jpg: 'documentos', png: 'documentos', jpeg: 'documentos', txt: 'general', doc: 'documentos', docx: 'documentos' };
    return {
      filename: file.name,
      status: 'processed',
      chunks_created: Math.floor(Math.random() * 8) + 2,
      topic: topicMap[ext] || 'general',
      angela_comment: `Procesé "${file.name}" correctamente. Extraje ${Math.floor(Math.random() * 8) + 2} fragmentos de información y los integré a tu base de conocimiento. Esto mejora mi contexto sobre tu negocio.`
    };
  }
  const form = new FormData();
  form.append('company_id', EMPRESA_ID);
  form.append('file', file);
  const res = await fetch(`${API_BASE}/ingest`, { method: 'POST', body: form });
  const data = await res.json();
  // Normalizar al formato que espera index.html
  return {
    filename: file.name,
    status: data.success ? 'processed' : 'error',
    chunks_created: data.chars ? Math.ceil(data.chars / 500) : 1,
    topic: 'documentos',
    angela_comment: data.success
      ? `Procesé "${file.name}" y lo integré a tu base de conocimiento (${data.chars} caracteres).`
      : `Error procesando "${file.name}": ${data.error}`,
  };
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
  const labels = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  return `${labels[month]} ${String(year).slice(2)}`;
}
