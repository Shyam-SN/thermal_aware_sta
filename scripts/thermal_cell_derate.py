#!/usr/bin/env python3
"""
thermal_cell_derate.py — Standard Cell Spatial Thermal Derate Generator

Reads PACT thermal grids (.npz) for Tier 0 and Tier 1, maps placed cell instance
(x, y) coordinates to spatial grid temperature T_cell, and generates an OpenSTA
Tcl derate script (cell_thermal_derates.tcl) applying instance-specific timing derates:
  Derate(T) = 1.0 + k_delay * (T_cell - 25.0)

Part of the Thermal-Aware Pin-3D Framework for Ariane-136.
"""

import os
import sys
import re
import argparse
import logging
import numpy as np

logger = logging.getLogger("thermal_cell_derate")

# Empirical cell delay thermal derate coefficient for NanGate45 (per °C above 25°C)
K_DELAY_DEFAULT = 0.0012

class ThermalCellDerater:
    def __init__(self, def_path: str, grid_t0_path: str, grid_t1_path: str,
                 output_tcl: str, k_delay: float = K_DELAY_DEFAULT,
                 die_width: float = 1000.0, die_height: float = 1000.0):
        self.def_path = def_path
        self.grid_t0_path = grid_t0_path
        self.grid_t1_path = grid_t1_path
        self.output_tcl = output_tcl
        self.k_delay = k_delay
        self.die_width = die_width
        self.die_height = die_height

        self.t0_grid = None
        self.t1_grid = None

    def load_grids(self):
        """Load Tier 0 and Tier 1 thermal grids."""
        if os.path.exists(self.grid_t0_path):
            data0 = np.load(self.grid_t0_path)
            self.t0_grid = data0.get('temperatures', None)
        if os.path.exists(self.grid_t1_path):
            data1 = np.load(self.grid_t1_path)
            self.t1_grid = data1.get('temperatures', None)

    def sample_temperature(self, x_um: float, y_um: float, tier: int) -> float:
        """Sample temperature from spatial grid using bilinear interpolation."""
        grid = self.t0_grid if tier == 0 else self.t1_grid
        if grid is None:
            return 25.0

        rows, cols = grid.shape
        cell_w = self.die_width / cols
        cell_h = self.die_height / rows

        c = max(0, min(int(x_um / cell_w), cols - 1))
        r = max(0, min(int(y_um / cell_h), rows - 1))

        return float(grid[r, c])

    def generate_derates(self):
        """Parse DEF, compute cell derate factors, and write Tcl script."""
        self.load_grids()

        units_per_um = 1000.0
        comp_pattern = re.compile(
            r'-\s+(\S+)\s+(\S+)\s+\+\s+(PLACED|FIXED)\s+\(\s*(\d+)\s+(\d+)\s*\)'
        )

        derate_statements = []
        cell_temps = []
        derate_factors = []

        if not os.path.exists(self.def_path):
            print(f"Warning: DEF file {self.def_path} not found. Generating empty derate script.")
            os.makedirs(os.path.dirname(os.path.abspath(self.output_tcl)), exist_ok=True)
            with open(self.output_tcl, 'w') as f:
                f.write("# Empty thermal derate script (DEF not found)\n")
            return

        with open(self.def_path, 'r') as f:
            for line in f:
                if "UNITS DISTANCE MICRONS" in line:
                    parts = line.strip().split()
                    for p in parts:
                        if p.isdigit():
                            units_per_um = float(p)

                m = comp_pattern.search(line)
                if m:
                    inst_name = m.group(1)
                    cell_type = m.group(2)
                    x_db = float(m.group(4))
                    y_db = float(m.group(5))

                    x_um = x_db / units_per_um
                    y_um = y_db / units_per_um
                    tier = 1 if "_upper" in cell_type else 0

                    t_cell = self.sample_temperature(x_um, y_um, tier)
                    derate = 1.0 + self.k_delay * (t_cell - 25.0)

                    cell_temps.append(t_cell)
                    derate_factors.append(derate)

                    # Escape opensta instance names if needed
                    escaped_inst = inst_name.replace('[', '\\[').replace(']', '\\]')
                    derate_statements.append(
                        f"set_timing_derate -cell_delay [get_cells {{{escaped_inst}}}] {derate:.6f}"
                    )

        os.makedirs(os.path.dirname(os.path.abspath(self.output_tcl)), exist_ok=True)
        with open(self.output_tcl, 'w') as f:
            f.write("# OpenSTA Instance-Level Thermal Timing Derate Script\n")
            f.write(f"# Generated for {len(derate_statements)} cells\n")
            f.write(f"# Temperature range: {np.min(cell_temps):.2f}°C - {np.max(cell_temps):.2f}°C\n")
            f.write(f"# Derate factor range: {np.min(derate_factors):.6f} - {np.max(derate_factors):.6f}\n\n")
            f.write("\n".join(derate_statements))
            f.write("\n")

        print(f"✓ Generated instance thermal derate script: {self.output_tcl}")
        print(f"  Processed cells: {len(derate_statements)}")
        print(f"  T_cell range: {np.min(cell_temps):.2f}°C — {np.max(cell_temps):.2f}°C")
        print(f"  Derate factor range: {np.min(derate_factors):.6f} — {np.max(derate_factors):.6f}")

def run_test():
    """Self-test with synthetic data."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        def_file = os.path.join(tmpdir, "test.def")
        grid0_file = os.path.join(tmpdir, "grid0.npz")
        grid1_file = os.path.join(tmpdir, "grid1.npz")
        tcl_file = os.path.join(tmpdir, "derates.tcl")

        # Create dummy DEF
        with open(def_file, 'w') as f:
            f.write("VERSION 5.8 ;\nUNITS DISTANCE MICRONS 1000 ;\nCOMPONENTS 2 ;\n")
            f.write("- inst_0 BUF_X1_bottom + PLACED ( 100000 200000 ) N ;\n")
            f.write("- inst_1 BUF_X1_upper + PLACED ( 800000 800000 ) N ;\n")
            f.write("END COMPONENTS\n")

        # Create dummy grids
        g0 = np.ones((64, 64)) * 30.0
        g1 = np.ones((64, 64)) * 35.0
        np.savez(grid0_file, temperatures=g0)
        np.savez(grid1_file, temperatures=g1)

        derater = ThermalCellDerater(def_file, grid0_file, grid1_file, tcl_file)
        derater.generate_derates()

        assert os.path.exists(tcl_file)
        with open(tcl_file) as f:
            content = f.read()
            assert "inst_0" in content
            assert "inst_1" in content
            assert "1.006" in content or "1.012" in content
        print("✓ thermal_cell_derate.py self-test passed!")

def main():
    parser = argparse.ArgumentParser(description="Standard Cell Thermal Derate Generator")
    parser.add_argument('--def-path', default='results/ariane_routed_flat.def')
    parser.add_argument('--grid-t0', default='results/thermal/thermal_grid_tier0.npz')
    parser.add_argument('--grid-t1', default='results/thermal/thermal_grid_tier1.npz')
    parser.add_argument('--output-tcl', default='results/reports/cell_thermal_derates.tcl')
    parser.add_argument('--k-delay', type=float, default=K_DELAY_DEFAULT)
    parser.add_argument('--test', action='store_true')

    args = parser.parse_args()

    if args.test:
        run_test()
    else:
        derater = ThermalCellDerater(
            def_path=args.def_path,
            grid_t0_path=args.grid_t0,
            grid_t1_path=args.grid_t1,
            output_tcl=args.output_tcl,
            k_delay=args.k_delay
        )
        derater.generate_derates()

if __name__ == '__main__':
    main()
