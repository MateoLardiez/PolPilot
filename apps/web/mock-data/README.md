# Mock Data — Video del Pitch

Datos simulados para las 3 interacciones de Angela en el video de la pitch.
Empresa: **Calatayud Frenos y Embragues SRL** (taller de frenos, Venado Tuerto, Santa Fe).

---

## Archivos

### `01_ingesta_audio.json` — El caos de datos (0:35 - 0:55)

El dueño manda un audio desordenado por WhatsApp con datos financieros del mes.
Angela lo parsea y devuelve contabilidad estructurada + health score + alertas.

**Input:** Audio de 22 segundos con números sueltos
**Output:** Tabla financiera, health score 58/100, alertas de liquidez y morosos

**Para el dashboard:** Usar `dashboard_data.revenue_chart` para el gráfico de facturación y `dashboard_data.alerts` para las alertas visuales.

---

### `02_alerta_proactiva.json` — El superagente (0:55 - 1:15)

Angela detecta sola una oportunidad cruzando regulaciones + proveedores + márgenes.
Notifica al dueño sin que él pregunte.

**Input:** Ninguno (Angela inicia la conversación)
**Output:** Notificación push con oportunidad de importación, ahorro del 20%, margen +8 puntos

**Para el dashboard:** Usar `dashboard_data` para mostrar la comparación de costos y el impacto en margen.

---

### `03_creditos_y_carpeta.json` — Créditos + PDF (1:15 - 1:55)

El dueño responde "¡Me sirve! ¿Tengo caja o saco crédito?" Angela analiza la caja,
busca créditos en el mercado, elige el mejor, y genera la carpeta bancaria en PDF.

**Input:** Audio de 5 segundos
**Output:** Análisis de caja + 3 créditos rankeados + PDF de carpeta bancaria completa

**Para el dashboard:**
- `angela_processing.steps` — los 4 pasos con la animación "Simulando Comité de Riesgo"
- `dashboard_data.credit_comparison_chart` — gráfico comparativo de los 3 créditos
- `dashboard_data.margin_projection` — barra de margen actual vs proyectado
- `pdf_attachment.sections` — las 8 secciones del PDF generado

---

## Flujo visual del video

```
[Audio del dueño]  →  Angela parsea  →  Dashboard se actualiza en tiempo real
         ↓
[Angela alerta sola]  →  Notificación push en WhatsApp
         ↓
[Audio: "me sirve!"]  →  "Simulando Comité de Riesgo"  →  3 créditos  →  PDF generado
```
