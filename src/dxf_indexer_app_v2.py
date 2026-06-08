import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import os, io, json, math, tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dxf_geometry_indexer_v2 import resolve_cam_color, LIGHTBURN_CAM_PALETTE

st.set_page_config(
    page_title="DXF Geometry Indexer V2.1 | Dev Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    h1, h2, h3, h4 { font-family: 'Inter', sans-serif; font-weight: 700; color: #F8FAFC; }
    .stTabs [data-baseweb="tab-list"] { gap: 14px; }
    .stTabs [data-baseweb="tab"] { color: #94A3B8; font-weight: 600; font-size: 13px; }
    .stTabs [aria-selected="true"] { color: #10B981 !important; }
    .stButton > button { background-color: #10B981; color: #0F172A; font-weight: 700; border: none; border-radius: 8px; }
    .metric-card { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 20px 16px; text-align: center; }
    .metric-value { font-size: 24px; font-weight: 800; color: #10B981; }
    .metric-value-sm { font-size: 18px; font-weight: 800; color: #F59E0B; }
    .metric-value-blue { font-size: 18px; font-weight: 800; color: #3B82F6; }
    .metric-label { font-size: 11px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.04em; }
    .feature-row { display: flex; flex-wrap: wrap; gap: 6px; }
    .feature-chip { background: #1E293B; border: 1px solid #334155; border-radius: 6px; padding: 6px 12px; font-size: 12px; color: #F8FAFC; white-space: nowrap; }
    .yield-bar { height: 8px; background: #334155; border-radius: 4px; overflow: hidden; margin: 8px 0; }
    .yield-fill { height: 100%; background: linear-gradient(90deg, #10B981, #3B82F6); border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; margin-bottom: 2px;'>📐 DXF Geometry Indexer V2.1</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 14px;'>Dev Dashboard — Semantic Analysis & RAG Backend</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Přetáhněte .dxf soubor", type=["dxf"], label_visibility="collapsed")

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()

    with st.spinner("Indexuji geometrii..."):
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent))

            # Save bytes to temp file
            with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            from dxf_geometry_indexer_v2 import index_dxf

            config_path = Path(__file__).resolve().parent / "dxf_tool_config.json"
            tool_cfg = None
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as cf:
                        tool_cfg = json.load(cf)
                except Exception:
                    pass

            result = index_dxf(Path(tmp_path), tool_cfg)
            os.unlink(tmp_path)

            if result is None:
                st.error("Soubor neobsahuje měřitelnou geometrii.")
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
            indexer_ver = result.get("indexer_version", "2.0.0")

            # ── KPI Row 1 ──
            st.markdown("### Výstup indexeru")
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)

            with c1:
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Entit</div><div class="metric-value">{sb['entity_count']}</div></div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Vrstev</div><div class="metric-value">{sb['layer_count']}</div></div>""", unsafe_allow_html=True)
            with c3:
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Closed / Open</div><div class="metric-value">{ts['total_closed_loops']} / {ts['total_open_paths']}</div></div>""", unsafe_allow_html=True)
            with c4:
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Graf komponent</div><div class="metric-value">{egf.get('connected_components', 0)}</div></div>""", unsafe_allow_html=True)
            with c5:
                sol = ba.get("solidity", "N/A")
                sv = f"{sol:.3f}" if isinstance(sol, float) else str(sol)
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Solidity</div><div class="metric-value-sm">{sv}</div></div>""", unsafe_allow_html=True)
            with c6:
                holes = ba.get("num_holes", "N/A")
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Děr (bool)</div><div class="metric-value-sm">{holes}</div></div>""", unsafe_allow_html=True)
            with c7:
                mfw = ba.get("estimated_min_feature_width_mm", "N/A")
                mfw_s = f"{mfw:.1f}" if isinstance(mfw, float) else str(mfw)
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Min šířka (mm)</div><div class="metric-value-sm">{mfw_s}</div></div>""", unsafe_allow_html=True)
            with c8:
                dr = ts.get("point_density_per_meter", 0)
                st.markdown(f"""<div class="metric-card"><div class="metric-label">Hustota bodů</div><div class="metric-value-sm">{dr:.1f}</div></div>""", unsafe_allow_html=True)

            st.caption(f"Indexer: V{indexer_ver} · DXF: {meta['dxf_version']} · {meta['file_size_bytes']/1024:.1f} KB · MD5: {meta['md5'][:16]}... · Libs: Shapely={'OK' if meta['libraries_available'].get('shapely') else 'N/A'} SciPy={'OK' if meta['libraries_available'].get('scipy') else 'N/A'} GUDHI={'OK' if meta['libraries_available'].get('gudhi') else 'N/A'}")

            # ── TABS ──
            tab_graph, tab_bool, tab_rag, tab_layers, tab_viz, tab_sem, tab_ml = st.tabs([
                "🔗 Entity Graph", "🟩 Boolean Ops", "🔍 RAG Queries",
                "📊 Layers", "📐 2D Viz", "🧠 Semantic", "📈 ML Vector"
            ])

            with tab_graph:
                es = eg.get("edge_statistics", {})
                cg1, cg2 = st.columns(2)
                with cg1:
                    st.metric("Adjacency hran (endpoint < 1 mm)", es.get("adjacency", 0))
                    st.metric("Containment hran", es.get("containment", 0))
                    st.metric("Cycles (containment-based)", egf.get("cycle_count", 0))
                with cg2:
                    st.metric("Intersection (bbox overlap)", es.get("intersection_bbox_overlaps", 0))
                    st.metric("Proximity hran (>5 mm, <250 mm)", es.get("proximity", 0))
                    st.metric("Max degree", egf.get("max_degree", 0))

                if egf.get("laplacian_eigenvalues_top10"):
                    st.markdown("#### Spektrum Laplacianu grafu")
                    import numpy as np
                    eigs = egf["laplacian_eigenvalues_top10"]
                    st.line_chart({"λ": eigs}, use_container_width=True)

                # Adjacency edge list
                edges = eg.get("edges", {})
                if edges.get("adjacency") or edges.get("containment"):
                    st.markdown("#### Top 50 hran")
                    edge_rows = []
                    for t in ["adjacency", "containment"]:
                        for e in edges.get(t, [])[:50]:
                            dist = e.get("distance_mm", e.get("_type", ""))
                            edge_rows.append({"Edge type": t, "Source": e.get("source") or e.get("child"),
                                              "Target": e.get("target") or e.get("parent"), "Detail": str(dist)})
                    if edge_rows:
                        st.dataframe(pd.DataFrame(edge_rows[:50]), use_container_width=True, hide_index=True)

            with tab_bool:
                st.markdown("#### Boolean analýza (Shapely)")
                if ba.get("method") == "unavailable":
                    st.warning("Shapely není nainstalován. `pip install shapely`")
                elif ba.get("_note"):
                    st.info(ba["_note"])
                else:
                    bc1, bc2, bc3 = st.columns(3)
                    with bc1:
                        st.metric("Plocha (mm²)", f"{ba.get('unified_area_mm2', 0):,.0f}")
                        st.metric("Délka hranice (mm)", f"{ba.get('boundary_length_mm', 0):,.0f}")
                    with bc2:
                        st.metric("Convex hull (mm²)", f"{ba.get('convex_hull_area_mm2', 0):,.0f}")
                        st.metric("Solidity", f"{ba.get('solidity', 0):.4f}")
                    with bc3:
                        st.metric("Počet děr", ba.get("num_holes", 0))
                        st.metric("Min šířka featur (mm)", f"{ba.get('estimated_min_feature_width_mm', 0):.1f}")

                    st.markdown("---")
                    st.markdown("#### Charakteristika tvaru")
                    sol = ba.get("solidity", 0)
                    holes = ba.get("num_holes", 0)
                    mfw = ba.get("estimated_min_feature_width_mm", 0)
                    interpretations = []
                    interpretations.append(f"- Solidity {sol:.3f}: " + ("Hladký konvexní tvar" if sol > 0.95 else ("Středně členitý" if sol > 0.7 else "Vysoce členitý/konkávní")))
                    interpretations.append(f"- Děry: {holes} — " + ("Bez vnitřních výřezů" if holes == 0 else f"{holes} vnitřních výřezů/otvorů"))
                    if mfw > 0:
                        interpretations.append(f"- Nejužší feature: {mfw:.1f} mm — " + ("Dostatečně široké pro standardní nástroj" if mfw > 5 else "Úzké prvky — nutný jemný nástroj"))
                    st.markdown("\n".join(interpretations))

            with tab_rag:
                st.markdown("#### RAG-ready dotazy")
                st.info(rag.get("nesting_summary", "N/A"))

                if rag.get("largest_closed_contours"):
                    st.markdown("##### Největší uzavřené kontury")
                    st.dataframe(pd.DataFrame(rag["largest_closed_contours"]), use_container_width=True, hide_index=True)

                if rag.get("isolated_features"):
                    st.markdown("##### Izolované featury (>100 mm od sousedů)")
                    st.dataframe(pd.DataFrame(rag["isolated_features"]), use_container_width=True, hide_index=True)

                if rag.get("dense_regions"):
                    st.markdown("##### Husté regiony (>50 entit/m²)")
                    st.dataframe(pd.DataFrame(rag["dense_regions"]), use_container_width=True, hide_index=True)

            with tab_layers:
                st.markdown("#### Vrstvy — geometrická statistika")
                layer_rows = []
                for l in result.get("layers", []):
                    sc = l["spatial_complexity"]
                    layer_rows.append({
                        "Vrstva": l["name"],
                        "Entit": l["entity_count"],
                        "Délka (m)": round(l["total_length_mm"] / 1000, 2),
                        "Bodů": l["total_point_count"],
                        "Closed %": f"{sc['closed_loop_ratio']:.1%}",
                        "Curv. idx": sc["curvature_index"],
                        "Sharp corners": sc["sharp_corners_count"],
                        "TAC (rad)": sc.get("total_tac_rad", 0),
                        "Arc ratio": f"{sc['arc_ratio']:.1%}",
                        "Geo typy": ", ".join(f"{k}:{v}" for k, v in sorted(l.get("geometry_types", {}).items()))
                    })
                st.dataframe(pd.DataFrame(layer_rows), use_container_width=True, hide_index=True)

                # Shape groups
                sg = result.get("shape_groups", [])
                if sg:
                    st.markdown("##### Opakující se tvary")
                    st.dataframe(pd.DataFrame([{
                        "ID": s["id"], "Typ": s["type"], "Instances": s["instance_count"],
                        "Délka (mm)": s["length_mm"], "Poměr stran": s["aspect_ratio"]
                    } for s in sg]), use_container_width=True, hide_index=True)

                lc = result.get("layer_card", {})
                if lc and lc.get("colors"):
                    st.markdown("---")
                    st.markdown("##### Layer Card — CAM Import Reference")
                    lc_rows = []
                    for ci_key, c in sorted(lc["colors"].items()):
                        tc = c.get("tool_config") or {}
                        lc_rows.append({
                            "ACI": ci_key,
                            "Barva": c["color_name"],
                            "Entit": c["entity_count"],
                            "Délka (m)": round(c["total_length_mm"] / 1000, 2),
                            "Bodů": c["total_point_count"],
                            "Pt/m": c["point_density_per_meter"],
                            "Closed": c["closed_count"],
                            "Open": c["open_count"],
                            "TAC": c["total_tac_rad"],
                            "Nástroj": tc.get("cutter_type", "unmapped"),
                            "Rychlost": tc.get("base_speed_mms", 0),
                            "Status": tc.get("validation_status", "unmapped")
                        })
                    st.dataframe(pd.DataFrame(lc_rows), use_container_width=True, hide_index=True)
                    st.caption(f"{lc['total_entities_mapped']} barev má mapovaný nástroj, {lc['total_entities_unmapped']} nemá")

            with tab_viz:
                st.markdown("#### 2D Digital Model")
                import ezdxf
                try:
                    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
                        tmp.write(file_bytes)
                        vis_path = tmp.name
                    doc = ezdxf.readfile(vis_path)
                    msp = doc.modelspace()
                    plt_ents = []
                    seen_colors = set()
                    for entity in msp:
                        dtype = entity.dxftype()
                        try:
                            if dtype == 'LINE':
                                s, e = entity.dxf.start, entity.dxf.end
                                verts = [(s.x, s.y), (e.x, e.y)]
                            elif dtype in ('LWPOLYLINE', 'POLYLINE'):
                                verts = [(p[0], p[1]) for p in entity.get_points()] if hasattr(entity, 'get_points') else [(v[0], v[1]) for v in entity.vertices]
                            elif dtype == 'CIRCLE':
                                r = entity.dxf.radius
                                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                                verts = [(cx + r * math.cos(2 * math.pi * i / 48), cy + r * math.sin(2 * math.pi * i / 48)) for i in range(49)]
                            elif dtype == 'ARC':
                                r, sd, ed_ang = entity.dxf.radius, entity.dxf.start_angle, entity.dxf.end_angle
                                ar = math.radians(ed_ang - sd)
                                if ar < 0: ar += 2 * math.pi
                                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                                n = max(12, int(ar / 0.08))
                                verts = [(cx + r * math.cos(math.radians(sd) + ar * i / n), cy + r * math.sin(math.radians(sd) + ar * i / n)) for i in range(n + 1)]
                            else:
                                continue
                            if len(verts) > 1:
                                color_idx = resolve_cam_color(entity, doc)
                                plt_ents.append({"verts": verts, "color": color_idx})
                                seen_colors.add(color_idx)
                        except Exception:
                            continue
                    os.unlink(vis_path)

                    if plt_ents:
                        fig, ax = plt.subplots(figsize=(12, 8), facecolor="#1E293B")
                        ax.set_facecolor("#0F172A")
                        cmap = {0: "#000000", 1: "#FF0000", 2: "#D0D000",
                                3: "#00E000", 5: "#0000FF", 6: "#FF00FF",
                                7: "#000000", 8: "#808080", 12: "#0000A0",
                                14: "#A00000", 30: "#FF8000", 34: "#C08000",
                                36: "#B45A00", 44: "#F0B98D", 51: "#FFDB66",
                                54: "#A0A000", 80: "#86FA88", 82: "#8CD78C",
                                84: "#00A000", 104: "#7D87B9", 134: "#004754",
                                140: "#00E0E0", 160: "#00A0FF", 170: "#4A6FE3",
                                194: "#500A78", 210: "#F6C4E1", 214: "#A000A0",
                                221: "#FA9ED4", 230: "#D33F6A", 252: "#B4B4B4"}
                        for el in plt_ents[:600]:
                            xs = [v[0] for v in el["verts"]]
                            ys = [v[1] for v in el["verts"]]
                            ax.plot(xs, ys, color=cmap.get(el["color"], "#64748B"), linewidth=1.0, alpha=0.8)

                        sem_loc = result.get("semantic_analysis", {})
                        zones = sem_loc.get("zones", [])
                        for z in zones:
                            yr = z.get("y_range_mm", [])
                            if len(yr) >= 2:
                                ax.axhline(y=yr[0], color="#F59E0B", linewidth=0.8, linestyle=":", alpha=0.6)
                                ax.axhline(y=yr[1], color="#F59E0B", linewidth=0.8, linestyle=":", alpha=0.6)

                        aci_names = {1: "Red", 2: "Yellow", 3: "Green", 4: "Cyan",
                                     5: "Blue", 6: "Magenta", 7: "White", 0: "ByBlock",
                                     30: "Orange", 52: "Lime", 92: "Azure"}
                        lc = result.get("layer_card", {}).get("colors", {})
                        legend_patches = []
                        shown_l = set()
                        for ci in sorted(seen_colors):
                            color = cmap.get(ci, "#64748B")
                            name = aci_names.get(ci, f"ACI {ci}")
                            if str(ci) in lc and lc[str(ci)].get("tool_config"):
                                ct = lc[str(ci)]["tool_config"]["cutter_type"]
                                label = f"{name} ({ct})"
                            else:
                                label = name
                            if label not in shown_l:
                                legend_patches.append(plt.Line2D([0], [0], color=color, linewidth=2, label=label))
                                shown_l.add(label)
                        if legend_patches:
                            ax.legend(handles=legend_patches, loc="upper right", fontsize=7,
                                     facecolor="#1E293B", edgecolor="#334155", labelcolor="#F8FAFC")

                        ax.set_title(f"2D: {uploaded_file.name}", color="#F8FAFC", fontsize=12)
                        ax.tick_params(colors="#94A3B8")
                        for spine in ax.spines.values():
                            spine.set_color("#334155")
                        ax.set_aspect('equal', 'box')
                        ax.invert_yaxis()
                        st.pyplot(fig)
                    else:
                        st.info("Nic k vykreslení.")
                except Exception as e:
                    st.error(f"Vizualizační chyba: {e}")

            with tab_sem:
                st.markdown("#### 🧠 Semantic Analysis (V2.1)")
                if sem:
                    panel_type = sem.get("panel_type", "unknown")
                    confidence = sem.get("confidence", "low")
                    confidence_color = "#10B981" if confidence == "high" else ("#F59E0B" if confidence == "medium" else "#EF4444")
                    
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    with sc1:
                        st.markdown(f"""<div class="metric-card"><div class="metric-label">Panel Type</div><div class="metric-value-sm">{panel_type}</div></div>""", unsafe_allow_html=True)
                    with sc2:
                        st.markdown(f"""<div class="metric-card"><div class="metric-label">Confidence</div><div class="metric-value-sm" style="color:{confidence_color};">{confidence}</div></div>""", unsafe_allow_html=True)
                    with sc3:
                        st.markdown(f"""<div class="metric-card"><div class="metric-label">Orthogonal</div><div class="metric-value-blue">{'Yes' if sem.get('is_orthogonal') else 'No'}</div></div>""", unsafe_allow_html=True)
                    with sc4:
                        st.markdown(f"""<div class="metric-card"><div class="metric-label">Has Arcs</div><div class="metric-value-blue">{'Yes' if sem.get('has_arcs_any') else 'No'}</div></div>""", unsafe_allow_html=True)

                    zones = sem.get("zones", [])
                    if zones:
                        st.markdown("---")
                        st.markdown("#### 🗺️ Zone Schema")
                        zdf = pd.DataFrame([{
                            "Zone": z["zone_id"],
                            "Type": z["zone_type"],
                            "Entities": z["entity_count"],
                            "Length (mm)": f"{z.get('length_mean_mm', 0):.0f}",
                            "Spacing (mm)": f"{z.get('spacing_mean_mm', 0):.1f}",
                            "Regularity": f"{z.get('regularity_score', 0):.2f}",
                            "Pattern": z.get("pattern", "unknown")
                        } for z in zones])
                        st.dataframe(zdf, use_container_width=True, hide_index=True)

                    ta = sem.get("tool_assignments", {})
                    if ta:
                        st.markdown("---")
                        st.markdown("#### 🔧 CNC Tool Assignments")
                        tdf_rows = []
                        for tool_name, td in ta.items():
                            display_len = td.get("double_pass_length_mm", td.get("total_length_mm", 0))
                            tdf_rows.append({
                                "Tool": tool_name,
                                "Entities": td.get("entity_count", 0),
                                "Length (m)": f"{display_len/1000:.1f}",
                                "Passes": td.get("passes", 1),
                                "Head Rotations": td.get("head_rotations", 0),
                                "Operation": td.get("operation", "unknown")
                            })
                        st.dataframe(pd.DataFrame(tdf_rows), use_container_width=True, hide_index=True)

                    ct = sem.get("cutting_time_estimate", {})
                    if ct:
                        st.markdown("---")
                        st.markdown("#### ⏱️ Cutting Time Estimate")
                        total_s = ct.get("total_time_s", 0)
                        mins = int(total_s / 60); secs = int(total_s % 60)
                        tc1, tc2, tc3 = st.columns(3)
                        with tc1:
                            st.metric("Vibrate cutter", f"{ct.get('vibrate_cutter_time_s', 0):.1f} s")
                            st.metric("V-slot", f"{ct.get('v_slot_time_s', 0):.1f} s")
                        with tc2:
                            st.metric("Head rotations", f"{ct.get('head_rotation_overhead_s', 0):.1f} s")
                            st.metric("Feed rate", f"{ct.get('config_feed_rate_mmps', 0):.0f} mm/s")
                        with tc3:
                            st.metric("**Total**", f"**{total_s:.1f} s ({mins}m {secs}s)**")

                    my = sem.get("material_yield", {})
                    if my:
                        st.markdown("---")
                        st.markdown("#### 📦 Material Yield")
                        yl_pct = my.get("yield_percent", 0)
                        stock = my.get("stock_plate_mm", [2900, 1220])
                        panel = my.get("panel_bbox_mm", [0, 0])
                        m1, m2 = st.columns([2, 1])
                        with m1:
                            st.markdown(f"Panel {panel[0]:.0f} x {panel[1]:.0f} mm ze surove desky {stock[0]:.0f} x {stock[1]:.0f} mm")
                            st.markdown(f'<div class="yield-bar"><div class="yield-fill" style="width:{yl_pct}%;"></div></div>', unsafe_allow_html=True)
                        with m2:
                            st.metric("Vyteznost", f"{yl_pct:.1f}%")
                            st.metric("Odpad", f"{my.get('waste_mm', [0,0])[0]:.0f} x {my.get('waste_mm', [0,0])[1]:.0f} mm")

                    mf = sem.get("mounting_flap", {})
                    if mf.get("detected"):
                        st.markdown("---")
                        st.markdown("#### 🔩 Mounting Flap Detected")
                        st.info(f"Montazni presah: {mf.get('width_mm', 0):.0f} x {mf.get('height_mm', 0):.0f} mm na Y ∈ {mf.get('position_y_mm', [0,0])}")

                    narrative = sem.get("narrative_summary", "")
                    if narrative:
                        st.markdown("---")
                        st.markdown("#### 📝 Narrative Summary")
                        st.markdown(f"> {narrative.replace(chr(10), '<br>')}", unsafe_allow_html=True)
                else:
                    st.info("Semanticka analyza neni k dispozici (indexer V2.0). Pro plnou analyzu pouzijte indexer V2.1.")

            with tab_ml:
                st.markdown("#### ML-ready feature vector (global aggregate)")
                if mfv:
                    st.markdown("##### Všechny featury")
                    st.dataframe(pd.DataFrame([{"feature": k, "value": v} for k, v in sorted(mfv.items())]), use_container_width=True, hide_index=True)

                    st.markdown("##### Surový vektor (flat float list)")
                    st.code(", ".join(f"{mfv[k]}".rstrip('0').rstrip('.') for k in sorted(mfv.keys())))
                else:
                    st.info("Žádné ML featury.")

            # ── EXPORT ──
            st.markdown("---")
            st.markdown("#### 📦 Export")
            ex1, ex2, ex3 = st.columns(3)
            with ex1:
                json_str = json.dumps(result, indent=2, ensure_ascii=False)
                st.download_button("⬇ JSON (plný)", data=json_str,
                                   file_name=f"{meta['file_name'].rsplit('.', 1)[0]}_index_v2.json",
                                   mime="application/json")
            with ex2:
                # Generate MD
                from dxf_geometry_indexer_v2 import write_md
                import io as std_io
                md_buf = std_io.StringIO()
                md_buf_path = Path(tmp_path) if 'tmp_path' in dir() else None
                # Write inline MD
                md_lines = []
                md_lines.append(f"# Geometry Index V2: {meta['file_name']}\n")
                md_lines.append(f"| Entities | Layers | Closed/Open | Solidity | Holes | Graph CC |\n")
                md_lines.append(f"|---|---|---|---|---|---|\n")
                md_lines.append(f"| {sb['entity_count']} | {sb['layer_count']} | {ts['total_closed_loops']}/{ts['total_open_paths']} | {ba.get('solidity', 'N/A')} | {ba.get('num_holes', 'N/A')} | {egf.get('connected_components', 0)} |\n")
                st.download_button("⬇ Markdown", data="\n".join(md_lines),
                                   file_name=f"{meta['file_name'].rsplit('.', 1)[0]}_index_v2.md",
                                   mime="text/markdown")
            with ex3:
                if mfv:
                    csv_lines = ["feature,value"]
                    for k in sorted(mfv.keys()):
                        csv_lines.append(f"{k},{mfv[k]}")
                    st.download_button("⬇ ML Vector CSV", data="\n".join(csv_lines),
                                       file_name=f"{meta['file_name'].rsplit('.', 1)[0]}_ml_vector.csv",
                                       mime="text/csv")

            # JSON preview (char limit)
            with st.expander("📄 JSON preview (prvních 3000 znaků)"):
                st.code(json_str[:3000] + ("..." if len(json_str) > 3000 else ""))

        except ImportError as e:
            st.error(f"Chybí knihovna: {e}")
        except Exception as e:
            st.exception(e)
else:
    st.markdown("---")
    col_i1, col_i2, col_i3 = st.columns([1, 2, 1])
    with col_i2:
        st.markdown("""
        <div style="text-align: center; padding: 40px 0; color: #94A3B8;">
            <h3 style="color: #64748B;">Žádný soubor nenahrán</h3>
            <p>Přetáhněte .dxf soubor, nebo použijte demo níže.</p>
            <p style="font-size: 13px;">Indexer V2.1 extrahuje: entitni graf, Boolean operace, <br>geometricke constrainty, semantickou analyzu, CNC tool assign, ML vektor (55 featur).</p>
        </div>
        """, unsafe_allow_html=True)

        demo_path = Path(__file__).resolve().parent / "demo_data"
        if demo_path.exists():
            demos = sorted(demo_path.glob("*.dxf"))
            if demos:
                st.markdown("#### Demo soubory (pro test)")
                for d in demos:
                    with open(d, "rb") as f:
                        demo_bytes = f.read()
                    size_kb = len(demo_bytes) / 1024
                    if st.button(f"📁 {d.name} ({size_kb:.0f} KB)", key=d.name, use_container_width=True):
                        st.session_state["demo_file_bytes_v2"] = demo_bytes
                        st.session_state["demo_file_name_v2"] = d.name
                        st.rerun()

if "demo_file_bytes_v2" in st.session_state:
    uploaded_file = io.BytesIO(st.session_state["demo_file_bytes_v2"])
    del st.session_state["demo_file_bytes_v2"]
    st.rerun()
