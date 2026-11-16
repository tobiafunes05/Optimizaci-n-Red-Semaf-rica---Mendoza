# Guía para armar la presentación en Gamma — CACIC 2026, Grupo 9

**Cómo usarlo:** entrá a gamma.app → "Crear nuevo" → **"Pegar texto"** (paste in text) → pegá desde
"## Diapositiva 1" hasta el final → Gamma va a generar una diapositiva por cada `##` que
encuentre. Elegí un tema visual simple (una sola tipografía, poco color) y después ajustá.
Para el gráfico de resultados, subilo como imagen en la diapositiva 5 (`chart_final_fijo_vs_rl_moderado.png`,
ya lo tenés en tu carpeta `delivery`).

Duración total: 5 minutos, 1 minuto por persona/tema. 5 diapositivas de contenido + portada +
cierre (estas dos casi no llevan tiempo de más, se muestran solas).

## Quién presenta qué

| # | Tema | Integrante | Basado en la sección del informe |
|---|------|-----------|-----------------------------------|
| 1 | Introducción y problema | Gerónimo Torres | 1. Introducción: Problema y justificación |
| 2 | Marco teórico y estado del arte | Valentino Cutrera | 2. Marco teórico + 3. Estado del arte |
| 3 | Metodología y arquitectura propuesta | Juan Jorge | 4. Propuesta de arquitectura + 5. Hipótesis + 6. Metodología |
| 4 | Resultados (avance experimental) | Francisco Segui (vos) | Reemplaza la sección 7 del informe — acá van los resultados REALES que ya sacamos, no los "esperados" |
| 5 | Conclusiones y trabajo futuro | Tobías Funes | 8. Conclusión |

Se las repartí siguiendo el orden del informe para que cada uno tenga la sección que ya
"conoce" del texto. Vos (Francisco) quedás con Resultados porque sos quien corrió los
experimentos esta semana y podés responder preguntas técnicas con más soltura si alguien
pregunta algo puntual.

---

## Diapositiva 1 — Portada

**Poner:**
- Título: *Optimización de la red semafórica urbana mediante inteligencia artificial*
- Subtítulo: *Gestión adaptativa y eficiente del tráfico en la ciudad de Mendoza*
- Autores: Gerónimo Torres, Valentino Cutrera, Francisco Segui, Juan Jorge, Tobías Funes — Miguel Mendez Garabetti (director)
- Universidad del Aconcagua · CACIC 2026

No se narra, queda mostrada mientras arranca a hablar la persona 1.

## Diapositiva 2 — Introducción y problema (Gerónimo, 1 min)

**Poner (título + 3-4 bullets cortos, no párrafos):**
- El crecimiento del parque automotor genera congestión, contaminación y pérdida de tiempo en ciudades latinoamericanas.
- Los semáforos de tiempo fijo no responden a la variación real del tránsito → desincronización, colas, más consumo y emisiones.
- **Pregunta de investigación:** ¿en qué medida la IA puede reducir congestión, tiempos de espera y emisiones?
- **Objetivo:** analizar el impacto de sistemas de control semafórico basados en IA sobre el tránsito urbano en Mendoza.

**Qué decir (guion de ~1 min):** arrancar con el problema concreto (una esquina con semáforo
que no "ve" que no hay autos y sigue en rojo igual), nombrar el objetivo general, y cerrar
pasando la posta: "para eso primero revisamos qué se hizo antes — te paso con Valentino."

## Diapositiva 3 — Marco teórico y estado del arte (Valentino, 1 min)

**Poner:**
- Sistemas de Transporte Inteligente (ITS): sensores + datos + modelos para gestionar tránsito en tiempo real.
- 3 herramientas de IA aplicables: aprendizaje automático (patrones), visión computacional (detectar autos por cámara), aprendizaje por refuerzo (agente que aprende a elegir fases).
- Antecedentes regionales: Nuevo Laredo (sensores de presencia), Loja (mejoras documentadas en espera/emisiones), Quito ("Smart Traffic" con YOLOv3), Guayaquil (IA + IoT).
- Conclusión del estado del arte: los sistemas adaptativos muestran ventajas, pero con desafíos de costo e implementación.

**Qué decir:** no leer los 4 antecedentes en detalle — mencionar 2 (Quito y Loja son los más
concretos) y remarcar la idea central: "en todos lados donde se probó, adaptativo le ganó a
tiempo fijo — nuestro trabajo es ver si eso se sostiene en un modelo de Mendoza."

## Diapositiva 4 — Metodología y arquitectura propuesta (Juan, 1 min)

**Poner:**
- Arquitectura en 4 capas: captura de datos (simulados) → procesamiento (colas, vehículos, espera) → decisión (RL / reglas adaptativas) → ejecución (cambia tiempos de verde/amarillo/rojo).
- Entorno de simulación: **SUMO**, sobre un mapa real del centro de Mendoza (63 intersecciones semaforizadas).
- Comparación: **tiempo fijo (línea base) vs. sistema adaptativo con aprendizaje por refuerzo**.
- Métricas: tiempo promedio de espera, flujo de vehículos por hora, % de reducción estimada de emisiones de CO2.

**Qué decir:** explicar las 4 capas rápido con una analogía ("como un termostato: mide, decide,
actúa"), y dejar clarísimas las 2 columnas que se comparan y las 3 métricas — eso es lo que
la diapositiva siguiente va a mostrar con números reales.

## Diapositiva 5 — Resultados: avance experimental (Francisco, 1 min)

Esta es la diapositiva más importante y la única con datos reales — no repitas "resultados
esperados" del informe, esos ya quedaron viejos: ya corrimos la simulación.

**Poner:**
- Imagen: `chart_final_fijo_vs_rl_moderado.png` (los 3 paneles: espera, flujo/hora, CO2).
- Título del bloque: "Pipeline experimental construido y validado en SUMO — resultados con entrenamiento completo (50.000 pasos)"
- 3 números del escenario tiempo fijo (línea base, 820 vehículos): 143,7s de espera promedio, 866 veh/hora, 276,3 kg CO2.
- 3 números del RL entrenado (50.880 pasos): 180,7s de espera, 716 veh/hora, CO2 por vehículo 669,7 g (vs 638,1 g del fijo).
- 1 bullet de estado honesto: "Con el entrenamiento completo el RL mejoró mucho respecto a la primera corrida (espera bajó de 220,9s a 180,7s; flujo subió de 592 a 716 veh/hora) pero todavía no supera al tiempo fijo — es un punto de partida real para seguir ajustando el modelo, no el resultado final."
- (Opcional, si da el tiempo) mencionar el hallazgo positivo ya confirmado: el controlador adaptativo por reglas (sin RL) coordinado entre semáforos vecinos SÍ superó al no coordinado: +12% de vehículos que completan su viaje, -15% de autos atascados.

**Qué decir (importante):** ser honesto en vivo, no vender el RL como si ya hubiera ganado —
decir algo como "entrenamos el modelo completo, 50.000 pasos, y mejoró bastante respecto a
la primera versión, pero todavía no le gana al tiempo fijo en las métricas principales. Eso
nos dice que el pipeline funciona de punta a punta —simulación, entrenamiento, métricas de
CO2— y que el siguiente paso es afinar la configuración del agente, no rehacer el enfoque."
Eso es un resultado real y defendible (nadie espera que la primera configuración de RL le
gane al baseline), mucho mejor que mostrar un número lindo que no se sostiene si alguien
pregunta.

## Diapositiva 6 — Conclusiones y trabajo futuro (Tobías, 1 min)

**Poner:**
- La optimización semafórica con IA es una alternativa concreta para mejorar la movilidad en Mendoza, no solo teórica — ya tenemos un entorno de simulación funcionando.
- La implementación real requiere infraestructura, datos confiables y planificación (no es "instalar y listo").
- Próximos pasos: terminar el entrenamiento del agente de RL, correr con demanda de tráfico real (no sintética), y evaluar coordinación entre más de 12 intersecciones.
- Cierre: agradecer y abrir a preguntas.

**Qué decir:** resumir en una frase la idea central ("tiempo fijo no escala, adaptativo sí,
y ya tenemos con qué probarlo"), nombrar 1-2 próximos pasos concretos, y cerrar agradeciendo.

## Diapositiva 7 — Cierre

**Poner:** "Gracias — ¿Preguntas?" + los mismos contactos de la portada.

---

## Tips generales para Gamma

- No pongas párrafos largos en las diapositivas — Gamma (y el público) lee bullets de 1
  línea. El texto completo de arriba es para que cada uno sepa qué DECIR, no para pegarlo
  entero en la diapositiva.
- Con 5 min totales, cada uno debería practicar su parte por separado con cronómetro al
  menos una vez — 1 minuto se pasa muy rápido si alguien empieza a leer de más.
- En la diapositiva de resultados, dejá el gráfico grande y los números como texto chico al
  costado — es la que más preguntas puede generar, así que Francisco conviene que la tenga
  bien ensayada.
