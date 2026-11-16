# Optimización de semáforos con IA (algoritmo genético) sobre un mapa SUMO de Mendoza

Este paquete contiene el código y los resultados del experimento descripto en
`Investigacion_IA_Semaforos_Mendoza.docx`. Resume, en formato práctico, cómo
correrlo de nuevo o extenderlo.

## Estructura

- `osm.net.xml` / `osm.net.xml.gz` — la red vial completa reescalada a **791 semáforos** (~28 MB comprimida / ~250 MB descomprimida; `ga_lib.py` descomprime automáticamente `osm.net.xml.gz` si no encuentra `osm.net.xml`).
- `scope_tls_791.json` — lista con los 791 IDs de semáforos de la red completa del Gran Mendoza (scope por defecto en `ga_lib.load_scope()`, 1.726 fases verdes en total).
- `build_controlled_lanes.py` — script nuevo que usa TraCI para generar automáticamente `tls_controlled_lanes.json` para los 791 semáforos (`python3 build_controlled_lanes.py osm.net.xml scope_tls_791.json tls_controlled_lanes.json`).
- `osm.poly.xml` — polígonos/edificios (sólo para visualización en sumo-gui).
- `osm.rou.xml` — demanda de tráfico sintética generada con `randomTrips.py` (reescalada a **10.286 vehículos** para la red de 791 semáforos; en el experimento inicial de 12 intersecciones era de 820 vehículos, 30 minutos, semilla 7).
- `sim.sumocfg` — configuración mínima para correr la simulación base (sumo-gui o sumo).
- `top_tls.json` — ranking completo de las 63 intersecciones por congestión (tiempo de cola agregado).
- `scope_tls_top12.json` — el subconjunto de 12 elegido para optimizar. **Usar siempre
  este archivo**, no `scope_tls.json` — ver "Bug encontrado y corregido" más abajo.
- `ga_lib.py` — funciones reutilizables: parseo del net.xml, reconstrucción de
  `<tlLogic>` a partir de un genoma, ejecución de SUMO headless, cálculo de fitness.
- `ga_run.py` — el algoritmo genético en sí (población, selección, cruce, mutación).
  Ejecutalo con `python3 ga_run.py`.
- `best_genome.json` — el mejor plan de tiempos encontrado (genoma + historial de convergencia).
- `net_best.xml` — la red vial completa con los 12 semáforos ya optimizados
  (podés abrirla directo en sumo-gui para verla funcionando).
- `ga_log.jsonl` — una línea por cada una de las 384 simulaciones evaluadas durante la búsqueda.
- `ga_progress.txt` — resumen legible de cada generación.
- `comparison.json`, `timing_table.json` — datos usados para las tablas del informe.
- `make_charts.py` — genera los dos gráficos (convergencia y comparación) a partir de los JSON.
- `Investigacion_IA_Semaforos_Mendoza.docx` — el informe de investigación completo.

### Coordinación entre semáforos vecinos (nuevo)

- `tls_topology.py` — usa `sumolib` para calcular, a partir de `osm.net.xml`, qué
  carriles quedan "aguas abajo" de cada movimiento de cada semáforo (hasta llegar
  al próximo semaforo o a un límite de saltos) y qué semáforos son vecinos directos.
  Correlo una vez con `python3 tls_topology.py`; genera:
  - `tls_downstream_lanes.json` — por semáforo y carril de entrada, los carriles de
    salida a vigilar (lo usan `adaptive_lib.py` y `sumo_rl_env.py`/`sumo_rl_multiagent_env.py`).
  - `tls_adjacency.json` — vecinos semaforizados directos de cada semáforo (documentación).
- `adaptive_lib.py` / `adaptive_run.py` — el controlador adaptativo (max-pressure) ahora
  usa "presión neta": cola local **menos** una penalidad si la calle de salida de esa
  fase ya está saturada, y corta el verde apenas se cumple el mínimo si esa calle está
  a punto de desbordarse (spillback), en vez de seguir empujándole autos al semáforo de
  atrás. Probado con la red real: en el escenario moderado pasó de 409 a 458 vehículos
  completados y de 104 a 88 teleports (autos removidos por quedar atascados) — ver
  `result_adaptive_moderado_nocoord.json` (antes) vs `result_adaptive_moderado_coord.json`
  (después). En el escenario denso (sobresaturado) la mejora es mucho más chica — cuando
  toda la red está saturada, la coordinación tiene menos margen para ayudar.
- `sumo_rl_env.py` — el entorno de RL de UN semáforo ahora también observa la ocupación
  de su calle de salida y la recompensa penaliza mandar autos a una calle saturada.
  **Ojo**: esto cambia la observación de 4 a 5 valores — `rl_model_final.zip` y los
  checkpoints viejos de `rl_checkpoints/` ya no son compatibles, hay que reentrenar.
- `sumo_rl_multiagent_env.py` / `train_rl_multi.py` — versión nueva que controla los
  12 semáforos de `scope_tls_top12.json` A LA VEZ con una sola política (PPO, acción
  `MultiDiscrete`): cada semáforo observa su propia cola, la ocupación de su calle de
  salida, y la cola del/los semáforo(s) vecino(s) directo(s) dentro del scope; la
  recompensa es compartida a nivel red (promedio de autos parados en los 12 semáforos),
  así que a ningún agente le conviene "resolver" su cola mandándosela al vecino. Es una
  simplificación práctica de RL multi-agente (una red centralizada, no 12 políticas
  independientes coordinadas vía PettingZoo/RLlib) — suficiente para 12 intersecciones,
  mencionada como tal en la sección 8 del informe. Entrenar bien esto (>=100-200k pasos)
  tarda bastante más que el algoritmo genético; arrancá con pocos miles de pasos para
  validar que la recompensa mejora (`rl_multi_train_log.csv`) y después dejalo corriendo
  más tiempo.

### Cómo ver la comparativa "antes vs. después" (sin coordinar vs. coordinado)

`adaptive_run.py` ahora acepta un flag `--no-coord` para correr exactamente el mismo
motor pero sin la coordinación entre vecinos (para tener el "antes" comparable):

```
export SUMO_HOME=$(python3 -c "import sumo,os; print(os.path.dirname(sumo.__file__))")
export PATH=$SUMO_HOME/bin:$PATH
export PYTHONPATH=$SUMO_HOME/tools:$PYTHONPATH

python3 adaptive_run.py osm.rou.xml moderado_nocoord 820 --no-coord   # antes (~25s)
python3 adaptive_run.py osm.rou.xml moderado_coord 820                # despues (~3 min)
python3 make_comparison_coord_chart.py                                 # genera el grafico
```

Esto genera `result_adaptive_moderado_nocoord.json`, `result_adaptive_moderado_coord.json`
y `chart_comparativa_coordinacion.png` (5 barras: baseline actuado, static, GA-optimizado,
adaptativo sin coordinar, adaptativo coordinado — fitness y vehículos completados/teleports).
Para el escenario denso, lo mismo pero con `osm_denso.rou.xml <tag> 1800`.

### Comparación final pedida por la cátedra: tiempo fijo vs. RL adaptativo

Esta es la comparación que efectivamente se entrega: **dos** escenarios (tiempo fijo
como línea base, y el sistema adaptativo de RL) evaluados con **tres** métricas (tiempo
promedio de espera, flujo de vehículos por hora, reducción % de emisiones de CO2). Se
sacaron el escenario "híbrido" y la métrica de longitud de cola que planteaba la consigna
original — decisión tomada en la sesión del 27/08.

- `ga_lib.compute_full_metrics()` — nueva función (además de `compute_fitness`, que se
  mantiene por compatibilidad con `ga_run.py`) que calcula, a partir del tripinfo/stats
  de una corrida: tiempo de espera promedio (`waitingTime` de SUMO), flujo de
  vehículos/hora (completados ÷ duración simulada en horas), y CO2 total/promedio por
  vehículo (requiere correr SUMO con `--device.emissions.probability 1.0`, que usa el
  modelo de emisiones HBEFA de SUMO a partir de la velocidad/aceleración instantánea de
  cada vehículo).
- `baseline_fixed_run.py` — corre el escenario "tiempo fijo": los 12 semáforos con sus
  duraciones ORIGINALES (antes de cualquier optimización), forzados a tiempo fijo,
  emisiones activadas. Es la misma definición que "Static" en el informe original del GA
  (se reproduce exactamente: mismo fitness, mismo tiempo de espera), ahora con CO2 y
  flujo/hora sumados.
  ```
  python3 baseline_fixed_run.py osm.rou.xml moderado 820
  ```
- `eval_rl_multi.py` — carga la política de RL ya entrenada (`train_rl_multi.py`) y
  corre una simulación completa en modo determinista (sin exploración), con las mismas
  salidas (tripinfo/stats/emisiones) que el baseline, para que las métricas sean
  comparables entre sí.
  ```
  python3 eval_rl_multi.py osm.rou.xml moderado 820
  ```
- `make_final_comparison_chart.py` — lee los dos JSON de resultado y genera
  `chart_final_fijo_vs_rl_<tag>.png` con las 3 métricas, marcando el % de reducción de
  CO2 en el título del panel correspondiente.
  ```
  python3 make_final_comparison_chart.py moderado
  ```

**Sobre el modelo de RL — actualizado 27/08, entrenamiento completado a 50.880 pasos**:
se retomó el entrenamiento (que se había cortado en 10.000 pasos por la caída del proceso
en background) en 8 tandas foreground de 5.000 pasos cada una con `--resume`, hasta
superar los 50.000 pasos planeados. El modelo entregado (`rl_multi_model_final.zip`,
`result_rl_multi_moderado.json`, el gráfico) es este, ya con el entrenamiento completo.

Con más entrenamiento el modelo **mejoró de forma clara** respecto al de 10.000 pasos:

| Métrica | RL @ 10.000 pasos | RL @ 50.880 pasos | Tiempo fijo (línea base) |
|---|---|---|---|
| Espera promedio | 220,9 s | 180,7 s | 143,7 s |
| Flujo | 592 veh/h | 716 veh/h | 866 veh/h |
| Vehículos completados | 296/820 | 358/820 | 433/820 |
| Teleports (autos atascados) | 220 | 161 | 83 |
| CO2 por vehículo completado | 701,4 g | 669,7 g | 638,1 g |

Es una mejora real y consistente en las 5 métricas. Pero, siendo honestos, **con 50.000
pasos el RL todavía no le gana al tiempo fijo** en ninguna de las 3 métricas pedidas:
sigue peor en espera (+25,7%), en flujo (-17,3%) y en CO2 por vehículo (+4,9%). El CO2
total bruto vuelve a dar "mejor" para el RL (-13,2%), pero es el mismo artefacto de
siempre: completa menos viajes que el fijo (358 vs 433), no es que sea más limpio por
auto.

Un dato técnico para quien siga esto: la curva de recompensa por episodio
(`rl_multi_train_log.csv`) se mantuvo prácticamente plana (entre -24 y -28) en las 8
tandas, sin una tendencia de mejora sostenida episodio a episodio — la mejora en las
métricas de arriba vino de comparar puntas (10k vs 50k), no de una curva que suba de
forma limpia. Eso sugiere que simplemente sumar más pasos con la misma configuración
puede seguir dando mejoras marginales, pero no garantiza alcanzar o superar al tiempo
fijo — el espacio de acción conjunto (`MultiDiscrete` de 12 semáforos, 4096 combinaciones)
es grande para PPO con `n_steps=256`. Si se quiere apuntar a un resultado claramente
positivo, lo que más rendiría no es solo "más pasos" sino ajustar la receta: bajar la
complejidad de la acción (política por semáforo en vez de una política conjunta),
probar otro `learning_rate`/`n_steps`, o directamente entrenar 150k-200k pasos en tu
propia máquina (ahí sí se puede dejar en background sin el problema de este entorno).

`train_rl_multi.py` sabe retomar desde el checkpoint o el modelo final indistintamente:
```
python3 train_rl_multi.py 5000 --resume   # suma 5000 pasos mas al ultimo checkpoint/modelo final
```

### Bug encontrado y corregido

`scope_tls.json` en esta carpeta quedó en algún momento sobreescrito con el ranking
completo de las 63 intersecciones (en vez del subconjunto de 12 que originalmente se
usaba para el GA/adaptativo/RL). Eso hace que `ga_run.py` y `adaptive_run.py` fallen
con `KeyError` al buscar esos 63 ids en `tls_controlled_lanes.json` (que solo tiene 12).
`ga_lib.load_scope()` ahora usa `scope_tls_top12.json` por defecto (los 12 ids
originales, que coinciden con `tls_controlled_lanes.json` y `best_genome.json`). Si en
algún momento necesitás optimizar más intersecciones, generá un nuevo scope con
`find_critical_tls.py` en vez de tocar `scope_tls.json` a mano.

## Cómo correrlo de nuevo (en tu computadora)

1. Instalar SUMO (misma versión usada acá, 1.27.1):
   ```
   pip install eclipse-sumo
   export SUMO_HOME=$(python3 -c "import sumo,os; print(os.path.dirname(sumo.__file__))")
   export PATH=$SUMO_HOME/bin:$PATH
   export PYTHONPATH=$SUMO_HOME/tools:$PYTHONPATH
   ```
2. Poner todos los archivos de esta carpeta juntos.
3. Correr el algoritmo genético:
   ```
   python3 ga_run.py
   ```
   Tarda unos 20-25 minutos (384 simulaciones de 30 minutos cada una, ~3.5s c/u).
4. Generar los gráficos:
   ```
   python3 make_charts.py
   ```

## Cómo extenderlo

- **Más intersecciones**: editá `scope_tls.json` para incluir más (o todas las 63)
  ids de semáforo — están en `top_tls.json` completo. Cuantos más genes, más
  generaciones/población conviene usar para que converja.
- **Demanda real**: si conseguís conteos de tráfico reales de Mendoza (por ejemplo,
  de la Dirección de Vialidad o Movilidad), reemplazá `osm.rou.xml` por rutas
  generadas a partir de esos datos (herramientas: `od2trips`, `activitygen`).
- **Control en tiempo real (RL)**: en vez de optimizar un plan de tiempos fijo
  offline, se puede usar la librería `traci` para leer el estado de cada semáforo
  paso a paso y entrenar un agente (por ejemplo con Stable-Baselines3) que decida
  cuándo cambiar de fase. La sección 8 del informe da más detalle.

## Ver la red optimizada en el simulador gráfico

```
sumo-gui -n net_best.xml -r osm.rou.xml
```
