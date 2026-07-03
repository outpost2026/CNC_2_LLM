import streamlit as st
import json, io, os, math, hashlib, tempfile, datetime, csv
from pathlib import Path
from collections import defaultdict

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dxf.indexer import DxfIndexer
from dxf.config import VERSION, ACI_COLOR_NAMES, VIZ_COLORS

st.set_page_config(
    page_title="DXF Indexer | Dev Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Dark theme CSS ──
st.markdown(
    """
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    h1, h2, h3, h4 { font-family: 'Inter', sans-serif; font-weight: 700; color: #F8FAFC; }
    .stTabs [data-baseweb="tab-list"] { gap: 14px; }
    .stTabs [data-baseweb="tab"] { color: #94A3B8; font-weight: 600; font-size: 13px; }
    .stTabs [aria-selected="true"] { color: #10B981 !important; }
    .stButton > button { background-color: #10B981; color: #0F172A; font-weight: 700; border: none; border-radius: 8px; }
    .stDownloadButton > button { background-color: #10B981; color: #0F172A; font-weight: 700; border: none; border-radius: 8px; }
    .metric-card { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 20px 16px; text-align: center; }
    .metric-value { font-size: 24px; font-weight: 800; color: #10B981; }
    .metric-value-sm { font-size: 18px; font-weight: 800; color: #F59E0B; }
    .metric-value-blue { font-size: 18px; font-weight: 800; color: #3B82F6; }
    .metric-label { font-size: 11px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.04em; }
    .yield-bar { height: 8px; background: #334155; border-radius: 4px; overflow: hidden; margin: 8px 0; }
    .yield-fill { height: 100%; background: linear-gradient(90deg, #10B981, #3B82F6); border-radius: 4px; }
    .hash-box { background: #0F172A; border: 1px solid #1E293B; border-radius: 6px; padding: 8px 12px; font-family: monospace; font-size: 11px; color: #94A3B8; word-break: break-all; }
    .section-header { font-size: 14px; font-weight: 700; color: #94A3B8; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
    .tier-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
    .tier-badge.t1 { background: #064E3B; color: #10B981; }
    .tier-badge.t2 { background: #451A03; color: #F59E0B; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    "<h1 style='text-align: center; margin-bottom: 2px;'>DXF Geometry Indexer</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; color: #94A3B8; font-size: 14px;'>Dev Dashboard — Semantic Analysis, Embedding & RAG Backend</p>",
    unsafe_allow_html=True,
)


def _render_png_bytes(entities, semantic, tool_config):
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.lines as mlines
    except ImportError:
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
        color = VIZ_COLORS.get(color_idx, "#64748B")
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        ax.plot(xs, ys, color=color, linewidth=0.9, alpha=0.85)
    if semantic:
        zones = semantic.get("zones", [])
        for z in zones:
            yr = z.get("y_range_mm", [])
            if len(yr) >= 2:
                ax.axhline(
                    y=yr[0], color="#F59E0B", linewidth=0.8, linestyle=":", alpha=0.6
                )
                ax.axhline(
                    y=yr[1], color="#F59E0B", linewidth=0.8, linestyle=":", alpha=0.6
                )
    legend_patches = []
    shown = set()
    for ci in sorted(seen_colors):
        color = VIZ_COLORS.get(ci, "#64748B")
        name = ACI_COLOR_NAMES.get(ci, f"ACI {ci}")
        if tool_config and str(ci) in tool_config.get("aci_color_mapping", {}):
            tc = tool_config["aci_color_mapping"][str(ci)]
            ct = tc.get("cutter_type", "")
            label = f"{name} ({ct})"
        else:
            label = name
        if label not in shown:
            legend_patches.append(
                mlines.Line2D([0], [0], color=color, linewidth=2, label=label)
            )
            shown.add(label)
    if legend_patches:
        ax.legend(
            handles=legend_patches,
            loc="upper right",
            fontsize=8,
            facecolor="#1E293B",
            edgecolor="#334155",
            labelcolor="#F8FAFC",
        )
    ax.set_aspect("equal", "box")
    ax.invert_yaxis()
    ax.tick_params(colors="#94A3B8")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.set_xlabel("X (mm)", color="#94A3B8")
    ax.set_ylabel("Y (mm)", color="#94A3B8")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor="#1E293B")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _build_llm_prompt(result, fname, file_hash, png_bytes, layer_card):
    sb = result["spatial_bounds"]
    ts = result["topology_stats"]
    eg = result.get("entity_graph", {})
    egf = eg.get("graph_features", {})
    eg_stat = eg.get("edge_statistics", {})
    sem = result.get("semantic_analysis", {}) or {}
    mfv = result.get("ml_feature_vector_global", {})
    ta = sem.get("tool_assignments", {})
    aci_colors = sorted(
        set(e.get("color_index", 0) for e in result.get("entities", []))
    )
    zs = sem.get("zones", [])
    zone_desc = (
        "\n".join(
            f"  - {z.get('zone_id', '?')}: {z.get('zone_type', '?')}, {z.get('entity_count', 0)} entit, "
            f"roztec {z.get('spacing_mean_mm', 'N/A')} mm, regularity={z.get('regularity_score', 0)}"
            for z in zs
        )
        if zs
        else "  (zadne zony)"
    )
    t1_keys = [
        "entity_count",
        "closed_loop_count",
        "open_path_count",
        "total_vertices",
        "total_length_mm",
        "total_sharp_corners",
        "total_direction_changes",
        "total_tac_rad",
        "tac_per_meter",
        "graph_connected_components",
        "v_slot_entity_count",
        "v_slot_double_pass_length_mm",
        "head_rotation_count",
        "vibrate_cutter_length_mm",
    ]
    ml_high_snr = {k: mfv.get(k, "CHYBI") for k in t1_keys if k in mfv}
    prompt = f"""# SEMANTIC EMBEDDING — Deterministic Data Audit

## SOURCE
- File: {fname}
- MD5: {file_hash}
- Indexer Version: {result.get("indexer_version", "?")}
- DXF Version: {result.get("metadata", {}).get("dxf_version", "?")}

## 1. PROSTOROVY LAYOUT
- Canvas: {sb["global_bbox_mm"][2] - sb["global_bbox_mm"][0]:.0f} x {sb["global_bbox_mm"][3] - sb["global_bbox_mm"][1]:.0f} mm
- Canvas Area: {sb["canvas_area_mm2"] / 1e6:.3f} m2
- Entity Count: {sb["entity_count"]}
- Closed loops: {ts["total_closed_loops"]} / Open paths: {ts["total_open_paths"]}
- Layer count: {sb["layer_count"]}
- Spatial clusters: {ts["spatial_clusters"]}
- Max nesting depth: {ts["max_nesting_depth"]}
- Distinct shape patterns: {ts["distinct_shape_patterns"]}

## 2. BAREVNA MAPA
- ACI Color Indexy: {", ".join(str(c) for c in aci_colors)}

## 3. NUMERICKA FAKTA — Geometrie
- Total Path Length: {sb["total_path_length_mm"]:.1f} mm = {sb["total_path_length_mm"] / 1000:.2f} m
- Total Vertices: {ts["total_vertices"]}
- Mean segment length: {ts["global_mean_segment_length_mm"]:.1f} mm
- Point density: {ts["point_density_per_meter"]:.1f} pts/m
- Closed ratio: {ts["closed_ratio"]:.3f}

## 4. NUMERICKA FAKTA — Graf
- Nodes: {eg.get("node_count", "?")}
- Edges — Adjacency: {eg_stat.get("adjacency", "?")}
- Edges — Containment: {eg_stat.get("containment", "?")}
- Edges — Intersection: {eg_stat.get("intersection_bbox_overlaps", "?")}
- Edges — Proximity: {eg_stat.get("proximity", "?")}
- Connected components: {egf.get("connected_components", "?")}
- Max degree: {egf.get("max_degree", "?")}
- Graph diameter: {egf.get("graph_diameter", "?")}

## 5. SEMANTICKA ANALYZA
- Panel type: {sem.get("panel_type", "?")}
- Tool conflict: {sem.get("tool_conflict_detected", False)}
- Zones:
{zone_desc}

## 6. TOOL ASSIGNMENTS
{json.dumps(ta, indent=2, ensure_ascii=False)}

## 7. CUTTING TIME
{json.dumps(sem.get("cutting_time_estimate", {}), indent=2, ensure_ascii=False)}

## 8. ML VECTOR — High SNR Features
{json.dumps(ml_high_snr, indent=2, ensure_ascii=False)}

## 9. LAYER CARD
{json.dumps({k: {sk: str(sv) for sk, sv in v.items() if sk in ("color_index", "color_name", "entity_count", "total_length_mm", "point_density_per_meter", "closed_count", "open_count", "is_mapped")} for k, v in layer_card.get("colors", {}).items()}, indent=2, ensure_ascii=False)}
"""
    return prompt


def _run_index(uploaded_file_bytes, fname):
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        tmp.write(uploaded_file_bytes)
        tmp_path = tmp.name
    src_dir = str(Path(__file__).resolve().parent)
    config_path = Path(src_dir) / "dxf_tool_config.json"
    tool_cfg = None
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as cf:
                tool_cfg = json.load(cf)
        except Exception:
            pass
    indexer = DxfIndexer(tool_config=tool_cfg, keep_vertices=True)
    result = indexer.index(Path(tmp_path))
    os.unlink(tmp_path)
    return result


# ── FILE UPLOAD ──
uploaded_file = st.file_uploader(
    "Pretahnete .dxf soubor", type=["dxf"], label_visibility="collapsed"
)

if uploaded_file is None:
    col_i1, col_i2, col_i3 = st.columns([1, 2, 1])
    with col_i2:
        st.markdown(
            """
        <div style="text-align: center; padding: 40px 0; color: #94A3B8;">
            <p style="font-size: 60px; margin-bottom: 0;">&#8999;&#10022;&#8999;</p>
            <p style="font-size: 16px; margin-top: 10px;">Pretahnete DXF soubor pro analyzu</p>
            <p style="font-size: 13px;">Indexer extrahuje: entitni graf, Boolean operace, geometricke constrainty,<br>
            semantickou analyzu, CNC tool assign, ML vektor (55+ feat), LLM embedding prompt</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
        demo_path = Path(__file__).resolve().parent.parent / "demo_data"
        if not demo_path.exists():
            demo_path = Path(__file__).resolve().parent / "demo_data"
        if demo_path.exists():
            demos = sorted(demo_path.glob("*.dxf"))
            if demos:
                st.markdown("#### Demo soubory")
                for d in demos:
                    with open(d, "rb") as f:
                        demo_bytes = f.read()
                    size_kb = len(demo_bytes) / 1024
                    if st.button(
                        f"{d.name} ({size_kb:.0f} KB)",
                        key=d.name,
                        use_container_width=True,
                    ):
                        st.session_state["demo_file_bytes"] = demo_bytes
                        st.session_state["demo_file_name"] = d.name
                        st.rerun()
    if "demo_file_bytes" in st.session_state:
        uploaded_file = io.BytesIO(st.session_state["demo_file_bytes"])
        fname = st.session_state["demo_file_name"]
        del st.session_state["demo_file_bytes"]
        del st.session_state["demo_file_name"]
        st.rerun()
    st.stop()

if isinstance(uploaded_file, io.BytesIO):
    file_bytes = uploaded_file.getvalue()
    fname = st.session_state.get("demo_file_name", "upload.dxf")
else:
    file_bytes = uploaded_file.getvalue()
    fname = uploaded_file.name

file_hash = hashlib.md5(file_bytes).hexdigest()

with st.spinner("Indexuji geometrii + renderuji vizualizaci..."):
    result = _run_index(file_bytes, fname)

if result is None:
    st.error("Soubor neobsahuje meritelnou geometrii.")
    st.stop()

sb = result["spatial_bounds"]
ts = result["topology_stats"]
eg = result.get("entity_graph", {})
egf = eg.get("graph_features", {})
ba = result.get("boolean_analysis", {}) or {}
gc = result.get("geometric_constraints", {}) or {}
rag = result.get("rag_queries", {})
mfv = result.get("ml_feature_vector_global", {})
sem = result.get("semantic_analysis", {}) or {}
meta = result["metadata"]
entities = result.get("entities", [])
lc = result.get("layer_card", {}) or {}
png_bytes = _render_png_bytes(entities, sem, None)

# ── KPI ROW ──
st.markdown(
    "<p class='section-header'>TIER 1 — primarni prediktory</p>", unsafe_allow_html=True
)

ta = sem.get("tool_assignments", {})
vslot_len = ta.get("v_slot_45deg", {}).get("double_pass_length_mm", 0)
vibr_len = ta.get("vibrate_cutter_0deg", {}).get("total_length_mm", 0)
rot_count = ta.get("v_slot_45deg", {}).get("head_rotations", 0)
sharp_c = sum(e["complexity"]["sharp_corners_count"] for e in entities)
dir_ch = sum(e["complexity"]["direction_changes"] for e in entities)
canvas_m2 = sb["canvas_area_mm2"] / 1e6

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">Celkova draha</div><div class="metric-value">{sb["total_path_length_mm"] / 1000:.1f} m</div></div>""",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">Entit</div><div class="metric-value">{sb["entity_count"]}</div></div>""",
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">Closed / Open</div><div class="metric-value">{ts["total_closed_loops"]} / {ts["total_open_paths"]}</div></div>""",
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">V-Slot (dvojity)</div><div class="metric-value">{vslot_len / 1000:.1f} m</div></div>""",
        unsafe_allow_html=True,
    )
with c5:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">Vibrate</div><div class="metric-value">{vibr_len / 1000:.1f} m</div></div>""",
        unsafe_allow_html=True,
    )
with c6:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">Rozloha</div><div class="metric-value">{canvas_m2:.3f} m2</div></div>""",
        unsafe_allow_html=True,
    )

st.markdown(
    "<p class='section-header' style='margin-top:16px;'>TIER 2 — featur engineering</p>",
    unsafe_allow_html=True,
)

tac_sum = round(sum(e.get("tac_rad", 0) for e in entities), 2)
ct = sem.get("cutting_time_estimate", {})

d1, d2, d3, d4, d5, d6 = st.columns(6)
with d1:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">TAC (rad)</div><div class="metric-value-sm">{tac_sum:.1f}</div></div>""",
        unsafe_allow_html=True,
    )
with d2:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">Sharp corners</div><div class="metric-value-sm">{sharp_c}</div></div>""",
        unsafe_allow_html=True,
    )
with d3:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">Direction changes</div><div class="metric-value-sm">{dir_ch}</div></div>""",
        unsafe_allow_html=True,
    )
with d4:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">Graf komponenty</div><div class="metric-value-sm">{egf.get("connected_components", 0)}</div></div>""",
        unsafe_allow_html=True,
    )
with d5:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">Solidity</div><div class="metric-value-sm">{ba.get("solidity", "N/A")}</div></div>""",
        unsafe_allow_html=True,
    )
with d6:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">Min sirka (mm)</div><div class="metric-value-sm">{ba.get("estimated_min_feature_width_mm", 0):.1f}</div></div>""",
        unsafe_allow_html=True,
    )

st.caption(
    f"Verze: V{result.get('indexer_version', VERSION)} | Soubor: {fname} | "
    f"DXF: {meta['dxf_version']} | {meta['file_size_bytes'] / 1024:.1f} KB | MD5: {file_hash[:16]}... | "
    f"Shapely={'OK' if meta['libraries_available'].get('shapely') else 'N/A'} | "
    f"SciPy={'OK' if meta['libraries_available'].get('scipy') else 'N/A'}"
)

# ── TABS ──
tab_graph, tab_bool, tab_rag, tab_layers, tab_viz, tab_sem, tab_ml, tab_prompt = (
    st.tabs(
        [
            "Entity Graph",
            "Boolean Ops",
            "RAG Queries",
            "Layers",
            "2D Viz",
            "Semantic",
            "ML Vector",
            "LLM Prompt",
        ]
    )
)

with tab_graph:
    es = eg.get("edge_statistics", {})
    cg1, cg2 = st.columns(2)
    with cg1:
        st.metric("Adjacency hran (endpoint < 1 mm)", es.get("adjacency", 0))
        st.metric("Containment hran", es.get("containment", 0))
        st.metric("Cycles (containment-based)", egf.get("cycle_count", 0))
    with cg2:
        st.metric(
            "Intersection (bbox overlap)", es.get("intersection_bbox_overlaps", 0)
        )
        st.metric("Proximity hran (>5 mm, <250 mm)", es.get("proximity", 0))
        st.metric("Max degree", egf.get("max_degree", 0))
    if egf.get("laplacian_eigenvalues_top10"):
        st.markdown("#### Spektrum Laplacianu grafu")
        import numpy as np

        st.line_chart(
            {"lambda": egf["laplacian_eigenvalues_top10"]}, use_container_width=True
        )
    edges = eg.get("edges", {})
    if edges.get("adjacency") or edges.get("containment"):
        st.markdown("#### Top 50 hran")
        edge_rows = []
        for t in ["adjacency", "containment"]:
            for e in edges.get(t, [])[:50]:
                dist = e.get("distance_mm", e.get("_type", ""))
                edge_rows.append(
                    {
                        "Edge": t,
                        "Source": e.get("source") or e.get("child"),
                        "Target": e.get("target") or e.get("parent"),
                        "Detail": str(dist),
                    }
                )
        if edge_rows:
            import pandas as pd

            st.dataframe(
                pd.DataFrame(edge_rows[:50]), use_container_width=True, hide_index=True
            )

with tab_bool:
    st.markdown("#### Boolean analyza (Shapely)")
    if ba.get("method") == "unavailable":
        st.warning("Shapely neni nainstalovan. pip install shapely")
    elif ba.get("_note"):
        st.info(ba["_note"])
    else:
        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            st.metric("Plocha (mm2)", f"{ba.get('unified_area_mm2', 0):,.0f}")
            st.metric("Delka hranice (mm)", f"{ba.get('boundary_length_mm', 0):,.0f}")
        with bc2:
            st.metric("Convex hull (mm2)", f"{ba.get('convex_hull_area_mm2', 0):,.0f}")
            st.metric("Solidity", f"{ba.get('solidity', 0):.4f}")
        with bc3:
            st.metric("Pocet der", ba.get("num_holes", 0))
            st.metric(
                "Min sirka featur (mm)",
                f"{ba.get('estimated_min_feature_width_mm', 0):.1f}",
            )
        st.markdown("---")
        st.markdown("#### Charakteristika tvaru")
        sol = ba.get("solidity", 0)
        holes = ba.get("num_holes", 0)
        mfw = ba.get("estimated_min_feature_width_mm", 0)
        interpretations = []
        interpretations.append(
            f"- Solidity {sol:.3f}: "
            + (
                "Hladky konvexni tvar"
                if sol > 0.95
                else ("Stredne clenity" if sol > 0.7 else "Vysoce clenity/konkavni")
            )
        )
        interpretations.append(
            f"- Dery: {holes} — "
            + (
                "Bez vnitrnich vyrezu"
                if holes == 0
                else f"{holes} vnitrnich vyrezu/otvoru"
            )
        )
        if mfw > 0:
            interpretations.append(
                f"- Nejuzsi feature: {mfw:.1f} mm — "
                + (
                    "Dostatecne siroke pro standardni nastroj"
                    if mfw > 5
                    else "Uzke prvky — nutny jemny nastroj"
                )
            )
        st.markdown("\n".join(interpretations))

with tab_rag:
    st.markdown("#### RAG-ready dotazy")
    st.info(rag.get("nesting_summary", "N/A"))
    if rag.get("largest_closed_contours"):
        st.markdown("##### Nejvetsi uzavrene kontury")
        import pandas as pd

        st.dataframe(
            pd.DataFrame(rag["largest_closed_contours"]),
            use_container_width=True,
            hide_index=True,
        )
    if rag.get("isolated_features"):
        st.markdown("##### Izolovane featury (>100 mm od sousedu)")
        import pandas as pd

        st.dataframe(
            pd.DataFrame(rag["isolated_features"]),
            use_container_width=True,
            hide_index=True,
        )
    if rag.get("dense_regions"):
        st.markdown("##### Huste regiony (>50 entit/m2)")
        import pandas as pd

        st.dataframe(
            pd.DataFrame(rag["dense_regions"]),
            use_container_width=True,
            hide_index=True,
        )

with tab_layers:
    st.markdown("#### Vrstvy — geometricka statistika")
    layer_rows = []
    for l in result.get("layers", []):
        sc = l["spatial_complexity"]
        layer_rows.append(
            {
                "Vrstva": l["name"],
                "Entit": l["entity_count"],
                "Delka (m)": round(l["total_length_mm"] / 1000, 2),
                "Bodu": l["total_point_count"],
                "Closed %": f"{sc['closed_loop_ratio']:.1%}",
                "Curv. idx": sc["curvature_index"],
                "Sharp": sc["sharp_corners_count"],
                "TAC (rad)": sc.get("total_tac_rad", 0),
                "Arc ratio": f"{sc['arc_ratio']:.1%}",
                "Geo typy": ", ".join(
                    f"{k}:{v}" for k, v in sorted(l.get("geometry_types", {}).items())
                ),
            }
        )
    import pandas as pd

    st.dataframe(pd.DataFrame(layer_rows), use_container_width=True, hide_index=True)
    sg = result.get("shape_groups", [])
    if sg:
        st.markdown("##### Opakujici se tvary")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": s["id"],
                        "Typ": s["type"],
                        "Instances": s["instance_count"],
                        "Delka (mm)": s["length_mm"],
                        "Pomer": s["aspect_ratio"],
                    }
                    for s in sg
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

with tab_viz:
    st.markdown("#### 2D Vizualizace")
    col_viz, col_info = st.columns([2, 1])
    with col_viz:
        if png_bytes:
            st.image(png_bytes, caption=f"{fname} — 1920x1080", use_column_width=True)
        else:
            st.warning("Matplotlib neni k dispozici")
    with col_info:
        st.markdown("**Metadata**")
        aci_colors = sorted(set(e.get("color_index", 0) for e in entities))
        st.markdown(f"""
| Polozka | Hodnota |
|---|---|
| Verze | V{result.get("indexer_version", VERSION)} |
| DXF verze | {meta.get("dxf_version", "?")} |
| Canvas | {sb["global_bbox_mm"][2] - sb["global_bbox_mm"][0]:.0f} x {sb["global_bbox_mm"][3] - sb["global_bbox_mm"][1]:.0f} mm |
| Vrstev | {sb["layer_count"]} |
| Nesting | {ts["max_nesting_depth"]} |
| Panel type | {sem.get("panel_type", "?")} |
| ACI barvy | {", ".join(str(c) for c in aci_colors)} |
""")
        st.markdown(f"<div class='hash-box'>{file_hash}</div>", unsafe_allow_html=True)

with tab_sem:
    st.markdown("#### Semantic Analysis")
    if sem:
        panel_type = sem.get("panel_type", "unknown")
        confidence = sem.get("confidence", "low")
        confidence_color = (
            "#10B981"
            if confidence == "high"
            else ("#F59E0B" if confidence == "medium" else "#EF4444")
        )
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.markdown(
                f"""<div class="metric-card"><div class="metric-label">Panel Type</div><div class="metric-value-sm">{panel_type}</div></div>""",
                unsafe_allow_html=True,
            )
        with sc2:
            st.markdown(
                f"""<div class="metric-card"><div class="metric-label">Confidence</div><div class="metric-value-sm" style="color:{confidence_color};">{confidence}</div></div>""",
                unsafe_allow_html=True,
            )
        with sc3:
            st.markdown(
                f"""<div class="metric-card"><div class="metric-label">Orthogonal</div><div class="metric-value-blue">{"Yes" if sem.get("is_orthogonal") else "No"}</div></div>""",
                unsafe_allow_html=True,
            )
        with sc4:
            st.markdown(
                f"""<div class="metric-card"><div class="metric-label">Has Arcs</div><div class="metric-value-blue">{"Yes" if sem.get("has_arcs_any") else "No"}</div></div>""",
                unsafe_allow_html=True,
            )
        zones = sem.get("zones", [])
        if zones:
            st.markdown("---")
            st.markdown("#### Zone Schema")
            zdf = pd.DataFrame(
                [
                    {
                        "Zone": z["zone_id"],
                        "Type": z["zone_type"],
                        "Entities": z["entity_count"],
                        "Length": f"{z.get('length_mean_mm', 0):.0f}",
                        "Spacing": f"{z.get('spacing_mean_mm', 0):.1f}",
                        "Regularity": f"{z.get('regularity_score', 0):.2f}",
                        "Pattern": z.get("pattern", "?"),
                    }
                    for z in zones
                ]
            )
            st.dataframe(zdf, use_container_width=True, hide_index=True)
        if ta:
            st.markdown("---")
            st.markdown("#### CNC Tool Assignments")
            tdf = pd.DataFrame(
                [
                    {
                        "Tool": tn,
                        "Entities": td.get("entity_count", 0),
                        "Length (m)": f"{td.get('double_pass_length_mm', td.get('total_length_mm', 0)) / 1000:.1f}",
                        "Passes": td.get("passes", 1),
                        "Rotations": td.get("head_rotations", 0),
                    }
                    for tn, td in ta.items()
                ]
            )
            st.dataframe(tdf, use_container_width=True, hide_index=True)
        if ct:
            st.markdown("---")
            st.markdown("#### Cutting Time Estimate")
            total_s = ct.get("total_time_s", 0)
            mins = int(total_s / 60)
            secs = int(total_s % 60)
            tc1, tc2, tc3 = st.columns(3)
            with tc1:
                st.metric(
                    "Vibrate cutter", f"{ct.get('vibrate_cutter_time_s', 0):.1f} s"
                )
                st.metric("V-slot", f"{ct.get('v_slot_time_s', 0):.1f} s")
            with tc2:
                st.metric(
                    "Head rotations", f"{ct.get('head_rotation_overhead_s', 0):.1f} s"
                )
                st.metric("Feed rate", f"{ct.get('config_feed_rate_mmps', 0):.0f} mm/s")
            with tc3:
                st.metric("**Total**", f"**{total_s:.1f} s ({mins}m {secs}s)**")
        my = sem.get("material_yield", {})
        if my:
            st.markdown("---")
            st.markdown("#### Material Yield")
            yl_pct = my.get("yield_percent", 0)
            stock = my.get("stock_plate_mm", [2900, 1220])
            panel = my.get("panel_bbox_mm", [0, 0])
            m1, m2 = st.columns([2, 1])
            with m1:
                st.markdown(
                    f"Panel {panel[0]:.0f} x {panel[1]:.0f} mm ze surove desky {stock[0]:.0f} x {stock[1]:.0f} mm"
                )
                st.markdown(
                    f'<div class="yield-bar"><div class="yield-fill" style="width:{yl_pct}%;"></div></div>',
                    unsafe_allow_html=True,
                )
            with m2:
                st.metric("Vyteznost", f"{yl_pct:.1f}%")
                st.metric(
                    "Odpad",
                    f"{my.get('waste_mm', [0, 0])[0]:.0f} x {my.get('waste_mm', [0, 0])[1]:.0f} mm",
                )
        mf = sem.get("mounting_flap", {})
        if mf.get("detected"):
            st.markdown("---")
            st.markdown("#### Mounting Flap Detected")
            st.info(
                f"Montazni presah: {mf.get('width_mm', 0):.0f} x {mf.get('height_mm', 0):.0f} mm"
            )
        if sem.get("narrative_summary"):
            st.markdown("---")
            st.markdown("#### Narrative Summary")
            st.markdown(
                f"> {sem['narrative_summary'].replace(chr(10), '<br>')}",
                unsafe_allow_html=True,
            )

with tab_ml:
    st.markdown("#### ML-ready feature vector (global aggregate)")
    if mfv:
        import pandas as pd

        st.dataframe(
            pd.DataFrame([{"feature": k, "value": v} for k, v in sorted(mfv.items())]),
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("##### Flat float vector")
        st.code(
            ", ".join(f"{mfv[k]}".rstrip("0").rstrip(".") for k in sorted(mfv.keys()))
        )
    else:
        st.info("Zadne ML featury.")

with tab_prompt:
    st.markdown("#### LLM Embedding Prompt")
    prompt = _build_llm_prompt(result, fname, file_hash, png_bytes, lc)
    st.code(prompt[:8000], language="markdown")

# ── EXPORT ──
st.markdown("---")
st.markdown("#### Export")
stem = Path(fname).stem
json_str = json.dumps(result, indent=2, ensure_ascii=False)
csv_buf = io.StringIO()
if mfv:
    w = csv.writer(csv_buf)
    w.writerow(sorted(mfv.keys()))
    w.writerow([mfv[k] for k in sorted(mfv.keys())])
csv_str = csv_buf.getvalue()

ex1, ex2, ex3, ex4 = st.columns(4)
with ex1:
    st.download_button(
        "JSON (plny)",
        data=json_str,
        file_name=f"{stem}_index.json",
        mime="application/json",
        use_container_width=True,
    )
with ex2:
    if csv_str:
        st.download_button(
            "ML Vector CSV",
            data=csv_str,
            file_name=f"{stem}_ml_vector.csv",
            mime="text/csv",
            use_container_width=True,
        )
with ex3:
    if png_bytes:
        st.download_button(
            "PNG (2D Viz)",
            data=png_bytes,
            file_name=f"{stem}_2d.png",
            mime="image/png",
            use_container_width=True,
        )
with ex4:
    txt = _build_llm_prompt(result, fname, file_hash, png_bytes, lc)
    st.download_button(
        "LLM Prompt TXT",
        data=txt,
        file_name=f"{stem}_embedding_prompt.txt",
        mime="text/plain",
        use_container_width=True,
    )

with st.expander("JSON preview (prvnich 3000 znaku)"):
    st.code(json_str[:3000] + ("..." if len(json_str) > 3000 else ""))
