"""Check placement evidence and record hashes; does not certify routed hardware."""
import hashlib
import copy
import heapq
import json
import math
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
sys.path.insert(0, str(WORK / "helpers" / "module_update"))
from cad_edit import children, first, parse, value

board = parse(ROOT / "smart_db.kicad_pcb")
project = json.loads((ROOT / "smart_db.kicad_pro").read_text())
baseline_project = json.loads((WORK / "resume_backup" / "smart_db.kicad_pro").read_text())
expected_project = copy.deepcopy(baseline_project)
for c in expected_project['net_settings']['classes']:
    if c['name'] == 'Default': c['track_width'] = .3
    if c['name'] == 'Power': c['track_width'] = .6
# KiCad remembers the user's last STEP export destination; it is not a rule.
expected_project['pcbnew']['last_paths']['step'] = project['pcbnew']['last_paths']['step']
assert project == expected_project, "Unexpected project change beyond requested preferred widths"
assert project == json.loads((WORK / 'before_camera_power' / 'smart_db.kicad_pro').read_text()), 'Camera addition changed project settings'
tracks = children(board, 'segment')
assert tracks and all(value(t, 'layer') in ['F.Cu', 'B.Cu'] for t in tracks)
assert all(float(value(t, 'width')) >= .2 for t in tracks)
for layer in ["In1.Cu", "In2.Cu"]:
    planes = [z for z in children(board, "zone") if value(z, "layer") == layer]
    assert planes and all(value(z, "net") == "BGND" for z in planes)
module = next(f for f in children(board, "footprint")
              if any(p[1:3] == ["Reference", "U4"] for p in children(f, "property")))
keepouts = children(module, "zone")
assert keepouts
for z in keepouts:
    assert set(first(z, "layers")[1:]) == {"F.Cu", "B.Cu", "In1.Cu", "In2.Cu"}
    for kind in ["tracks", "vias", "pads", "copperpour"]:
        assert value(first(z, "keepout"), kind) == "not_allowed"

netlist = ET.parse(WORK / "netlist_current.xml")
nets = {(n.get("ref"), n.get("pin")): net.get("name")
        for net in netlist.findall("./nets/net") for n in net.findall("node")}
expected = {
    "J2": {"1": "BGND", "2": "LOGIC_5V_IN"},
    "J5": {"1": "LOAD_IN", "2": "LOAD_OUT"},
    "J3": {"1": "SDA", "2": "SCL", "3": "BGND", "4": "MCU_3V3"},
    "J1": {"T": "CT_HI", "S": "CT_BIAS"},
    "J6": {"1": "LOGIC_5V_FUSED", "2": "unconnected-(J6-D--Pad2)",
           "3": "unconnected-(J6-D+-Pad3)", "4": "BGND", "SH": "BGND"},
    "C25": {"1": "LOGIC_5V_FUSED", "2": "BGND"},
    "C26": {"1": "LOGIC_5V_FUSED", "2": "BGND"},
}
for ref, pins in expected.items():
    for pin, net in pins.items():
        assert nets[ref, pin] == net, (ref, pin, nets[ref, pin], net)

# This addition must retain every original route, via and component position.
camera_before = parse(WORK / 'before_camera_power' / 'smart_db.kicad_pcb')
for kind in ['segment', 'via']:
    now = {value(t, 'uuid'): t for t in children(board, kind)}
    for t in children(camera_before, kind):
        assert now[value(t, 'uuid')] == t, ('Existing copper changed', value(t, 'uuid'))
current_footprints = {next(p[2] for p in children(f, 'property') if p[1] == 'Reference'): f
                      for f in children(board, 'footprint')}
for f in children(camera_before, 'footprint'):
    ref = next(p[2] for p in children(f, 'property') if p[1] == 'Reference')
    assert first(f, 'at') == first(current_footprints[ref], 'at'), ref
    assert children(f, 'pad') == children(current_footprints[ref], 'pad'), ref
for ref in ['J6','C25','C26']:
    for pad in children(current_footprints[ref], 'pad'):
        assert value(pad, 'net') == expected[ref][pad[1]]

erc = json.loads((WORK / "erc_current.json").read_text())
drc = json.loads((WORK / "drc_routing_current.json").read_text())
erc_count = sum(len(s.get("violations", [])) for s in erc["sheets"])
assert erc_count == 0
assert not drc["violations"] and not drc["schematic_parity"]
assert not drc['unconnected_items'], 'Board routing is not complete'
assert set(drc["included_severities"]) == {"error", "warning"}
baseline = json.loads((WORK / "drc_resumed.json").read_text())
assert drc["ignored_checks"] == baseline["ignored_checks"]
completed = {net.get('name') for net in netlist.findall('./nets/net')
             if not net.get('name').startswith('unconnected-')}
for issue in drc['unconnected_items']:
    assert not any('[' + net + ']' in item['description'] for item in issue['items'] for net in completed), issue

def xy(node, key):
    return tuple(round(float(v),4) for v in first(node,key)[1:3])
def usb_path(net, source, destination):
    segments = [t for t in tracks if value(t,'net') == net]
    vias = [v for v in children(board,'via') if value(v,'net') == net]
    nodes = {(value(t,'layer'),p) for t in segments for p in [xy(t,'start'),xy(t,'end')]}
    for v in vias:
        for layer in ['F.Cu','B.Cu']: nodes.add((layer,xy(v,'at')))
    graph = {p: [] for p in nodes}
    for t in segments:
        a,c=xy(t,'start'),xy(t,'end');length=math.dist(a,c)
        if not length: continue
        layer=value(t,'layer')
        on=sorted((math.dist(a,p), (l,p)) for l,p in nodes if l==layer and abs(math.dist(a,p)+math.dist(p,c)-length)<.0002)
        for (d1,p1),(d2,p2) in zip(on,on[1:]):
            graph[p1].append((p2,d2-d1,0));graph[p2].append((p1,d2-d1,0))
    for v in vias:
        a=('F.Cu',xy(v,'at'));c=('B.Cu',xy(v,'at'))
        graph[a].append((c,0,1));graph[c].append((a,0,1))
    start=('F.Cu',source);end=('F.Cu',destination)
    heap=[(0,0,start)];seen=set()
    while heap:
        distance,count,node=heapq.heappop(heap)
        if node in seen: continue
        seen.add(node)
        if node==end:return {'planar_length_mm':round(distance,3),'layer_transitions':count}
        for other,d,v in graph[node]:
            if other not in seen:heapq.heappush(heap,(distance+d,count+v,other))
    raise AssertionError(('USB route missing',net))
usb = {
    'D+_A6_to_U5': usb_path('USB_D+', (66.46,82.75), (80.55,83)),
    'D+_B6_to_U5': usb_path('USB_D+', (66.46,83.75), (80.55,83)),
    'D-_A7_to_U5': usb_path('USB_D-', (66.46,83.25), (80.55,83.5)),
    'D-_B7_to_U5': usb_path('USB_D-', (66.46,82.25), (80.55,83.5)),
}
camera_path = usb_path('LOGIC_5V_FUSED', (140.7875,107), (99.5,110.92))
assert camera_path['layer_transitions'] == 2
assert current_footprints['J6'][1] == 'SmartDB:USB_A_TE_292303-7_Horizontal_Edge'
assert xy(current_footprints['J6'], 'at') == (103,117.3)
assert all(p[2] == 'smd' for p in children(current_footprints['J6'],'pad') if p[1] in ['1','2','3','4'])
assert not any(value(t,'net') in [expected['J6']['2'],expected['J6']['3']] for t in tracks)
files = ["smart_db.kicad_pcb", "smart_db.kicad_sch", "smart_db.kicad_pro",
         "SmartDB.pretty/ESP32_S3_WROOM_1_Edge.kicad_mod", "SmartDB.kicad_sym",
         "fp-lib-table", "sym-lib-table", "work/erc_current.json",
         "work/drc_routing_current.json", "work/netlist_current.xml",
         "work/placement_current.pdf", "work/back_labels_current.pdf",
         "work/schematic_current.pdf", "work/routing_current.pdf",
         "SmartDB.pretty/PinHeader_1x04_P2.54mm_Horizontal_Edge.kicad_mod",
         "SmartDB.pretty/USB_C_Receptacle_Amphenol_12401948E412A_Preview.kicad_mod",
         "SmartDB.3dshapes/USB_C_12401948_preview.wrl",
         "SmartDB.3dshapes/USB_C_12401948_preview.step",
         "SmartDB.3dshapes/LED_ROHM_SMLVN6_preview.step",
         "SmartDB.3dshapes/SJ-3523-SMT_aligned.step",
         "SmartDB.3dshapes/provenance.json",
         "SmartDB.pretty/LED_ROHM_SMLVN6_Preview.kicad_mod",
         "SmartDB.pretty/Jack_3.5mm_SJ-3523-SMT_Local.kicad_mod",
         "SmartDB.pretty/USB_A_TE_292303-7_Horizontal_Edge.kicad_mod",
         "smart_db.step", "work/camera_power_review.json"]
width_summary = {}
for t in tracks:
    w = str(float(value(t, 'width')))
    entry = width_summary.setdefault(w, {'segments': 0, 'length_mm': 0})
    entry['segments'] += 1
    entry['length_mm'] += math.dist(xy(t, 'start'), xy(t, 'end'))
for entry in width_summary.values(): entry['length_mm'] = round(entry['length_mm'], 3)
load_tracks = [t for t in tracks if value(t, 'net') in ['LOAD_IN', 'LOAD_OUT']]
assert load_tracks and all(float(value(t, 'width')) >= 1 for t in load_tracks)
assert not any(value(v, 'net') in ['LOAD_IN', 'LOAD_OUT'] for v in children(board, 'via'))
report = {
    "recorded_at": datetime.now(timezone.utc).isoformat(),
    "milestone": "Full board routed, including J6 USB-A fused 5 V output for external ESP32-CAM-MB",
    "kicad_version": drc["kicad_version"],
    "erc_violations": erc_count,
    "drc_violations": len(drc["violations"]),
    "unconnected_items": len(drc["unconnected_items"]),
    "schematic_parity_issues": len(drc["schematic_parity"]),
    "clearance_rules_and_exclusions_unchanged": True,
    "camera_addition_preserves_original_copper_and_placements": True,
    "requested_preferred_widths_mm": {'Default': .3, 'Power': .6, 'Supply': .75, 'Load': 1.0},
    "actual_widths_mm": width_summary,
    "load_routes_minimum_1mm_without_vias": True,
    "inner_ground_planes_preserved": True,
    "four_layer_antenna_keepout_preserved": True,
    "connector_label_net_checks": expected,
    "completed_nets": sorted(completed),
    "track_count": len(tracks),
    "via_count": len(children(board, 'via')),
    "inner_signal_track_count": 0,
    "minimum_track_width_mm": min(float(value(t,'width')) for t in tracks),
    "usb_paths": usb,
    "camera_power_path": camera_path,
    "usb_main_pair": {'width_mm': .2, 'gap_mm': .3, 'reference': 'In2.Cu ground', 'impedance_validated': False},
    "sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files},
}
(WORK / "validation_current.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "sha256"}, indent=2))
