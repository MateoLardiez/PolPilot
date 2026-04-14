# PolPilot — Arquitectura Completa de Agentes

> Documento tecnico de implementacion para el equipo de desarrollo.
> Hackathon Anthropic — 14 de abril de 2026
> Basado en mejores practicas de multi-agent systems (abril 2026), Anthropic Claude tool-use patterns, y skills.sh.

---

## 1. Principios de Diseno (Best Practices 2026)

### 1.1 El Orquestador NUNCA Ejecuta

Principio critico validado en produccion (fuente: Towards AI, marzo 2026): el orquestador descompone, delega, valida y escala. **Nunca busca datos, nunca llama APIs, nunca genera la respuesta final directamente.** Si lo hace, su context window se contamina con detalles de implementacion y pierde capacidad de razonamiento estrategico.

### 1.2 Aislamiento de Contexto por Agente

Cada agente recibe SOLO la vista minima necesaria para su tarea (fuente: Anthropic, "When to use multi-agent systems"). Esto:
- Protege contra context pollution
- Reduce tokens (single-agent usa 3-10x mas tokens que multi-agent bien diseñado)
- Mejora la especializacion: cada agente elige mejor sus herramientas cuando tiene foco

### 1.3 Artefactos Estructurados, No Chat Libre

Los agentes no "conversan" entre si. Producen artefactos tipados (JSON) que circulan por el gateway/orquestador. Esto reduce costo en tokens, mejora trazabilidad, y permite deteccion de loops (ver doc tecnico v2).

### 1.4 Tool Definitions con Descripciones Exhaustivas

Principio Anthropic: cada tool definition necesita minimo 3-4 oraciones describiendo que hace, cuando usarlo, cuando NO usarlo, y efectos de cada parametro. Esto es el factor #1 de performance en agentes Claude.

### 1.5 Modelo por Criticidad

- **Opus 4.6**: razonamiento complejo (orquestador mesh, agente finanzas)
- **Sonnet 4.6**: tareas de investigacion, validacion
- **Haiku**: clasificacion, routing, resumenes

### 1.6 Strict Tool Use

Todas las tool definitions usan `"strict": true` + `"additionalProperties": false` para garantizar type safety en las llamadas. Elimina la necesidad de validacion y retry logic.

---

## 2. Mapa Completo de Agentes

```
┌───────────────────────────────────────────────────────────────────┐
│                        USUARIO                                     │
│                     (chat / upload)                                │
└────────────────────────┬──────────────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────────────┐
│                   API GATEWAY (FastAPI)                             │
│              POST /query  │  POST /ingest  │  GET /health          │
└────────────────────────┬──────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
┌──────────────────────┐   ┌──────────────────────┐
│   CLASIFICADOR        │   │   DATA SERVICE        │
│   (Haiku)             │   │   (Ingesta/Embeddings) │
│                       │   │                        │
│   Decide:             │   │   Procesa uploads      │
│   - trivial → resp    │   │   Normaliza → Markdown  │
│     directa           │   │   Clasifica topicos     │
│   - simple → 1 agente │   │   Genera embeddings     │
│   - compleja → orq.   │   │   Almacena en DBs       │
└───────────┬───────────┘   └────────────────────────┘
            │
            ▼ (si compleja)
┌───────────────────────────────────────────────────────────────────┐
│                     ORQUESTADOR (Opus 4.6)                         │
│                                                                    │
│  Etapa 1: Entender intencion + contexto del negocio               │
│  Etapa 2: Expandir pregunta → N sub-preguntas por topico          │
│  Etapa 3: Despachar agentes en paralelo (asyncio)                 │
│  Etapa 4: MESH — cruzar respuestas entre agentes                  │
│  Etapa 5: Enviar a Validador Stop-Loss                            │
│  Etapa 6: Entregar respuesta unificada                            │
│                                                                    │
│  ⛔ NO busca datos                                                 │
│  ⛔ NO llama APIs externas                                         │
│  ⛔ NO genera la respuesta visible al usuario                      │
└──────────┬─────────┬──────────┬──────────┬────────────────────────┘
           │         │          │          │
     ┌─────┘    ┌────┘     ┌───┘     ┌────┘
     ▼          ▼          ▼         ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐
│ AGENTE  │ │ AGENTE  │ │ AGENTE  │ │ AGENTE   │
│FINANZAS │ │ECONOMIA │ │INVESTIG.│ │VALIDADOR │
│(Opus)   │ │(Opus)   │ │(Sonnet) │ │(Sonnet)  │
└─────────┘ └─────────┘ └─────────┘ └──────────┘
```

### Resumen de Agentes

| # | Agente | Modelo | Rol Principal | Lee de | Escribe en |
|---|--------|--------|---------------|--------|------------|
| 1 | **Clasificador** | Haiku | Routing rapido de queries | memory.sqlite | — |
| 2 | **Orquestador** | Opus 4.6 | Descomposicion, expansion, mesh, coordinacion | Todos (via tools) | query_log (memory.sqlite) |
| 3 | **Finanzas** | Opus 4.6 | Analisis financiero interno, health score, proyecciones | internal.sqlite, vectors/ | — |
| 4 | **Economia** | Opus 4.6 | Creditos, macro, regulaciones, oportunidades externas | external.sqlite, internal.sqlite (perfil), vectors/ | external.sqlite |
| 5 | **Investigador** | Sonnet 4.6 | Web search, APIs BCRA, tendencias, novedades | external.sqlite, internal.sqlite (perfil) | external.sqlite |
| 6 | **Validador** | Sonnet 4.6 | Verificacion stop-loss "modo usuario" | Solo pregunta original + respuesta | — |
| 7 | **Resumen** | Haiku | Merge summaries de conversaciones | memory.sqlite | memory.sqlite (summaries) |

---

## 3. Agente Clasificador (Intent Router)

### Proposito
Primer filtro. Recibe el mensaje raw del usuario y decide como procesarlo. Es el "Dummy Analyzer" del doc tecnico v2 — pero simplificado para hackathon.

### Modelo
Claude Haiku (rapido, barato, suficiente para clasificacion)

### System Prompt

```
Sos un clasificador de intenciones para PolPilot, un asistente financiero para PyMEs argentinas.

Tu UNICA tarea es analizar el mensaje del usuario y clasificarlo en una de estas categorias:

1. TRIVIAL — Saludo, agradecimiento, pregunta sobre el producto. No requiere agentes.
2. SIMPLE_FINANZAS — Pregunta directa sobre datos internos (flujo de caja, margen, stock). Un solo agente basta.
3. SIMPLE_ECONOMIA — Pregunta directa sobre datos externos (tasas, creditos, regulaciones). Un solo agente basta.
4. COMPLEJA — Requiere cruzar datos internos con externos, o analisis multi-dimensional. Requiere orquestador.
5. INGESTA — El usuario quiere cargar datos (excel, pdf, audio, imagen, texto con datos).

Responde SOLO con JSON estructurado. No expliques tu razonamiento.

Contexto adicional que recibis:
- Resumen acumulado de la conversacion (si existe)
- Ultimo mensaje del usuario
- Perfil basico de la empresa (si existe)
```

### Tool Definitions

```json
[
  {
    "name": "classify_intent",
    "description": "Clasifica la intencion del mensaje del usuario. Usa esto SIEMPRE como tu primera y unica accion. Analiza el mensaje considerando el contexto conversacional previo y el perfil de la empresa para determinar la categoria correcta. Si el usuario menciona datos internos Y externos en la misma consulta, clasifica como COMPLEJA. Si solo menciona uno u otro, clasifica como SIMPLE. Si es un saludo o pregunta generica, clasifica como TRIVIAL.",
    "input_schema": {
      "type": "object",
      "properties": {
        "category": {
          "type": "string",
          "enum": ["TRIVIAL", "SIMPLE_FINANZAS", "SIMPLE_ECONOMIA", "COMPLEJA", "INGESTA"],
          "description": "La categoria de la consulta del usuario"
        },
        "confidence": {
          "type": "number",
          "description": "Nivel de confianza en la clasificacion, de 0.0 a 1.0"
        },
        "detected_topics": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Topicos detectados: 'finanzas', 'economia', 'creditos', 'macro', 'regulaciones', 'proveedores', 'clientes', 'stock', 'proyeccion'"
        },
        "requires_data": {
          "type": "boolean",
          "description": "true si la respuesta requiere consultar bases de datos"
        },
        "summary_for_orchestrator": {
          "type": "string",
          "description": "Resumen de 1 linea de lo que el usuario necesita, para pasarle al orquestador"
        }
      },
      "required": ["category", "confidence", "detected_topics", "requires_data", "summary_for_orchestrator"],
      "additionalProperties": false
    },
    "strict": true
  }
]
```

### Flujo
```
Usuario → Clasificador → {
  TRIVIAL → Respuesta directa (Haiku, sin agentes)
  SIMPLE_* → Agente correspondiente (sin orquestador)
  COMPLEJA → Orquestador completo
  INGESTA → Data Service
}
```

---

## 4. Orquestador (Cerebro Core)

### Proposito
El componente mas critico del sistema. Recibe consultas complejas, las descompone en sub-preguntas por topico, despacha agentes en paralelo, cruza sus respuestas (MESH), y coordina la validacion final.

### Modelo
Claude Opus 4.6 (maximo razonamiento, creditos ilimitados en hackathon)

### System Prompt

```
Sos el Orquestador de PolPilot, un sistema de inteligencia empresarial para PyMEs argentinas.

Tu rol es COORDINAR, no ejecutar. Nunca buscas datos vos mismo. Nunca llamas APIs. 
Tu trabajo es pensar estrategicamente:

1. ENTENDER: Analiza la intencion real del usuario. No te quedes con lo literal.
   - "quiero un credito" → necesita: situacion financiera + opciones de credito + pre-calificacion + estrategia
   - "como estoy?" → necesita: health score + alertas + comparacion con sector

2. EXPANDIR: De 1 pregunta del usuario, genera 3-5 sub-preguntas por topico relevante.
   Cada sub-pregunta debe ser ESPECIFICA y ACCIONABLE para el agente que la va a recibir.
   
3. DESPACHAR: Envia las sub-preguntas a los agentes correspondientes en paralelo.
   - Preguntas sobre datos INTERNOS → Agente Finanzas
   - Preguntas sobre datos EXTERNOS → Agente Economia  
   - Necesidad de datos frescos de la web → Agente Investigador

4. MESH (cruce de respuestas): Cuando los agentes responden, CRUZA la informacion.
   Esto es tu valor diferencial. Ejemplo:
   - Economia dice: "hay credito al 29% TNA, requiere liquidez > $2M"
   - Finanzas dice: "liquidez actual $1.8M, pero si cobra a Gutierrez sube a $2.3M"
   - Tu cruce: "Aplica condicionalmente. Estrategia: cobrar deuda pendiente primero."

5. VALIDAR: Envia la respuesta unificada al Validador antes de entregarla al usuario.

REGLAS DURAS:
- Maximo 3 iteraciones por consulta
- Maximo 4 agentes activos simultaneos
- Si un agente no responde en 5 segundos, continuar sin el
- Siempre incluir nivel de confianza en la respuesta

CONTEXTO QUE RECIBIS:
- Clasificacion del intent (del Clasificador)
- Perfil de la empresa
- Resumen conversacional acumulado
- Resultado de las sub-preguntas de cada agente
```

### Tool Definitions

```json
[
  {
    "name": "expand_query",
    "description": "Expande la pregunta del usuario en sub-preguntas especializadas por topico. Usa esto como primer paso despues de entender la intencion. Genera preguntas ESPECIFICAS que los agentes puedan responder consultando sus fuentes de datos. Cada pregunta debe ser autocontenida — el agente receptor no tiene contexto de las otras preguntas. Incluye el contexto necesario en cada pregunta (ej: 'la empresa factura $18M/ano' si es relevante).",
    "input_schema": {
      "type": "object",
      "properties": {
        "original_intent": {
          "type": "string",
          "description": "La intencion real del usuario en 1 oracion (no la pregunta literal)"
        },
        "finance_questions": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Sub-preguntas para el Agente Finanzas (datos internos: caja, margenes, deudas, clientes, stock)"
        },
        "economy_questions": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Sub-preguntas para el Agente Economia (datos externos: creditos, tasas, regulaciones, macro)"
        },
        "research_needed": {
          "type": "boolean",
          "description": "true si se necesita informacion fresca de la web que no esta en las bases de datos"
        },
        "research_tasks": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Tareas de investigacion para el Agente Investigador (solo si research_needed=true)"
        }
      },
      "required": ["original_intent", "finance_questions", "economy_questions", "research_needed"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "dispatch_agents",
    "description": "Despacha las sub-preguntas a los agentes correspondientes para ejecucion paralela. Solo usa esto DESPUES de expand_query. Los agentes se ejecutan en paralelo via asyncio. El resultado de cada agente incluye los datos encontrados, su analisis, y su nivel de confianza.",
    "input_schema": {
      "type": "object",
      "properties": {
        "agents_to_call": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "agent_name": {
                "type": "string",
                "enum": ["finance", "economy", "research"],
                "description": "Nombre del agente a llamar"
              },
              "questions": {
                "type": "array",
                "items": { "type": "string" },
                "description": "Las sub-preguntas asignadas a este agente"
              },
              "priority": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "Prioridad de ejecucion"
              },
              "context_hint": {
                "type": "string",
                "description": "Contexto adicional que el agente necesita para responder mejor"
              }
            },
            "required": ["agent_name", "questions", "priority"],
            "additionalProperties": false
          },
          "description": "Lista de agentes a ejecutar con sus preguntas"
        }
      },
      "required": ["agents_to_call"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "mesh_responses",
    "description": "Cruza las respuestas de multiples agentes para generar una respuesta integrada. Este es el paso MAS IMPORTANTE del orquestador. Busca conexiones, contradicciones, y oportunidades que solo emergen al cruzar datos internos con externos. Ejemplo: si Finanzas dice 'tiene $2M de liquidez' y Economia dice 'el credito requiere $1.5M de garantia', el mesh identifica que aplica y calcula el margen.",
    "input_schema": {
      "type": "object",
      "properties": {
        "agent_responses": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "agent_name": { "type": "string" },
              "key_findings": {
                "type": "array",
                "items": { "type": "string" }
              },
              "confidence": { "type": "number" },
              "data_gaps": {
                "type": "array",
                "items": { "type": "string" }
              }
            },
            "required": ["agent_name", "key_findings", "confidence"],
            "additionalProperties": false
          }
        },
        "cross_insights": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Insights que SOLO emergen al cruzar respuestas de distintos agentes"
        },
        "contradictions": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Contradicciones detectadas entre agentes (si las hay)"
        },
        "unified_recommendation": {
          "type": "string",
          "description": "Recomendacion unificada que integra todos los hallazgos"
        },
        "confidence_overall": {
          "type": "number",
          "description": "Confianza global de la respuesta (0.0 a 1.0)"
        },
        "needs_second_pass": {
          "type": "boolean",
          "description": "true si se detectaron gaps criticos que requieren otra ronda de agentes"
        }
      },
      "required": ["agent_responses", "cross_insights", "unified_recommendation", "confidence_overall", "needs_second_pass"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "request_validation",
    "description": "Envia la respuesta unificada al Agente Validador para verificacion stop-loss. El validador solo conoce la pregunta original del usuario y la respuesta propuesta — no sabe que agentes fueron consultados ni que sub-preguntas se hicieron. Esto garantiza que la respuesta sea util desde la perspectiva del usuario.",
    "input_schema": {
      "type": "object",
      "properties": {
        "original_user_query": {
          "type": "string",
          "description": "La pregunta EXACTA del usuario (sin modificar)"
        },
        "proposed_response": {
          "type": "string",
          "description": "La respuesta unificada que se propone entregar"
        },
        "confidence": {
          "type": "number",
          "description": "Confianza del orquestador en esta respuesta"
        }
      },
      "required": ["original_user_query", "proposed_response", "confidence"],
      "additionalProperties": false
    },
    "strict": true
  }
]
```

---

## 5. Agente Finanzas (Internal Analyst)

### Proposito
Especialista en datos internos de la empresa. Analiza flujo de caja, margenes, indicadores financieros, salud de clientes/proveedores, stock, y genera proyecciones. Es el agente que "conoce el negocio desde adentro".

### Modelo
Claude Opus 4.6

### System Prompt

```
Sos el Agente de Finanzas de PolPilot, especializado en analisis financiero interno de PyMEs argentinas.

Tu UNICO trabajo es analizar datos INTERNOS de la empresa para responder preguntas financieras.

CAPACIDADES:
- Calcular y evaluar Health Score (0-100) basado en margenes, liquidez, endeudamiento y ciclo de caja
- Analizar flujo de caja: tendencias, estacionalidad, proyecciones a 3-6 meses
- Evaluar capacidad de repago para creditos
- Identificar clientes morosos y su impacto en liquidez
- Comparar rentabilidad por producto/servicio
- Detectar anomalias en ingresos/egresos
- Calcular ratios financieros: margen bruto, neto, ROA, ROE, razon corriente, prueba acida
- Proyectar escenarios (optimista, base, pesimista) considerando estacionalidad

REGLAS:
- Solo trabajas con datos que EXISTEN en la base interna. Si no hay datos, decilo claramente.
- Nunca inventes numeros. Si falta informacion, indica que datos necesitarias.
- Siempre contextualizas los numeros: "$2M de liquidez" no significa nada sin comparar con obligaciones.
- Cuando calculas ratios, explica que significan en terminos simples para un dueno PyME.
- Si detectas riesgo financiero, alerta con severidad (bajo/medio/alto/critico).
- Incluye siempre el periodo de los datos que estas analizando.

FORMATO DE RESPUESTA:
Responde con datos concretos, numeros, y recomendaciones accionables.
Incluye nivel de confianza basado en la completitud de datos disponibles.
```

### Tool Definitions

```json
[
  {
    "name": "query_financials",
    "description": "Consulta datos financieros mensuales de la empresa (ingresos, egresos, flujo de caja, saldo, cuentas por cobrar/pagar, inventario). Usa esto para obtener la foto financiera de la empresa en un rango de meses. Si necesitas tendencias, consulta al menos 6 meses. Para estacionalidad, consulta 12 meses. Los datos vienen de internal.sqlite tabla financials_monthly.",
    "input_schema": {
      "type": "object",
      "properties": {
        "months_back": {
          "type": "integer",
          "description": "Cuantos meses hacia atras consultar desde hoy (ej: 6 para ultimo semestre, 12 para ultimo año)"
        },
        "metrics": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["revenue", "expenses", "net_cash_flow", "cash_balance", "accounts_receivable", "accounts_payable", "inventory_value"]
          },
          "description": "Metricas especificas a consultar. Si necesitas todo, incluye todas."
        }
      },
      "required": ["months_back", "metrics"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "query_indicators",
    "description": "Consulta indicadores financieros calculados de la empresa (margenes, ratios, health score). Los indicadores se calculan periodicamente y se almacenan en internal.sqlite tabla financial_indicators. Usa esto cuando necesites evaluar la salud financiera general o comparar periodos.",
    "input_schema": {
      "type": "object",
      "properties": {
        "period": {
          "type": "string",
          "description": "Periodo a consultar: 'latest', 'YYYY-MM', 'YYYY-QN' (ej: '2026-03', '2026-Q1', 'latest')"
        },
        "indicators": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["gross_margin", "net_margin", "roa", "roe", "current_ratio", "quick_ratio", "working_capital", "debt_to_equity", "days_receivable", "days_payable", "inventory_turnover", "cash_cycle", "health_score"]
          },
          "description": "Indicadores especificos a consultar"
        }
      },
      "required": ["period", "indicators"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "query_clients",
    "description": "Consulta datos de los clientes de la empresa (facturacion, morosidad, riesgo). Usa esto para evaluar la calidad de la cartera de clientes, identificar morosos, o calcular impacto de cobro. Los datos vienen de internal.sqlite tabla clients.",
    "input_schema": {
      "type": "object",
      "properties": {
        "filter": {
          "type": "string",
          "enum": ["all", "high_risk", "overdue", "top_revenue"],
          "description": "Filtro: 'all' para todos, 'high_risk' para riesgo alto, 'overdue' para morosos, 'top_revenue' para mayores"
        },
        "limit": {
          "type": "integer",
          "description": "Cantidad maxima de clientes a retornar (default 10)"
        }
      },
      "required": ["filter"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "query_products",
    "description": "Consulta datos de productos/servicios de la empresa (rentabilidad, stock, margenes). Usa esto para analizar que productos generan mas valor o tienen problemas de stock. Los datos vienen de internal.sqlite tabla products.",
    "input_schema": {
      "type": "object",
      "properties": {
        "sort_by": {
          "type": "string",
          "enum": ["margin_desc", "revenue_desc", "low_stock"],
          "description": "Ordenamiento: 'margin_desc' por mejor margen, 'revenue_desc' por mayor ingreso, 'low_stock' por stock critico"
        }
      },
      "required": ["sort_by"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "query_suppliers",
    "description": "Consulta datos de proveedores de la empresa (precios, confiabilidad, plazos de pago). Usa esto para comparar proveedores o evaluar riesgo de supply chain. Los datos vienen de internal.sqlite tabla suppliers.",
    "input_schema": {
      "type": "object",
      "properties": {
        "filter": {
          "type": "string",
          "enum": ["all", "primary", "by_reliability"],
          "description": "Filtro: 'all', 'primary' para principales, 'by_reliability' ordenados por confiabilidad"
        }
      },
      "required": ["filter"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "semantic_search_internal",
    "description": "Busqueda semantica sobre datos internos de la empresa usando ChromaDB (embeddings). Usa esto cuando necesites encontrar informacion que no esta en tablas estructuradas — por ejemplo, contenido de documentos cargados, notas de conversaciones previas, o datos cualitativos. La busqueda devuelve los fragmentos mas relevantes semanticamente.",
    "input_schema": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Consulta en lenguaje natural (ej: 'problemas de liquidez en los ultimos meses', 'deudas con proveedores')"
        },
        "top_k": {
          "type": "integer",
          "description": "Cantidad de resultados a retornar (recomendado: 5-10)"
        },
        "collection": {
          "type": "string",
          "enum": ["internal_docs", "conversation_context"],
          "description": "Collection de ChromaDB: 'internal_docs' para documentos de la empresa, 'conversation_context' para historial de conversaciones"
        }
      },
      "required": ["query", "top_k", "collection"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "calculate_repayment_capacity",
    "description": "Calcula la capacidad de repago de la empresa para un credito dado. Usa los datos de flujo de caja proyectado, obligaciones existentes, y el monto/cuota del credito evaluado. Retorna si la empresa puede pagar, con que margen, y bajo que condiciones.",
    "input_schema": {
      "type": "object",
      "properties": {
        "credit_amount": {
          "type": "number",
          "description": "Monto del credito a evaluar (en pesos)"
        },
        "monthly_payment": {
          "type": "number",
          "description": "Cuota mensual estimada del credito"
        },
        "term_months": {
          "type": "integer",
          "description": "Plazo del credito en meses"
        }
      },
      "required": ["credit_amount", "monthly_payment", "term_months"],
      "additionalProperties": false
    },
    "strict": true
  }
]
```

### Skills (inspiradas en skills.sh/qodex-ai/financial-analysis-agent)

1. **Analisis Tecnico Financiero**: Calculo de tendencias, promedios moviles de ingresos, RSI de flujo de caja (detectar sobre-extension o contraccion)
2. **Analisis Fundamental**: Ratios de rentabilidad, valuacion, liquidez, endeudamiento
3. **Risk Assessment**: Volatilidad de ingresos, VaR simplificado (peor escenario a 95% de confianza), evaluacion de riesgo por cliente
4. **Proyeccion Estacional**: Usar historial para proyectar meses futuros considerando patron estacional del negocio
5. **Health Score Composite**: Score 0-100 ponderado: liquidez (30%) + rentabilidad (25%) + endeudamiento (20%) + ciclo de caja (15%) + tendencia (10%)

---

## 6. Agente Economia (External Analyst)

### Proposito
Especialista en el contexto externo. Maneja creditos disponibles, indicadores macro, regulaciones, oportunidades, y la inteligencia colectiva de la red PolPilot. Es el agente que "mira hacia afuera".

### Modelo
Claude Opus 4.6

### System Prompt

```
Sos el Agente de Economia de PolPilot, especializado en contexto economico externo para PyMEs argentinas.

Tu UNICO trabajo es analizar datos EXTERNOS y cruzarlos con el perfil de la empresa para generar recomendaciones de oportunidades y riesgos.

CAPACIDADES:
- Evaluar creditos disponibles y pre-calificar a la empresa
- Analizar indicadores macroeconomicos (tasas BCRA, inflacion, tipo de cambio) y su impacto en el negocio
- Interpretar regulaciones nuevas y su relevancia para la empresa
- Detectar oportunidades crediticias (matching credito-empresa)
- Generar ranking de creditos por conveniencia (considerando tasa, plazo, monto, requisitos, capacidad de repago)
- Evaluar perfil crediticio BCRA (situacion 1-5, historial 24 meses, cheques rechazados)
- Analizar señales del sector (precios, demanda, competencia)
- Consultar inteligencia colectiva de la red PolPilot (benchmarks anonimizados)

REGLAS:
- Cuando recomiendes un credito, SIEMPRE incluye: banco, tasa TNA, monto max, plazo, requisitos, y por que aplica o no.
- Si el perfil crediticio BCRA tiene problemas (situacion > 1), alertalo como CRITICO.
- Siempre contextualiza las tasas: "33% TNA es X% real considerando inflacion actual de Y%".
- Cuando hables de regulaciones, indica si son CONFIRMADAS o PRE-OFICIALES con probabilidad.
- Si no hay datos suficientes para pre-calificar, indica que informacion falta.

FORMATO DE RESPUESTA:
Datos concretos, comparativas, rankings. Nunca generalidades.
Incluye fuentes (BCRA, banco, web) y fecha de ultima actualizacion.
```

### Tool Definitions

```json
[
  {
    "name": "query_available_credits",
    "description": "Consulta creditos disponibles filtrados por tipo, monto, o banco. Los datos vienen de external.sqlite tabla available_credits, actualizada periodicamente por el Agente Investigador con datos de BCRA Transparencia y bancos. Usa esto para encontrar opciones de credito y luego evaluar si la empresa califica.",
    "input_schema": {
      "type": "object",
      "properties": {
        "credit_type": {
          "type": "string",
          "enum": ["all", "inversion", "capital_trabajo", "maquinaria"],
          "description": "Tipo de credito a buscar"
        },
        "min_amount": {
          "type": "number",
          "description": "Monto minimo requerido (en pesos). Filtra creditos cuyo max_amount sea >= este valor."
        },
        "max_rate": {
          "type": "number",
          "description": "Tasa maxima aceptable (TNA). Filtra creditos con annual_rate <= este valor."
        },
        "requires_mipyme": {
          "type": "boolean",
          "description": "Filtrar solo creditos que requieran (true) o no requieran (false) certificado MiPyME. null para no filtrar."
        }
      },
      "required": ["credit_type"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "query_macro_indicators",
    "description": "Consulta indicadores macroeconomicos actuales y recientes. Datos de external.sqlite tabla macro_indicators, alimentada por APIs BCRA. Usa esto para contextualizar tasas de credito, evaluar costo real de financiamiento, o analizar tendencias macro.",
    "input_schema": {
      "type": "object",
      "properties": {
        "indicators": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["tasa_referencia", "inflacion_mensual", "inflacion_anual", "usd_oficial", "usd_blue", "reservas", "riesgo_pais", "badlar"]
          },
          "description": "Indicadores a consultar"
        },
        "days_back": {
          "type": "integer",
          "description": "Cuantos dias hacia atras consultar (ej: 30 para ultimo mes, 90 para trimestre)"
        }
      },
      "required": ["indicators"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "query_credit_profile",
    "description": "Consulta el perfil crediticio BCRA de la empresa por CUIT. Incluye situacion (1-5), deuda total, dias de atraso, historial 24 meses, y cheques rechazados. CRITICO para pre-calificacion de creditos. Datos de external.sqlite tabla credit_profile.",
    "input_schema": {
      "type": "object",
      "properties": {
        "cuit": {
          "type": "string",
          "description": "CUIT de la empresa (formato: XX-XXXXXXXX-X)"
        }
      },
      "required": ["cuit"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "query_regulations",
    "description": "Consulta regulaciones y novedades normativas relevantes para la empresa. Incluye regulaciones BCRA, boletin oficial, ARCA, y programas gubernamentales. Los datos incluyen titulo, resumen, fuente, estado (confirmada/pre-oficial), y relevancia para la empresa.",
    "input_schema": {
      "type": "object",
      "properties": {
        "filter": {
          "type": "string",
          "enum": ["all", "confirmed", "pre_official", "high_relevance"],
          "description": "Filtro: 'all', 'confirmed' solo confirmadas, 'pre_official' rumores/proyectos, 'high_relevance' relevancia > 0.7"
        },
        "sector": {
          "type": "string",
          "description": "Filtrar por sector especifico (ej: 'automotriz', 'alimentos', 'servicios'). Dejar vacio para todos."
        }
      },
      "required": ["filter"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "query_sector_signals",
    "description": "Consulta señales y tendencias del sector de la empresa. Incluye cambios de precios, shifts de demanda, movimientos de competidores, y delays de supply chain. Datos de external.sqlite tabla sector_signals.",
    "input_schema": {
      "type": "object",
      "properties": {
        "sector": {
          "type": "string",
          "description": "Sector a consultar (ej: 'automotriz', 'repuestos', 'servicios_mecanicos')"
        },
        "impact_level": {
          "type": "string",
          "enum": ["all", "high", "medium"],
          "description": "Nivel de impacto minimo"
        }
      },
      "required": ["sector"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "query_collective_intelligence",
    "description": "Consulta datos anonimizados de la red PolPilot (inteligencia colectiva). Benchmark contra otras empresas del sector. Incluye promedios de margen, dias de cobro, tendencias de precios, y comparativas. NUNCA revela datos individuales de otras empresas.",
    "input_schema": {
      "type": "object",
      "properties": {
        "metric_name": {
          "type": "string",
          "enum": ["avg_margin_sector", "avg_payment_days", "price_trend_product", "demand_trend", "supplier_reliability"],
          "description": "Metrica de la red a consultar"
        },
        "sector": {
          "type": "string",
          "description": "Sector para el benchmark"
        },
        "region": {
          "type": "string",
          "description": "Region geografica (ej: 'santa_fe', 'buenos_aires', 'nacional')"
        }
      },
      "required": ["metric_name", "sector"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "rank_credits_for_company",
    "description": "Genera un ranking de creditos ordenados por conveniencia para ESTA empresa especifica. Cruza los creditos disponibles con el perfil de la empresa (tamaño, sector, situacion BCRA, liquidez). Retorna top N creditos con score de matching, explicacion de por que aplica o no, y acciones necesarias si no aplica directamente.",
    "input_schema": {
      "type": "object",
      "properties": {
        "company_profile_summary": {
          "type": "string",
          "description": "Resumen del perfil de la empresa: sector, facturacion, liquidez, situacion BCRA, certificado MiPyME"
        },
        "purpose": {
          "type": "string",
          "enum": ["inversion", "capital_trabajo", "maquinaria", "general"],
          "description": "Para que quiere el credito"
        },
        "desired_amount": {
          "type": "number",
          "description": "Monto deseado (en pesos)"
        },
        "top_n": {
          "type": "integer",
          "description": "Cuantos creditos incluir en el ranking (recomendado: 5)"
        }
      },
      "required": ["company_profile_summary", "purpose", "top_n"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "semantic_search_external",
    "description": "Busqueda semantica sobre datos externos usando ChromaDB collection 'external_research'. Usa esto para encontrar informacion no estructurada: articulos de investigacion, notas de regulaciones, reportes de sector, etc.",
    "input_schema": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Consulta en lenguaje natural"
        },
        "top_k": {
          "type": "integer",
          "description": "Cantidad de resultados (recomendado: 5-10)"
        }
      },
      "required": ["query", "top_k"],
      "additionalProperties": false
    },
    "strict": true
  }
]
```

### Skills

1. **Credit Matching Engine**: Algoritmo de matching empresa-credito que pondera: situacion BCRA (peso 0.3), liquidez vs cuota (0.25), certificado MiPyME (0.15), historial (0.15), sector elegible (0.15)
2. **Macro Context Analyzer**: Interpreta datos BCRA en contexto (tasa real = TNA - inflacion, costo real de financiamiento, tendencia de tasas)
3. **Pre-Qualification Engine**: Evalua automaticamente si la empresa cumple requisitos de cada credito disponible
4. **Regulatory Impact Scorer**: Califica relevancia de cada regulacion para la empresa especifica (0-1)
5. **Sector Benchmarking**: Compara metricas de la empresa contra promedios anonimizados de la red

---

## 7. Agente Investigador (Web Research Agent)

### Proposito
Sale a la web a buscar informacion fresca. Consulta APIs del BCRA en tiempo real, busca noticias del sector, regulaciones nuevas, tendencias de mercado. Alimenta la base externa con informacion actualizada. Es el agente que "sale a la calle".

### Modelo
Claude Sonnet 4.6 (balance costo/calidad, muchas llamadas a tools)

### System Prompt

```
Sos el Agente Investigador de PolPilot. Tu trabajo es salir a buscar informacion actualizada de internet y APIs externas.

CAPACIDADES:
- Consultar APIs del BCRA (Transparencia, Central de Deudores, Variables Monetarias)
- Buscar noticias y novedades del sector de la empresa
- Buscar regulaciones nuevas (BCRA, Boletin Oficial, ARCA)
- Investigar creditos y programas de financiamiento actuales
- Detectar señales de mercado (precios, demanda, competencia)
- Extraer datos estructurados de paginas web

REGLAS:
- Maximo 5 busquedas web por tarea para mantener latencia acotada
- Siempre incluir fuente y fecha de la informacion
- Distinguir entre datos confirmados y rumores/proyectos
- Antes de buscar en la web, verificar si ya existe informacion reciente en external.sqlite (evitar duplicados)
- Los datos que encuentres se guardan en external.sqlite para uso futuro
- Priorizar fuentes oficiales (BCRA, bancos, gobierno) sobre noticias/blogs
- Si la API del BCRA falla, usar datos curados como fallback

WORKFLOW RECOMENDADO:
1. Verificar que datos ya existen y su antiguedad
2. Si hay datos frescos (< 24h), no re-consultar
3. Si faltan o estan viejos, consultar APIs/web
4. Estructurar la informacion encontrada
5. Guardar en external.sqlite para futuro uso
6. Retornar hallazgos al orquestador
```

### Tool Definitions

```json
[
  {
    "name": "bcra_transparency_api",
    "description": "Consulta la API de Transparencia del BCRA para obtener tasas y condiciones de creditos publicadas por bancos. Sin autenticacion requerida. Retorna datos JSON con tasas TNA/TEA, montos, plazos, y condiciones por banco. Esta es la fuente PRINCIPAL de datos de creditos actualizados. URL base: https://api.bcra.gob.ar/centraldebalances/v1/transparencia",
    "input_schema": {
      "type": "object",
      "properties": {
        "product_type": {
          "type": "string",
          "enum": ["prestamos_personales", "prestamos_prendarios", "prestamos_hipotecarios", "tasas_tarjetas"],
          "description": "Tipo de producto financiero a consultar"
        },
        "bank_id": {
          "type": "string",
          "description": "ID de la entidad bancaria (opcional, dejar vacio para todas)"
        }
      },
      "required": ["product_type"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "bcra_debtors_api",
    "description": "Consulta la Central de Deudores del BCRA para obtener el perfil crediticio de una empresa por CUIT. Sin autenticacion requerida. Retorna: situacion (1-5), deuda total, dias de mora, historial 24 meses, cheques rechazados. URL base: https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas",
    "input_schema": {
      "type": "object",
      "properties": {
        "cuit": {
          "type": "string",
          "description": "CUIT de la empresa (formato numerico, sin guiones)"
        }
      },
      "required": ["cuit"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "bcra_statistics_api",
    "description": "Consulta la API de Estadisticas Monetarias del BCRA (v4.0) para obtener variables macroeconomicas. Requiere token gratuito. Retorna: tasas de referencia, inflacion, tipo de cambio, reservas, BADLAR, etc. URL base: https://api.bcra.gob.ar/estadisticascambiarias/v1.0",
    "input_schema": {
      "type": "object",
      "properties": {
        "variable": {
          "type": "string",
          "enum": ["tasa_politica_monetaria", "badlar", "inflacion_mensual", "usd_oficial", "usd_mayorista", "reservas_internacionales", "base_monetaria"],
          "description": "Variable macroeconomica a consultar"
        },
        "date_from": {
          "type": "string",
          "description": "Fecha desde (formato YYYY-MM-DD)"
        },
        "date_to": {
          "type": "string",
          "description": "Fecha hasta (formato YYYY-MM-DD)"
        }
      },
      "required": ["variable"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "web_search",
    "description": "Busca informacion en la web usando Tavily Search API (optimizada para AI/RAG). Usa esto para buscar noticias del sector, regulaciones, programas de credito, tendencias de mercado. Soporta topics: 'general', 'news', 'finance'. Maximo 5 busquedas por tarea. Priorizar queries especificos sobre genericos.",
    "input_schema": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Query de busqueda (ser especifico, incluir 'Argentina', 'PyME', sector, año)"
        },
        "topic": {
          "type": "string",
          "enum": ["general", "news", "finance"],
          "description": "Tipo de busqueda: 'finance' para datos financieros, 'news' para noticias recientes, 'general' para todo"
        },
        "max_results": {
          "type": "integer",
          "description": "Maximo de resultados (recomendado: 5)"
        },
        "days_back": {
          "type": "integer",
          "description": "Solo resultados de los ultimos N dias (para noticias frescas)"
        }
      },
      "required": ["query", "topic", "max_results"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "fetch_url",
    "description": "Extrae contenido de una URL especifica y lo convierte a texto estructurado. Usa esto cuando web_search encuentra una pagina relevante y necesitas el contenido completo. Ideal para paginas de bancos con detalles de creditos, resoluciones del BCRA, o articulos de analisis.",
    "input_schema": {
      "type": "object",
      "properties": {
        "url": {
          "type": "string",
          "description": "URL completa a extraer"
        }
      },
      "required": ["url"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "save_to_external_db",
    "description": "Guarda datos investigados en external.sqlite para uso futuro de otros agentes. SIEMPRE usa esto despues de encontrar informacion nueva. Esto alimenta el cerebro de PolPilot y evita re-consultar la misma informacion. Cada dato se guarda con fuente, fecha, y tipo.",
    "input_schema": {
      "type": "object",
      "properties": {
        "table": {
          "type": "string",
          "enum": ["available_credits", "macro_indicators", "regulations", "sector_signals", "credit_profile"],
          "description": "Tabla destino en external.sqlite"
        },
        "data": {
          "type": "object",
          "description": "Datos a guardar, estructura dependiente de la tabla. Los campos deben coincidir con el schema de la tabla."
        },
        "source": {
          "type": "string",
          "description": "Fuente de la informacion (ej: 'bcra_api', 'web_search', 'curated')"
        }
      },
      "required": ["table", "data", "source"],
      "additionalProperties": false
    },
    "strict": true
  },
  {
    "name": "check_data_freshness",
    "description": "Verifica la antiguedad de los datos existentes en external.sqlite para decidir si hay que re-consultar. Retorna la fecha de la ultima actualizacion para la tabla y filtros indicados. Si los datos tienen < 24h, generalmente no es necesario re-consultar.",
    "input_schema": {
      "type": "object",
      "properties": {
        "table": {
          "type": "string",
          "enum": ["available_credits", "macro_indicators", "regulations", "sector_signals", "credit_profile"],
          "description": "Tabla a verificar"
        },
        "filter_key": {
          "type": "string",
          "description": "Clave de filtro opcional (ej: 'bank_name', 'indicator_name', 'cuit')"
        },
        "filter_value": {
          "type": "string",
          "description": "Valor del filtro"
        }
      },
      "required": ["table"],
      "additionalProperties": false
    },
    "strict": true
  }
]
```

### Skills (inspiradas en skills.sh/smithery/web-research + skills.sh/jwynia/web-search-tavily)

1. **Structured Web Research**: Metodologia de investigacion en 3 pasos: planificar subtemas → buscar en paralelo → sintetizar hallazgos
2. **BCRA Data Pipeline**: Consulta secuencial de las 3 APIs del BCRA, normalizacion de datos, y almacenamiento estructurado
3. **Source Validation**: Clasifica fuentes por confiabilidad (A=oficial, B=banco, C=medios especializados, D=blogs, E=redes sociales)
4. **Deduplication Check**: Antes de guardar, verifica si el dato ya existe y solo actualiza si cambio
5. **Freshness Policy**: Datos macro se refrescan cada 24h, creditos cada 48h, regulaciones cada 72h, señales de sector cada semana

---

## 8. Agente Validador (Stop-Loss)

### Proposito
Ultimo filtro antes de entregar la respuesta al usuario. Opera en "modo usuario" — solo conoce la pregunta original y la respuesta propuesta. No sabe que agentes fueron consultados, que sub-preguntas se hicieron, ni que datos se usaron. Evalua: "esto realmente responde lo que el usuario pidio?"

### Modelo
Claude Sonnet 4.6

### System Prompt

```
Sos el Agente Validador de PolPilot. Sos el ultimo control de calidad antes de que una respuesta llegue al usuario.

Tu rol es SIMULAR SER EL USUARIO. Solo conoces:
- La pregunta ORIGINAL del usuario (tal cual la escribio)
- La respuesta PROPUESTA (que generaron los otros agentes)

NO conoces:
- Que agentes fueron consultados
- Que sub-preguntas se generaron
- Que datos se usaron
- Cuantas iteraciones hubo

EVALUAS:
1. RELEVANCIA: La respuesta aborda lo que el usuario pregunto? (no algo tangencialmente relacionado)
2. COMPLETITUD: Cubre todos los aspectos de la pregunta? Si pregunto "a que credito puedo aplicar", necesita opciones concretas, no generalidades.
3. ACCIONABILIDAD: El usuario puede HACER algo con esta respuesta? Tiene pasos concretos?
4. CLARIDAD: Un dueno de PyME sin formacion financiera puede entender esto?
5. DATOS CONCRETOS: Tiene numeros, tasas, montos, plazos? O son solo opiniones vagas?
6. HONESTIDAD: Si hay limitaciones o datos faltantes, se mencionan claramente?

DECISION:
- APROBADA: La respuesta es util, completa, y accionable. Entregarla al usuario.
- MEJORAR: La respuesta tiene gaps especificos. Retornar con instrucciones de que falta.
- RECHAZADA: La respuesta no sirve. Retornar con razon.

REGLAS:
- Maximo 1 ronda de mejora. Si despues de 1 correccion sigue insuficiente, entregar con disclaimer.
- No re-escribas la respuesta vos mismo. Solo evaluas y das feedback.
- Se critico pero justo. No rechaces por detalles menores.
```

### Tool Definitions

```json
[
  {
    "name": "validate_response",
    "description": "Evalua la respuesta propuesta desde la perspectiva del usuario. Simula ser el dueno de una PyME que hizo una pregunta y evalua si la respuesta es util. No tenés contexto de como se genero la respuesta — solo la pregunta original y la respuesta. Esto es intencional para garantizar que la respuesta sea autocontenida y util.",
    "input_schema": {
      "type": "object",
      "properties": {
        "decision": {
          "type": "string",
          "enum": ["APPROVED", "IMPROVE", "REJECTED"],
          "description": "Decision: APPROVED si la respuesta es util, IMPROVE si tiene gaps corregibles, REJECTED si no sirve"
        },
        "relevance_score": {
          "type": "number",
          "description": "Que tan relevante es la respuesta a la pregunta (0.0 a 1.0)"
        },
        "completeness_score": {
          "type": "number",
          "description": "Que tan completa es la respuesta (0.0 a 1.0)"
        },
        "actionability_score": {
          "type": "number",
          "description": "Que tan accionable es para el usuario (0.0 a 1.0)"
        },
        "clarity_score": {
          "type": "number",
          "description": "Que tan clara es para un dueno PyME (0.0 a 1.0)"
        },
        "has_concrete_data": {
          "type": "boolean",
          "description": "true si incluye numeros concretos (montos, tasas, plazos, etc.)"
        },
        "improvement_instructions": {
          "type": "string",
          "description": "Si decision es IMPROVE: instrucciones especificas de que mejorar. Si APPROVED: vacio."
        },
        "rejection_reason": {
          "type": "string",
          "description": "Si decision es REJECTED: razon concreta. Si no: vacio."
        }
      },
      "required": ["decision", "relevance_score", "completeness_score", "actionability_score", "clarity_score", "has_concrete_data"],
      "additionalProperties": false
    },
    "strict": true
  }
]
```

---

## 9. Agente Resumen (Merge Summaries)

### Proposito
Corre en paralelo a la conversacion. Cada N mensajes (o al final de la conversacion), genera un resumen acumulativo que compacta el contexto sin perder informacion clave. Esto es lo que permite que PolPilot "recuerde" conversaciones anteriores sin explotar el context window.

### Modelo
Claude Haiku (rapido, barato, ideal para resumen)

### System Prompt

```
Sos el Agente de Resumen de PolPilot. Tu trabajo es comprimir conversaciones en resumenes incrementales sin perder informacion clave.

TECNICA: Merge Summaries
- Tomas el resumen anterior (si existe) + los ultimos N mensajes
- Generas un nuevo resumen que INTEGRA ambos
- El resumen nuevo reemplaza al anterior + mensajes procesados

QUE INCLUIR SIEMPRE:
- Hechos clave mencionados por el usuario (numeros, datos del negocio, decisiones)
- Preguntas hechas y respuestas dadas (resumidas)
- Preferencias del usuario detectadas (tono, nivel de detalle, temas de interes)
- Datos del negocio mencionados que aun no esten en la base interna
- Pendientes o seguimientos prometidos

QUE EXCLUIR:
- Saludos, cortesias, filler
- Razonamiento interno de los agentes
- Datos que ya estan en las bases de datos (no duplicar)
- Detalles de implementacion tecnica

FORMATO:
Maximo 500 tokens por resumen. Si el resumen anterior es largo, comprimir manteniendo lo mas reciente con mas detalle.
```

### Tool Definitions

```json
[
  {
    "name": "generate_merge_summary",
    "description": "Genera un resumen incremental que fusiona el resumen previo con los mensajes recientes. El output reemplaza al resumen anterior. Usa esto cada 5-10 mensajes o al finalizar una conversacion. El resumen se guarda en memory.sqlite tabla summaries y se usa como contexto para futuras conversaciones.",
    "input_schema": {
      "type": "object",
      "properties": {
        "previous_summary": {
          "type": "string",
          "description": "Resumen acumulado anterior (vacio si es la primera vez)"
        },
        "new_messages": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "role": { "type": "string", "enum": ["user", "assistant"] },
              "content": { "type": "string" },
              "timestamp": { "type": "string" }
            },
            "required": ["role", "content"],
            "additionalProperties": false
          },
          "description": "Mensajes nuevos desde el ultimo resumen"
        },
        "summary_text": {
          "type": "string",
          "description": "El resumen fusionado generado (max 500 tokens)"
        },
        "key_facts_extracted": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Hechos clave nuevos extraidos de esta ronda de mensajes"
        },
        "pending_followups": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Seguimientos o promesas pendientes (ej: 'Angela prometio analizar los datos del Q1')"
        }
      },
      "required": ["new_messages", "summary_text", "key_facts_extracted"],
      "additionalProperties": false
    },
    "strict": true
  }
]
```

---

## 10. Flujo Completo E2E — Ejemplo: "A que credito puedo aplicar?"

```
USUARIO: "Quiero saber a que credito puedo aplicar para comprar un elevador hidraulico"

PASO 1 — CLASIFICADOR (Haiku, ~200ms)
├─ Input: mensaje + resumen conversacion + perfil empresa
├─ Output: {
│    category: "COMPLEJA",
│    topics: ["finanzas", "economia", "creditos"],
│    summary: "El usuario quiere evaluar opciones de credito para inversion en maquinaria"
│  }
└─ Derivar al Orquestador

PASO 2 — ORQUESTADOR: EXPANSION (Opus, ~1s)
├─ Entender: "Necesita: opciones de credito + pre-calificacion + capacidad de repago + estrategia"
├─ expand_query → {
│    finance_questions: [
│      "Cual es la liquidez actual (saldo de caja + cuentas por cobrar)?",
│      "Cual es el flujo de caja neto promedio de los ultimos 6 meses?",
│      "Hay deudas vigentes o compromisos financieros que limiten la capacidad de repago?",
│      "Cual es el health score actual de la empresa?"
│    ],
│    economy_questions: [
│      "Que creditos de tipo 'inversion' o 'maquinaria' estan disponibles actualmente?",
│      "Cual es el perfil crediticio BCRA de esta empresa (CUIT: 20-12345678-9)?",
│      "Cuales son las tasas de referencia BCRA y la inflacion actual?",
│      "Hay programas de subsidio o lineas PyME con tasa bonificada vigentes?"
│    ],
│    research_needed: true,
│    research_tasks: [
│      "Verificar que datos de creditos en external.sqlite estan actualizados (< 48h)",
│      "Si estan viejos, consultar BCRA Transparencia para creditos PyME actualizados"
│    ]
│  }
└─ Despachar agentes en paralelo

PASO 3 — EJECUCION PARALELA (asyncio, ~2-3s)
│
├─ AGENTE FINANZAS (Opus)
│  ├─ query_financials(months_back=6, metrics=[cash_balance, net_cash_flow, accounts_receivable])
│  ├─ query_indicators(period="latest", indicators=[health_score, current_ratio, debt_to_equity])
│  ├─ query_clients(filter="overdue")
│  └─ Respuesta: {
│       "liquidez_actual": "$1.8M",
│       "flujo_neto_promedio": "$420K/mes",
│       "health_score": 72,
│       "deudas_pendientes": "$340K (Gutierrez, 47 dias)",
│       "capacidad_repago_mensual": "$280K (con compromisos actuales)",
│       "riesgo": "Liquidez ajustada si toma cuota > $250K/mes",
│       "confidence": 0.88
│     }
│
├─ AGENTE ECONOMIA (Opus)
│  ├─ query_credit_profile(cuit="20-12345678-9")
│  ├─ query_available_credits(credit_type="maquinaria")
│  ├─ query_macro_indicators(indicators=["tasa_referencia", "inflacion_mensual"])
│  ├─ rank_credits_for_company(purpose="maquinaria", top_n=5)
│  └─ Respuesta: {
│       "perfil_bcra": "Situacion 1, sin irregularidades",
│       "creditos_disponibles": [
│         { "banco": "Provincia", "tasa": "33% TNA", "max": "$5M", "plazo": "36 meses", "cuota_est": "$210K" },
│         { "banco": "Galicia", "tasa": "38% TNA", "max": "$8M", "plazo": "48 meses", "cuota_est": "$260K" },
│         { "banco": "BICE", "tasa": "28% TNA (bonificada)", "max": "$10M", "plazo": "60 meses", "cuota_est": "$180K" }
│       ],
│       "tasa_referencia_bcra": "40% TNA",
│       "inflacion_mensual": "3.2%",
│       "confidence": 0.91
│     }
│
└─ AGENTE INVESTIGADOR (Sonnet, solo si datos viejos)
   ├─ check_data_freshness(table="available_credits")
   ├─ bcra_transparency_api(product_type="prestamos_prendarios") [si datos > 48h]
   ├─ web_search("creditos PyME maquinaria Argentina 2026", topic="finance", max_results=5)
   └─ save_to_external_db(table="available_credits", data={...})

PASO 4 — ORQUESTADOR: MESH (Opus, ~1s)
├─ mesh_responses → {
│    cross_insights: [
│      "Con BICE a $180K/mes cuota, la empresa tiene margen de $100K/mes sobre capacidad de repago",
│      "Si cobra los $340K de Gutierrez, la liquidez sube a $2.14M y habilita incluso Galicia",
│      "El credito Provincia es viable AHORA sin cambios. BICE es la mejor opcion pero requiere tramite MiPyME"
│    ],
│    contradictions: [],
│    unified_recommendation: "Aplica a 3 creditos. Recomendacion: BICE (mejor tasa), con Provincia como plan B inmediato.",
│    confidence_overall: 0.87,
│    needs_second_pass: false
│  }
└─ Generar respuesta unificada

PASO 5 — VALIDADOR (Sonnet, ~500ms)
├─ Input: pregunta original + respuesta propuesta
├─ validate_response → {
│    decision: "APPROVED",
│    relevance_score: 0.95,
│    completeness_score: 0.90,
│    actionability_score: 0.92,
│    clarity_score: 0.85,
│    has_concrete_data: true
│  }
└─ Entregar al usuario

PASO 6 — RESPUESTA AL USUARIO
├─ "Aplicas para 3 creditos. Te recomiendo el BICE al 28% TNA..."
├─ Tabla comparativa de creditos con scores
├─ Estrategia de optimizacion (cobrar a Gutierrez para ampliar opciones)
└─ Carpeta crediticia auto-generada (preview)

PASO 7 — EN PARALELO: MERGE SUMMARY (Haiku)
└─ Actualiza memory.sqlite con resumen de esta conversacion
```

---

## 11. Implementacion Python — Estructura de Archivos

```
polpilot/
  backend/
    main.py                      ← FastAPI app, endpoints, SSE streaming
    config.py                    ← API keys, model selection, thresholds
    
    orchestrator/
      orchestrator.py            ← Logica del Orquestador (expand, dispatch, mesh)
      classifier.py              ← Agente Clasificador
      validator.py               ← Agente Validador Stop-Loss
    
    agents/
      base_agent.py              ← Clase base: agentic loop con Claude tool-use
      finance_agent.py           ← Agente Finanzas + sus tools
      economy_agent.py           ← Agente Economia + sus tools
      research_agent.py          ← Agente Investigador + sus tools
      summary_agent.py           ← Agente Resumen (merge summaries)
    
    tools/
      internal_db_tools.py       ← Implementacion real de query_financials, query_clients, etc.
      external_db_tools.py       ← Implementacion real de query_credits, query_macro, etc.
      vector_tools.py            ← Implementacion real de semantic_search
      web_tools.py               ← Implementacion real de web_search, fetch_url
      bcra_tools.py              ← Implementacion real de APIs BCRA
      calculation_tools.py       ← Implementacion real de calculate_repayment, rank_credits
    
    data/
      db.py                      ← Conexiones SQLite, helpers, FTS5
      vector_store.py            ← ChromaDB wrapper
      data_service.py            ← Ingesta, normalizacion, embeddings
    
    seed/
      seed_database.py
      seed_*.json                ← 7 archivos de datos demo
  
  frontend/
    index.html
    styles.css
    app.js
```

### Patron base_agent.py (Agentic Loop)

```python
"""
Patron base para todos los agentes de PolPilot.
Implementa el agentic loop de Claude tool-use:
1. Enviar mensaje + tools al modelo
2. Si el modelo quiere usar un tool, ejecutarlo
3. Enviar el resultado del tool de vuelta
4. Repetir hasta que el modelo responda sin tool calls
"""

import anthropic
from typing import Any

class BaseAgent:
    def __init__(self, name: str, model: str, system_prompt: str, tools: list[dict]):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools
        self.client = anthropic.Anthropic()
        self.tool_handlers: dict[str, callable] = {}

    def register_tool(self, name: str, handler: callable):
        self.tool_handlers[name] = handler

    async def run(self, messages: list[dict], max_rounds: int = 10) -> dict:
        current_messages = messages.copy()

        for _ in range(max_rounds):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                tools=self.tools,
                messages=current_messages,
            )

            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

                current_messages.append({"role": "assistant", "content": response.content})
                current_messages.append({"role": "user", "content": tool_results})

        return {"error": "Max rounds exceeded", "agent": self.name}

    async def _execute_tool(self, name: str, inputs: dict) -> Any:
        handler = self.tool_handlers.get(name)
        if not handler:
            return f"Error: tool '{name}' not registered"
        return await handler(**inputs)

    def _extract_text(self, response) -> dict:
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        return {"agent": self.name, "response": text}
```

---

## 12. Capacidades por Agente (Matriz de Skills)

```
┌──────────────┬─────────┬──────────┬──────────────┬───────────┬─────────┐
│ Skill        │Finanzas │Economia  │Investigador  │Validador  │Resumen  │
├──────────────┼─────────┼──────────┼──────────────┼───────────┼─────────┤
│ SQL Read     │ ✅      │ ✅       │ ✅ (check)   │ ❌        │ ✅      │
│ SQL Write    │ ❌      │ ✅ (ext) │ ✅ (ext)     │ ❌        │ ✅ (mem)│
│ Vector Read  │ ✅      │ ✅       │ ❌           │ ❌        │ ❌      │
│ Vector Write │ ❌      │ ❌       │ ❌           │ ❌        │ ❌      │
│ Web Search   │ ❌      │ ❌       │ ✅           │ ❌        │ ❌      │
│ API BCRA     │ ❌      │ ❌       │ ✅           │ ❌        │ ❌      │
│ URL Fetch    │ ❌      │ ❌       │ ✅           │ ❌        │ ❌      │
│ Calculo      │ ✅      │ ✅       │ ❌           │ ❌        │ ❌      │
│ Validacion   │ ❌      │ ❌       │ ❌           │ ✅        │ ❌      │
│ Compresion   │ ❌      │ ❌       │ ❌           │ ❌        │ ✅      │
└──────────────┴─────────┴──────────┴──────────────┴───────────┴─────────┘

Nota: Vector Write lo hace el Data Service (no un agente).
```

---

## 13. Skills de skills.sh Recomendadas para Integracion

| Skill (skills.sh) | Repositorio | Uso en PolPilot |
|---|---|---|
| **financial-analysis-agent** | qodex-ai/ai-agent-skills | Base para skills de Agente Finanzas: ratios, risk assessment, health score |
| **web-research** | smithery/ai | Metodologia del Agente Investigador: plan → buscar → sintetizar |
| **web-search-tavily** | jwynia/agent-skills | Implementacion de web_search tool con Tavily API |
| **yahoo-finance** | 0juano/agent-skills | Datos de mercado en tiempo real (opcional, post-hackathon) |
| **stock-research-executor** | liangdabiao/claude-code-stock-deep-research-agent | Patron multi-fase de research con quality ratings |

### Instalacion

```bash
npx skills add https://github.com/qodex-ai/ai-agent-skills --skill financial-analysis-agent
npx skills add https://github.com/smithery/ai --skill web-research
npx skills add https://github.com/jwynia/agent-skills --skill web-search-tavily
```

---

## 14. Patrones de Comunicacion Inter-Agente

### 14.1 Patron: Orquestador → Agente (Dispatch)

```json
{
  "execution_id": "exec_001",
  "from": "orchestrator",
  "to": "finance",
  "type": "task_dispatch",
  "questions": [
    "Cual es la liquidez actual?",
    "Hay deudas que limiten capacidad de repago?"
  ],
  "context": {
    "company_id": "empresa_demo",
    "conversation_summary": "El usuario quiere evaluar creditos para maquinaria"
  },
  "deadline_ms": 5000
}
```

### 14.2 Patron: Agente → Orquestador (Response)

```json
{
  "execution_id": "exec_001",
  "from": "finance",
  "to": "orchestrator",
  "type": "task_response",
  "findings": [
    { "fact": "Liquidez actual: $1.8M", "confidence": 0.95, "source": "financials_monthly" },
    { "fact": "Deuda pendiente: $340K (Gutierrez, 47 dias)", "confidence": 0.90, "source": "clients" }
  ],
  "analysis": "Capacidad de repago mensual estimada: $280K",
  "data_gaps": ["No hay datos de compromisos financieros a largo plazo"],
  "confidence": 0.88,
  "tokens_used": 1200,
  "latency_ms": 1800
}
```

### 14.3 Patron: Cross-Agent Request (via Orquestador)

Cuando el Orquestador necesita que Finanzas valide algo que Economia encontro:

```json
{
  "execution_id": "exec_001",
  "from": "orchestrator",
  "to": "finance",
  "type": "cross_validation",
  "context_from_economy": "El credito BICE requiere liquidez > $1.5M",
  "question": "La empresa tiene liquidez suficiente para este requisito? Considerar deudas pendientes."
}
```

---

## 15. Configuracion de Modelos y Costos

### Hackathon (creditos ilimitados)

| Agente | Modelo | Justificacion |
|--------|--------|---------------|
| Clasificador | claude-haiku-3-5 | Routing rapido, no necesita razonamiento profundo |
| Orquestador | claude-opus-4-6 | Maximo razonamiento para expansion y mesh |
| Finanzas | claude-opus-4-6 | Analisis financiero requiere precision |
| Economia | claude-opus-4-6 | Evaluacion de creditos requiere juicio complejo |
| Investigador | claude-sonnet-4-6 | Balance para web search y normalizacion |
| Validador | claude-sonnet-4-6 | Evaluacion de calidad, no necesita Opus |
| Resumen | claude-haiku-3-5 | Compresion de texto, tarea simple |

### Produccion (optimizacion de costos)

| Agente | Modelo | Justificacion |
|--------|--------|---------------|
| Clasificador | claude-haiku-3-5 | Sin cambio |
| Orquestador | claude-sonnet-4-6 | Reducir costo, Sonnet es suficiente para orchestration |
| Finanzas | claude-sonnet-4-6 | Con tools bien definidos, Sonnet alcanza |
| Economia | claude-sonnet-4-6 | Idem |
| Investigador | claude-haiku-3-5 | Solo busca y estructura, no razona |
| Validador | claude-haiku-3-5 | Evaluacion binaria, Haiku alcanza |
| Resumen | claude-haiku-3-5 | Sin cambio |

---

## 16. Guardrails y Limites

### Por Ejecucion

| Parametro | Limite | Razon |
|-----------|--------|-------|
| Iteraciones maximas | 3 | Evitar loops infinitos |
| Agentes simultaneos | 4 | Paralelismo controlado |
| Cross-calls inter-agente | 4 | Evitar complejidad explosiva |
| Latencia maxima (compleja) | 7 segundos | UX aceptable |
| Latencia target (simple) | 2.5 segundos | UX optima |
| Web searches por investigacion | 5 | Costo y latencia |
| Rondas de validacion | 1 | Evitar ping-pong infinito |

### Por Agente

| Agente | Max tokens input | Max tokens output | Timeout |
|--------|-----------------|------------------|---------|
| Clasificador | 2K | 500 | 1s |
| Orquestador | 8K | 2K | 3s |
| Finanzas | 6K | 2K | 5s |
| Economia | 6K | 2K | 5s |
| Investigador | 4K | 1K | 10s (web) |
| Validador | 4K | 1K | 2s |
| Resumen | 4K | 500 | 2s |

---

## 17. Retroalimentacion y Aprendizaje

### 17.1 Feedback Loop del Usuario

Cada respuesta incluye opcion de feedback:
- 👍 Util → Se registra en query_log con `validation_passed: true`
- 👎 No util → Se registra con `validation_passed: false` + razon opcional

### 17.2 Auto-mejora del Investigador

El Agente Investigador aprende que fuentes son mas confiables:
- Si datos de una fuente se confirman repetidamente → subir source_score
- Si datos de una fuente se contradicen → bajar source_score
- Priorizar fuentes con score alto en busquedas futuras

### 17.3 Contexto Incremental

Cada interaccion alimenta:
1. **memory.sqlite** — Merge summaries acumulados (el cerebro "recuerda")
2. **external.sqlite** — Datos investigados persistidos (no se re-buscan)
3. **vectors/** — Embeddings actualizados (busqueda semantica mejora)
4. **query_log** — Historial de que funciono y que no (para optimizar expansion)

Este ciclo es el nucleo del "contexto incremental permanente": el cerebro SOLO mejora con el uso.

---

## 18. Dependencias Python

```
anthropic>=0.40.0          # Claude API (tool-use, streaming)
fastapi>=0.115.0           # API Gateway
uvicorn>=0.30.0            # ASGI server
chromadb>=0.5.0            # Vector store
sqlite-utils>=3.37         # SQLite helpers
httpx>=0.27.0              # Async HTTP (APIs BCRA, web)
tavily-python>=0.5.0       # Web search optimizado para AI
pydantic>=2.9.0            # Validacion de datos
python-multipart>=0.0.9    # File uploads
```

### Instalacion

```bash
pip install anthropic fastapi uvicorn chromadb sqlite-utils httpx tavily-python pydantic python-multipart
```

---

## 19. Checklist de Implementacion Hackathon

| # | Tarea | Prioridad | Tiempo Est. |
|---|-------|-----------|-------------|
| 1 | `base_agent.py` — Agentic loop generico con tool-use | CRITICA | 30 min |
| 2 | `classifier.py` — Intent routing | CRITICA | 20 min |
| 3 | `internal_db_tools.py` — SQLite queries internos | CRITICA | 45 min |
| 4 | `external_db_tools.py` — SQLite queries externos | CRITICA | 45 min |
| 5 | `finance_agent.py` — Instanciar con tools | CRITICA | 30 min |
| 6 | `economy_agent.py` — Instanciar con tools | CRITICA | 30 min |
| 7 | `orchestrator.py` — Expand + dispatch + mesh | CRITICA | 60 min |
| 8 | `bcra_tools.py` — APIs BCRA reales | ALTA | 45 min |
| 9 | `web_tools.py` — Tavily search | ALTA | 20 min |
| 10 | `research_agent.py` — Instanciar con tools | ALTA | 30 min |
| 11 | `validator.py` — Stop-loss | MEDIA | 20 min |
| 12 | `vector_tools.py` — ChromaDB search | MEDIA | 30 min |
| 13 | `summary_agent.py` — Merge summaries | BAJA | 20 min |
| 14 | `main.py` — FastAPI endpoints + SSE | CRITICA | 45 min |
| 15 | Seed data + `seed_database.py` | CRITICA | 30 min |

**Total estimado: ~8 horas de desarrollo puro.**

---

## 20. Referencias

- **Anthropic Tool Use Docs**: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use
- **Anthropic Multi-Agent Guide**: https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them
- **Anthropic Financial Services Agents**: https://www.claude.com/blog/building-ai-agents-in-financial-services
- **CreditXAI (Multi-Agent Credit Rating)**: https://arxiv.org/abs/2510.22222
- **MASCA (LLM Credit Assessment)**: https://openreview.net/forum?id=qb8fYCYUl2
- **skills.sh Financial Analysis Agent**: https://skills.sh/qodex-ai/ai-agent-skills/financial-analysis-agent
- **skills.sh Web Research Skill**: https://skills.sh/smithery/ai/web-research
- **BCRA APIs**: https://www.bcra.gob.ar/BCRAyVos/catalogo-de-APIs-banco-central.asp
- **bcra-connector (Python)**: https://github.com/PPeitsch/bcra-connector
- **Tavily AI Search**: https://docs.tavily.com/documentation/integrations/anthropic
