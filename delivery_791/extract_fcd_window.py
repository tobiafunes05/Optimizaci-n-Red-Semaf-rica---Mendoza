import xml.etree.ElementTree as ET
import json
import sys

fcd_path = sys.argv[1]
out_path = sys.argv[2]

CX, CY = 1397.195, 2576.78
MARGIN = 320  # bigger margin than plot box, to catch approaching vehicles
T0, T1 = 540, 900   # ventana de 6 minutos (9:00 a 15:00 min de simulacion)
STEP_SAMPLE = 2      # tomar 1 de cada 2 segundos simulados

frames = []
context = ET.iterparse(fcd_path, events=("start", "end"))
_, root = next(context)

cur_time = None
cur_vehs = None
for event, elem in context:
    if event == "start" and elem.tag == "timestep":
        cur_time = float(elem.get("time"))
        cur_vehs = []
    elif event == "end" and elem.tag == "vehicle":
        if cur_time is not None and T0 <= cur_time <= T1:
            x, y = float(elem.get("x")), float(elem.get("y"))
            if abs(x - CX) < MARGIN and abs(y - CY) < MARGIN:
                cur_vehs.append({"id": elem.get("id"), "x": x, "y": y,
                                  "angle": float(elem.get("angle", 0)),
                                  "speed": float(elem.get("speed", 0))})
        elem.clear()
    elif event == "end" and elem.tag == "timestep":
        if cur_time is not None and T0 <= cur_time <= T1:
            if int(round(cur_time)) % STEP_SAMPLE == 0:
                frames.append({"time": cur_time, "vehicles": cur_vehs})
        elem.clear()
        root.clear()
    if cur_time is not None and cur_time > T1:
        break

json.dump({"frames": frames}, open(out_path, "w"))
print(f"{fcd_path}: {len(frames)} frames guardados en {out_path}")
