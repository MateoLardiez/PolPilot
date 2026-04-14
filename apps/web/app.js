// PolPilot — App Controller
// Manages views, charts, Angela widget, and data flow

let currentView = 'dashboard';
let dashboardData = null;
let finanzasData = null;
let creditosData = null;
let charts = {};
let angelaOpen = false;
let isQuerying = false;

// ═══════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
  initNavigation();
  initAngela();
  initDragDrop();
  await loadDashboard();
});

// ═══════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════

function initNavigation() {
  document.querySelectorAll('.nav-item, .mobile-nav-item').forEach(item => {
    item.addEventListener('click', () => navigateTo(item.dataset.view));
  });
}

async function navigateTo(view) {
  if (view === currentView) return;
  document.querySelectorAll('.nav-item, .mobile-nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === view));
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === `view-${view}`));

  const titles = { dashboard: 'Dashboard', finanzas: 'Finanzas', creditos: 'Créditos' };
  document.getElementById('headerTitle').textContent = titles[view] || view;
  currentView = view;
  updateAngelaContext();

  if (view === 'finanzas' && !finanzasData) await loadFinanzas();
  if (view === 'creditos' && !creditosData) await loadCreditos();
}

// ═══════════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════════

async function loadDashboard() {
  dashboardData = await fetchDashboard();
  renderStats(dashboardData);
  renderRevenueChart(dashboardData.financials);
  renderHealthGauge(dashboardData.indicators.health_score);
  renderAlerts(dashboardData.alerts);
  renderBenchmark(dashboardData.benchmark);
  renderCashFlowChart(dashboardData.financials);
}

function renderStats(d) {
  const fin = d.financials[d.financials.length - 1];
  const prevFin = d.financials[d.financials.length - 2];
  const revDelta = ((fin.revenue - prevFin.revenue) / prevFin.revenue * 100).toFixed(1);
  const grid = document.getElementById('statsGrid');

  const stats = [
    { label: 'Facturación mensual', value: formatCurrency(fin.revenue), delta: `${revDelta > 0 ? '+' : ''}${revDelta}%`, deltaClass: revDelta >= 0 ? 'positive' : 'negative', sublabel: monthLabel(fin.year, fin.month) },
    { label: 'Flujo de caja', value: formatCurrency(fin.net_cash_flow), delta: fin.net_cash_flow < 0 ? 'Negativo' : 'Positivo', deltaClass: fin.net_cash_flow >= 0 ? 'positive' : 'negative', sublabel: 'Neto mensual' },
    { label: 'Cuentas por cobrar', value: formatCurrency(fin.accounts_receivable), delta: `${d.indicators.days_receivable} días`, deltaClass: 'neutral', sublabel: `${d.morosos.length} morosos` },
    { label: 'Saldo en caja', value: formatCurrency(fin.cash_balance), delta: fin.cash_balance < 5000000 ? 'Crítico' : 'Estable', deltaClass: fin.cash_balance < 5000000 ? 'negative' : 'positive', sublabel: 'Disponible hoy' }
  ];

  grid.innerHTML = stats.map(s => `
    <div class="stat-card">
      <div class="stat-label">${s.label}</div>
      <div class="stat-value">${s.value}</div>
      <div class="stat-delta ${s.deltaClass}">${s.delta} · ${s.sublabel}</div>
    </div>
  `).join('');
}

function renderRevenueChart(financials) {
  const cats = financials.map(f => monthLabel(f.year, f.month));
  if (charts.revenue) charts.revenue.destroy();
  charts.revenue = new ApexCharts(document.getElementById('revenueChart'), {
    chart: { type: 'area', height: 280, background: 'transparent', toolbar: { show: false }, fontFamily: 'Inter' },
    series: [
      { name: 'Ingresos', data: financials.map(f => f.revenue) },
      { name: 'Egresos', data: financials.map(f => f.expenses) }
    ],
    xaxis: { categories: cats, labels: { style: { colors: '#64748b', fontSize: '11px' } }, axisBorder: { show: false }, axisTicks: { show: false } },
    yaxis: { labels: { style: { colors: '#64748b', fontSize: '11px' }, formatter: v => formatCurrency(v) } },
    colors: ['#10b981', '#ef4444'],
    fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.05, stops: [0, 90, 100] } },
    stroke: { curve: 'smooth', width: 2.5 },
    grid: { borderColor: 'rgba(255,255,255,0.06)', strokeDashArray: 4 },
    dataLabels: { enabled: false },
    tooltip: { theme: 'dark', y: { formatter: v => formatCurrency(v) } },
    legend: { position: 'top', horizontalAlign: 'right', labels: { colors: '#94a3b8' } }
  });
  charts.revenue.render();
}

function renderHealthGauge(score) {
  const r = 65;
  const circ = 2 * Math.PI * r;
  const pct = score / 100;
  const offset = circ * (1 - pct);
  const color = score >= 70 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';

  document.getElementById('healthGauge').innerHTML = `
    <div class="health-gauge">
      <svg width="160" height="160" viewBox="0 0 160 160">
        <circle class="gauge-bg" cx="80" cy="80" r="${r}" />
        <circle class="gauge-fill" cx="80" cy="80" r="${r}"
          stroke="${color}"
          stroke-dasharray="${circ}"
          stroke-dashoffset="${offset}" />
      </svg>
      <div class="gauge-value">
        <div class="gauge-number" style="color:${color}">${score}</div>
        <div class="gauge-label">de 100</div>
      </div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:0.82rem;color:var(--text-secondary);">${score >= 70 ? 'Saludable' : score >= 50 ? 'Atención requerida' : 'Crítico'}</div>
      <div style="font-size:0.72rem;color:var(--text-muted);margin-top:4px;">Período: Mar 2026</div>
    </div>
  `;
}

function renderAlerts(alerts) {
  document.getElementById('alertCount').textContent = `${alerts.length} alertas`;
  document.getElementById('alertsList').innerHTML = alerts.map(a => `
    <div class="alert-item ${a.severity}">
      <span class="alert-icon">${a.severity === 'critical' ? '🔴' : '🟡'}</span>
      <div>
        <div class="alert-title">${a.title}</div>
        <div class="alert-desc">${a.description}</div>
        <div class="alert-action">${a.action_suggested}</div>
      </div>
    </div>
  `).join('');
}

function renderBenchmark(bm) {
  const html = Object.entries(bm).map(([key, data]) => {
    const label = key === 'gross_margin' ? 'Margen Bruto' : 'Días de Cobro';
    const compVal = key === 'gross_margin' ? formatPct(data.company) : `${data.company} días`;
    const sectorVal = key === 'gross_margin' ? formatPct(data.sector_avg) : `${data.sector_avg} días`;
    const isGood = data.status === 'above' || data.status === 'better';
    const fillPct = key === 'gross_margin' ? (data.company / 0.5 * 100) : (data.company / 60 * 100);
    const markerPct = key === 'gross_margin' ? (data.sector_avg / 0.5 * 100) : (data.sector_avg / 60 * 100);
    const color = isGood ? 'var(--accent)' : 'var(--warning)';

    return `
      <div style="margin-bottom:20px;">
        <div style="display:flex;justify-content:space-between;font-size:0.82rem;">
          <span>${label}</span>
          <span style="font-family:var(--font-mono);font-weight:600;color:${color}">${compVal}</span>
        </div>
        <div class="bench-bar">
          <div class="bench-fill" style="width:${Math.min(fillPct, 100)}%;background:${color};"></div>
          <div class="bench-marker" style="left:${Math.min(markerPct, 100)}%;" title="Promedio sector: ${sectorVal}"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:0.68rem;color:var(--text-muted);">
          <span>Tu empresa: ${compVal}</span>
          <span>Sector: ${sectorVal}</span>
        </div>
      </div>
    `;
  }).join('');
  document.getElementById('benchmarkContent').innerHTML = html;
}

function renderCashFlowChart(financials) {
  const cats = financials.map(f => monthLabel(f.year, f.month));
  if (charts.cashFlow) charts.cashFlow.destroy();
  charts.cashFlow = new ApexCharts(document.getElementById('cashFlowChart'), {
    chart: { type: 'bar', height: 240, background: 'transparent', toolbar: { show: false }, fontFamily: 'Inter' },
    series: [{ name: 'Flujo neto', data: financials.map(f => f.net_cash_flow) }],
    xaxis: { categories: cats, labels: { style: { colors: '#64748b', fontSize: '11px' } }, axisBorder: { show: false }, axisTicks: { show: false } },
    yaxis: { labels: { style: { colors: '#64748b', fontSize: '11px' }, formatter: v => formatCurrency(v) } },
    colors: financials.map(f => f.net_cash_flow >= 0 ? '#10b981' : '#ef4444'),
    plotOptions: { bar: { borderRadius: 6, columnWidth: '50%', distributed: true } },
    grid: { borderColor: 'rgba(255,255,255,0.06)', strokeDashArray: 4 },
    dataLabels: { enabled: false },
    tooltip: { theme: 'dark', y: { formatter: v => formatCurrency(v) } },
    legend: { show: false }
  });
  charts.cashFlow.render();
}

// ═══════════════════════════════════════════════════════════════
// FINANZAS
// ═══════════════════════════════════════════════════════════════

async function loadFinanzas() {
  finanzasData = await fetchFinanzas();
  renderRevenueDistribution(finanzasData.clients);
  renderIndicatorsTable(finanzasData.indicators);
  renderProductsChart(finanzasData.products);
  renderMorososTable(finanzasData.morosos);
  renderEmployeesTable(finanzasData.employees);
}

function renderRevenueDistribution(clients) {
  if (charts.revDist) charts.revDist.destroy();
  charts.revDist = new ApexCharts(document.getElementById('revenueDistChart'), {
    chart: { type: 'donut', height: 300, background: 'transparent', fontFamily: 'Inter' },
    series: clients.map(c => c.annual_revenue),
    labels: clients.map(c => c.name.length > 25 ? c.name.slice(0, 25) + '…' : c.name),
    colors: ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#06b6d4', '#ef4444', '#ec4899', '#64748b'],
    plotOptions: { pie: { donut: { size: '65%', labels: { show: true, total: { show: true, label: 'Total Anual', fontSize: '12px', color: '#94a3b8', formatter: () => formatCurrency(clients.reduce((s, c) => s + c.annual_revenue, 0)) } } } } },
    dataLabels: { enabled: false },
    legend: { position: 'bottom', labels: { colors: '#94a3b8' }, fontSize: '11px' },
    stroke: { width: 1, colors: ['#111827'] },
    tooltip: { theme: 'dark', y: { formatter: v => formatCurrency(v) } }
  });
  charts.revDist.render();
}

function renderIndicatorsTable(indicators) {
  const ind = indicators[0];
  const prev = indicators[1];
  const rows = [
    ['Margen Bruto', formatPct(ind.gross_margin), formatPct(prev?.gross_margin), ind.gross_margin > (prev?.gross_margin || 0)],
    ['Margen Neto', formatPct(ind.net_margin), formatPct(prev?.net_margin), ind.net_margin > (prev?.net_margin || 0)],
    ['Liquidez Corriente', ind.current_ratio.toFixed(2), prev?.current_ratio?.toFixed(2), ind.current_ratio > (prev?.current_ratio || 0)],
    ['Quick Ratio', ind.quick_ratio.toFixed(2), prev?.quick_ratio?.toFixed(2), ind.quick_ratio > (prev?.quick_ratio || 0)],
    ['Capital de Trabajo', formatCurrency(ind.working_capital), formatCurrency(prev?.working_capital), ind.working_capital > (prev?.working_capital || 0)],
    ['Deuda / Patrimonio', ind.debt_to_equity.toFixed(2), prev?.debt_to_equity?.toFixed(2), ind.debt_to_equity < (prev?.debt_to_equity || 0)],
    ['Días Cobro', `${ind.days_receivable}d`, `${prev?.days_receivable}d`, ind.days_receivable < (prev?.days_receivable || 0)],
    ['Días Pago', `${ind.days_payable}d`, `${prev?.days_payable}d`, ind.days_payable > (prev?.days_payable || 0)],
    ['Ciclo de Caja', `${ind.cash_cycle}d`, `${prev?.cash_cycle}d`, ind.cash_cycle < (prev?.cash_cycle || 0)],
  ];

  document.getElementById('indicatorsTable').innerHTML = `
    <table class="data-table">
      <thead><tr><th>Indicador</th><th>Mar 2026</th><th>Q4 2025</th><th></th></tr></thead>
      <tbody>${rows.map(([label, curr, prev, good]) => `
        <tr>
          <td>${label}</td>
          <td class="mono">${curr}</td>
          <td class="mono" style="color:var(--text-muted)">${prev || '-'}</td>
          <td style="color:${good ? 'var(--accent)' : 'var(--danger)'};">${good ? '▲' : '▼'}</td>
        </tr>
      `).join('')}</tbody>
    </table>
  `;
}

function renderProductsChart(products) {
  if (charts.products) charts.products.destroy();
  charts.products = new ApexCharts(document.getElementById('productsChart'), {
    chart: { type: 'bar', height: 300, background: 'transparent', toolbar: { show: false }, fontFamily: 'Inter' },
    series: [
      { name: 'Ingreso mensual', data: products.map(p => p.monthly_revenue) },
      { name: 'Margen %', data: products.map(p => p.margin_pct) }
    ],
    xaxis: { categories: products.map(p => p.name.length > 20 ? p.name.slice(0, 20) + '…' : p.name), labels: { style: { colors: '#64748b', fontSize: '10px' }, rotate: -30 }, axisBorder: { show: false } },
    yaxis: [
      { labels: { style: { colors: '#64748b' }, formatter: v => formatCurrency(v) } },
      { opposite: true, labels: { style: { colors: '#64748b' }, formatter: v => v.toFixed(0) + '%' }, max: 60 }
    ],
    colors: ['#3b82f6', '#10b981'],
    plotOptions: { bar: { borderRadius: 4, columnWidth: '60%' } },
    grid: { borderColor: 'rgba(255,255,255,0.06)', strokeDashArray: 4 },
    dataLabels: { enabled: false },
    tooltip: { theme: 'dark', y: { formatter: (v, { seriesIndex }) => seriesIndex === 0 ? formatCurrency(v) : v.toFixed(1) + '%' } },
    legend: { labels: { colors: '#94a3b8' } }
  });
  charts.products.render();
}

function renderMorososTable(morosos) {
  document.getElementById('morosoBadge').textContent = `${morosos.length} morosos`;
  document.getElementById('morososTable').innerHTML = `
    <table class="data-table">
      <thead><tr><th>Cliente</th><th>Deuda</th><th>Días Atraso</th><th>Riesgo</th></tr></thead>
      <tbody>${morosos.map(m => `
        <tr>
          <td>${m.name}</td>
          <td class="mono">${formatCurrency(m.outstanding_balance)}</td>
          <td class="mono" style="color:var(--danger);">${m.avg_payment_days}d</td>
          <td><span style="color:var(--danger);font-weight:600;font-size:0.78rem;">● ALTO</span></td>
        </tr>
      `).join('')}</tbody>
    </table>
  `;
}

function renderEmployeesTable(employees) {
  document.getElementById('employeeBadge').textContent = `${employees.length} personas`;
  document.getElementById('employeesTable').innerHTML = `
    <table class="data-table">
      <thead><tr><th>Nombre</th><th>Rol</th><th>Área</th><th>Salario</th><th>Carga</th></tr></thead>
      <tbody>${employees.map(e => `
        <tr>
          <td style="font-weight:500;">${e.name}</td>
          <td>${e.role}</td>
          <td>${e.area}</td>
          <td class="mono">${formatCurrency(e.salary)}</td>
          <td><span style="color:${e.workload_pct > 100 ? 'var(--danger)' : e.workload_pct >= 95 ? 'var(--warning)' : 'var(--accent)'};">${e.workload_pct}%</span></td>
        </tr>
      `).join('')}</tbody>
    </table>
  `;
}

// ═══════════════════════════════════════════════════════════════
// CREDITOS
// ═══════════════════════════════════════════════════════════════

async function loadCreditos() {
  creditosData = await fetchCreditos();
  renderMacroStrip(creditosData.macro);
  renderCreditsGrid(creditosData.credits);
  renderBCRA(creditosData.creditProfile);
  renderRegulations(creditosData.regulations);
}

function renderMacroStrip(macro) {
  const pills = [
    { label: 'USD Oficial', value: `$${macro.usd_oficial.toLocaleString()}` },
    { label: 'USD Blue', value: `$${macro.usd_blue.toLocaleString()}` },
    { label: 'Inflación', value: formatPct(macro.inflacion_mensual) + '/mes' },
    { label: 'BADLAR', value: formatPct(macro.tasa_badlar) },
    { label: 'Riesgo País', value: `${macro.riesgo_pais} bp` },
    { label: 'PBI', value: `+${formatPct(macro.pbi_variacion_anual)}` },
  ];
  document.getElementById('macroStrip').innerHTML = pills.map(p => `
    <div class="macro-pill">
      <span class="label">${p.label}</span>
      <span class="value">${p.value}</span>
    </div>
  `).join('');
}

function renderCreditsGrid(credits) {
  document.getElementById('creditsGrid').innerHTML = credits.map(c => {
    const rate = (c.annual_rate * 100).toFixed(0);
    const hasFailReasons = c.qualification_reasons_fail && c.qualification_reasons_fail.length > 0;
    const matchClass = c.matches_profile ? (hasFailReasons ? 'partial' : 'yes') : 'no';
    const matchLabel = c.matches_profile ? (hasFailReasons ? 'Parcial' : 'Aplica ✓') : 'No aplica';
    let reqs = [];
    try { reqs = typeof c.requirements === 'string' ? JSON.parse(c.requirements) : c.requirements; } catch(e) { reqs = []; }

    return `
      <div class="credit-card ${c.matches_profile ? '' : 'no-match'}">
        <div class="credit-card-header">
          <div>
            <div class="credit-bank">${c.bank_name}</div>
            <div class="credit-name">${c.credit_name}</div>
          </div>
          <span class="match-badge ${matchClass}">${matchLabel}</span>
        </div>
        <div class="credit-stats">
          <div><div class="credit-stat-label">Tasa TNA</div><div class="credit-stat-value">${rate}%</div></div>
          <div><div class="credit-stat-label">Máximo</div><div class="credit-stat-value">${formatCurrency(c.max_amount)}</div></div>
          <div><div class="credit-stat-label">Plazo</div><div class="credit-stat-value">${c.max_term_months}m</div></div>
        </div>
        <div class="credit-reasons">
          ${(c.qualification_reasons_ok || []).map(r => `<span class="reason-tag ok">✓ ${r}</span>`).join('')}
          ${(c.qualification_reasons_fail || []).map(r => `<span class="reason-tag fail">✗ ${r}</span>`).join('')}
        </div>
      </div>
    `;
  }).join('');
}

function renderBCRA(profile) {
  const sitLabels = { 1: 'Normal', 2: 'Con riesgo', 3: 'Con problemas', 4: 'Alto riesgo', 5: 'Irrecuperable' };
  const sitColors = { 1: 'var(--accent)', 2: 'var(--warning)', 3: 'var(--danger)' };
  document.getElementById('bcraBadge').textContent = `Sit ${profile.situation}: ${sitLabels[profile.situation]}`;
  document.getElementById('bcraBadge').style.color = sitColors[profile.situation] || 'var(--danger)';
  document.getElementById('bcraBadge').style.background = profile.situation === 1 ? 'var(--accent-glow)' : 'var(--danger-glow)';

  document.getElementById('bcraContent').innerHTML = `
    <div style="margin-bottom:12px;">
      <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:4px;">CUIT</div>
      <div style="font-family:var(--font-mono);font-weight:600;">${profile.cuit}</div>
    </div>
    <div style="margin-bottom:12px;">
      <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:4px;">Deuda total reportada</div>
      <div style="font-family:var(--font-mono);font-weight:600;color:var(--accent);">${formatCurrency(profile.total_debt)}</div>
    </div>
    <div style="margin-bottom:12px;">
      <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:4px;">Cheques rechazados</div>
      <div style="font-family:var(--font-mono);font-weight:600;color:var(--accent);">0</div>
    </div>
    <div>
      <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px;">Últimos 24 meses</div>
      <div class="bcra-bar">
        ${profile.last_24_months.map(s => `<div class="bcra-month ${s > 1 ? 'bad' : ''}" title="Sit ${s}"></div>`).join('')}
      </div>
      <div style="font-size:0.68rem;color:var(--text-muted);margin-top:4px;">24/24 en situación normal ✓</div>
    </div>
  `;
}

function renderRegulations(regs) {
  document.getElementById('regulationsContent').innerHTML = regs.map(r => `
    <div style="padding:12px 0;border-bottom:1px solid var(--border);">
      <div style="font-size:0.82rem;font-weight:600;margin-bottom:4px;">${r.title}</div>
      <div style="font-size:0.75rem;color:var(--text-secondary);line-height:1.5;">${r.summary}</div>
      <div style="display:flex;gap:8px;margin-top:6px;font-size:0.68rem;color:var(--text-muted);">
        <span>📅 ${r.published_date}</span>
        <span>📌 Relevancia: ${(r.relevance_score * 100).toFixed(0)}%</span>
      </div>
    </div>
  `).join('');
}

// ═══════════════════════════════════════════════════════════════
// ANGELA WIDGET
// ═══════════════════════════════════════════════════════════════

function initAngela() {
  const fab = document.getElementById('angelaFab');
  const panel = document.getElementById('angelaPanel');
  const close = document.getElementById('angelaClose');
  const input = document.getElementById('angelaInput');
  const send = document.getElementById('angelaSend');
  const uploadBtn = document.getElementById('angelaUploadBtn');
  const fileInput = document.getElementById('fileInput');

  fab.addEventListener('click', () => toggleAngela(true));
  close.addEventListener('click', () => toggleAngela(false));

  send.addEventListener('click', () => handleSend());
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  });
  input.addEventListener('input', autoResize);

  uploadBtn.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => {
    if (e.target.files[0]) handleFileUpload(e.target.files[0]);
    e.target.value = '';
  });

  document.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      input.value = chip.dataset.q;
      handleSend();
    });
  });
}

function toggleAngela(open) {
  angelaOpen = open;
  document.getElementById('angelaPanel').classList.toggle('open', open);
  document.getElementById('angelaFab').style.display = open ? 'none' : 'flex';
  if (open) {
    updateAngelaContext();
    document.getElementById('angelaInput').focus();
  }
}

function updateAngelaContext() {
  const viewLabels = { dashboard: 'Dashboard', finanzas: 'Finanzas', creditos: 'Créditos' };
  document.getElementById('angelaViewLabel').textContent = viewLabels[currentView];

  let contextText = `👁 Viendo: ${viewLabels[currentView]}`;
  if (currentView === 'dashboard' && dashboardData) {
    contextText += ` · Health Score: ${dashboardData.indicators.health_score} · ${dashboardData.alerts.length} alertas`;
  } else if (currentView === 'creditos' && creditosData) {
    const matching = creditosData.credits.filter(c => c.matches_profile).length;
    contextText += ` · ${matching}/${creditosData.credits.length} créditos compatibles`;
  } else if (currentView === 'finanzas' && finanzasData) {
    const fin = finanzasData.financials[finanzasData.financials.length - 1];
    contextText += ` · Facturación: ${formatCurrency(fin.revenue)}`;
  }
  document.getElementById('angelaContextBar').textContent = contextText;

  const suggestions = {
    dashboard: [
      { q: '¿A qué crédito puedo aplicar para importar discos de freno?', label: '💳 ¿Qué créditos tengo?' },
      { q: '¿Por qué mi flujo de caja es negativo?', label: '📉 ¿Por qué flujo negativo?' },
      { q: '¿Cuáles son mis clientes morosos y cuánto me deben?', label: '⚠️ Clientes morosos' }
    ],
    finanzas: [
      { q: '¿Cuál es mi producto más rentable?', label: '🏆 Producto más rentable' },
      { q: '¿Cómo puedo mejorar mi capital de trabajo?', label: '💡 Mejorar capital' },
      { q: '¿Mi margen está por encima o debajo del sector?', label: '📊 Benchmark margen' }
    ],
    creditos: [
      { q: '¿A qué crédito puedo aplicar para importar discos de freno?', label: '🏦 Mejor crédito para importar' },
      { q: '¿Cuánto puedo pedir prestado dado mi flujo actual?', label: '📐 Capacidad de endeudamiento' },
      { q: '¿Hay regulaciones nuevas que me beneficien?', label: '📜 Regulaciones recientes' }
    ]
  };

  const container = document.getElementById('angelaSuggestions');
  const chips = suggestions[currentView] || suggestions.dashboard;
  container.innerHTML = chips.map(c => `<div class="suggestion-chip" data-q="${c.q}">${c.label}</div>`).join('');
  container.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.getElementById('angelaInput').value = chip.dataset.q;
      handleSend();
    });
  });
}

function autoResize() {
  const ta = document.getElementById('angelaInput');
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
}

async function handleSend() {
  const input = document.getElementById('angelaInput');
  const msg = input.value.trim();
  if (!msg || isQuerying) return;

  input.value = '';
  input.style.height = 'auto';
  isQuerying = true;
  document.getElementById('angelaSend').disabled = true;
  document.getElementById('angelaSuggestions').style.display = 'none';

  addMessage('user', msg);

  const context = {
    current_view: currentView,
    visible_metrics: getVisibleMetrics()
  };

  const cancelFn = sendQueryStreaming(msg, context,
    (step) => addStep(step),
    (result) => {
      clearSteps();
      const rendered = renderMarkdown(result.response);
      addMessage('assistant', rendered, true);

      if (result.cards && result.cards.length > 0) {
        addCreditCards(result.cards);
      }
      if (result.navigate_to && result.navigate_to !== currentView) {
        addMessage('assistant', `<div style="font-size:0.78rem;color:var(--accent);cursor:pointer;" onclick="navigateTo('${result.navigate_to}')">📍 Ver vista de ${result.navigate_to} →</div>`, true);
      }

      isQuerying = false;
      document.getElementById('angelaSend').disabled = false;
      document.getElementById('angelaSuggestions').style.display = 'flex';
    }
  );
}

function getVisibleMetrics() {
  if (currentView === 'dashboard' && dashboardData) {
    return {
      health_score: dashboardData.indicators.health_score,
      cash_flow: dashboardData.financials[dashboardData.financials.length - 1].net_cash_flow,
      alerts_count: dashboardData.alerts.length
    };
  }
  if (currentView === 'creditos' && creditosData) {
    return {
      credits_matching: creditosData.credits.filter(c => c.matches_profile).length,
      bcra_situation: creditosData.creditProfile.situation
    };
  }
  return {};
}

function addMessage(role, content, isHtml = false) {
  const container = document.getElementById('angelaMessages');
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  if (isHtml) { div.innerHTML = content; } else { div.textContent = content; }
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function addStep(step) {
  const container = document.getElementById('angelaMessages');
  const existing = container.querySelector(`.msg-step[data-step="${step.step}"]`);
  if (existing) return;

  container.querySelectorAll('.msg-step:not(.done)').forEach(el => el.classList.add('done'));

  const div = document.createElement('div');
  div.className = 'msg-step';
  div.dataset.step = step.step;
  div.innerHTML = `<span class="step-dot"></span> ${step.message}`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function clearSteps() {
  document.querySelectorAll('.msg-step').forEach(el => el.remove());
}

function addCreditCards(cards) {
  const container = document.getElementById('angelaMessages');
  const div = document.createElement('div');
  div.style.cssText = 'display:flex;flex-direction:column;gap:8px;max-width:92%;animation:msgIn 0.3s ease;';
  div.innerHTML = cards.map(c => `
    <div style="background:var(--bg-glass);border:1px solid var(--border);border-radius:8px;padding:10px 14px;font-size:0.78rem;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <div style="font-weight:700;">${c.bank} — ${c.name}</div>
          <div style="color:var(--text-muted);margin-top:2px;">Tasa: ${c.rate} · Hasta ${c.amount}</div>
        </div>
        <span class="match-badge ${c.match ? 'yes' : 'no'}" style="font-size:0.65rem;">${c.match ? '✓' : '⚠'}</span>
      </div>
    </div>
  `).join('');
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function renderMarkdown(text) {
  if (typeof marked !== 'undefined') {
    return marked.parse(text);
  }
  return text.replace(/\n/g, '<br>');
}

// ═══════════════════════════════════════════════════════════════
// FILE UPLOAD
// ═══════════════════════════════════════════════════════════════

function initDragDrop() {
  const overlay = document.getElementById('dropOverlay');
  let dragCounter = 0;

  document.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dragCounter++;
    overlay.classList.add('active');
  });

  document.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) { overlay.classList.remove('active'); dragCounter = 0; }
  });

  document.addEventListener('dragover', (e) => e.preventDefault());

  document.addEventListener('drop', (e) => {
    e.preventDefault();
    dragCounter = 0;
    overlay.classList.remove('active');
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  });
}

async function handleFileUpload(file) {
  if (!angelaOpen) toggleAngela(true);

  const extIcons = { xlsx: '📊', xls: '📊', csv: '📊', pdf: '📄', jpg: '🖼', png: '🖼', jpeg: '🖼', txt: '📝', doc: '📄', docx: '📄' };
  const ext = file.name.split('.').pop().toLowerCase();
  const icon = extIcons[ext] || '📎';
  const sizeKb = (file.size / 1024).toFixed(1);

  const container = document.getElementById('angelaMessages');
  const previewDiv = document.createElement('div');
  previewDiv.className = 'upload-preview';
  previewDiv.innerHTML = `
    <span class="file-icon">${icon}</span>
    <div class="file-info">
      <div class="file-name">${file.name}</div>
      <div class="file-size">${sizeKb} KB</div>
      <div class="upload-progress"><div class="upload-progress-fill" id="uploadFill" style="width:0%"></div></div>
    </div>
  `;
  container.appendChild(previewDiv);
  container.scrollTop = container.scrollHeight;

  const fill = previewDiv.querySelector('#uploadFill');
  let pct = 0;
  const interval = setInterval(() => {
    pct += Math.random() * 25 + 10;
    if (pct > 90) pct = 90;
    fill.style.width = pct + '%';
  }, 300);

  const result = await ingestFile(file);

  clearInterval(interval);
  fill.style.width = '100%';

  setTimeout(() => {
    addMessage('assistant', renderMarkdown(result.angela_comment), true);
  }, 500);
}
