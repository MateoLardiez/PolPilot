# PolPilot v2 - Diseno Tecnico Formal del Sistema Interagente

## 0. Proposito y alcance

Este documento define, de forma formal y ejecutable, la evolucion de PolPilot desde un esquema de agentes aislados hacia un **sistema interagente orquestado**.  
El foco no es comercial ni de posicionamiento, sino de arquitectura, modelo matematico y plan de implementacion.

El objetivo tecnico es implementar un motor que:

1. descomponga un problema empresarial en topicos especializados,
2. active solo los agentes con valor marginal esperado positivo,
3. coordine colaboracion interagente por contratos estructurados,
4. detenga la expansion cuando deja de aportar utilidad neta,
5. entregue respuesta accionable con trazabilidad y costo acotado.

## 1. Delta de arquitectura: que es nuevo y por que

La innovacion no es "tener varios agentes", sino pasar de una arquitectura de respuesta directa a una arquitectura de **resolucion iterativa controlada**.

### 1.1 Antes (modelo no deseado para v2)

- Agente unico o multiagente sin supervision estricta.
- Alto acoplamiento entre razonamiento y memoria conversacional.
- Ausencia de criterio formal para detener expansion.
- Baja auditabilidad de por que se decidio continuar o detener.

### 1.2 Ahora (modelo objetivo v2)

- Dummy Analyzer como filtro economico inicial.
- Topic Analyzer para descomposicion y mapeo de dominios.
- Gateway/Orchestrator como autoridad unica de estado.
- Colaboracion interagente por artefactos, no chat libre.
- Stop-Loss cognitivo global y local por topico.
- Jerarquia de verdad en memoria para resolver contradicciones.
- Versionado fuerte de problema, contexto, topicos y artefactos.

## 2. Principios de diseno

1. **Control antes que espontaneidad**: en MVP, interacciones supervisadas por gateway.
2. **Utilidad por costo**: la funcion objetivo optimiza valor de decision con guardrails economicos.
3. **Aislamiento de contexto**: cada agente recibe vista minima necesaria.
4. **Artefactos tipados**: hechos, reclamos, riesgos y recomendaciones estructurados.
5. **Trazabilidad total**: cada decision debe ser reconstruible.
6. **Recursion limitada**: iterar solo si hay ganancia marginal medible.

## 3. Modelo formal del sistema

### 3.1 Definiciones

Sea:

- \(U\): input del usuario.
- \(C_t\): contexto activo en iteracion \(t\).
- \(M\): memoria total disponible.
- \(A=\{a_1,\dots,a_n\}\): catalogo de agentes.
- \(G\): gateway orquestador.
- \(S\): sintetizador.
- \(L\): motor stop-loss.
- \(P_0\): problema raiz normalizado.

Funcion total:

\[
\text{PolPilot}(U,C_0,M,A)\rightarrow R
\]

Respuesta final:

\[
R=\{\text{decision},\text{acciones},\text{riesgos},\text{supuestos},\text{confianza},\text{traza}\}
\]

### 3.2 Descomposicion iterativa

En iteracion \(t\):

\[
P_t \rightarrow \{p_{t1},p_{t2},...,p_{tk}\}
\]

Asignacion:

\[
\text{assign}(p_{ti})=a_j
\]

Produccion de artefacto:

\[
o_{ti}=\text{solve}(a_j,p_{ti},K_t^j)
\]

Sintesis de iteracion:

\[
Y_t=S(\{o_{t1},...,o_{tk}\},P_0)
\]

Regla de continuidad:

\[
\text{continue}_t=L(P_0,Y_t,\Delta Cost_t,\Delta Utility_t,Drift_t)
\]

Si `continue_t=false`, finalizar y responder.  
Si `continue_t=true`, generar \(t+1\).

## 4. Funcion objetivo y restricciones

### 4.1 Objetivo principal

Unidad de optimizacion recomendada para MVP:

\[
\max J = \alpha U_d - \beta C_m - \gamma L_t + \delta R_u
\]

Donde:

- \(U_d\): utilidad de decision.
- \(C_m\): costo monetario/tokens.
- \(L_t\): latencia total.
- \(R_u\): reusabilidad futura de artefactos/memoria.

Inicializacion sugerida:

- \(\alpha=0.45\)
- \(\beta=0.30\)
- \(\gamma=0.20\)
- \(\delta=0.05\)

### 4.2 Restricciones duras (guardrails)

Para una ejecucion \(e\):

- \(iter(e)\le 3\)
- \(agents(e)\le 4\)
- \(cross\_calls(e)\le 4\)
- \(latency(e)\le 7000ms\) en casos complejos
- \(latency\_target(e)\approx 2500ms\) en casos simples

Si cualquier restriccion dura se incumple, se fuerza cierre con sintesis parcial.

## 5. Modelo de costo computacional

### 5.1 Variables base

- \(T_{in}^{k,t}\): tokens de entrada en modelo \(k\), iteracion \(t\).
- \(T_{out}^{k,t}\): tokens de salida en modelo \(k\), iteracion \(t\).
- \(p_{in}^k,p_{out}^k\): precio por token en modelo \(k\).

Costo monetario:

\[
Cost=\sum_{t}\sum_k (p_{in}^kT_{in}^{k,t}+p_{out}^kT_{out}^{k,t})
\]

### 5.2 Costo por etapa

En cada iteracion:

\[
TokenCost_t = Base_t + Agent_t + Cross_t + Synth_t
\]

- `Base_t`: dummy + topic + control.
- `Agent_t`: suma de agentes activos.
- `Cross_t`: colaboracion interagente.
- `Synth_t`: sintesis + validacion.

### 5.3 Politica de modelos

- Dummy Analyzer: modelo low-cost y rapido.
- Topic Analyzer: modelo medio.
- Domain Agents: adaptativo por criticidad.
- Synthesizer: modelo robusto.
- Contradiction Resolver: medio/robusto segun severidad.

## 6. Pipeline logico de procesamiento

### 6.1 Etapa 1 - Ingesta y normalizacion

Convierte input multimodal a `NormalizedInput`.

### 6.2 Etapa 2 - Dummy Analyzer

Decide:

- follow-up resoluble con contexto,
- consulta simple sin expansion,
- consulta expandible multi-dominio.

### 6.3 Etapa 3 - Topic Analyzer

Produce:

- topicos,
- dependencias,
- estrategia de razonamiento,
- agentes candidatos,
- presupuesto inicial.

### 6.4 Etapa 4 - Context Builder

Construye \(K_t^j\), vista por agente:

\[
K_t^j=\text{filter}(C_t,M,domain_j,topic_j)
\]

### 6.5 Etapa 5 - Ejecucion de malla interagente

Fase A:

- corrida primaria paralela independiente por topico.

Fase B:

- colaboracion puntual via `support_request` solo donde hay dependencia.

### 6.6 Etapa 6 - Sintesis y contradicciones

El sintetizador:

- integra artefactos,
- mide cobertura y accionabilidad,
- detecta contradicciones materiales.

### 6.7 Etapa 7 - Stop-Loss

Evalua si se abre iteracion \(t+1\) o se cierra.

### 6.8 Etapa 8 - Respuesta y memoria

- genera salida estructurada final,
- decide persistencia selectiva,
- actualiza trazas y ledger de costos.

## 7. Sistema interagente: protocolo y contratos

### 7.1 Regla de colaboracion

No se habilita chat libre entre agentes en MVP.  
Toda colaboracion circula por gateway.

### 7.2 Mensaje interagente (contrato minimo)

```json
{
  "message_id": "uuid",
  "execution_id": "exec_123",
  "iteration": 2,
  "from_agent": "legal",
  "to_agent": "finance",
  "message_type": "support_request",
  "priority": "high",
  "topic_id": "topic_legal_1",
  "problem_version": "p0.v3",
  "context_version": "ctx.v7",
  "payload": {
    "question": "validar capacidad de caja para permisos y cadena de frio"
  },
  "deadline_ms": 1200,
  "created_at": "2026-04-14T12:00:00Z"
}
```

Tipos recomendados:

- `support_request`
- `partial_answer`
- `contradiction_flag`
- `dependency_resolved`
- `context_update`
- `assumption_check`
- `fact_request`

### 7.3 Artefacto estructurado (unidad de conocimiento)

```json
{
  "artifact_id": "art_001",
  "execution_id": "exec_123",
  "source_agent": "legal",
  "artifact_type": "FACT",
  "content": "se requiere permiso sanitario previo",
  "confidence": 0.86,
  "truth_level": "inferred",
  "dependencies": ["art_0007"],
  "problem_version": "p0.v3",
  "context_version": "ctx.v7",
  "metadata": {
    "tokens_in": 420,
    "tokens_out": 170,
    "latency_ms": 980
  }
}
```

### 7.4 Por que artefactos y no conversacion libre

- Menor costo en tokens.
- Menor riesgo de drift semantico.
- Mejor trazabilidad para auditoria.
- Control de versionado y dependencias.
- Deteccion de loops posible por grafo.

## 8. Grafo de dependencias y control de ciclos

Sea \(D=(V,E)\), con \(V\) topicos/tareas y \(E\) dependencias.

### 8.1 Regla de activacion de tareas

Una tarea \(t_i\) se ejecuta si su indegree actual es 0.

### 8.2 Actualizacion dinamica

Cuando llega un artefacto que resuelve dependencia:

- decrementar indegree de tareas dependientes,
- activar nuevas tareas desbloqueadas.

### 8.3 Deteccion de ciclo

Si al insertar arista \(u\rightarrow v\) se detecta ciclo:

- bloquear nueva dependencia,
- generar `contradiction_flag` o `dependency_cycle_flag`,
- escalar a sintetizador/arbitro.

Implementacion recomendada:

- Kahn para ejecucion por niveles.
- DFS/Tarjan para deteccion de ciclos dinamicos.

## 9. Stop-Loss cognitivo: definicion matematica

### 9.1 Variables positivas

- \(R_t\): relevancia con problema raiz.
- \(N_t\): novedad informativa.
- \(G_t\): gain de cobertura de decision.
- \(CR_t\): ganancia por resolver contradiccion.
- \(A_t\): incremento de accionabilidad.

### 9.2 Variables de penalizacion

- \(D_t\): drift semantico.
- \(Red_t\): redundancia.
- \(C_t\): costo normalizado.
- \(L_t\): latencia normalizada.
- \(B_t\): bloat de complejidad.

### 9.3 Funcion recomendada

\[
S_t=
(0.30R_t+0.20N_t+0.25G_t+0.15CR_t+0.10A_t)
-
(0.30D_t+0.20Red_t+0.20C_t+0.15L_t+0.15B_t)
\]

Decision:

- si \(S_t < \tau_{stop}\), `STOP`.
- si \(S_t \ge \tau_{stop}\), `CONTINUE` (si hay budget).

Valor inicial sugerido:

\[
\tau_{stop}=0.18
\]

### 9.4 Stop-Loss local por topico

Para topico \(q\):

\[
S_t^{(q)}=\eta_1G_t^{(q)}-\eta_2D_t^{(q)}-\eta_3C_t^{(q)}-\eta_4Red_t^{(q)}
\]

Si \(S_t^{(q)}<\tau_q\), se cierra el topico aunque el global continue.

### 9.5 Justificacion matematica

El sistema es un proceso de decision secuencial con costo de informacion.  
El stop-loss implementa una regla de parada aproximada del tipo optimal stopping:

\[
\text{continuar si } \mathbb{E}[\Delta Utility_{t+1}\mid \mathcal{I}_t] > \mathbb{E}[\Delta Cost_{t+1}\mid \mathcal{I}_t]
\]

La funcion \(S_t\) es una proxy operacional de esa desigualdad.

## 10. Activacion de agentes y poda de topicos

Para cada agente candidato \(a_j\):

\[
A_j=\lambda_1 Rel_j+\lambda_2 Gain_j-\lambda_3 Cost_j-\lambda_4 Red_j
\]

Regla:

- si \(A_j < \tau_{act}\), no activar.
- si \(A_j \ge \tau_{act}\), activar.

Valor inicial:

\[
\tau_{act}=0.20
\]

Poda de topicos:

- ordenar por utilidad marginal esperada,
- eliminar topicos de baja prioridad hasta cumplir budget.

## 11. Memoria, verdad y persistencia

### 11.1 Tipos de memoria

- `M_int`: integraciones estructuradas.
- `M_onb`: onboarding/perfil negocio.
- `M_conv`: conversacional observacional.
- `M_inf`: inferencias.
- `M_reason`: arboles de razonamiento intermedios.

### 11.2 Jerarquia de verdad

\[
M_{int} > M_{onb} > M_{conv} > M_{inf} > M_{reason}
\]

Razon:

- protege consistencia operacional,
- evita que inferencia temporal opaque dato duro.

### 11.3 Unidad de memoria

```json
{
  "memory_id": "mem_001",
  "user_id": "u_1",
  "scope": "business",
  "memory_type": "onboarding",
  "truth_level": "user_stated",
  "content": "operamos con cadena de frio tercerizada",
  "confidence": 0.79,
  "source": "onboarding_form",
  "version": 3,
  "created_at": "2026-04-14T12:00:00Z",
  "expires_at": null,
  "invalidation_rule": "if_erp_conflict_then_invalidate"
}
```

### 11.4 Regla de promocion a memoria persistente

\[
PersistScore=w_1RelFuture+w_2Stability+w_3Confidence-w_4ContamRisk
\]

Promover si:

\[
PersistScore>\tau_{persist}
\]

Valor inicial:

\[
\tau_{persist}=0.72
\]

### 11.5 Invalidacion

Invalidar cuando:

- entra fuente estructurada contradictoria,
- vence ventana semantica,
- supuesto base fue refutado,
- cae relevancia operativa.

## 12. Estado y versionado

### 12.1 Estado de ejecucion

```json
{
  "execution_id": "exec_123",
  "user_id": "u_1",
  "root_problem": "quiero importar pollo",
  "root_problem_version": "p0.v3",
  "current_iteration": 2,
  "status": "running",
  "active_topics": ["legal", "finance", "operations"],
  "pending_dependencies": ["dep_14"],
  "context_version": "ctx.v7",
  "budget_state": {
    "tokens_used": 8940,
    "tokens_max": 12000,
    "latency_ms": 3620,
    "max_latency_ms": 7000
  }
}
```

### 12.2 Politica de versiones

- Toda salida declara version de problema y contexto consumidos.
- Si cambia `root_problem_version`, artefactos viejos pasan a `stale` salvo compatibilidad explicita.
- No se mezcla sintesis nueva con artefactos stale sin reconciliacion.

## 13. Modelo de datos recomendado

Entidades nucleares:

1. `User`
2. `Session`
3. `Problem`
4. `Execution`
5. `Topic`
6. `Agent`
7. `AgentRun`
8. `InterAgentMessage`
9. `Artifact`
10. `MemoryUnit`
11. `BudgetLedger`
12. `StopLossDecision`
13. `Synthesis`
14. `Contradiction`

Campos minimos de alto impacto:

- `AgentRun`: `tokens_in`, `tokens_out`, `latency_ms`, `status`, `model`.
- `BudgetLedger`: costo acumulado por iteracion.
- `StopLossDecision`: score, threshold, decision, razones.

## 14. Diseño de runtime e infraestructura

### 14.1 Componentes de backend

- API/Entry service.
- Orchestrator service.
- Context service.
- Memory service.
- Agent workers por dominio.
- Synthesis + contradiction validator.
- Budget and observability service.
- Estado transaccional + store documental/vectorial.

### 14.2 Patron de ejecucion

- Sincrono para flujo simple.
- Asincrono/hibrido para flujo multiagente.

### 14.3 Cola y concurrencia

- Cola interna para `agent_run` y `support_request`.
- Timeout por agente y timeout global.
- Reintentos idempotentes en fallos transitorios.
- Fallback a sintesis parcial si expira SLA.

## 15. Algoritmo operativo (pseudocodigo)

```text
function execute_problem(input):
  ni = normalize(input)
  da = dummy_analyze(ni)

  if da.requires_expansion == false:
    return simple_response(ni)

  state = init_execution(ni)
  plan = topic_analyze(ni, state)
  while state.iteration < MAX_ITER and within_budget(state):
    tasks = select_topics_and_agents(plan, state)
    run_parallel(tasks)
    resolve_support_requests_via_gateway(state)
    synthesis = synthesize(state)
    score_g = stop_loss_global(state, synthesis)
    score_l = stop_loss_local_by_topic(state, synthesis)
    close_low_value_topics(score_l, state)
    if score_g < TAU_STOP:
      break
    plan = replan_critical_gaps(state, synthesis)
    state.iteration += 1

  final = build_final_response(state)
  persist_memory_selectively(final, state)
  return final
```

## 16. Respuesta final al usuario (contrato de salida)

```json
{
  "executive_answer": "no conviene avanzar sin resolver habilitacion sanitaria",
  "recommended_actions": [
    "validar costo de permisos y cadena de frio",
    "abrir piloto logistico limitado",
    "recalcular flujo de caja con escenario conservador"
  ],
  "confidence_score": 0.81,
  "assumptions": [
    "demanda mensual estimada de 4 toneladas",
    "sin subsidios extraordinarios"
  ],
  "unresolved_risks": [
    "variacion de costo de importacion",
    "incertidumbre regulatoria local"
  ],
  "domains_consulted": ["legal", "finance", "operations"],
  "stop_reason": "marginal_utility_below_threshold",
  "trace_summary": "2 iteraciones, 3 agentes, 1 colaboracion cruzada"
}
```

## 17. Observabilidad y evaluacion

### 17.1 Metricas minimas por ejecucion

- latencia total,
- latencia por agente,
- tokens input/output por agente,
- costo por iteracion,
- cantidad de iteraciones,
- cross-calls interagente,
- contradicciones detectadas,
- utilidad marginal por iteracion,
- motivo de stop.

### 17.2 Metricas de calidad del sistema

- `DecisionCoverage`: porcentaje de dimensiones del problema cubiertas.
- `Actionability`: porcentaje de recomendaciones ejecutables.
- `ContradictionRate`: contradicciones abiertas por respuesta.
- `StopPrecision`: porcentaje de stops correctos (ni temprano ni tarde).
- `CostPerUsefulDecision`: costo por respuesta aceptada como util.

### 17.3 Plan de evaluacion

1. Banco de casos con ground truth experto por dominio.
2. Pruebas A/B con y sin colaboracion interagente.
3. Pruebas A/B con y sin stop-loss local por topico.
4. Stress test con concurrencia alta.
5. Calibracion de thresholds \(\tau_{stop},\tau_{act},\tau_{persist}\).

## 18. Riesgos tecnicos y mitigaciones

### 18.1 Memoria contaminada

- Mitigar con jerarquia de verdad + invalidacion automatica.

### 18.2 Drift semantico

- Mitigar con contextos filtrados y score de drift explicito.

### 18.3 Loops de colaboracion

- Mitigar con DAG + bloqueo de ciclos + profundidad maxima.

### 18.4 Stop-loss mal calibrado

- Mitigar con datasets de calibracion y monitoreo de stop precision.

### 18.5 Sobre-costo en PyME

- Mitigar con dummy fuerte, poda agresiva, modelos por etapa y budget caps.

## 19. Plan de implementacion incremental

### Fase 1 - Fundaciones de control

- definir schemas de artefacto y mensaje,
- construir `ExecutionState` y `BudgetLedger`,
- implementar Dummy + Topic + Gateway base.

### Fase 2 - Malla interagente MVP

- activar agentes por dominio en paralelo,
- habilitar `support_request` via gateway,
- bloqueo de ciclos y versionado de contexto.

### Fase 3 - Stop-Loss y memoria formal

- incorporar score global/local,
- persistencia selectiva con `PersistScore`,
- invalidacion y reconciliacion de memoria.

### Fase 4 - Robustez productiva

- observabilidad completa,
- calibracion de thresholds,
- hardening de latencia, retries y fallback.

## 20. Decisiones abiertas que deben cerrarse

1. Nivel de explicabilidad visible al usuario final.
2. Politica de arbitraje cuando dos fuentes mismo nivel se contradicen.
3. Reutilizacion de reasoning tree entre problemas similares.
4. Politica de upgrade de modelo por criticidad de dominio.
5. Limite exacto de profundidad de colaboracion interagente.

## 21. Cierre tecnico

La arquitectura objetivo de PolPilot v2 no debe implementarse como "agentes conversando".  
Debe implementarse como un **sistema de decision interagente gobernado por estado, contratos, versionado y stop-loss matematico**.

La viabilidad real depende de cinco invariantes:

1. gateway con autoridad total de orquestacion,
2. artefactos estructurados tipados,
3. stop-loss global y local calibrado,
4. memoria con jerarquia de verdad,
5. observabilidad por agente e iteracion.

Si esas invariantes se sostienen, el sistema puede escalar con calidad, costo controlado y auditabilidad.  
Si se rompen, la arquitectura cae en sobre-costo, opacidad y drift.

