A continuación presento la especificación técnica formal de **PolPilot v2.0**. Este documento está diseñado para un perfil de analista de sistemas y arquitectura de IA, enfocándose en la transición de un modelo de "agente único" a un "ecosistema inter-agente de orquestación cognitiva".

---

# Especificación Técnica: PolPilot — Motor de Orquestación Cognitiva Multiagente (MOCM)

## 1. Resumen Ejecutivo de la Arquitectura
PolPilot evoluciona de ser una interfaz de chat con herramientas a un **Sistema de Razonamiento Ejecutivo Recursivo**. La premisa fundamental es que un solo LLM, por potente que sea, sufre de degradación de atención en contextos largos y sesgos de confirmación en razonamientos complejos. 

La solución propuesta implementa una **Malla de Agentes Especialistas** coordinados por un **Gateway Orquestador**, donde la expansión del razonamiento está gobernada por un **Stop-Loss Cognitivo** matemático que optimiza la relación entre utilidad de la decisión y costo computacional.

---

## 2. Formalización del Modelo Inter-Agente

### 2.1. De la Conversación a la Transacción de Artefactos
A diferencia de los sistemas multiagente convencionales donde los agentes "chatean" entre sí (lo que genera *drift* semántico y consumo excesivo de tokens), PolPilot utiliza un modelo de **Intercambio de Artefactos Estructurados**.

**Definición de Artefacto ($\mathcal{A}$):**
Un artefacto es un objeto JSON inmutable que representa una unidad de conocimiento validada.
$$\mathcal{A} = \{ID_{type}, \Phi_{payload}, \sigma_{confidence}, \Delta_{deps}\}$$
Donde:
*   $ID_{type}$: Clasificación (FACT, CLAIM, RISK, RECOMMENDATION, REQUEST).
*   $\Phi_{payload}$: El contenido técnico o ejecutivo.
*   $\sigma_{confidence}$: Score probabilístico de veracidad (0-1).
*   $\Delta_{deps}$: Grafo de dependencias de otros artefactos previos.

### 2.2. El Rol del Gateway Orquestador
El Gateway no es un simple router; es el administrador del **Estado de Ejecución Global**. Supervisa la concurrencia y resuelve el **Grafo de Dependencias (DAG)**.
*   **Aislamiento de Contexto:** Cada agente recibe únicamente la vista filtrada del contexto necesaria para su tarea, evitando la "contaminación de ruido".
*   **Detección de Ciclos:** El Gateway impide que el Agente A dependa del Agente B y este a su vez del A, rompiendo bucles de razonamiento infinitos.

---

## 3. Dinámica del Procesamiento y Stop-Loss

### 3.1. El "Pesado" de Procesamiento
El peso computacional ($W$) de una consulta en PolPilot se define como:
$$W = \sum_{i=1}^{n} (A_i \times I_i \times C_i)$$
Donde $A$ es la amplitud (número de agentes), $I$ es la profundidad (iteraciones) y $C$ es la densidad de contexto. PolPilot busca minimizar $W$ sin degradar la calidad de la respuesta final.

### 3.2. Stop-Loss Cognitivo (Mecánica de Control)
Este es el núcleo diferencial. El sistema evalúa tras cada iteración si existe un **Valor Incremental** suficiente para continuar.

**Ecuación de Utilidad Marginal ($U_m$):**
$$U_m = \left( \omega_1 R + \omega_2 N + \omega_3 G \right) - \left( \omega_4 D + \omega_5 K \right)$$

Variables y Coeficientes Sugeridos:
*   **$R$ (Relevancia):** Similitud semántica con el problema raíz ($\omega_1 = 0.35$).
*   **$N$ (Novedad):** Información no presente en la memoria de trabajo ($\omega_2 = 0.25$).
*   **$G$ (Ganancia de Decisión):** Capacidad de reducir la incertidumbre en un KPI ($\omega_3 = 0.25$).
*   **$D$ (Drift/Deriva):** Desviación del objetivo original ($\omega_4 = 0.40$).
*   **$K$ (Costo):** Penalización por consumo de tokens y latencia ($\omega_5 = 0.20$).

**Regla de Decisión:**
$$\text{Si } U_m < \tau \implies \text{STOP y Sintetizar}$$
Donde $\tau$ (threshold) es típicamente $0.18$. Este valor previene que el sistema entre en "parálisis por análisis".

---

## 4. Estrategia de Memoria y Verdad Canonica

El sistema inter-agente requiere una jerarquía de verdad para resolver conflictos cuando dos agentes discrepan.

### 4.1. Niveles de Persistencia y Verdad
1.  **Nivel 1 (Hard-Data):** Datos estructurados (integraciones con ERP/CRM). Verdad absoluta.
2.  **Nivel 2 (Onboarding):** Reglas de negocio definidas por el usuario. Prioridad alta.
3.  **Nivel 3 (Conversacional):** Lo que el usuario dijo en la sesión actual. Prioridad media.
4.  **Nivel 4 (Inferencial):** Deducciones de los agentes. Verdad temporal/hipotética.

### 4.2. Resolución de Contradicciones
Cuando el **Contradiction Resolver** detecta que el Agente Legal y el Agente de Finanzas han emitido artefactos opuestos, el Gateway:
1.  Identifica el nivel de verdad de cada fuente.
2.  Si son del mismo nivel, activa una **Iteración de Arbitraje** con un tercer agente con capacidad de razonamiento superior (ej. modelo o1).

---

## 5. Flujo de Implementación Técnica (Pipeline)

### Paso 1: Deconstrucción (Topic Analysis)
El input se descompone en un grafo de tareas.
*   *Input:* "Quiero exportar carne a China".
*   *Output:* Tópicos [Sanitario, Arancelario, Logístico, Financiero].

### Paso 2: Orquestación en Malla
El Gateway despacha los artefactos de contexto a los agentes. Los agentes pueden emitir un `SUPPORT_REQUEST`.
*   *Ejemplo:* El Agente Logístico solicita al Agente Financiero el "Presupuesto de cadena de frío".

### Paso 3: Síntesis Cognitiva
El sintetizador no resume texto; **ensambla decisiones**.
1.  Recolecta artefactos finalizados.
2.  Verifica cobertura de los tópicos iniciales.
3.  Genera el `Action Plan` final.

---

## 6. Detalles Matemáticos de la Colaboración Inter-Agente

Para evitar que la colaboración degrade la latencia, implementamos un modelo de **Concurrencia con Bloqueos de Dependencia**.

Sea $T = \{t_1, t_2, \dots, t_n\}$ el conjunto de tareas.
Definimos una matriz de adyacencia de dependencias $D$, donde $D_{ij} = 1$ si $t_i$ requiere un artefacto de $t_j$.

*   **Ejecución:** El Gateway lanza todas las tareas $t_i$ donde $\sum D_{ij} = 0$.
*   **Callback:** Al completar $t_j$, se actualiza la matriz $D$. Las tareas que queden con dependencia cero se activan en la siguiente micro-ronda.

---

## 7. Justificación del Diseño (Por qué este camino)

1.  **Escalabilidad Económica:** Al usar un **Dummy Analyzer** al inicio, evitamos gastar tokens en preguntas simples. El costo escala solo con la complejidad real.
2.  **Auditabilidad (Traceability):** Al usar artefactos JSON en lugar de texto libre, podemos generar un "Árbol de Razonamiento" que explica exactamente por qué se tomó una decisión (ideal para cumplimiento legal en PyMEs).
3.  **Reducción de Alucinaciones:** El aislamiento de contexto asegura que un agente de finanzas no intente inventar leyes legales, ya que no tiene acceso a esa parte de la memoria.

---

## 8. Conclusión para la Implementación

La implementación de PolPilot como sistema inter-agente transforma la IA de un "asistente que responde" a un **"motor de resolución que piensa"**. La clave del éxito reside en la rigurosidad del Gateway y en la precisión de la fórmula de Stop-Loss.

**Próximos pasos técnicos:**
*   Definir los schemas JSON de los 5 tipos de artefactos.
*   Calibrar el threshold $\tau$ mediante pruebas de estrés.
*   Implementar el DAG de dependencias para la orquestación asíncrona.

--- 
*Fin del Documento Técnico.*