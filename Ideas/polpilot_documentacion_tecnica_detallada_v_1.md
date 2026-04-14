# PolPilot — Documentación Técnica Detallada
## Motor de Orquestación Cognitiva Multiagente con Expansión Controlada

> **Objetivo del documento**  
> Definir con profundidad la arquitectura lógica, los componentes, los algoritmos de decisión y especialmente la mecánica del **stop-loss cognitivo**, para transformar PolPilot en un sistema de razonamiento ejecutivo multiagente robusto, escalable y medible.

---

# 1. Visión técnica del sistema

La evolución propuesta convierte a PolPilot en un **motor de resolución de problemas empresariales complejos**, capaz de:

1. interpretar el input multimodal del usuario
2. decidir si requiere expansión analítica
3. descomponer el problema en tópicos
4. asignar agentes especialistas
5. permitir colaboración inter-agente
6. sintetizar resultados parciales
7. iterar solo si existe valor incremental
8. detener la expansión antes de introducir sesgo

La diferencia clave no está solo en tener múltiples agentes, sino en poseer una **capa metacognitiva que decide cuándo seguir pensando y cuándo responder**.

---

# 2. Arquitectura por capas

## 2.1 Input Layer
Responsable de normalizar:
- texto
- audio
- imágenes
- documentos
- continuación conversacional

### Salida esperada
```json
{
  "problem_statement": "texto normalizado",
  "input_type": "text|audio|image|contextual",
  "confidence": 0.94,
  "conversation_link": true
}
```

---

## 2.2 Dummy Analyzer
Primera capa de decisión.

### Objetivo
Evitar costo innecesario.

### Decisiones
- ¿es follow-up?
- ¿puede responderse con contexto previo?
- ¿es pregunta simple?
- ¿requiere razonamiento multi-dimensional?

### Output
```json
{
  "requires_expansion": true,
  "reason": "multi_domain_decision",
  "complexity_score": 0.81
}
```

---

## 2.3 Topic Analyzer
Descompone el problema en dominios.

## Funciones
- topic extraction
- question expansion
- agent mapping
- dependency hints
- domain confidence

### Ejemplo
Problema:
> Quiero importar pollo

Topics:
- legal
- cashflow
- logistics
- brand-fit
- demand forecast

---

## 2.4 Gateway / Orchestrator
Es la capa más crítica del runtime.

### Responsabilidades
- crear ejecución paralela
- resolver dependencias
- manejar timeouts
- coordinar colaboración
- versionar iteraciones
- guardar trazabilidad
- controlar presupuesto computacional

### Estructura sugerida
```json
{
  "iteration": 2,
  "threads": 4,
  "dependencies": [
    ["legal", "finance"]
  ],
  "budget_tokens": 12000,
  "latency_limit_ms": 3000
}
```

---

# 3. Ciclo iterativo de razonamiento

## Fase A — Resolución primaria
Cada agente responde su tópico.

## Fase B — Síntesis global
El sintetizador responde:
- ¿la pregunta principal ya está resuelta?
- ¿faltan vacíos críticos?
- ¿existe contradicción entre agentes?
- ¿hace falta colaboración cruzada?

## Fase C — Re-expansión
Solo si el valor incremental supera threshold.

---

# 4. Stop-loss cognitivo (núcleo diferencial)

Este es el componente más importante de la arquitectura.

## 4.1 Problema que resuelve
Sin control, un sistema recursivo puede:
- sobrepreguntar
- sobredimensionar edge cases
- desviarse del objetivo inicial
- consumir costo innecesario
- introducir sesgo por hiperprofundización

El stop-loss evita exactamente eso.

---

## 4.2 Definición formal

El sistema solo puede seguir iterando si:

### Regla 1 — Relevancia semántica
La nueva pregunta mantiene alta similitud con el problema original.

```text
semantic_similarity(new_question, root_problem) > threshold
```

Threshold inicial sugerido:
```text
0.82
```

---

### Regla 2 — Valor incremental
La nueva iteración debe aumentar cobertura de decisión.

```text
decision_coverage_gain > min_gain
```

Ejemplo:
```text
+15% nueva información útil
```

---

### Regla 3 — No redundancia
No repetir preguntas equivalentes.

```text
novelty_score > redundancy_floor
```

---

### Regla 4 — Budget guardrail
No superar costo máximo.

Métricas:
- tokens
- tiempo
- llamadas externas
- número de agentes
- iteraciones

---

## 4.3 Fórmula recomendada

```text
StopLossScore =
(
  relevance * 0.35 +
  novelty * 0.25 +
  decision_gain * 0.25 +
  contradiction_resolution * 0.15
)
-
(
  drift_risk * 0.40 +
  redundancy * 0.20 +
  token_cost * 0.20 +
  latency_cost * 0.20
)
```

### Decisión
```text
if StopLossScore < 0.18 => STOP
else => CONTINUE
```

---

## 4.4 Señales de drift (sesgo)

El sistema debe detectar drift cuando:
- el nuevo tópico no afecta la decisión final
- la pregunta deriva en curiosidad no accionable
- la expansión se aleja del KPI original
- aparecen ramas demasiado específicas
- múltiples agentes empiezan a discutir subcasos irrelevantes

---

# 5. Colaboración inter-agente

Nueva capacidad clave.

## Caso
Agente legal necesita presupuesto para validar viabilidad regulatoria.

### Flujo
1. legal genera support request
2. gateway detecta dependencia finance
3. finance responde solo contexto faltante
4. legal refina
5. sintetizador vuelve a evaluar

## Payload sugerido
```json
{
  "from": "legal",
  "to": "finance",
  "request_type": "context_support",
  "question": "¿hay caja para permisos + cadena de frío?",
  "priority": "high"
}
```

---

# 6. Preguntas abiertas para diseño

Estas son las preguntas que recomiendo resolver ahora para robustecer el proyecto:

## A. Límite de iteraciones
- ¿máximo 3?
- ¿adaptativo según complejidad?

## B. Métrica de utilidad
- ¿cómo medimos decision_gain?
- ¿coverage por dimensión?
- ¿score por impacto financiero?

## C. Colaboración entre agentes
- ¿pueden hablar peer-to-peer?
- ¿solo vía gateway?
- ¿sync o async?

## D. Persistencia
- ¿guardamos reasoning tree?
- ¿sirve como memoria futura?

## E. Explainability
- ¿el usuario verá reasoning trace?
- ¿solo insight final?

---

# 7. Ideas estratégicas para mejorar

## Idea 1 — Adaptive stop-loss
El threshold cambia según tipo de problema:
- financiero → más profundidad
- operativo → menor profundidad
- legal → alta precisión + menor drift

## Idea 2 — Agent trust score
Cada agente acumula reputación.

Si finanzas históricamente aporta alto gain, el gateway puede priorizarlo.

## Idea 3 — Contradiction resolver
Nuevo agente dedicado a detectar contradicciones entre outputs.

## Idea 4 — Decision confidence
La respuesta final debería incluir:
- confidence
- domains covered
- unresolved risks
- assumptions

---

# 8. Preguntas para definir contigo

Quiero dejar estas preguntas abiertas porque van a determinar la arquitectura final:

1. ¿Quieres que el stop-loss sea **global** o por cada tópico?
2. ¿La colaboración entre agentes debe poder encadenarse en múltiples saltos?
3. ¿Quieres guardar el árbol de reasoning para reutilizarlo con problemas futuros similares?
4. ¿La salida final debe priorizar **acción concreta** o **explicabilidad del razonamiento**?
5. ¿Quieres que cada agente tenga memoria propia además de la memoria global?

---

# 9. Posicionamiento técnico final

> **Recursive Executive Intelligence Engine**  
> Motor multiagente que descompone problemas empresariales, coordina especialistas, optimiza profundidad mediante stop-loss cognitivo y entrega decisiones accionables con costo controlado.

