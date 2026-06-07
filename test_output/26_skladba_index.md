# DXF Geometry Index V2.1: 26_skladba.dxf
- Indexer: V2.2.0 - DXF: AC1015 - MD5: 85b4ca6b1567e38c...
- Timestamp: 2026-06-07T00:39:47
- Libs: Shapely=OK - SciPy=OK - GUDHI=N/A

## Spatial Bounds
| Property | Value |
|---|---|
| Canvas bbox (mm) | [390, -0, 1610, 2900] |
| Canvas area (m2) | 3.538 |
| Total path length (m) | 104.54 |
| Entities | 183 | Layers | 1 |

## Topology
| Property | Value |
|---|---|
| Closed loops | 183 | Open paths | 0 |
| Closed ratio | 100.0% | Max nesting depth | 1 |
| Shape patterns | 6 | Spatial clusters | 1 |
| Total vertices | 7288 | Mean seg length | 19.9 mm |
| Point density | 69.7 pts/m |

## Entity Graph
| Metric | Value |
|---|---|
| Nodes | 183 |
| Adjacency edges | 0 |
| Containment edges | 208 |
| Intersection overlaps | 208 |
| Proximity edges | 1741 |
| Connected components | 2 |
| Max degree | 31 |
| Cycle count | 208 |

## Boolean Analysis (Shapely)
| Property | Value |
|---|---|
| Unified area (mm2) | 3538000 |
| Boundary length (mm) | 8240.0 |
| Convex hull area (mm2) | 3538000 |
| Solidity | 1.000 |
| Number of holes | 0 |
| Min feature width (mm) | 0.0 |

## Geometric Constraints
| Property | Value |
|---|---|
| Parallel pairs | 16653 |
| Perpendicular pairs | 0 |
| Orthogonal ratio | 1.000 |

## Semantic Analysis (V2.1)
| Property | Value |
|---|---|
| Panel type | unknown |
| Confidence | medium |
| Is orthogonal | Yes |
| Has arcs | No |

### Tool Assignments
| Tool | Entities | Length (m) | Passes | Operation |
|---|---|---|---|---|
| vibrate_cutter_0deg | 183 | 104.5 | 1 | outer_format |

### Material Yield
- Panel: 1220 x 2900 mm from stock 2900 x 1220 mm
- Yield: 100.0%

### Cutting Time Estimate
| Operation | Time (s) |
|---|---|
| Vibrate cutter | 522.7 |
| V-slot | 0.0 |
| Head rotations | 0.0 |
| **Total** | **522.7 s (8m 42s)** |
| Feed rate | 200 mm/s |

### Narrative Summary
Vyrez o rozmerech 1220 x 2900 mm (3.54 m2). Celkova delka tras: 104.5 m. Nalezeno 183 uzavrenych obrysu a 0 otevrenych drah.
Prirazeni nastroju CNC:
- Vibrate cutter 0deg: 183 entit, 104.5 m (vnejsi format)
Vyteznost materialu: 100.0% z formatu 2900x1220 mm (panel otocen o 90deg).
Odhadovany cas CNC rezu: 8m 42s (při feed rate 200 mm/s).


## Layers
| Layer | Entities | Length (m) | Points | Closed | Curv. index | TAC (rad) | Arc ratio |
|---|---|---|---|---|---|---|---|
| mainlayer | 183 | 104.54 | 7288 | 100.0% | 0.000000 | 0.00 | 0.0% |

## Shape Groups
| ID | Type | Instances | Length (mm) | Points | Aspect |
|---|---|---|---|---|---|---|
| Shape_G1 | LWPOLYLINE | 1 | 8240.0 | 8 | 0.4 |
| Shape_G2 | LWPOLYLINE | 52 | 512.0 | 48 | 1.2 |
| Shape_G3 | LWPOLYLINE | 52 | 784.0 | 56 | 0.6 |
| Shape_G4 | LWPOLYLINE | 26 | 440.0 | 24 | 0.8 |
| Shape_G5 | LWPOLYLINE | 26 | 600.0 | 40 | 0.5 |
| Shape_G6 | LWPOLYLINE | 26 | 72.0 | 8 | 2.0 |

## Layer Card (CAM Import Reference)
| Color ID | Name | Entities | Length (m) | Points | Pt/m | Closed | Open | TAC (rad) | Tool | Speed | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Red | 1 | 8.24 | 8 | 1.0 | 1 | 0 | 0.0 | Vibrate cutter | 150 | hypothesis |
| 4 | Cyan | 182 | 96.30 | 7280 | 75.6 | 182 | 0 | 0.0 | ambiguous | 200 | hypothesis |
| | | 2 mapped + 0 unmapped | | | | | | | | | |

## ML Feature Vector (V2.1 — 55 feats)
| Feature | Value |
|---|---|
| boundary_length_mm | 8240.0 |
| closed_loop_count | 183 |
| constraints_orthogonal_ratio | 1.0 |
| constraints_parallel | 16653 |
| constraints_perpendicular | 0 |
| convex_hull_area_mm2 | 3537999.82 |
| entity_count | 183 |
| graph_connected_components | 2 |
| graph_cycle_count | 208 |
| graph_diameter | 182 |
| graph_max_degree | 31 |
| has_arcs_entity_count | 0 |
| has_arcs_ratio | 0.0 |
| has_mounting_flap | 0 |
| head_rotation_count | 0 |
| largest_zone_entity_count | 0 |
| max_bulge_any | 0.0 |
| max_point_count | 56 |
| max_tac_rad | 0.0 |
| max_zone_spacing_mm | 0 |
| mean_area_mm2 | 31892.9 |
| mean_avg_segment_mm | 19.94 |
| mean_bulge_all | 0.0 |
| mean_curvature_index | 0.0 |
| mean_length_mm | 571.28 |
| mean_point_count | 39.83 |
| mean_tac_rad | 0.0 |
| min_feature_width_mm | 0.0 |
| min_length_mm | 72.0 |
| num_holes | 0 |
| open_path_count | 0 |
| p50_length_mm | 512.0 |
| p95_length_mm | 784.0 |
| panel_fits_stock | 1 |
| panel_is_orthogonal | 1 |
| panel_yield_percent | 100.0 |
| semantic_zone_count | 0 |
| solidity | 1.0 |
| std_area_mm2 | 259992.76 |
| std_avg_segment_mm | 85.83 |
| std_curvature_index | 0.0 |
| std_length_mm | 610.9 |
| std_tac_rad | 0.0 |
| tac_per_meter | 0.0 |
| total_area_mm2 | 5836400.21 |
| total_direction_changes | 0 |
| total_length_mm | 104544.0 |
| total_sharp_corners | 0 |
| total_tac_rad | 0.0 |
| total_vertices | 7288 |
| unified_area_mm2 | 3537999.82 |
| v_slot_double_pass_length_mm | 0 |
| v_slot_entity_count | 0 |
| v_slot_single_pass_length_mm | 0 |
| vibrate_cutter_length_mm | 104544.0 |
| zone_lengths_mean | 0.0 |