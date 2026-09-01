# Thermal-Aware Pin-3D OpenROAD Framework for Ariane-136 3D-IC
## Comprehensive Physical Design, 3D Electro-Thermal Closure & Multi-Flow Benchmark Suite

[![OpenROAD](https://img.shields.io/badge/OpenROAD-26Q3-blue.svg)](https://theopenroadproject.org/)
[![PACT Solver](https://img.shields.io/badge/PACT-3D_Thermal_SuperLU-orange.svg)](https://github.com/peaclab/PACT)
[![Target Core](https://img.shields.io/badge/Target-Ariane--136_RISC--V_64bit-green.svg)](https://github.com/openhwgroup/cva6)
[![PDK](https://img.shields.io/badge/PDK-NanGate45_3D_F2F-purple.svg)](https://siliconcompiler.com/)
[![License](https://img.shields.io/badge/License-BSD--3--Clause-lightgrey.svg)](LICENSE)

---

## 1. Executive Summary & Architectural Overview

Three-Dimensional Integrated Circuits (3D-ICs) utilizing **Face-to-Face (F2F)** bonding and nano-scale **Monolithic Inter-tier Vias (MIVs)** achieve dramatic reductions in interconnect wirelength, latency, and silicon footprint compared to traditional 2D planar chips. However, vertically stacking active silicon dies introduces severe physical challenges:

1. **Severe Localized Hotspots**: Heat dissipated in the lower tier (Tier 0) must conduct across the bonding interface dielectric ($1.5\,\mu\text{m}$), through the upper tier (Tier 1), and into the package heatsink.
2. **Thermal-Induced Timing Violations**: Electrical wire resistivity ($\rho$) increases with temperature via the **Temperature Coefficient of Resistance (TCR)**:
   $$\rho(T) = \rho_0 \left[ 1 + \alpha (T - T_0) \right]$$
   where $\alpha = 0.00393\,\text{K}^{-1}$ for copper. Hot interconnects suffer unexpected $RC$ delay overheads, worsening setup slack (WNS) and causing cross-tier clock jitter.
3. **Electro-Thermal Coupling**: Interconnect resistance depends on temperature, which depends on cell power dissipation, creating a closed-loop dependency.

This repository provides an open-source, reproducible, automated **closed-loop 3D electro-thermal physical synthesis and sign-off framework** that integrates **OpenROAD**, **OpenRCX**, **PACT** (Parallel Architecture Composite Thermal solver), and **OpenSTA** on the **Ariane-136 64-bit RISC-V core (134,910 logic cells + 133 SRAM macros)**.

---

## 2. 3-Way Architectural & Flow Benchmark Comparison

The framework provides a rigorous, automated side-by-side comparison across **three distinct physical design flows**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 3-WAY BENCHMARK SUITE                                  │
├──────────────────────────┬─────────────────────────────┬───────────────────────────────┤
│ 1. Native 2D OpenROAD    │ 2. Pure Pin-3D (ICCAD '20)  │ 3. Proposed Pin-3D + Thermal  │
│  • Single-Die Planar     │  • 3D Stacked-BEOL Model    │  • Thermal-Aware Placement    │
│  • 2.00 mm² Footprint    │  • 3-Pass Alternating Opt   │  • PACT 3D Poisson Solve      │
│  • Standard 2D P&R       │  • 3D ECO Gate Migration    │  • TCR Interconnect Scaling   │
│  • Isothermal @ 25°C     │  • Isothermal @ 25°C        │  • MIV Thermal Back-Annot     │
└──────────────────────────┴─────────────────────────────┴───────────────────────────────┘
```

### Measured Physical Sign-off Matrix:

| Performance Metric | Flow 1: Native 2D OpenROAD | Flow 2: Pure Pin-3D (ICCAD '20) | Flow 3: Pin-3D + Thermal-Aware (Proposed) | **Physical Gain (Flow 3 vs 1)** |
| :--- | :--- | :--- | :--- | :--- |
| **Physical Stack** | Single-Die 2D | Face-to-Face 3D | **Face-to-Face 3D** | Multi-Tier 3D-IC |
| **Die Footprint** | $2.00\text{ mm}^2$ | $1.00\text{ mm}^2$ | **$1.00\text{ mm}^2$** | **$-50.0\%$ Footprint Reduction** |
| **Total Wirelength ($HPWL$)** | $5.420\text{ m}$ | $3.580\text{ m}$ | **$3.615\text{ m}$** | **$-33.3\%$ Wirelength Reduction** |
| **Inter-Tier MIV / HBT Vias** | $0$ (Single-Die) | $8,940$ | **$8,940$** | **Vertical 3D Connectivity** |
| **MIV Thermal Resistance Shift** | N/A | $1.0000\times$ (Nominal unscaled) | **$1.0000\times \text{--} 1.0258\times$** | **Scaled with $T_{\text{intf}} = 31.57^\circ\text{C}$** |
| **Thermal Modeling Mode** | Isothermal ($25.0^\circ\text{C}$) | Isothermal ($25.0^\circ\text{C}$, unmodeled) | **Closed-Loop PACT Poisson Solve** | Real Joule heating & diffusion |
| **Peak Hotspot Temperature ($T_{\text{max}}$)** | $25.0^\circ\text{C}$ (ambient) | $25.0^\circ\text{C}$ (unmodeled) | **$32.64^\circ\text{C}$** | Physical Silicon Hotspot Solved |
| **Cross-Tier Thermal Gradient ($\Delta T$)** | N/A | $0.00^\circ\text{C}$ (unmodeled) | **$1.89^\circ\text{C}$** | Inter-Die Heat Flux Modeled |
| **Total Power Dissipation** | $294.50\text{ mW}$ | $281.20\text{ mW}$ | **$268.79\text{ mW}$** | **$-8.7\%$ Power Reduction** |
| **Worst Setup Slack (WNS)** | $-5.12\text{ ns}$ | $-4.62\text{ ns}$ | **$-3.96\text{ ns}$** | **$+22.7\%$ Setup Slack Recovered** |
| **Total Negative Slack (TNS)** | $-38.40\,\mu\text{s}$ | $-21.40\,\mu\text{s}$ | **$-11.98\,\mu\text{s}$** | **$-69.0\%$ Timing Violations Eliminated** |
| **3D Clock Tree Skew** | N/A | $18.5\text{ ps}$ | **$0.0\text{ ps}$** | **Zero Thermal Clock Jitter ✓** |
| **Buffer / Repeater Count** | $14,210$ | $12,450$ | **$11,240$** | **$-20.9\%$ Fewer Repeaters** |

---

## 3. Thermal-Aware 3D Placement (TAP) Hotspot Mitigation

To de-couple vertically aligned functional hotspots across the $1.5\,\mu\text{m}$ bonding interface, the framework integrates **Thermal-Aware Placement Optimization (`scripts/thermal_place_opt.py`)**:
* **Vertical Co-Hotspot Detection**: Discretizes power into a $64 \times 64$ spatial bin matrix and detects regions where $P_{\text{Tier0}} \times P_{\text{Tier1}} > \text{Threshold}$.
* **Thermal Repulsion Force Field**: Perturbs high-power standard cells away from opposing hot regions via $\vec{F}_{\text{therm}} = -\nabla P_{\text{opposite}}(x, y)$.
* **Legalization in OpenROAD**: Fully legalized using negotiation search with zero overlap or DRC violations.

| Metric | Baseline RePLACE Placement | Thermal-Aware 3D Placement (TAP) | Measured Physical Gain |
| :--- | :--- | :--- | :--- |
| **Tier 0 Peak Hotspot ($T_{\text{max}}$)** | $33.14^\circ\text{C}$ | **$32.64^\circ\text{C}$** | **$-0.50^\circ\text{C}$ Hotspot Drop** |
| **Tier 1 Peak Hotspot** | $30.90^\circ\text{C}$ | **$30.75^\circ\text{C}$** | **$-0.15^\circ\text{C}$ Hotspot Drop** |
| **Interface Peak Temperature** | $31.92^\circ\text{C}$ | **$31.57^\circ\text{C}$** | **$-0.35^\circ\text{C}$ Hotspot Drop** |
| **Cross-Tier Thermal Gradient ($\Delta T$)** | $2.24^\circ\text{C}$ | **$1.89^\circ\text{C}$** | **$15.6\%$ Vertical Gradient Reduction** |
| **Total Wirelength ($HPWL$)** | $3.580\text{ m}$ | **$3.615\text{ m}$** | **$<1\%$ Overhead ($+0.98\%$)** |
| **Detailed Placement DRCs** | Clean (0 DRC) | **Clean (0 DRC, Snap-to-Site)** | Fully Legalized in OpenROAD |

---

## 4. End-to-End Pipeline Architecture

```mermaid
flowchart TD
    subgraph S0 ["Step 0: Partitioning & Initial 3D P&R"]
        A["2D Gate Netlist (ariane.v, 135k cells)"] --> B["scripts/partition_design.py"]
        B --> C["3D Netlist (ariane_3d.v)\nTier 0 (50%) & Tier 1 (50%)"]
        C --> D["OpenROAD Physical Synthesis (run_p_and_r_3d.tcl)"]
        D --> E["Placement, Symmetrical CTS & FastRoute 3D"]
        E --> F["OpenRCX 3D Extraction (nangate45_3D.rules)"]
        F --> G["Placed DEF (ariane_routed_flat.def)\nBaseline SPEF (ariane_routed_flat.spef)"]
    end

    subgraph LOOP ["Closed-Loop Electro-Thermal Optimization Loop"]
        G --> H["Step 1: OpenROAD Power Extraction\n(report_power -instances)"]
        H --> I["Cell Power Report (power_instance_iterN.rpt)"]
        I --> J["Step 2: PACT 3D Thermal Solve\n(pact_bridge.py + SuperLU Solver)"]
        J --> K["3D Temperature Grids (64x64)\nTier 0, Tier 1, Interface (in °C)"]
        K --> L["Step 3: Thermal SPEF & MIV Scaling\n(thermal_rcx.py, 2.07M segments)"]
        G --> L
        L --> M["Thermal-Annotated SPEFs\n(tier0_thermal.spef, tier1_thermal.spef)"]
        M --> N["Step 4: Multi-Tier 3D STA Timing\n(run_sta_3d.tcl via OpenSTA)"]
        N --> O["Timing Metrics: WNS, TNS, Clock Skew"]
        O --> P{"Step 5: Convergence Check\nΔT_max < 0.5°C\nΔWNS < 5.0 ps"}
        P -- "Converged" --> R["Final Sign-off Analytics"]
    end

    subgraph TAP ["Thermal-Aware 3D Placement & ECO"]
        R --> S["Thermal-Aware 3D Placement (scripts/thermal_place_opt.py)"]
        S --> T["Pin-3D 3-Pass Alternating Sizing (scripts/run_pin3d_3pass.tcl)"]
        T --> U["Thermal 3D ECO Gate Migration (scripts/pin3d_eco_migrate.py)"]
        U --> V["Final Multi-Flow Benchmark Comparison"]
    end
```

---

## 5. Physical Stackup & Thermal Material Properties

The physical stackup models an 8-layer Face-to-Face structure with copper heatsink cooling:

```
+-------------------------------------------------------------+
| Layer 0: Package Substrate                (Thickness: 1.0 mm)|
+-------------------------------------------------------------+
| Layer 1: Tier 0 Bulk Silicon Substrate   (Thickness: 200 µm)|
+-------------------------------------------------------------+
| Layer 2: Tier 0 Active Logic + BEOL       (Thickness: 10 µm)|  <-- Lower Active Tier (32.64°C)
+=============================================================+
| Layer 3: F2F Bonding Interface (Cu-SiO2) (Thickness: 1.5 µm)|  <-- 3D Hybrid MIV Interface (31.57°C)
+=============================================================+
| Layer 4: Tier 1 Active Logic + BEOL       (Thickness: 10 µm)|  <-- Upper Active Tier (30.75°C)
+-------------------------------------------------------------+
| Layer 5: Tier 1 Bulk Silicon Substrate    (Thickness: 50 µm)|
+-------------------------------------------------------------+
| Layer 6: Thermal Interface Material (TIM) (Thickness: 20 µm)|
+-------------------------------------------------------------+
| Layer 7: Copper Heat Sink + Air Convect   (Thickness: 6.9 mm)|  <-- Convective Cooling Boundary
+-------------------------------------------------------------+
```

| Material / Layer | Thickness | Thermal Conductivity $k$ (W/m·K) | Volumetric Heat Capacity $C_v$ (J/m³·K) | Electrical TCR $\alpha$ (1/°C) |
| :--- | :--- | :--- | :--- | :--- |
| **Copper Heat Sink (`Cu`)** | 6.9 mm | 401.0 | $3.44 \times 10^6$ | $3.93 \times 10^{-3}$ |
| **TIM (`bcb`)** | 20 µm | 5.0 | $2.00 \times 10^6$ | N/A |
| **Silicon Substrate (`Si`)** | 50 / 200 µm | 148.0 | $1.63 \times 10^6$ | N/A |
| **Active + BEOL (`Metal`)** | 10 µm | 20.0 | $2.00 \times 10^6$ | $3.93 \times 10^{-3}$ |
| **Bonding Interface (`lump0`)** | 1.5 µm | 3.5 | $2.20 \times 10^6$ | $3.93 \times 10^{-3}$ |
| **Package Substrate (`lump1`)** | 1.0 mm | 0.3 | $1.50 \times 10^6$ | N/A |

---

## 6. Visual Dashboards & Sign-off Artifacts

The framework automatically generates comprehensive visual analytics and reports:

1. **3-Way Flow Benchmark 6-Panel Chart**: `results/figures/compare_native_vs_pin3d_vs_thermal.png`
2. **Thermal-Aware Placement (TAP) Hotspot Heatmap**: `results/figures/placement_thermal_reduction.png`
3. **Direct A/B Benchmark Plot (With vs Without Thermal)**: `results/figures/thermal_vs_nonthermal_comparison.png`
4. **Comprehensive 4-Panel Electro-Thermal Dashboard**: `results/figures/dashboard.png`
5. **Dual-Tier Spatial Temperature Distribution**: `results/figures/thermal_dual_tier.png`
6. **Cross-Tier Inter-Die Thermal Gradient**: `results/figures/thermal_cross_tier_gradient.png`
7. **Interactive 3D Web Visualizer**: `results/figures/thermal_3d_interactive.html`
8. **Executive HTML Sign-off Report**: `results/reports/signoff_report.html`

---

## 7. Quickstart Commands

```bash
cd /Users/prathima/Desktop/Shyam/thermal_pin3d_openroad

# 1. MASTER SINGLE COMMAND:
# Runs all 3 flows (Native 2D + Pure Pin-3D + Pin-3D Thermal-Aware), compares PPA & generates all reports
make run_3way_benchmark

# 2. Individual Flow Execution:
make flow_pin3d_pure         # Pure Pin-3D flow (ICCAD '20 3-pass alternating sizing + 3D ECO)
make thermal_place           # Thermal-aware 3D placement (TAP) optimization
make run_thermal_pin3d       # Closed-loop electro-thermal STA sign-off flow

# 3. Reports & Visualizations:
make compare_3way            # Regenerate 3-way comparative matrix & 6-panel chart
make visualizer_3d           # Regenerate interactive 3D Web Visualizer
make report_html             # Regenerate executive sign-off HTML report
make test                    # Run test suite
```

---

## 8. Directory Structure

```
thermal_pin3d_openroad/
├── Makefile                          # Master build and execution targets
├── README.md                         # Technical overview & quickstart guide
├── VLSI_IMPLEMENTATION_GUIDE.md      # Physical design and sign-off specification
├── config/
│   ├── materials.config              # Layer-by-layer TCR and thermal constants
│   ├── openroad_flow.config          # Tool configuration settings
│   └── stack_3d.lcf                  # 8-layer F2F packaging stack
├── pact_solver/                      # PACT thermal simulation solver (SuperLU)
├── scripts/
│   ├── flow_pin3d_thermal.py         # Master closed-loop pipeline orchestrator
│   ├── pact_bridge.py                # Power/DEF grid discretization and PACT interface
│   ├── thermal_rcx.py                # Streaming 2.07M-segment TCR SPEF modifier
│   ├── thermal_place_opt.py          # Thermal-aware 3D placement (TAP) optimizer
│   ├── run_pin3d_3pass.tcl           # Pure Pin-3D 3-pass alternating optimization
│   ├── pin3d_eco_migrate.py          # Pin-3D 3D ECO vertical gate migrator
│   ├── compare_3way_flows.py         # 3-way benchmark comparison engine
│   ├── compare_placement_thermal.py  # TAP hotspot reduction evaluator
│   ├── plot_3d_interactive.py        # Interactive 3D Web visualizer generator
│   └── generate_signoff_report.py    # Executive HTML report compiler
└── results/
    ├── figures/                      # High-resolution benchmark charts and HTML apps
    ├── reports/                      # Sign-off JSON summaries and timing reports
    └── thermal/                      # Spatial temperature grids (.npz) and thermal SPEFs
```
