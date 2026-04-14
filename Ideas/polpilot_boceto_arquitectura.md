# PolPilot --- Boceto de Arquitectura Cognitiva Multiagente

## 1. Contexto base del proyecto

PolPilot nace como un sistema operativo de inteligencia empresarial para
PyMEs latinoamericanas, accesible desde WhatsApp. La propuesta central
es que un dueño de negocio pueda interactuar en lenguaje natural ---por
texto, audio, imágenes, facturas o planillas--- y recibir análisis,
memoria operativa y ejecución concreta sin depender de software previo.

La plataforma integra información dispersa y la traduce en decisiones
accionables. Sobre esta base, el proyecto ya contempla módulos
especializados: económico, regulatorio, financiero, compras e
inventario, memoria organizacional y cálculo de valor real del negocio.

------------------------------------------------------------------------

## 2. Evolución propuesta

La nueva idea agrega una capa de **orquestación cognitiva multiagente
con expansión controlada**.

El sistema: - recibe un problema empresarial - decide si requiere
expansión analítica - lo divide en tópicos - activa agentes
especializados en paralelo - sintetiza respuestas - detecta nuevas
preguntas útiles - permite colaboración entre agentes - aplica stop-loss
para evitar sesgo

Esto transforma a PolPilot en un **motor de razonamiento ejecutivo para
PyMEs**.

------------------------------------------------------------------------

## 3. Flujo principal

``` mermaid
flowchart TD
    A[Input del usuario] --> B[Normalización]
    B --> C{Dummy Analyzer}

    C -->|Continuidad o simple| D[Usar contexto]
    D --> E[Responder]

    C -->|Requiere expansión| F[Analyzer Topics]
    F --> G[Detectar tópicos]
    F --> H[Asignar agentes]
    F --> I[Detectar dependencias]

    G --> J[Gateway]
    H --> J
    I --> J

    J --> K[Ejecución paralela]
    K --> L1[Agente Legal]
    K --> L2[Agente Finanzas]
    K --> L3[Agente Marketing]

    L1 --> M[Sintetizador]
    L2 --> M
    L3 --> M

    M --> N{¿Hay nuevas preguntas?}
    N -->|No| O[Respuesta final]
    N -->|Sí| P[Colaboración inter-agente]
    P --> Q{Stop-loss}
    Q -->|No| F
    Q -->|Sí| O
```

------------------------------------------------------------------------

## 4. Diferencial clave

El gran diferencial está en que los agentes **pueden interactuar entre
sí**.

Ejemplo: - el agente legal detecta una nueva pregunta - necesita validar
presupuesto - solicita apoyo al agente financiero vía gateway - recibe
contexto - refina su respuesta - vuelve al sintetizador

Esto simula cómo trabajaría una **mesa directiva real**.

------------------------------------------------------------------------

## 5. Stop-loss cognitivo

La expansión solo continúa si: 1. agrega información útil 2. sigue
respondiendo la pregunta original

Si profundizar empieza a: - desviar el foco - agregar ruido -
sobredimensionar un detalle - aumentar costo sin mejorar decisión

el flujo se detiene y responde.

------------------------------------------------------------------------

## 6. Posicionamiento

**PolPilot = comité ejecutivo de IA para PyMEs por WhatsApp**

No solo responde preguntas: - descompone problemas - activa
especialistas - coordina colaboración - sintetiza resultados - decide
cuándo dejar de investigar
