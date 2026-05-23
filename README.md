# 🍺 SmartBuy — Decision Support System for Raw Materials

> **Damm x Engineering HUB Hackathon 2026** · Predictive Intelligence for Strategic Procurement 
> Built with Python · Cala.ai · # (ML Library) · # (Dashboard Tool)

---

## 💡 Inspiración

En un mercado global volátil, las decisiones de compra impactan directamente en el margen y la disponibilidad de suministro de Damm. Detectar señales avanzadas antes de que el mercado reaccione es la clave para pasar de una actitud reactiva a una estratégica. **SmartBuy** nace para dotar al equipo de Compras de una herramienta que no solo predice precios, sino que recomienda acciones concretas basadas en evidencias explicables.

---

## 🚀 Qué hace (What It Does)

SmartBuy es un sistema de recomendación inteligente que evalúa el mercado de materias primas críticas como aluminio, PET, energía y cebada. El sistema ofrece:

- **Forecast de Precios** — Estimación de tendencias a 26 semanas, especialmente para la cebada.
- **Detección de Señales Avanzadas** — Combina datos de Cala.ai con noticias, macroeconomía, geopolítica y regulación.
- **Sistema de Recomendación Accionable** — Clasifica la decisión en cuatro estados clave:
    - 🟢 **COMPRAR**: Oportunidad de mercado detectada.
    - 🟡 **ESPERAR**: Se prevé una corrección o bajada inminente.
    - 🔵 **CUBRIRSE (HEDGING)**: Riesgo de subida; asegurar precio y definir horizonte.
    - ⚪ **MONITORIZAR**: Incertidumbre alta o seguimiento continuo.

---

## 🛠️ Cómo lo hemos construido (How We Built It)

[cite_start]Hemos diseñado un pipeline que une los datos históricos con el pulso del mercado en tiempo real[cite: 6, 18]:

1. [cite_start]**Ingesta de Datos**: Uso de datasets estructurados de Cala.ai y referencias sectoriales (Fastmarkets, OMIP, etc.)[cite: 11, 20].
2. [cite_start]**Enriquecimiento Externo**: Integración de fuentes adicionales como informes COT, datos macroeconómicos y noticias para anticipar movimientos de grandes fondos[cite: 13, 20].
3. **Motor de Predicción**: Implementación de la función `fit_predict` capaz de generar proyecciones semanales precisas [Notebook].
4. [cite_start]**Capa de Explicabilidad**: Generación de un *score* de riesgo y desglose de *drivers* que justifican cada decisión para el usuario de negocio[cite: 25, 26, 41].

---

## 📊 Tecnologías y Datos

| Componente | Herramientas / Fuentes |
|---|---|
| **Lenguaje** | [cite_start]Python [cite: 33] |
| **Modelado de AI** | # (Ej. Prophet, XGBoost, Scikit-learn) [Notebook] |
| **Visualización** | # (Ej. Streamlit, Power BI) [cite_start][cite: 33] |
| **Fuentes de Datos** | [cite_start]Cala.ai, Expana, OMIP, TTF, ICIS [cite: 11, 20] |
| **Datos Externos** | # (Ej. Macroeconomía, Clima, Geopolítica) [cite_start][cite: 20] |

---

## 🧠 El Modelo de AI

El núcleo técnico es un modelo de forecast optimizado para minimizar el **MAE** (Mean Absolute Error) [Notebook].

- [cite_start]**Entrada**: Datos históricos de precios y variables explicativas externas[cite: 18, 20].
- **Proceso**: Entrenamiento con *validation splits* para asegurar la capacidad de generalización [Notebook].
- **Salida**: Predicción de 26 pasos semanales y recomendación de compra con horizonte temporal sugerido.

---

## ⚠️ Retos (Challenges)

[cite_start]**Integración de señales no estructuradas** — Combinar precios numéricos con datos de noticias y regulación europea para detectar tendencias antes que el resto del mercado[cite: 18, 20].

[cite_start]**Accionabilidad técnica** — Pasar de un modelo descriptivo a uno prescriptivo que realmente ayude a decidir si conviene cubrirse o esperar[cite: 38, 43].

---

## ⚙️ Cómo empezar (Getting Started)

### Requisitos
- Python 3.10+
- # (Lista de librerías principales)

### Instalación y Ejecución
1. Clona el repositorio: `git clone # (URL-tu-repo)`.
2. Instala las dependencias: `pip install -r requirements.txt`.
3. Ejecuta el notebook de entrenamiento: `Damm_Hackathon_ForecastChallenge.ipynb` [Notebook].
4. Lanza la demo funcional: `# (Comando para tu dashboard)`.

---

## 👥 Equipo

- **# (Nombre)** — Data Scientist / Modelado
- **# (Nombre)** — Data Engineer / Pipeline de datos
- **# (Nombre)** — Frontend / Dashboard Specialist

**Damm x Engineering HUB Hackathon 2026**
