# Investigacion: Creditos PyME - Fuentes de Datos

**Fecha:** 14 de abril de 2026
**Objetivo:** Analizar la viabilidad de obtener programaticamente informacion sobre creditos disponibles para PyMEs desde bancos argentinos y fuentes oficiales.

---

## Resumen Ejecutivo

Se analizaron tres fuentes solicitadas (Banco Provincia, Banco Galicia, Boletin Oficial) y se descubrieron fuentes alternativas con acceso programatico real. **Los sitios de los bancos no exponen APIs publicas**, pero el BCRA ofrece varias APIs gratuitas que cubren gran parte de la necesidad.

---

## 1. Banco Provincia

**Sitio:** https://www.bancoprovincia.com.ar

### Productos de Credito PyME Encontrados

#### Provincia en Marcha - Inversion Productiva
- **Monto maximo:** $250 millones por empresa
- **Tasa:** desde 36% anual (con bonificacion de 10-15 puntos porcentuales)
- **Bonificacion extra:** hasta 15 puntos para proyectos en agrupamientos industriales o sustentables
- **Plazo:** hasta 60 meses (5 anios)
- **Requisito:** certificado MiPyME vigente + actividad principal en Provincia de Buenos Aires

#### Provincia en Marcha - Compra de Insumos Industriales
- **Monto maximo:** $50 millones
- **Tasa:** 33.6% fija anual
- **Plazo:** hasta 24 meses

#### RePyme (Reactivacion PyME)
- **Capital de trabajo:** desde 44% TNA
- **Inversion:** desde 55% TNA

#### Creditos PyME Mujeres
- **Tasa:** desde 16.6% anual (bonificada)
- **Tasa alternativa:** desde 33% para PyMEs lideradas por mujeres

#### Creditos PEM (Programa Estimulo MiPyME)
- Coordinado con el Ministerio de Produccion de Provincia de Buenos Aires

### Acceso Programatico

**No disponible.** El sitio es una SPA (Single Page Application) que carga contenido dinamicamente con JavaScript. No expone API publica ni datos estructurados. Las lineas de credito cambian con frecuencia.

### Fuentes
- https://www.bancoprovincia.com.ar/Noticias/ProvinciaPymes/conoce-la-linea-de-creditos-con-tasas-desde-33-para-pymes-lideradas-por-mujeres-1685
- https://www.ambito.com/negocios/creditos-pymes-banco-provincia-relanza-sus-lineas-repyme-tasas-especiales-n6168492
- https://www.infobae.com/economia/2026/03/31/lanzan-nuevos-creditos-para-pymes-a-tasas-mas-bajas-cuando-estaran-disponibles-y-de-cuanto-es-el-cupo/
- https://www.gba.gob.ar/produccion/creditos_pem

---

## 2. Banco Galicia

**Sitio:** https://www.galicia.ar/

### Productos de Credito PyME Encontrados

#### Prestamo de Inversion Productiva
- Para capital de trabajo, proyectos de inversion y bienes de capital
- Tasas competitivas y plazos extendidos
- **URL producto:** https://www.galicia.ar/empresas/financiaciones/prestamo-inversion-productiva

#### Prestamos PyME Generales
- **Prestamos:** tasa desde 33%
- **Descuento de cheques:** tasa desde 35%
- **Plazos fijos:** tasa del 31%

#### PYMEnton (Programa de Beneficios)
- Edicion abril 2026
- Beneficios para PyMEs clientes y nuevas
- **URL:** https://www.galicia.ar/empresas/pymenton-beneficios

#### Financiamiento Sustentable
- Tasas preferenciales para empresas con certificado MiPyME
- Requisito: modelo de negocio con impacto social, economico o medioambiental

#### Cuenta PyME
- Gratis por 1 anio
- Financiacion a medida
- Atencion 24/7
- **URL:** https://www.galicia.ar/empresas/tarjetas-y-cuentas/cuenta-pyme

### Acceso Programatico

**No disponible.** Mismo problema que Banco Provincia: SPA con contenido dinamico, sin API publica expuesta.

### Fuentes
- https://www.galicia.ar/empresas/financiaciones/prestamo-inversion-productiva
- https://www.galicia.ar/empresas/pymenton-beneficios
- https://puntopyme.com.ar/nota/1840/galicia-lanza-creditos-para-pymes/
- https://www.iprofesional.com/negocios/425546-banco-galicia-lanza-prestamos-con-tasa-baja-para-pymes

---

## 3. Boletin Oficial

**Sitio:** https://www.boletinoficial.gob.ar/

### Informacion Relevante

El Boletin Oficial publica resoluciones del BCRA, normativas sobre tasas preferenciales, programas de credito subsidiado y regulaciones sobre financiamiento PyME.

### Acceso Programatico

**Muy limitado.**
- No expone API publica de busqueda
- Tiene sistema de busqueda web pero no es apto para scraping estructurado
- No se encontraron RSS feeds ni endpoints de datos
- El sitio usa Blockchain Federal Argentina (BFA) para verificacion de documentos
- Repositorio de recibos disponible en: `otslist.boletinoficial.gob.ar/ots/`

### Uso Posible

Revision periodica manual para detectar nuevas regulaciones y programas de credito PyME.

---

## 4. Fuentes Alternativas con Acceso Programatico

### 4.1 API de Regimen de Transparencia del BCRA (MEJOR OPCION)

**URL Catalogo:** https://www.bcra.gob.ar/en/central-bank-api-catalog/
**Documentacion:** https://www.bcra.gob.ar/en/news/the-bcra-launches-the-transparency-regime-api-to-facilitate-access-to-financial-information/

| Campo | Detalle |
|-------|---------|
| **Autenticacion** | No requiere (endpoints abiertos) |
| **Rate limit** | No especificado |
| **Formato** | JSON |
| **Actualizacion** | Diaria (declaracion jurada de los bancos) |
| **Filtrado** | Por entidad financiera (banco individual) |

**Productos cubiertos:**
- Cuentas de ahorro
- Plazos fijos
- Tarjetas de credito
- Prestamos personales
- Prestamos hipotecarios
- Prestamos prendarios
- Paquetes de productos

**Limitacion:** Se enfoca en productos de consumo/personas. No esta confirmado si incluye lineas especificas PyME/empresas.

**Ventaja clave:** Datos actualizados diariamente por cada banco del sistema financiero argentino. Permite comparar condiciones entre bancos.

---

### 4.2 API de Principales Variables del BCRA

**Documentacion no oficial:** https://estadisticasbcra.com/api/documentacion
**GitHub:** https://github.com/aledc7/BCRA-API

| Campo | Detalle |
|-------|---------|
| **Autenticacion** | Token gratuito (registro por email) |
| **Rate limit** | 100 consultas diarias |
| **Formato** | JSON: `[{"d":"YYYY-MM-DD","v":valor}...]` |

**Endpoints relevantes para creditos:**
```
/tasa_prestamos_personales
/tasa_adelantos_cuenta_corriente
/tasa_depositos_30_dias
/base
/base_usd
/inflacion_mensual_oficial
/inflacion_interanual_oficial
/reservas
/usd
/usd_of
```

**Limitacion:** Son tasas agregadas del sistema financiero, no desglosadas por banco individual.

**Uso:** Indicadores macroeconomicos y tasas de referencia para contextualizar las ofertas de credito.

---

### 4.3 API de Central de Deudores del BCRA

**Documentacion:** https://deudores.bcra.apidocs.ar/
**PDF tecnico:** https://www.bcra.gob.ar/Catalogo/Content/files/pdf/central-deudores-v1.pdf

| Campo | Detalle |
|-------|---------|
| **Autenticacion** | No requiere |
| **Consulta por** | CUIT / CUIL / CDI |

**Endpoints disponibles:**

| Endpoint | Datos |
|----------|-------|
| **Deudas** | Situacion crediticia, monto de deuda, dias de mora, observaciones del ultimo periodo reportado |
| **Historicas** | Situacion crediticia de los ultimos 24 meses |
| **Cheques Rechazados** | Informacion de cheques rechazados y motivos de rechazo |

**Uso para PolPilot:** Evaluar la salud crediticia de la PyME por CUIT antes de sugerirle lineas de credito. Permite precalificar automaticamente.

---

### 4.4 Dataset FONDEP (datos.gob.ar)

**URL:** https://datos.gob.ar/dataset/produccion-creditos-con-tasa-bonificada-fondep

| Campo | Detalle |
|-------|---------|
| **Formato** | XLS (Excel) - descarga directa |
| **Licencia** | Creative Commons Attribution 4.0 |
| **Ultima actualizacion** | Mayo 2021 (DESACTUALIZADO) |
| **API** | No disponible |

**Contenido:**
- Montos y cantidad de creditos por linea con bonificacion de tasa
- Detalle por provincia y actividad economica
- Descripcion de lineas: entidades financieras, monto total, maximo por beneficiario, destino, tasas

**Limitacion:** Datos de 2020, sin actualizacion reciente. Sin API programatica.

---

## 5. Estrategia Recomendada para PolPilot

### Arquitectura de Datos Propuesta

```
+--------------------------------------------------+
|                   PolPilot                        |
|                                                  |
|  +--------------------------------------------+  |
|  |          Modulo de Creditos PyME            |  |
|  |                                            |  |
|  |  +----------+  +-----------+  +----------+ |  |
|  |  | API BCRA |  | API BCRA  |  | API BCRA | |  |
|  |  | Transpa- |  | Central   |  | Variables| |  |
|  |  | rencia   |  | Deudores  |  | Princip. | |  |
|  |  +----+-----+  +-----+-----+  +----+-----+ |  |
|  |       |               |              |       |  |
|  |  Tasas por      Perfil credit.   Tasas de   |  |
|  |  banco (diario) PyME por CUIT   referencia  |  |
|  |                                            |  |
|  |  +--------------------------------------+  |  |
|  |  |     Datos Curados Manualmente        |  |  |
|  |  |  (Lineas especificas PyME de cada    |  |  |
|  |  |   banco - actualizacion mensual)     |  |  |
|  |  +--------------------------------------+  |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
```

### Matriz de Fuentes

| Fuente | Metodo | Datos | Frecuencia | Prioridad |
|--------|--------|-------|------------|-----------|
| BCRA Transparencia API | API REST (sin auth) | Tasas y condiciones por banco | Diaria | Alta |
| BCRA Central Deudores API | API REST (sin auth) | Perfil crediticio PyME por CUIT | Tiempo real | Alta |
| BCRA Variables API | API REST (token gratis) | Tasas de referencia del sistema | Diaria | Media |
| Banco Provincia | Datos curados manualmente | Lineas especificas PyME | Mensual | Media |
| Banco Galicia | Datos curados manualmente | Lineas especificas PyME | Mensual | Media |
| Boletin Oficial | Revision manual | Nuevas regulaciones/programas | Quincenal | Baja |
| FONDEP (datos.gob.ar) | Descarga XLS | Lineas con tasa bonificada | Esporadica | Baja |

### Proximos Pasos Sugeridos

1. **Investigar a fondo la API de Transparencia del BCRA** - Verificar si cubre prestamos empresariales/PyME ademas de productos de consumo
2. **Probar la API de Central de Deudores** - Hacer una consulta de prueba con un CUIT para validar la estructura de datos
3. **Disenar el modelo de datos** - Definir como se van a almacenar y comparar las ofertas de credito en PolPilot
4. **Crear un sistema de datos curados** - Para las lineas PyME especificas de cada banco que no estan disponibles via API
5. **Integrar con la funcionalidad existente** - PolPilot ya tiene precalificacion BCRA al 29% TNA; expandir esa base

---

## Contactos Utiles

| Recurso | Contacto |
|---------|----------|
| BCRA API Soporte | api@bcra.gob.ar |
| Boletin Oficial | Tel: 5218-8400 / 0810-345-BORA |
| Boletin Oficial Sede | Suipacha 767, C.A.B.A. |

---

## Referencias Completas

### Banco Provincia
- [Linea creditos PyME mujeres - Banco Provincia](https://www.bancoprovincia.com.ar/Noticias/ProvinciaPymes/conoce-la-linea-de-creditos-con-tasas-desde-33-para-pymes-lideradas-por-mujeres-1685)
- [RePyme tasas especiales - Ambito](https://www.ambito.com/negocios/creditos-pymes-banco-provincia-relanza-sus-lineas-repyme-tasas-especiales-n6168492)
- [Nuevos creditos PyME tasas bajas - Infobae](https://www.infobae.com/economia/2026/03/31/lanzan-nuevos-creditos-para-pymes-a-tasas-mas-bajas-cuando-estaran-disponibles-y-de-cuanto-es-el-cupo/)
- [Provincia en Marcha - 0221](https://www.infozona.com.ar/creditos-banco-provincia-como-acceder-a-las-nuevas-lineas-bonificadas-de-provincia-en-marcha-para-pymes/)
- [Creditos PEM - Gobierno PBA](https://www.gba.gob.ar/produccion/creditos_pem)
- [Prestamos PyMEs $15 mil millones - ABAPPRA](https://abappra.org.ar/banco-provincia-lanza-nuevos-prestamos-a-pymes-por-15-mil-millones-de-pesos)

### Banco Galicia
- [Prestamo Inversion Productiva](https://www.galicia.ar/empresas/financiaciones/prestamo-inversion-productiva)
- [PYMEnton de Beneficios](https://www.galicia.ar/empresas/pymenton-beneficios)
- [Galicia lanza creditos PyMEs - PuntoPyme](https://puntopyme.com.ar/nota/1840/galicia-lanza-creditos-para-pymes/)
- [Prestamos tasa baja PyMEs - iProfesional](https://www.iprofesional.com/negocios/425546-banco-galicia-lanza-prestamos-con-tasa-baja-para-pymes)
- [Cuenta PyME](https://www.galicia.ar/empresas/tarjetas-y-cuentas/cuenta-pyme)

### BCRA y APIs
- [Catalogo de APIs BCRA](https://www.bcra.gob.ar/en/central-bank-api-catalog/)
- [API Transparencia - Anuncio](https://www.bcra.gob.ar/en/news/the-bcra-launches-the-transparency-regime-api-to-facilitate-access-to-financial-information/)
- [API Central de Deudores - Documentacion](https://deudores.bcra.apidocs.ar/)
- [API Central de Deudores - PDF Tecnico](https://www.bcra.gob.ar/Catalogo/Content/files/pdf/central-deudores-v1.pdf)
- [API Estadisticas BCRA (no oficial)](https://estadisticasbcra.com/api/documentacion)
- [GitHub - BCRA API Wrapper](https://github.com/aledc7/BCRA-API)
- [GitHub - BCRA Python Wrapper](https://github.com/Jaldekoa/BCRA-Wrapper)

### Datos Abiertos
- [FONDEP - datos.gob.ar](https://datos.gob.ar/dataset/produccion-creditos-con-tasa-bonificada-fondep)
- [Datasets Dinero y Bancos - datos.gob.ar](https://datos.gob.ar/dataset?tags=Dinero+y+Bancos)
- [Datos Produccion - FONDEP](https://datos.produccion.gob.ar/dataset/creditos-con-tasa-bonificada-del-fondep)
