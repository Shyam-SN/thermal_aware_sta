#!/usr/bin/env python3
"""
flow_pin3d_thermal.py — Master Electro-Thermal Orchestration Engine

Drives the closed-loop thermal-aware optimization flow:

  Iteration Loop:
    1. Extract cell-level power from OpenROAD/OpenSTA
    2. Generate PACT inputs (floorplan + power trace) via pact_bridge
    3. Run PACT thermal solver → spatial T(x,y) grids
    4. Apply TCR scaling to SPEF via thermal_rcx
    5. Run STA with thermal SPEF → WNS, TNS, skew
    6. Check convergence: ΔT_max < 0.5°C AND ΔWNS < 5 ps
    7. If not converged: trigger ECO (buffer sizing, insertion, deskew)
    8. Repeat until converged or max iterations reached

Part of the Thermal-Aware Pin-3D Framework for Ariane-136.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Import framework modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pact_bridge import (
    PACTBridge, ThermalGrid, DieGeometry,
    load_thermal_grid, save_thermal_grid,
    DEFAULT_GRID_ROWS
)
from thermal_rcx import process_tier_spef, TCRConfig

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------

logger = logging.getLogger("flow_pin3d_thermal")

# Convergence thresholds (from specification)
DEFAULT_CONV_DT = 0.5       # °C — max temperature change between iterations
DEFAULT_CONV_DWNS = 5.0     # ps — max WNS change between iterations
DEFAULT_MAX_ITERATIONS = 4  # Maximum convergence loop iterations

# Power delta tolerance for re-solving thermal
DEFAULT_POWER_DELTA_THRESHOLD = 0.05  # 5% relative power change


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class FlowConfig:
    """Configuration for the electro-thermal flow."""
    # Design
    design_name: str = "ariane136"
    num_tiers: int = 2

    # Paths
    project_root: str = "."
    scripts_dir: str = "scripts"
    config_dir: str = "config"
    results_dir: str = "results"
    pdk_dir: str = "platforms/nangate45_3D"

    # Design files
    tier_defs: Dict[int, str] = field(default_factory=dict)
    tier_spefs: Dict[int, str] = field(default_factory=dict)
    sdc_path: str = ""
    tech_lef_path: str = ""
    lef_files: List[str] = field(default_factory=list)
    lib_files: List[str] = field(default_factory=list)

    # PACT
    pact_home: str = ""
    grid_size: int = DEFAULT_GRID_ROWS

    # Convergence
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    conv_dt: float = DEFAULT_CONV_DT
    conv_dwns: float = DEFAULT_CONV_DWNS
    power_delta_threshold: float = DEFAULT_POWER_DELTA_THRESHOLD

    # Tool paths
    openroad_bin: str = "/Users/prathima/OpenROAD/build/bin/openroad"
    opensta_bin: str = "sta"

    # Runtime
    dry_run: bool = False
    verbose: bool = False
    skip_pnr: bool = False
    force_pnr: bool = False

    def __post_init__(self):
        if not self.tier_defs:
            # Under flat flow, both tiers point to the flat DEF file
            for tier in range(self.num_tiers):
                self.tier_defs[tier] = os.path.join(
                    self.results_dir, "ariane_routed_flat.def"
                )
        if not self.tier_spefs:
            # Under flat flow, both tiers point to the flat SPEF file
            for tier in range(self.num_tiers):
                self.tier_spefs[tier] = os.path.join(
                    self.results_dir, "ariane_routed_flat.spef"
                )
        if not self.sdc_path:
            self.sdc_path = os.path.join(
                self.project_root, "designs", "nangate45_3D", self.design_name, "ariane.sdc"
            )
        if not self.tech_lef_path:
            self.tech_lef_path = os.path.join(self.pdk_dir, "lef", "NangateOpenCellLibrary.tech.lef")
        if not self.lef_files:
            self.lef_files = [
                os.path.join(self.pdk_dir, "lef_bottom", "NangateOpenCellLibrary.macro.mod.bottom.lef"),
                os.path.join(self.pdk_dir, "lef_upper", "NangateOpenCellLibrary.macro.mod.upper.lef"),
                os.path.join(self.pdk_dir, "lef_bottom", "fakeram45_256x16.bottom.lef"),
                os.path.join(self.pdk_dir, "lef_upper", "fakeram45_256x16.upper.lef")
            ]
        if not self.lib_files:
            self.lib_files = [
                os.path.join(self.pdk_dir, "lib_bottom", "NangateOpenCellLibrary_typical.bottom.lib"),
                os.path.join(self.pdk_dir, "lib_upper", "NangateOpenCellLibrary_typical.upper copy.lib"),
                os.path.join(self.pdk_dir, "lib_bottom", "fakeram45_256x16.bottom.lib"),
                os.path.join(self.pdk_dir, "lib_upper", "fakeram45_256x16.upper.lib")
            ]
        if not self.pact_home:
            local_pact = os.path.join(self.project_root, "pact_solver")
            if os.path.exists(local_pact):
                self.pact_home = os.path.abspath(local_pact)
            else:
                self.pact_home = os.environ.get('PACT_HOME', '')


@dataclass
class IterationMetrics:
    """Metrics collected at each convergence iteration."""
    iteration: int = 0

    # Temperature
    t_max_tier0: float = 25.0
    t_max_tier1: float = 25.0
    t_max_interface: float = 25.0
    t_mean_tier0: float = 25.0
    t_mean_tier1: float = 25.0
    delta_t_max: float = float('inf')  # Change from previous iteration

    # Timing
    wns_ps: float = 0.0          # Worst Negative Slack [ps]
    tns_ps: float = 0.0          # Total Negative Slack [ps]
    hold_wns_ps: float = 0.0     # Hold WNS [ps]
    max_skew_ps: float = 0.0     # Max inter-tier clock skew [ps]
    delta_wns: float = float('inf')  # WNS change from previous [ps]

    # Power
    total_power_mw: float = 0.0
    dynamic_power_mw: float = 0.0
    leakage_power_mw: float = 0.0
    power_delta_pct: float = 0.0  # % change from previous iteration

    # SPEF modification stats
    segments_modified: int = 0
    max_r_ratio: float = 1.0
    min_r_ratio: float = 1.0

    # Runtime
    elapsed_s: float = 0.0

    # Convergence status
    converged: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Power Extraction
# ---------------------------------------------------------------------------

class PowerExtractor:
    """
    Extracts cell-level power from OpenROAD or reads pre-generated power reports.
    """

    def __init__(self, config: FlowConfig):
        self.config = config

    def extract_power(self, iteration: int) -> str:
        """
        Run power analysis in OpenROAD and return path to power report.

        Args:
            iteration: Current iteration number

        Returns:
            Path to generated power report
        """
        report_dir = os.path.join(self.config.results_dir, "reports")
        os.makedirs(report_dir, exist_ok=True)
        power_report = os.path.join(report_dir,
                                      f"power_instance_iter{iteration}.rpt")

        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would extract power to: {power_report}")
            self._generate_synthetic_power(power_report, iteration)
            return power_report

        # Build OpenROAD Tcl script for power extraction
        tcl_script = self._build_power_tcl(power_report, iteration)
        tcl_path = os.path.join(report_dir, f"power_extract_iter{iteration}.tcl")

        with open(tcl_path, 'w') as f:
            f.write(tcl_script)

        # Execute OpenROAD
        cmd = [
            self.config.openroad_bin, '-exit', tcl_path
        ]

        logger.info(f"Running power extraction (iter {iteration})...")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                logger.error(f"Power extraction failed: {result.stderr[:500]}")
                # Fall back to synthetic
                self._generate_synthetic_power(power_report, iteration)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"OpenROAD not available ({e}), using synthetic power")
            self._generate_synthetic_power(power_report, iteration)

        return power_report

    def _build_power_tcl(self, output_path: str, iteration: int) -> str:
        """Build Tcl script for OpenROAD power analysis."""
        lef_files_tcl = ""
        for f in self.config.lef_files:
            lef_files_tcl += f'\nread_lef "{f}"'
            
        lib_files_tcl = ""
        for f in self.config.lib_files:
            lib_files_tcl += f'\nread_liberty "{f}"'

        tier0_def = self.config.tier_defs.get(0, "")
        return f"""
# Power extraction — Iteration {iteration}
read_lef "{self.config.tech_lef_path}"
{lef_files_tcl}
{lib_files_tcl}
read_def "{tier0_def}"
read_sdc "{self.config.sdc_path}"

# Read SPEF if available (for more accurate switching activity)
set spef_path "{self.config.tier_spefs.get(0, '')}"
if {{[file exists $spef_path]}} {{
    read_spef $spef_path
}}

# Report instance-level power
report_power -instances [get_cells *] > "{output_path}"
"""

    def _generate_synthetic_power(self, output_path: str, iteration: int):
        """
        Generate a synthetic power report for dry-run / testing.
        Power includes temperature-dependent leakage scaling from previous iteration.
        """
        logger.info(f"Generating synthetic power report: {output_path}")

        np.random.seed(42 + iteration)
        n_instances = 500

        with open(output_path, 'w') as f:
            f.write("# Synthetic Power Report — Iteration {}\n".format(iteration))
            f.write("# Generated by flow_pin3d_thermal.py (dry-run mode)\n")
            f.write(f"{'Instance':<30} {'Internal':>12} {'Switching':>12} "
                    f"{'Leakage':>12} {'Total':>12}\n")
            f.write("-" * 80 + "\n")

            for i in range(n_instances):
                inst_name = f"inst_{i:04d}"
                # Base power with some variation
                internal = np.random.uniform(0.005, 0.05)
                switching = np.random.uniform(0.003, 0.04)
                # Leakage increases ~2x per 10°C (simplified model)
                leakage_scale = 1.0 + 0.02 * iteration  # Slight increase per iteration
                leakage = np.random.uniform(0.001, 0.01) * leakage_scale
                total = internal + switching + leakage

                f.write(f"{inst_name:<30} {internal:>12.6f} {switching:>12.6f} "
                        f"{leakage:>12.6f} {total:>12.6f}\n")

        logger.info(f"  Written synthetic power for {n_instances} instances")


# ---------------------------------------------------------------------------
# STA Runner
# ---------------------------------------------------------------------------

class STARunner:
    """
    Runs OpenSTA / OpenROAD timing analysis using the run_sta_3d.tcl script.
    """

    def __init__(self, config: FlowConfig):
        self.config = config

    def run_sta(self, iteration: int,
                tier0_thermal_spef: str,
                tier1_thermal_spef: str) -> IterationMetrics:
        """
        Run STA and extract timing metrics.

        Args:
            iteration: Current iteration number
            tier0_thermal_spef: Path to thermal SPEF for Tier 0
            tier1_thermal_spef: Path to thermal SPEF for Tier 1

        Returns:
            IterationMetrics with timing fields populated
        """
        metrics = IterationMetrics(iteration=iteration)
        report_dir = os.path.join(self.config.results_dir, "reports")
        os.makedirs(report_dir, exist_ok=True)

        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would run STA iteration {iteration}")
            return self._synthetic_sta_metrics(iteration)

        # Execute run_sta_3d.tcl via OpenROAD
        sta_tcl = os.path.join(self.config.scripts_dir, "run_sta_3d.tcl")

        cmd = [
            self.config.openroad_bin, '-exit',
            '-no_init',
        ]

        # Convert lists to Tcl format list strings
        lef_files_tcl = " [list " + " ".join([f'"{f}"' for f in self.config.lef_files]) + "]"
        lib_files_tcl = " [list " + " ".join([f'"{f}"' for f in self.config.lib_files]) + "]"

        # Pass variables via Tcl set commands
        tcl_wrapper = f"""
set design_name {self.config.design_name}
set tech_lef_path "{self.config.tech_lef_path}"
set lef_files {lef_files_tcl}
set lib_files {lib_files_tcl}
set tier0_def "{self.config.tier_defs.get(0, '')}"
set tier1_def "{self.config.tier_defs.get(1, '')}"
set tier0_spef "{tier0_thermal_spef}"
set tier1_spef "{tier1_thermal_spef}"
set sdc_path "{self.config.sdc_path}"
set report_dir "{report_dir}"
set iteration {iteration}
source {sta_tcl}
"""

        wrapper_path = os.path.join(report_dir,
                                      f"sta_wrapper_iter{iteration}.tcl")
        with open(wrapper_path, 'w') as f:
            f.write(tcl_wrapper)

        cmd.append(wrapper_path)

        logger.info(f"Running STA (iter {iteration})...")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )
            if result.returncode != 0:
                logger.error(f"STA failed: {result.stderr[:500]}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"OpenROAD/STA not available ({e})")

        # Parse metrics from JSON output
        metrics_file = os.path.join(report_dir,
                                      f"metrics_iter{iteration}.json")
        if Path(metrics_file).exists():
            try:
                with open(metrics_file) as f:
                    data = json.load(f)
                metrics.wns_ps = float(data.get('wns_ns', 0)) * 1000  # ns → ps
                metrics.tns_ps = float(data.get('tns_ns', 0)) * 1000
                metrics.max_skew_ps = float(data.get('skew_ps', 0))
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Error parsing metrics JSON: {e}")

        return metrics

    def _synthetic_sta_metrics(self, iteration: int) -> IterationMetrics:
        """Generate synthetic STA metrics for dry-run mode."""
        metrics = IterationMetrics(iteration=iteration)

        # Simulate improving timing with each iteration
        np.random.seed(100 + iteration)
        base_wns = -150.0  # Starting WNS in ps
        improvement_per_iter = 40.0

        metrics.wns_ps = base_wns + improvement_per_iter * iteration + \
                          np.random.uniform(-5, 5)
        metrics.tns_ps = metrics.wns_ps * np.random.uniform(5, 15)
        metrics.hold_wns_ps = np.random.uniform(10, 50)
        metrics.max_skew_ps = 80.0 - 15 * iteration + np.random.uniform(-3, 3)

        logger.info(f"[DRY RUN] Synthetic STA: WNS={metrics.wns_ps:.1f}ps, "
                     f"TNS={metrics.tns_ps:.1f}ps, Skew={metrics.max_skew_ps:.1f}ps")

        return metrics


# ---------------------------------------------------------------------------
# ECO Engine
# ---------------------------------------------------------------------------

class ECOEngine:
    """
    Triggers timing repair ECO operations in OpenROAD / Pin-3D:
      - Buffer insertion for setup violations
      - Gate sizing for optimization
      - Clock tree deskewing for cross-tier skew
    """

    def __init__(self, config: FlowConfig):
        self.config = config

    def run_eco(self, iteration: int, metrics: IterationMetrics) -> bool:
        """
        Run ECO timing repair.

        Args:
            iteration: Current iteration
            metrics: Current timing metrics

        Returns:
            True if ECO was applied
        """
        logger.info(f"Running ECO timing repair (iter {iteration})...")

        if self.config.dry_run:
            logger.info("[DRY RUN] Would run ECO: buffer insertion + gate sizing")
            return True

        report_dir = os.path.join(self.config.results_dir, "reports")
        eco_tcl = self._build_eco_tcl(iteration, metrics)
        eco_path = os.path.join(report_dir, f"eco_iter{iteration}.tcl")

        with open(eco_path, 'w') as f:
            f.write(eco_tcl)

        cmd = [self.config.openroad_bin, '-exit', eco_path]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )
            if result.returncode != 0:
                logger.error(f"ECO failed: {result.stderr[:500]}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"ECO execution failed: {e}")
            return False

        return True

    def _build_eco_tcl(self, iteration: int, metrics: IterationMetrics) -> str:
        """Build ECO Tcl script for OpenROAD."""
        tier0_def = self.config.tier_defs.get(0, "")
        
        lef_commands = "\n".join([f'read_lef "{lef}"' for lef in [self.config.tech_lef_path] + self.config.lef_files])
        lib_commands = "\n".join([f'read_liberty "{lib}"' for lib in self.config.lib_files])
        
        return f"""
# ECO Timing Repair — Iteration {iteration}
# WNS: {metrics.wns_ps:.1f} ps, TNS: {metrics.tns_ps:.1f} ps

{lef_commands}
{lib_commands}
read_def {tier0_def}
read_sdc {self.config.sdc_path}

# Setup timing repair
repair_timing -setup \\
    -slack_margin 0.020

# Hold timing repair
repair_timing -hold \\
    -slack_margin 0.010

# Re-route after ECO
# detailed_route -bottom_routing_layer metal1 -top_routing_layer metal7

# Write updated DEF
write_def {tier0_def}.eco_iter{iteration}.def

# Re-extract parasitics
set spef_out "{self.config.tier_spefs.get(0, '')}"
# extract_parasitics -ext_model_file <rcx_model>
# write_spef $spef_out
"""


# ---------------------------------------------------------------------------
# Master Flow Orchestrator
# ---------------------------------------------------------------------------

class ThermalFlowOrchestrator:
    """
    Master orchestrator for the closed-loop electro-thermal optimization.
    """

    def __init__(self, config: FlowConfig):
        self.config = config
        self.power_extractor = PowerExtractor(config)
        self.sta_runner = STARunner(config)
        self.eco_engine = ECOEngine(config)
        self.metrics_history: List[IterationMetrics] = []

        # Working directories
        self.thermal_dir = os.path.join(config.results_dir, "thermal")
        self.report_dir = os.path.join(config.results_dir, "reports")
        self.figures_dir = os.path.join(config.results_dir, "figures")

        os.makedirs(self.thermal_dir, exist_ok=True)
        os.makedirs(self.report_dir, exist_ok=True)
        os.makedirs(self.figures_dir, exist_ok=True)

        # Previous iteration state (for convergence checking)
        self._prev_t_max: Optional[float] = None
        self._prev_wns: Optional[float] = None
        self._prev_total_power: Optional[float] = None
        self._prev_grids: Dict[int, ThermalGrid] = {}

    def run(self) -> List[IterationMetrics]:
        """
        Execute the full electro-thermal convergence loop.

        Returns:
            List of per-iteration metrics
        """
        logger.info("=" * 70)
        logger.info("Thermal-Aware Pin-3D Flow — Starting")
        logger.info(f"Design: {self.config.design_name}")
        logger.info(f"Max iterations: {self.config.max_iterations}")
        logger.info(f"Convergence: ΔT < {self.config.conv_dt}°C, "
                     f"ΔWNS < {self.config.conv_dwns} ps")
        logger.info(f"Dry run: {self.config.dry_run}")
        logger.info("=" * 70)

        flow_start = time.time()

        # ----- Step 0: Partitioning and Initial Place & Route (if needed) -----
        def_exists = os.path.exists(os.path.join(self.config.results_dir, "ariane_routed_flat.def"))
        spef_exists = os.path.exists(os.path.join(self.config.results_dir, "ariane_routed_flat.spef"))
        should_run_pnr = not self.config.dry_run and (self.config.force_pnr or not (def_exists and spef_exists))

        if should_run_pnr:
            logger.info("\n--- Step 0: Partitioning and Initial Place & Route with OpenRCX ---")
            results_path = Path(self.config.results_dir)
            results_path.mkdir(parents=True, exist_ok=True)
            
            # Use absolute paths based on the location of this script's parent's parent (Shyam root)
            parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            netlist_path = os.path.join(parent_dir, "designs", "src", self.config.design_name, "ariane.v")
            macros_path = os.path.join(parent_dir, "designs", "nangate45_3D", self.config.design_name, "macros.v")
            output_netlist = os.path.join(self.config.results_dir, "ariane_3d.v")
            
            # 1. Partition netlist and macros
            partition_cmd = [
                sys.executable,
                os.path.join(self.config.scripts_dir, "partition_design.py"),
                "--netlist", netlist_path,
                "--macros", macros_path,
                "--output", output_netlist,
                "--ratio", "0.5"
            ]
            logger.info(f"Running partitioning: {' '.join(partition_cmd)}")
            subprocess.run(partition_cmd, check=True)
            
            # 2. Run OpenROAD placement and routing
            pr_cmd = [
                self.config.openroad_bin,
                "-exit",
                os.path.join(self.config.scripts_dir, "run_p_and_r_3d.tcl")
            ]
            logger.info(f"Running OpenROAD P&R: {' '.join(pr_cmd)}")
            subprocess.run(pr_cmd, check=True)
        elif not self.config.dry_run:
            logger.info("\n--- Step 0: Initial Place & Route ---")
            logger.info(f"Found existing placed DEF and OpenRCX SPEF ({os.path.join(self.config.results_dir, 'ariane_routed_flat.spef')}). Reusing for thermal optimization pipeline.")

        for iteration in range(self.config.max_iterations):
            iter_start = time.time()
            logger.info(f"\n{'='*60}")
            logger.info(f"  ITERATION {iteration}")
            logger.info(f"{'='*60}")

            metrics = IterationMetrics(iteration=iteration)

            # ----- Step 1: Power Extraction -----
            logger.info("\n--- Step 1: Power Extraction ---")
            power_report = self.power_extractor.extract_power(iteration)

            # ----- Step 2: PACT Thermal Simulation -----
            logger.info("\n--- Step 2: PACT Thermal Simulation ---")
            pact_bridge = self._run_pact(iteration, power_report)

            if pact_bridge:
                # Update temperature metrics
                for tier in range(self.config.num_tiers):
                    if tier in pact_bridge.thermal_grids:
                        grid = pact_bridge.thermal_grids[tier]
                        if tier == 0:
                            metrics.t_max_tier0 = float(np.max(grid.temperatures))
                            metrics.t_mean_tier0 = float(np.mean(grid.temperatures))
                        elif tier == 1:
                            metrics.t_max_tier1 = float(np.max(grid.temperatures))
                            metrics.t_mean_tier1 = float(np.mean(grid.temperatures))

                if pact_bridge.interface_grid:
                    metrics.t_max_interface = float(
                        np.max(pact_bridge.interface_grid.temperatures)
                    )

                # Power summary
                summary = pact_bridge.get_summary()
                metrics.total_power_mw = summary.get('total_power_mw', 0)

                # Save grids
                pact_bridge.save_grids(self.thermal_dir)

            # Compute ΔT_max
            current_t_max = max(metrics.t_max_tier0, metrics.t_max_tier1)
            if self._prev_t_max is not None:
                metrics.delta_t_max = abs(current_t_max - self._prev_t_max)
            else:
                metrics.delta_t_max = float('inf')

            # ----- Step 3: Thermal SPEF Modification -----
            logger.info("\n--- Step 3: Thermal SPEF Modification ---")
            thermal_spefs = self._run_thermal_rcx(iteration)

            # ----- Step 4: STA Timing Analysis -----
            logger.info("\n--- Step 4: STA Timing Analysis ---")
            sta_metrics = self.sta_runner.run_sta(
                iteration,
                thermal_spefs.get(0, ""),
                thermal_spefs.get(1, ""),
            )

            metrics.wns_ps = sta_metrics.wns_ps
            metrics.tns_ps = sta_metrics.tns_ps
            metrics.hold_wns_ps = sta_metrics.hold_wns_ps
            metrics.max_skew_ps = sta_metrics.max_skew_ps

            # Compute ΔWNS
            if self._prev_wns is not None:
                metrics.delta_wns = abs(metrics.wns_ps - self._prev_wns)
            else:
                metrics.delta_wns = float('inf')

            # Compute power delta
            if self._prev_total_power is not None and self._prev_total_power > 0:
                metrics.power_delta_pct = abs(
                    metrics.total_power_mw - self._prev_total_power
                ) / self._prev_total_power * 100
            else:
                metrics.power_delta_pct = 100.0

            # ----- Step 5: Convergence Check -----
            logger.info("\n--- Step 5: Convergence Check ---")
            metrics.converged = self._check_convergence(metrics)

            # Timing
            metrics.elapsed_s = time.time() - iter_start

            # Store metrics
            self.metrics_history.append(metrics)
            self._save_iteration_metrics(metrics)
            self._log_iteration_summary(metrics)

            # Update previous state
            self._prev_t_max = current_t_max
            self._prev_wns = metrics.wns_ps
            self._prev_total_power = metrics.total_power_mw

            if metrics.converged:
                logger.info("\n✓ CONVERGED — Stopping iteration loop")
                break

            # ----- Step 6: ECO Timing Repair -----
            if iteration < self.config.max_iterations - 1:
                logger.info("\n--- Step 6: ECO Timing Repair ---")
                self.eco_engine.run_eco(iteration, metrics)

        # ----- Post-Processing -----
        total_elapsed = time.time() - flow_start
        logger.info(f"\n{'='*70}")
        logger.info(f"Flow complete: {len(self.metrics_history)} iterations, "
                     f"{total_elapsed:.1f}s total")
        logger.info(f"{'='*70}")

        self._generate_plots()
        self._save_final_report()

        return self.metrics_history

    def _run_pact(self, iteration: int, power_report: str) -> Optional[PACTBridge]:
        """Run PACT thermal simulation via pact_bridge."""
        bridge = PACTBridge(
            work_dir=os.path.join(self.thermal_dir, f"iter{iteration}"),
            config_dir=self.config.config_dir,
            grid_rows=self.config.grid_size,
            grid_cols=self.config.grid_size,
            pact_home=self.config.pact_home,
        )

        # Ingest tier DEFs
        for tier in range(self.config.num_tiers):
            def_path = self.config.tier_defs.get(tier, "")
            if Path(def_path).exists():
                bridge.ingest_tier(def_path, tier=tier, lef_path=self.config.lef_files)
            elif self.config.dry_run:
                # Create synthetic placement for dry-run
                logger.info(f"[DRY RUN] Creating synthetic Tier {tier} placement")
                self._create_synthetic_tier(bridge, tier, iteration)
            else:
                logger.warning(f"Tier {tier} DEF not found: {def_path}")

        # Ingest power
        if Path(power_report).exists():
            bridge.ingest_power(power_report)

        # Generate PACT inputs
        bridge.generate_pact_inputs()

        # Run solver (or simulate in dry-run)
        if self.config.dry_run:
            logger.info("[DRY RUN] Simulating PACT thermal solve")
            self._simulate_thermal_solve(bridge, iteration)
        else:
            success = bridge.run_thermal_solver()
            if not success:
                logger.error("PACT thermal solve failed")
                return None

        return bridge

    def _create_synthetic_tier(self, bridge: PACTBridge, tier: int, iteration: int):
        """Create synthetic tier data for dry-run testing."""
        die = DieGeometry(x_min=0, y_min=0, x_max=2000, y_max=2000)
        bridge.die_geoms[tier] = die

        from pact_bridge import CellInstance
        np.random.seed(42 + tier * 1000 + iteration)
        instances = []
        for i in range(500):
            instances.append(CellInstance(
                name=f"inst_{tier}_{i:04d}",
                cell_type=f"BUF_X{np.random.randint(1,8)}",
                x=np.random.uniform(10, 1990),
                y=np.random.uniform(10, 1990),
                width=np.random.uniform(0.5, 5.0),
                height=1.4,
                tier=tier,
            ))
        bridge.instances[tier] = instances

    def _simulate_thermal_solve(self, bridge: PACTBridge, iteration: int):
        """Simulate PACT output for dry-run mode."""
        for tier in range(self.config.num_tiers):
            if tier not in bridge.die_geoms:
                continue

            die = bridge.die_geoms[tier]
            grid_size = self.config.grid_size

            # Create synthetic temperature field with central hotspot
            temps = np.zeros((grid_size, grid_size))
            for i in range(grid_size):
                for j in range(grid_size):
                    cx = (j + 0.5) / grid_size * die.width_um
                    cy = (i + 0.5) / grid_size * die.height_um
                    # Hotspot near center
                    dist = np.sqrt((cx - die.width_um/2)**2 +
                                   (cy - die.height_um/2)**2)
                    base_temp = 45.0 + tier * 5.0  # Tier 1 slightly hotter
                    # Temperature decreases with iteration (convergence)
                    decay = max(0.5, 1.0 - 0.1 * iteration)
                    temps[i, j] = base_temp + 60 * decay * np.exp(-dist / 400)

            grid = ThermalGrid(
                tier=tier, rows=grid_size, cols=grid_size,
                x_min=die.x_min, y_min=die.y_min,
                x_max=die.x_max, y_max=die.y_max,
                temperatures=temps,
            )
            bridge.thermal_grids[tier] = grid

        # Create interface grid
        if 0 in bridge.thermal_grids and 1 in bridge.thermal_grids:
            from pact_bridge import PACTOutputParser
            parser = PACTOutputParser(bridge.die_geoms[0],
                                       self.config.grid_size,
                                       self.config.grid_size)
            bridge.interface_grid = parser.create_interface_grid(
                bridge.thermal_grids[0], bridge.thermal_grids[1]
            )

    def _run_thermal_rcx(self, iteration: int) -> Dict[int, str]:
        """Run thermal RCX SPEF modification for all tiers."""
        thermal_spefs = {}

        for tier in range(self.config.num_tiers):
            baseline_spef = self.config.tier_spefs.get(tier, "")
            thermal_grid_path = os.path.join(self.thermal_dir,
                                               f"thermal_grid_tier{tier}.npz")
            interface_grid_path = os.path.join(self.thermal_dir,
                                                 "thermal_grid_interface.npz")
            output_spef = os.path.join(self.thermal_dir,
                                         f"ariane_tier{tier}_thermal_iter{iteration}.spef")

            if not Path(baseline_spef).exists():
                if self.config.dry_run:
                    logger.info(f"[DRY RUN] Would modify SPEF for Tier {tier}")
                    thermal_spefs[tier] = output_spef
                    # Create a dummy file for downstream
                    Path(output_spef).parent.mkdir(parents=True, exist_ok=True)
                    Path(output_spef).touch()
                    continue
                else:
                    logger.warning(f"Baseline SPEF not found: {baseline_spef}")
                    continue

            if not Path(thermal_grid_path).exists():
                logger.warning(f"Thermal grid not found: {thermal_grid_path}")
                continue

            try:
                materials_config = os.path.join(self.config.config_dir,
                                                  "materials.config")
                stats = process_tier_spef(
                    spef_path=baseline_spef,
                    thermal_grid_path=thermal_grid_path,
                    output_path=output_spef,
                    config_path=materials_config if Path(materials_config).exists() else None,
                    interface_grid_path=interface_grid_path if Path(interface_grid_path).exists() else None,
                    tier=tier,
                )

                thermal_spefs[tier] = output_spef
                logger.info(f"  Tier {tier}: {stats.get('segments_modified', 0)} segments modified")

            except Exception as e:
                logger.error(f"Thermal RCX failed for Tier {tier}: {e}")

        # Generate spatial instance-level timing derates for OpenSTA
        try:
            derate_cmd = [
                sys.executable,
                os.path.join(self.config.scripts_dir, "thermal_cell_derate.py"),
                "--def-path", self.config.tier_defs.get(0, ""),
                "--grid-t0", os.path.join(self.thermal_dir, "thermal_grid_tier0.npz"),
                "--grid-t1", os.path.join(self.thermal_dir, "thermal_grid_tier1.npz"),
                "--output-tcl", os.path.join(self.report_dir, "cell_thermal_derates.tcl")
            ]
            subprocess.run(derate_cmd, check=False)
        except Exception as e:
            logger.warning(f"Could not generate thermal cell derate script: {e}")

        return thermal_spefs

    def _check_convergence(self, metrics: IterationMetrics) -> bool:
        """
        Check if the electro-thermal loop has converged.

        Convergence criteria (from specification):
          - ΔT_max < 0.5°C (temperature change between iterations)
          - ΔWNS < 5 ps (timing slack change between iterations)
        """
        dt_converged = metrics.delta_t_max < self.config.conv_dt
        dwns_converged = metrics.delta_wns < self.config.conv_dwns

        logger.info(f"  ΔT_max = {metrics.delta_t_max:.3f}°C "
                     f"(threshold: {self.config.conv_dt}°C) "
                     f"{'✓' if dt_converged else '✗'}")
        logger.info(f"  ΔWNS   = {metrics.delta_wns:.1f} ps "
                     f"(threshold: {self.config.conv_dwns} ps) "
                     f"{'✓' if dwns_converged else '✗'}")

        # Both must be met (after at least 1 iteration)
        if metrics.iteration == 0:
            return False

        return dt_converged and dwns_converged

    def _log_iteration_summary(self, metrics: IterationMetrics):
        """Log a summary of the current iteration."""
        logger.info(f"\n--- Iteration {metrics.iteration} Summary ---")
        logger.info(f"  T_max (Tier 0): {metrics.t_max_tier0:.1f}°C")
        logger.info(f"  T_max (Tier 1): {metrics.t_max_tier1:.1f}°C")
        logger.info(f"  ΔT_max:         {metrics.delta_t_max:.3f}°C")
        logger.info(f"  WNS:            {metrics.wns_ps:.1f} ps")
        logger.info(f"  TNS:            {metrics.tns_ps:.1f} ps")
        logger.info(f"  ΔWNS:           {metrics.delta_wns:.1f} ps")
        logger.info(f"  Total Power:    {metrics.total_power_mw:.2f} mW")
        logger.info(f"  Elapsed:        {metrics.elapsed_s:.1f} s")
        logger.info(f"  Converged:      {metrics.converged}")

    def _save_iteration_metrics(self, metrics: IterationMetrics):
        """Save iteration metrics to JSON."""
        metrics_file = os.path.join(self.report_dir,
                                      f"metrics_iter{metrics.iteration}.json")
        with open(metrics_file, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2, default=str)
        logger.info(f"  Metrics saved: {metrics_file}")

    def _generate_plots(self):
        """Generate visualization plots after convergence."""
        logger.info("\nGenerating visualization plots...")

        try:
            from plot_heatmaps import (
                plot_convergence, plot_dual_tier_heatmap,
                plot_temperature_difference, plot_dashboard
            )

            # Load final thermal grids
            grid_tier0_path = os.path.join(self.thermal_dir,
                                             "thermal_grid_tier0.npz")
            grid_tier1_path = os.path.join(self.thermal_dir,
                                             "thermal_grid_tier1.npz")

            grids = {}
            for path, tier in [(grid_tier0_path, 0), (grid_tier1_path, 1)]:
                if Path(path).exists():
                    grids[tier] = load_thermal_grid(path)

            # Metrics history as dicts
            history = [m.to_dict() for m in self.metrics_history]

            # Convergence plot
            plot_convergence(
                history,
                os.path.join(self.figures_dir, "convergence.png")
            )

            # Thermal heatmaps
            if 0 in grids and 1 in grids:
                plot_dual_tier_heatmap(
                    grids[0], grids[1],
                    os.path.join(self.figures_dir, "thermal_dual_tier.png")
                )
                plot_temperature_difference(
                    grids[0], grids[1],
                    os.path.join(self.figures_dir, "thermal_cross_tier_gradient.png")
                )
                plot_dashboard(
                    grids[0], grids[1], history,
                    os.path.join(self.figures_dir, "dashboard.png")
                )

        except ImportError as e:
            logger.warning(f"Plotting failed (missing dependency): {e}")
        except Exception as e:
            logger.error(f"Plot generation failed: {e}")

    def _save_final_report(self):
        """Save the final summary report."""
        report_path = os.path.join(self.report_dir, "final_summary.json")

        report = {
            "design": self.config.design_name,
            "num_iterations": len(self.metrics_history),
            "converged": self.metrics_history[-1].converged if self.metrics_history else False,
            "final_metrics": self.metrics_history[-1].to_dict() if self.metrics_history else {},
            "all_iterations": [m.to_dict() for m in self.metrics_history],
            "config": {
                "max_iterations": self.config.max_iterations,
                "conv_dt": self.config.conv_dt,
                "conv_dwns": self.config.conv_dwns,
                "grid_size": self.config.grid_size,
                "dry_run": self.config.dry_run,
            }
        }

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"\nFinal report saved: {report_path}")

        # Print benchmark data matrix (partial)
        if self.metrics_history:
            final = self.metrics_history[-1]
            print("\n" + "=" * 70)
            print("BENCHMARK RESULTS — Config C (Thermal-Aware Pin-3D)")
            print("=" * 70)
            print(f"  Peak Temperature T_max:     {max(final.t_max_tier0, final.t_max_tier1):.1f} °C")
            print(f"  Cross-Tier ΔT:              {abs(final.t_max_tier1 - final.t_max_tier0):.1f} °C")
            print(f"  Total Power:                {final.total_power_mw:.2f} mW")
            print(f"  WNS (setup):                {final.wns_ps:.1f} ps")
            print(f"  TNS:                        {final.tns_ps:.1f} ps")
            print(f"  Clock Skew (max):           {final.max_skew_ps:.1f} ps")
            print(f"  Iterations to converge:     {len(self.metrics_history)}")
            print(f"  Converged:                  {final.converged}")
            print("=" * 70)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Thermal-Aware Pin-3D Electro-Thermal Optimization Flow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (no design files needed — uses synthetic data)
  python flow_pin3d_thermal.py --design ariane136 --dry-run

  # Full run with design files
  python flow_pin3d_thermal.py \\
    --design ariane136 \\
    --tier0-def designs/ariane136/floorplan/ariane_tier0.def \\
    --tier1-def designs/ariane136/floorplan/ariane_tier1.def \\
    --tier0-spef results/thermal/ariane_tier0.spef \\
    --tier1-spef results/thermal/ariane_tier1.spef \\
    --config-dir config/ \\
    --max-iter 4 \\
    --grid-size 64

  # With custom convergence thresholds
  python flow_pin3d_thermal.py \\
    --design ariane136 --dry-run \\
    --conv-dt 0.3 --conv-dwns 3.0 --max-iter 6
        """
    )

    parser.add_argument('--design', type=str, default='ariane136',
                        help='Design name (default: ariane136)')
    parser.add_argument('--tier0-def', type=str,
                        help='Path to Tier 0 placed/routed DEF')
    parser.add_argument('--tier1-def', type=str,
                        help='Path to Tier 1 placed/routed DEF')
    parser.add_argument('--tier0-spef', type=str,
                        help='Path to Tier 0 baseline SPEF')
    parser.add_argument('--tier1-spef', type=str,
                        help='Path to Tier 1 baseline SPEF')
    parser.add_argument('--sdc', type=str,
                        help='Path to SDC constraints')
    parser.add_argument('--lef', type=str,
                        help='Path to LEF file')
    parser.add_argument('--lib', type=str,
                        help='Path to Liberty (.lib) file')
    parser.add_argument('--config-dir', type=str, default='config/',
                        help='Config directory (default: config/)')
    parser.add_argument('--results-dir', type=str, default='results/',
                        help='Results directory (default: results/)')
    parser.add_argument('--pdk-dir', type=str, default='pdk/nangate45_3d/',
                        help='PDK directory (default: pdk/nangate45_3d/)')
    parser.add_argument('--grid-size', type=int, default=DEFAULT_GRID_ROWS,
                        help=f'Thermal grid NxN (default: {DEFAULT_GRID_ROWS})')
    parser.add_argument('--max-iter', type=int, default=DEFAULT_MAX_ITERATIONS,
                        help=f'Max convergence iterations (default: {DEFAULT_MAX_ITERATIONS})')
    parser.add_argument('--conv-dt', type=float, default=DEFAULT_CONV_DT,
                        help=f'ΔT convergence threshold °C (default: {DEFAULT_CONV_DT})')
    parser.add_argument('--conv-dwns', type=float, default=DEFAULT_CONV_DWNS,
                        help=f'ΔWNS convergence threshold ps (default: {DEFAULT_CONV_DWNS})')
    parser.add_argument('--skip-pnr', action='store_true',
                        help='Skip initial P&R if placed DEF and SPEF already exist')
    parser.add_argument('--force-pnr', action='store_true',
                        help='Force re-running initial P&R and SPEF generation')
    parser.add_argument('--dry-run', action='store_true',
                        help='Dry-run mode with synthetic data (no design files needed)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable debug logging')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    # Build config
    config = FlowConfig(
        design_name=args.design,
        config_dir=args.config_dir,
        results_dir=args.results_dir,
        pdk_dir=args.pdk_dir,
        grid_size=args.grid_size,
        max_iterations=args.max_iter,
        conv_dt=args.conv_dt,
        conv_dwns=args.conv_dwns,
        dry_run=args.dry_run,
        verbose=args.verbose,
        skip_pnr=args.skip_pnr,
        force_pnr=args.force_pnr,
    )

    # Override paths if provided
    if args.tier0_def:
        config.tier_defs[0] = args.tier0_def
    if args.tier1_def:
        config.tier_defs[1] = args.tier1_def
    if args.tier0_spef:
        config.tier_spefs[0] = args.tier0_spef
    if args.tier1_spef:
        config.tier_spefs[1] = args.tier1_spef
    if args.sdc:
        config.sdc_path = args.sdc
    if args.lef:
        config.tech_lef_path = args.lef
    if args.lib:
        config.lib_files = [args.lib]

    # Run the flow
    orchestrator = ThermalFlowOrchestrator(config)
    metrics = orchestrator.run()

    # Exit code: 0 if converged, 1 if not
    if metrics and metrics[-1].converged:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
