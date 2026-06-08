import streamlit as st
import json, io, os, math, hashlib, tempfile, datetime
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

st.set_page_config(
    page_title="Semantic Embedding | CNC_2_LLM",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #0B1120; color: #F8FAFC; }
    h1, h2, h3 { color: #F8FAFC; font-weight: 700; }
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; margin: 16px 0; }
    .kpi-card { background: #111827; border: 1px solid #1E293B; border-radius: 10px; padding: 16px; }
    .kpi-card.t1 { border-left: 3px solid #10B981; }
    .kpi-card.t2 { border-left: 3px solid #F59E0B; }
    .kpi-value { font-size: 26px; font-weight: 800; color: #10B981; }
    .kpi-value-sm { font-size: 22px; font-weight: 800; color: #F59E0B; }
    .kpi-label { font-size: 11px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }
    .kpi-sub { font-size: 12px; color: #9CA3AF; margin-top: 2px; }
    .hash-box { background: #0F172A; border: 1px solid #1E293B; border-radius: 6px; padding: 8px 12px; font-family: monospace; font-size: 11px; color: #94A3B8; word-break: break-all; }
    .tier-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
    .tier-badge.t1 { background: #064E3B; color: #10B981; }
    .tier-badge.t2 { background: #451A03; color: #F59E0B; }
    .download-section { margin-top: 24px; padding: 16px; background: #111827; border-radius: 10px; border: 1px solid #1E293B; }
    .section-header { font-size: 14px; font-weight: 700; color: #94A3B8; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center; margin-bottom:2px;'>Sémantický Embedding</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#6B7280; font-size:13px;'>Drag & drop DXF → KPI + PNG + LLM prompt artifacts</p>", unsafe_allow_html=True)

# ── Helper functions (must be defined before UI logic) ──

def _render_png_bytes(entities, semantic, tool_config):
    try:
        from dxf_geometry_indexer_v2 import _VIZ_COLORS, _ACI_COLOR_NAMES
    except Exception:
        return None

    fig, ax = plt.subplots(figsize=(19.2, 10.8), facecolor="#1E293B")
    ax.set_facecolor("#0F172A")
    seen_colors = set()

    for entity in entities:
        verts = entity.get("vertices", [])
        if not verts or len(verts) < 2:
            continue
        color_idx = entity.get("color_index", 7)
        seen_colors.add(color_idx)
        color = _VIZ_COLORS.get(color_idx, "#64748B")
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        ax.plot(xs, ys, color=color, linewidth=0.9, alpha=0.85)

    if semantic:
        zones = semantic.get("zones", [])
        for z in zones:
            yr = z.get("y_range_mm", [])
            if len(yr) >= 2:
                ax.axhline(y=yr[0], color="#F59E0B", linewidth=0.8, linestyle=":", alpha=0.6)
                ax.axhline(y=yr[1], color="#F59E0B", linewidth=0.8, linestyle=":", alpha=0.6)

    # Legend
    legend_patches = []
    shown = set()
    for ci in sorted(seen_colors):
        color = _VIZ_COLORS.get(ci, "#64748B")
        name = _ACI_COLOR_NAMES.get(ci, f"ACI {ci}")
        if tool_config and str(ci) in tool_config.get("aci_color_mapping", {}):
            tc = tool_config["aci_color_mapping"][str(ci)]
            ct = tc.get("cutter_type", "")
            label = f"{name} ({ct})"
        else:
            label = name
        if label not in shown:
            import matplotlib.lines as mlines
            legend_patches.append(mlines.Line2D([0], [0], color=color, linewidth=2, label=label))
            shown.add(label)

    if legend_patches:
        ax.legend(handles=legend_patches, loc="upper right", fontsize=8,
                 facecolor="#1E293B", edgecolor="#334155", labelcolor="#F8FAFC")

    ax.set_aspect('equal', 'box')
    ax.invert_yaxis()
    ax.tick_params(colors="#94A3B8")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.set_xlabel("X (mm)", color="#94A3B8")
    ax.set_ylabel("Y (mm)", color="#94A3B8")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, facecolor="#1E293B")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _build_json_output(result, file_path, fname, file_hash, timestamp):
    out = dict(result)
    out["semantic_embedding"] = {
        "source_file": file_path,
        "file_name": fname,
        "md5": file_hash,
        "timestamp": timestamp,
        "description": "Deterministic geometric data ready for multimodal LLM semantic embedding"
    }
    return json.dumps(out, indent=2, ensure_ascii=False)


def _build_ml_csv(mfv):
    if not mfv:
        return "No ML vector data"
    keys = sorted(mfv.keys())
    import csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(keys)
    w.writerow([mfv.get(k, "") for k in keys])
    return buf.getvalue()


def _build_llm_prompt(result, file_path, fname, file_hash, png_bytes, layer_card):
    sb = result["spatial_bounds"]
    ts = result["topology_stats"]
    eg = result.get("entity_graph", {})
    egf = eg.get("graph_features", {})
    eg_stat = eg.get("edge_statistics", {})
    sem = result.get("semantic_analysis", {}) or {}
    mfv = result.get("ml_feature_vector_global", {})
    ta = sem.get("tool_assignments", {})

    aci_colors = sorted(set(e.get("color_index", 0) for e in result.get("entities", [])))

    zs = sem.get("zones", [])
    zone_desc = "\n".join(f"  - {z.get('zone_id', '?')}: {z.get('zone_type', '?')}, {z.get('entity_count', 0)} entit, "
                          f"rozteč {z.get('spacing_mean_mm', 'N/A')} mm, regularity={z.get('regularity_score', 0)}"
                          for z in zs) if zs else "  (žádné zóny)"

    t1_keys = ['entity_count', 'closed_loop_count', 'open_path_count', 'total_vertices',
               'total_length_mm', 'total_sharp_corners', 'total_direction_changes',
               'total_tac_rad', 'tac_per_meter', 'graph_connected_components',
               'v_slot_entity_count', 'v_slot_double_pass_length_mm',
               'head_rotation_count', 'vibrate_cutter_length_mm']
    ml_high_snr = {k: mfv.get(k, 'CHYBÍ') for k in t1_keys if k in mfv}

    prompt = f"""# SEMANTIC EMBEDDING — Deterministic Data Audit

## SOURCE
- File: {file_path}
- File Name: {fname}
- MD5: {file_hash}
- Indexer Version: {result.get('indexer_version', '?')}
- DXF Version: {result.get('metadata', {}).get('dxf_version', '?')}

## 1. PROSTOROVÝ LAYOUT
- Canvas: {sb['global_bbox_mm'][2]-sb['global_bbox_mm'][0]:.0f} × {sb['global_bbox_mm'][3]-sb['global_bbox_mm'][1]:.0f} mm
- Canvas Area: {sb['canvas_area_mm2']/1e6:.3f} m²
- Entity Count: {sb['entity_count']}
- Closed loops: {ts['total_closed_loops']} / Open paths: {ts['total_open_paths']}
- Layer count: {sb['layer_count']}
- Spatial clusters: {ts['spatial_clusters']}
- Max nesting depth: {ts['max_nesting_depth']}
- Distinct shape patterns: {ts['distinct_shape_patterns']}

## 2. BAREVNÁ MAPA
- ACI Color Indexy: {', '.join(str(c) for c in aci_colors)}

## 3. NUMERICKÁ FAKTA — Geometrie
- Total Path Length: {sb['total_path_length_mm']:.1f} mm = {sb['total_path_length_mm']/1000:.2f} m
- Total Vertices: {ts['total_vertices']}
- Mean segment length: {ts['global_mean_segment_length_mm']:.1f} mm
- Point density: {ts['point_density_per_meter']:.1f} pts/m
- Closed ratio: {ts['closed_ratio']:.3f}

## 4. NUMERICKÁ FAKTA — Graf
- Nodes: {eg.get('node_count', '?')}
- Edges — Adjacency: {eg_stat.get('adjacency', '?')}
- Edges — Containment: {eg_stat.get('containment', '?')}
- Edges — Intersection: {eg_stat.get('intersection_bbox_overlaps', '?')}
- Edges — Proximity: {eg_stat.get('proximity', '?')}
- Connected components: {egf.get('connected_components', '?')}
- Max degree: {egf.get('max_degree', '?')}
- Graph diameter: {egf.get('graph_diameter', '?')}

## 5. SÉMANTICKÁ ANALÝZA
- Panel type: {sem.get('panel_type', '?')}
- Tool conflict: {sem.get('tool_conflict_detected', False)}
- Tool conflict IDs: {sem.get('tool_conflict_entity_ids', [])}
- Zones:
{zone_desc}

## 6. TOOL ASSIGNMENTS (deterministické — z ACI mappingu)
{json.dumps(ta, indent=2, ensure_ascii=False)}

## 7. CUTTING TIME
{json.dumps(sem.get('cutting_time_estimate', {}), indent=2, ensure_ascii=False)}

## 8. ML VECTOR — Vysoké SNR Featury (Tier 1)
{json.dumps(ml_high_snr, indent=2, ensure_ascii=False)}

## 9. LAYER CARD — Per-Color Agregace
{json.dumps({k: {sk: str(sv) for sk, sv in v.items() if sk in ('color_index','color_name','entity_count','total_length_mm','point_density_per_meter','closed_count','open_count','is_mapped')} for k, v in layer_card.get('colors', {}).items()}, indent=2, ensure_ascii=False)}

## INSTRUCTION for Multimodal LLM:
You are analyzing a DXF CNC drawing rendered as a 2D PNG visualization.
Use the numerical data ABOVE as ground truth.
Describe what you SEE in the PNG — spatial layout, color patterns,
entity distribution, zones, anomalies.
DO NOT infer. DO NOT assign tools. DO NOT estimate time.
Only describe observable facts that are directly supported by the
numerical data above or visible in the PNG.
"""
    return prompt


# ── UI LOGIC ──

uploaded_file = st.file_uploader("Přetáhněte .dxf soubor", type=["dxf"], label_visibility="collapsed")

if uploaded_file is None:
    st.markdown("""
    <div style='text-align:center; color:#374151; margin-top:80px; padding:40px;'>
        <p style='font-size:60px;'>└✦┘</p>
        <p style='font-size:16px;'>Přetáhněte DXF soubor pro analýzu</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

file_bytes = uploaded_file.getvalue()

with st.spinner("Indexuji geometrii + renderuji vizualizaci..."):
    import sys
    src_dir = str(Path(__file__).resolve().parent)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from dxf_geometry_indexer_v2 import index_dxf, VERSION, _ACI_COLOR_NAMES, _VIZ_COLORS

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    config_path = Path(src_dir) / "dxf_tool_config.json"
    tool_cfg = None
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as cf:
                tool_cfg = json.load(cf)
        except Exception:
            pass

    result = index_dxf(Path(tmp_path), tool_cfg, keep_vertices=True)
    os.unlink(tmp_path)

    if result is None:
        st.error("Soubor neobsahuje měřitelnou geometrii.")
        st.stop()

    fname = uploaded_file.name
    file_hash = hashlib.md5(file_bytes).hexdigest()
    file_path = str(Path(tmp_path).resolve())
    timestamp = datetime.datetime.now().isoformat(timespec='seconds')

    sb = result["spatial_bounds"]
    ts = result["topology_stats"]
    meta = result["metadata"]
    entities = result.get("entities", [])
    sem = result.get("semantic_analysis", {}) or {}
    mfv = result.get("ml_feature_vector_global", {})
    lc = result.get("layer_card", {}) or {}
    eg = result.get("entity_graph", {})
    egf = eg.get("graph_features", {})

    png_bytes = _render_png_bytes(entities, sem, tool_cfg)

st.markdown("---")

# ── KPI ROW ──
st.markdown("<p class='section-header'>TIER 1 — Primární prediktory cutting time</p>", unsafe_allow_html=True)

ta = sem.get("tool_assignments", {})
vslot_len = ta.get("v_slot_45deg", {}).get("double_pass_length_mm", 0)
vibr_len = ta.get("vibrate_cutter_0deg", {}).get("total_length_mm", 0)
rot_count = ta.get("v_slot_45deg", {}).get("head_rotations", 0)
sharp_c = sum(e["complexity"]["sharp_corners_count"] for e in entities)
dir_ch = sum(e["complexity"]["direction_changes"] for e in entities)
has_conflict = sem.get("tool_conflict_detected", False)
canvas_m2 = sb["canvas_area_mm2"] / 1e6

st.markdown(f"""
<div class='kpi-grid'>
  <div class='kpi-card t1'>
    <div class='kpi-value'>{sb['total_path_length_mm']/1000:.1f} m</div>
    <div class='kpi-label'>Total Path Length <span class='tier-badge t1'>T1</span></div>
    <div class='kpi-sub'>Čitatel T = L/v</div>
  </div>
  <div class='kpi-card t1'>
    <div class='kpi-value'>{sb['entity_count']}</div>
    <div class='kpi-label'>Entity Count <span class='tier-badge t1'>T1</span></div>
    <div class='kpi-sub'>Plunge overhead násobič</div>
  </div>
  <div class='kpi-card t1'>
    <div class='kpi-value'>{ts['total_vertices']}</div>
    <div class='kpi-label'>Total Vertices <span class='tier-badge t1'>T1</span></div>
    <div class='kpi-sub'>Corner slowdown násobič</div>
  </div>
  <div class='kpi-card t1'>
    <div class='kpi-value'>{ts['total_closed_loops']} / {ts['total_open_paths']}</div>
    <div class='kpi-label'>Closed / Open <span class='tier-badge t1'>T1</span></div>
    <div class='kpi-sub'>Tool split — vibrate / V-slot</div>
  </div>
  <div class='kpi-card t1'>
    <div class='kpi-value'>{vslot_len/1000:.1f} m</div>
    <div class='kpi-label'>V-Slot Double-Pass <span class='tier-badge t1'>T1</span></div>
    <div class='kpi-sub'>Největší faktor variance času</div>
  </div>
  <div class='kpi-card t1'>
    <div class='kpi-value'>{vibr_len/1000:.1f} m</div>
    <div class='kpi-label'>Vibrate Cutter Length <span class='tier-badge t1'>T1</span></div>
    <div class='kpi-sub'>Druhá složka času</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<p class='section-header' style='margin-top:20px;'>TIER 2 — Feature engineering & speed modulation</p>", unsafe_allow_html=True)

tac_sum = round(sum(e.get("tac_rad", 0) for e in entities), 2)
ct = sem.get("cutting_time_estimate", {})
zone_count = len(sem.get("zones", []))
aci_colors = sorted(set(e.get("color_index", 0) for e in entities))

st.markdown(f"""
<div class='kpi-grid'>
  <div class='kpi-card t2'>
    <div class='kpi-value-sm'>{tac_sum:.1f} rad</div>
    <div class='kpi-label'>Total TAC <span class='tier-badge t2'>T2</span></div>
    <div class='kpi-sub'>Speed density modulation</div>
  </div>
  <div class='kpi-card t2'>
    <div class='kpi-value-sm'>{sharp_c}</div>
    <div class='kpi-label'>Sharp Corners <span class='tier-badge t2'>T2</span></div>
    <div class='kpi-sub'>Každý +0.05s overhead</div>
  </div>
  <div class='kpi-card t2'>
    <div class='kpi-value-sm'>{dir_ch}</div>
    <div class='kpi-label'>Direction Changes <span class='tier-badge t2'>T2</span></div>
    <div class='kpi-sub'>Rotation overhead</div>
  </div>
  <div class='kpi-card t2'>
    <div class='kpi-value-sm'>{rot_count}</div>
    <div class='kpi-label'>Head Rotations <span class='tier-badge t2'>T2</span></div>
    <div class='kpi-sub'>1.5s každá</div>
  </div>
  <div class='kpi-card t2'>
    <div class='kpi-value-sm'>{ts['spatial_clusters']}</div>
    <div class='kpi-label'>Spatial Clusters <span class='tier-badge t2'>T2</span></div>
    <div class='kpi-sub'>Between-cluster traverse</div>
  </div>
  <div class='kpi-card t2'>
    <div class='kpi-value-sm'>{ts['point_density_per_meter']:.1f}</div>
    <div class='kpi-label'>Point Density (pts/m) <span class='tier-badge t2'>T2</span></div>
    <div class='kpi-sub'>Speed density lookup</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 2D VIZUALIZACE ──
st.markdown("<p class='section-header' style='margin-top:24px;'>2D Vizualizace</p>", unsafe_allow_html=True)

col_viz, col_info = st.columns([2, 1])

with col_viz:
    if png_bytes:
        st.image(png_bytes, caption=f"{fname} — 1920×1080", use_column_width=True)
    else:
        st.warning("Matplotlib není k dispozici pro render PNG.")

with col_info:
    st.markdown("**📋 Metadata**")
    st.markdown(f"""
| Položka | Hodnota |
|---|---|
| Verze indexeru | {VERSION} |
| DXF verze | {meta.get('dxf_version', '?')} |
| Canvas | {sb['global_bbox_mm'][2]-sb['global_bbox_mm'][0]:.0f} × {sb['global_bbox_mm'][3]-sb['global_bbox_mm'][1]:.0f} mm |
| Canvas plocha | {canvas_m2:.3f} m² |
| Počet vrstev | {sb['layer_count']} |
| Nesting depth | {ts['max_nesting_depth']} |
| CC count | {egf.get('connected_components', '?')} |
| Panel type | {sem.get('panel_type', '?')} |
| Tool conflict | {'⚠️ ANO' if has_conflict else '✅ Ne'} |
| ACI barvy | {', '.join(str(c) for c in aci_colors)} |
""")

    st.markdown("**🔑 Hash**")
    st.markdown(f"<div class='hash-box'>{file_hash}</div>", unsafe_allow_html=True)

# ── DOWNLOAD SECTION ──
st.markdown("<p class='section-header' style='margin-top:24px;'>Stáhnout artefakty</p>", unsafe_allow_html=True)

stem = Path(fname).stem

# Build outputs
json_str = _build_json_output(result, file_path, fname, file_hash, timestamp)
csv_str = _build_ml_csv(mfv)
txt_str = _build_llm_prompt(result, file_path, fname, file_hash, png_bytes, lc)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.download_button("📦 JSON", json_str, f"{stem}_index.json", "JSON — full deterministic data", type="primary")
with col2:
    st.download_button("📊 CSV (ML vector)", csv_str, f"{stem}_ml_vector.csv", "CSV — 55+ ML featů")
with col3:
    if png_bytes:
        st.download_button("🖼 PNG (2D Viz)", png_bytes, f"{stem}_2d.png", "PNG — 1920×1080 vizualizace")
with col4:
    st.download_button("📝 TXT (LLM Prompt)", txt_str, f"{stem}_embedding_prompt.txt", "TXT — strukturovaný prompt pro multimodal LLM")

# ── PROMPT PREVIEW ──
with st.expander("🔍 Náhled LLM promptu", expanded=False):
    st.code(txt_str[:6000], language="markdown")
    if len(txt_str) > 6000:
        st.caption(f"... a {len(txt_str)-6000} dalších znaků")



