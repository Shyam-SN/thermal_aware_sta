#!/usr/bin/env python3
"""
plot_heatmaps.py — Thermal Map and Timing Visualization Module

Generates publication-quality visualizations:
  1. Spatial thermal heatmaps for Tier 0, Tier 1, and bonding interface
  2. Setup/hold slack distribution histograms
  3. Cross-tier clock skew scatter plots
  4. Electro-thermal convergence curves (ΔT_max, WNS vs. iteration)
  5. Power density maps

Part of the Thermal-Aware Pin-3D Framework for Ariane-136.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Import thermal grid utilities
try:
    from pact_bridge import ThermalGrid, load_thermal_grid
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pact_bridge import ThermalGrid, load_thermal_grid

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logger = logging.getLogger("plot_heatmaps")

# Try importing matplotlib (may not be available in all environments)
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.gridspec import GridSpec
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib not available — plotting disabled")

# Color maps
THERMAL_CMAP = 'hot'           # For temperature heatmaps
POWER_CMAP = 'YlOrRd'         # For power density maps
SLACK_CMAP = 'RdYlGn'         # For timing slack maps
DIVERGING_CMAP = 'coolwarm'   # For temperature differences

# Figure defaults
FIG_DPI = 150
FIG_FORMAT = 'png'  # 'png' or 'pdf'


# ---------------------------------------------------------------------------
# Thermal Heatmap Plotting
# ---------------------------------------------------------------------------

def plot_thermal_heatmap(grid: ThermalGrid, output_path: str,
                          title: str = "Temperature Distribution",
                          die_width_um: float = None,
                          die_height_um: float = None,
                          vmin: float = None, vmax: float = None):
    """
    Plot a 2D thermal heatmap for a single tier.

    Args:
        grid: ThermalGrid with temperature data
        output_path: Output image path
        title: Plot title
        die_width_um: Die width for axis labels (µm)
        die_height_um: Die height for axis labels (µm)
        vmin, vmax: Temperature range for colorbar
    """
    if not HAS_MATPLOTLIB:
        logger.warning("Skipping plot (matplotlib not available)")
        return

    fig, ax = plt.subplots(figsize=(8, 7))

    if die_width_um and die_height_um:
        extent = [0, die_width_um, 0, die_height_um]
        ax.set_xlabel('X Position (µm)', fontsize=12)
        ax.set_ylabel('Y Position (µm)', fontsize=12)
    else:
        extent = [grid.x_min, grid.x_max, grid.y_min, grid.y_max]
        ax.set_xlabel('X (µm)', fontsize=12)
        ax.set_ylabel('Y (µm)', fontsize=12)

    if vmin is None:
        vmin = np.min(grid.temperatures)
    if vmax is None:
        vmax = np.max(grid.temperatures)

    im = ax.imshow(
        grid.temperatures,
        origin='lower',
        extent=extent,
        cmap=THERMAL_CMAP,
        vmin=vmin,
        vmax=vmax,
        interpolation='bilinear',
        aspect='equal',
    )

    # Add colorbar
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.1)
    cbar = plt.colorbar(im, cax=cax)
    cbar.set_label('Temperature (°C)', fontsize=12)

    ax.set_title(title, fontsize=14, fontweight='bold')

    # Add peak temperature marker
    peak_idx = np.unravel_index(np.argmax(grid.temperatures),
                                 grid.temperatures.shape)
    if extent:
        peak_x = extent[0] + (peak_idx[1] + 0.5) / grid.cols * (extent[1] - extent[0])
        peak_y = extent[2] + (peak_idx[0] + 0.5) / grid.rows * (extent[3] - extent[2])
    else:
        peak_x = peak_idx[1]
        peak_y = peak_idx[0]

    ax.plot(peak_x, peak_y, 'w*', markersize=15, markeredgecolor='black',
            markeredgewidth=1.0)
    ax.annotate(
        f'Peak: {np.max(grid.temperatures):.1f}°C',
        xy=(peak_x, peak_y),
        xytext=(20, 20),
        textcoords='offset points',
        fontsize=10,
        color='white',
        fontweight='bold',
        arrowprops=dict(arrowstyle='->', color='white', lw=1.5),
        bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7),
    )

    # Add statistics text box
    stats_text = (f'Min: {np.min(grid.temperatures):.1f}°C\n'
                  f'Mean: {np.mean(grid.temperatures):.1f}°C\n'
                  f'Max: {np.max(grid.temperatures):.1f}°C\n'
                  f'Std: {np.std(grid.temperatures):.1f}°C')
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"Saved thermal heatmap: {output_path}")


def plot_dual_tier_heatmap(grid_tier0: ThermalGrid, grid_tier1: ThermalGrid,
                            output_path: str,
                            title: str = "Dual-Tier Temperature Distribution"):
    """
    Plot side-by-side thermal heatmaps for both tiers.
    """
    if not HAS_MATPLOTLIB:
        return

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(16, 7))

    # Unified color scale
    vmin = min(np.min(grid_tier0.temperatures), np.min(grid_tier1.temperatures))
    vmax = max(np.max(grid_tier0.temperatures), np.max(grid_tier1.temperatures))

    for ax, grid, tier_name in [(ax0, grid_tier0, "Tier 0 (Bottom)"),
                                  (ax1, grid_tier1, "Tier 1 (Top)")]:
        extent = [grid.x_min, grid.x_max, grid.y_min, grid.y_max]

        im = ax.imshow(
            grid.temperatures,
            origin='lower',
            extent=extent,
            cmap=THERMAL_CMAP,
            vmin=vmin,
            vmax=vmax,
            interpolation='bilinear',
            aspect='equal',
        )

        ax.set_title(tier_name, fontsize=13, fontweight='bold')
        ax.set_xlabel('X (µm)', fontsize=11)
        ax.set_ylabel('Y (µm)', fontsize=11)

        # Stats
        stats = (f'Min: {np.min(grid.temperatures):.1f}°C\n'
                 f'Max: {np.max(grid.temperatures):.1f}°C')
        ax.text(0.02, 0.98, stats, transform=ax.transAxes,
                fontsize=9, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Shared colorbar
    fig.subplots_adjust(right=0.9)
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label('Temperature (°C)', fontsize=12)

    fig.suptitle(title, fontsize=15, fontweight='bold', y=1.02)

    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"Saved dual-tier heatmap: {output_path}")


def plot_temperature_difference(grid_tier0: ThermalGrid, grid_tier1: ThermalGrid,
                                  output_path: str):
    """
    Plot the cross-tier temperature gradient (Tier 1 - Tier 0).
    """
    if not HAS_MATPLOTLIB:
        return

    fig, ax = plt.subplots(figsize=(8, 7))

    diff = grid_tier1.temperatures - grid_tier0.temperatures
    vabs = max(abs(np.min(diff)), abs(np.max(diff)))

    extent = [grid_tier0.x_min, grid_tier0.x_max,
              grid_tier0.y_min, grid_tier0.y_max]

    im = ax.imshow(
        diff,
        origin='lower',
        extent=extent,
        cmap=DIVERGING_CMAP,
        vmin=-vabs,
        vmax=vabs,
        interpolation='bilinear',
        aspect='equal',
    )

    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.1)
    cbar = plt.colorbar(im, cax=cax)
    cbar.set_label('ΔT (Tier1 - Tier0) [°C]', fontsize=12)

    ax.set_title('Cross-Tier Temperature Gradient', fontsize=14, fontweight='bold')
    ax.set_xlabel('X (µm)', fontsize=12)
    ax.set_ylabel('Y (µm)', fontsize=12)

    stats = (f'Max |ΔT|: {np.max(np.abs(diff)):.1f}°C\n'
             f'Mean ΔT: {np.mean(diff):.1f}°C')
    ax.text(0.02, 0.98, stats, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"Saved temperature difference plot: {output_path}")


# ---------------------------------------------------------------------------
# Convergence Curve Plotting
# ---------------------------------------------------------------------------

def plot_convergence(metrics_history: List[dict], output_path: str):
    """
    Plot convergence curves: ΔT_max and WNS vs. iteration.

    Args:
        metrics_history: List of per-iteration metrics dicts with keys:
            - iteration, delta_t_max, wns_ps, tns_ps, total_power_mw
        output_path: Output image path
    """
    if not HAS_MATPLOTLIB:
        return

    if not metrics_history:
        logger.warning("No metrics history — skipping convergence plot")
        return

    iterations = [m.get('iteration', i) for i, m in enumerate(metrics_history)]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # --- ΔT_max vs Iteration ---
    ax = axes[0, 0]
    dt_vals = [m.get('delta_t_max', 0) for m in metrics_history]
    ax.plot(iterations, dt_vals, 'bo-', linewidth=2, markersize=8)
    ax.axhline(y=0.5, color='r', linestyle='--', linewidth=1, label='Threshold (0.5°C)')
    ax.set_xlabel('Iteration', fontsize=11)
    ax.set_ylabel('ΔT_max (°C)', fontsize=11)
    ax.set_title('Temperature Convergence', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # --- WNS vs Iteration ---
    ax = axes[0, 1]
    wns_vals = [m.get('wns_ps', 0) for m in metrics_history]
    ax.plot(iterations, wns_vals, 'rs-', linewidth=2, markersize=8)
    ax.axhline(y=0, color='g', linestyle='--', linewidth=1, label='Zero slack')
    ax.set_xlabel('Iteration', fontsize=11)
    ax.set_ylabel('WNS (ps)', fontsize=11)
    ax.set_title('Setup Timing Convergence', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # --- TNS vs Iteration ---
    ax = axes[1, 0]
    tns_vals = [m.get('tns_ps', 0) for m in metrics_history]
    ax.plot(iterations, tns_vals, 'g^-', linewidth=2, markersize=8)
    ax.axhline(y=0, color='g', linestyle='--', linewidth=1)
    ax.set_xlabel('Iteration', fontsize=11)
    ax.set_ylabel('TNS (ps)', fontsize=11)
    ax.set_title('Total Negative Slack', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)

    # --- Total Power vs Iteration ---
    ax = axes[1, 1]
    power_vals = [m.get('total_power_mw', 0) for m in metrics_history]
    ax.plot(iterations, power_vals, 'mD-', linewidth=2, markersize=8)
    ax.set_xlabel('Iteration', fontsize=11)
    ax.set_ylabel('Total Power (mW)', fontsize=11)
    ax.set_title('Power Evolution', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)

    fig.suptitle('Electro-Thermal Convergence', fontsize=15, fontweight='bold')
    plt.tight_layout()
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"Saved convergence plot: {output_path}")


# ---------------------------------------------------------------------------
# Slack Distribution Histograms
# ---------------------------------------------------------------------------

def plot_slack_histogram(slack_values: List[float], output_path: str,
                          slack_type: str = "Setup",
                          bins: int = 50):
    """
    Plot a histogram of timing slack values.

    Args:
        slack_values: List of path slack values (positive = met, negative = violated)
        output_path: Output image path
        slack_type: "Setup" or "Hold"
        bins: Number of histogram bins
    """
    if not HAS_MATPLOTLIB:
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    slack_arr = np.array(slack_values)
    colors = np.where(slack_arr >= 0, '#2ecc71', '#e74c3c')

    n, bins_edges, patches = ax.hist(slack_arr, bins=bins, edgecolor='black',
                                       linewidth=0.5)

    # Color bars based on positive/negative
    for patch, left_edge in zip(patches, bins_edges[:-1]):
        if left_edge < 0:
            patch.set_facecolor('#e74c3c')  # Red for violations
        else:
            patch.set_facecolor('#2ecc71')  # Green for met

    ax.axvline(x=0, color='black', linestyle='-', linewidth=2, label='Zero Slack')

    ax.set_xlabel(f'{slack_type} Slack (ps)', fontsize=12)
    ax.set_ylabel('Number of Paths', fontsize=12)
    ax.set_title(f'{slack_type} Slack Distribution', fontsize=14, fontweight='bold')

    # Stats annotation
    n_violated = np.sum(slack_arr < 0)
    n_met = np.sum(slack_arr >= 0)
    stats = (f'Total paths: {len(slack_arr)}\n'
             f'Met: {n_met} ({100*n_met/max(len(slack_arr),1):.1f}%)\n'
             f'Violated: {n_violated} ({100*n_violated/max(len(slack_arr),1):.1f}%)\n'
             f'WNS: {np.min(slack_arr):.1f} ps')
    ax.text(0.02, 0.98, stats, transform=ax.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))

    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"Saved slack histogram: {output_path}")


# ---------------------------------------------------------------------------
# Clock Skew Visualization
# ---------------------------------------------------------------------------

def plot_clock_skew(skew_data: List[dict], output_path: str):
    """
    Plot cross-tier clock skew scatter/bar chart.

    Args:
        skew_data: List of dicts with keys: sink_name, tier, skew_ps, x, y
        output_path: Output image path
    """
    if not HAS_MATPLOTLIB:
        return

    if not skew_data:
        logger.warning("No skew data — skipping plot")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Bar chart of skew values
    names = [d.get('sink_name', f'sink_{i}')[:15] for i, d in enumerate(skew_data)]
    skews = [d.get('skew_ps', 0) for d in skew_data]
    tiers = [d.get('tier', 0) for d in skew_data]
    colors = ['#3498db' if t == 0 else '#e67e22' for t in tiers]

    ax1.barh(range(len(names)), skews, color=colors, edgecolor='black', linewidth=0.5)
    ax1.set_yticks(range(len(names)))
    ax1.set_yticklabels(names, fontsize=8)
    ax1.set_xlabel('Clock Skew (ps)', fontsize=11)
    ax1.set_title('Cross-Tier Clock Skew', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='x')

    # Spatial scatter plot
    xs = [d.get('x', 0) for d in skew_data]
    ys = [d.get('y', 0) for d in skew_data]
    scatter = ax2.scatter(xs, ys, c=skews, cmap='coolwarm',
                           s=50, edgecolors='black', linewidth=0.5)
    plt.colorbar(scatter, ax=ax2, label='Skew (ps)')
    ax2.set_xlabel('X (µm)', fontsize=11)
    ax2.set_ylabel('Y (µm)', fontsize=11)
    ax2.set_title('Spatial Skew Distribution', fontsize=13, fontweight='bold')
    ax2.set_aspect('equal')

    plt.tight_layout()
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"Saved clock skew plot: {output_path}")


# ---------------------------------------------------------------------------
# R-Scaling Distribution
# ---------------------------------------------------------------------------

def plot_r_scaling_distribution(stats: dict, output_path: str):
    """
    Plot the distribution of resistance scaling ratios from thermal_rcx.py stats.
    """
    if not HAS_MATPLOTLIB:
        return

    fig, ax = plt.subplots(figsize=(8, 5))

    r_min = stats.get('min_r_ratio', 1.0)
    r_max = stats.get('max_r_ratio', 1.0)

    # Generate a synthetic distribution (in practice, collect from thermal_rcx)
    r_values = np.linspace(r_min, r_max, 100)
    # Gaussian-ish distribution centered between min and max
    r_mean = (r_min + r_max) / 2
    r_std = (r_max - r_min) / 4
    density = np.exp(-0.5 * ((r_values - r_mean) / max(r_std, 0.001)) ** 2)
    density /= np.max(density)

    ax.fill_between(r_values, density, alpha=0.4, color='steelblue')
    ax.plot(r_values, density, 'b-', linewidth=2)
    ax.axvline(x=1.0, color='green', linestyle='--', linewidth=1.5,
               label=f'Nominal (T={25}°C)')
    ax.axvline(x=r_max, color='red', linestyle='--', linewidth=1.5,
               label=f'Max ratio: {r_max:.4f}')

    ax.set_xlabel('R Scaling Ratio (R_thermal / R_nominal)', fontsize=12)
    ax.set_ylabel('Relative Density', fontsize=12)
    ax.set_title('Resistance Scaling Distribution', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"Saved R-scaling distribution: {output_path}")


# ---------------------------------------------------------------------------
# Composite Dashboard
# ---------------------------------------------------------------------------

def plot_dashboard(grid_tier0: ThermalGrid, grid_tier1: ThermalGrid,
                    metrics_history: List[dict],
                    output_path: str,
                    title: str = "Thermal-Aware Pin-3D Dashboard"):
    """
    Generate a composite dashboard with thermal maps, convergence curves,
    and key metrics in a single figure.
    """
    if not HAS_MATPLOTLIB:
        return

    fig = plt.figure(figsize=(20, 12))
    gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3)

    # Unified temp scale
    vmin = min(np.min(grid_tier0.temperatures), np.min(grid_tier1.temperatures))
    vmax = max(np.max(grid_tier0.temperatures), np.max(grid_tier1.temperatures))

    # Tier 0 heatmap
    ax0 = fig.add_subplot(gs[0, 0])
    im0 = ax0.imshow(grid_tier0.temperatures, origin='lower', cmap=THERMAL_CMAP,
                      vmin=vmin, vmax=vmax, interpolation='bilinear', aspect='equal')
    ax0.set_title('Tier 0 (Bottom)', fontsize=12, fontweight='bold')
    plt.colorbar(im0, ax=ax0, shrink=0.8)

    # Tier 1 heatmap
    ax1 = fig.add_subplot(gs[0, 1])
    im1 = ax1.imshow(grid_tier1.temperatures, origin='lower', cmap=THERMAL_CMAP,
                      vmin=vmin, vmax=vmax, interpolation='bilinear', aspect='equal')
    ax1.set_title('Tier 1 (Top)', fontsize=12, fontweight='bold')
    plt.colorbar(im1, ax=ax1, shrink=0.8)

    # Cross-tier gradient
    ax2 = fig.add_subplot(gs[0, 2])
    diff = grid_tier1.temperatures - grid_tier0.temperatures
    vabs = max(abs(np.min(diff)), abs(np.max(diff)), 0.1)
    im2 = ax2.imshow(diff, origin='lower', cmap=DIVERGING_CMAP,
                      vmin=-vabs, vmax=vabs, interpolation='bilinear', aspect='equal')
    ax2.set_title('Cross-Tier ΔT', fontsize=12, fontweight='bold')
    plt.colorbar(im2, ax=ax2, shrink=0.8)

    # Convergence: ΔT_max
    if metrics_history:
        iters = [m.get('iteration', i) for i, m in enumerate(metrics_history)]

        ax3 = fig.add_subplot(gs[1, 0])
        dt_vals = [m.get('delta_t_max', 0) for m in metrics_history]
        ax3.plot(iters, dt_vals, 'bo-', linewidth=2, markersize=8)
        ax3.axhline(y=0.5, color='r', linestyle='--', alpha=0.7)
        ax3.set_title('ΔT Convergence', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Iteration')
        ax3.set_ylabel('ΔT_max (°C)')
        ax3.grid(True, alpha=0.3)

        # Convergence: WNS
        ax4 = fig.add_subplot(gs[1, 1])
        wns_vals = [m.get('wns_ps', 0) for m in metrics_history]
        ax4.plot(iters, wns_vals, 'rs-', linewidth=2, markersize=8)
        ax4.axhline(y=0, color='g', linestyle='--', alpha=0.7)
        ax4.set_title('WNS Convergence', fontsize=12, fontweight='bold')
        ax4.set_xlabel('Iteration')
        ax4.set_ylabel('WNS (ps)')
        ax4.grid(True, alpha=0.3)

        # Summary metrics table
        ax5 = fig.add_subplot(gs[1, 2])
        ax5.axis('off')
        latest = metrics_history[-1]
        table_data = [
            ['Metric', 'Value'],
            ['Peak T (Tier 0)', f'{np.max(grid_tier0.temperatures):.1f} °C'],
            ['Peak T (Tier 1)', f'{np.max(grid_tier1.temperatures):.1f} °C'],
            ['Max |ΔT_cross|', f'{np.max(np.abs(diff)):.1f} °C'],
            ['WNS', f'{latest.get("wns_ps", "N/A")} ps'],
            ['TNS', f'{latest.get("tns_ps", "N/A")} ps'],
            ['Total Power', f'{latest.get("total_power_mw", "N/A")} mW'],
            ['Iterations', f'{len(metrics_history)}'],
        ]
        table = ax5.table(cellText=table_data, loc='center',
                           cellLoc='center', colWidths=[0.5, 0.5])
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.0, 1.5)
        # Style header row
        for j in range(2):
            table[0, j].set_facecolor('#2c3e50')
            table[0, j].set_text_props(color='white', fontweight='bold')
        ax5.set_title('Summary', fontsize=12, fontweight='bold')

    fig.suptitle(title, fontsize=16, fontweight='bold', y=0.98)
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"Saved dashboard: {output_path}")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Thermal heatmap and timing visualization for Pin-3D",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Plot thermal heatmaps from saved grids
  python plot_heatmaps.py \\
    --tier0-grid results/thermal/thermal_grid_tier0.npz \\
    --tier1-grid results/thermal/thermal_grid_tier1.npz \\
    --output-dir results/figures/

  # Plot convergence from metrics history
  python plot_heatmaps.py \\
    --metrics-dir results/reports/ \\
    --output-dir results/figures/

  # Generate full dashboard
  python plot_heatmaps.py \\
    --tier0-grid results/thermal/thermal_grid_tier0.npz \\
    --tier1-grid results/thermal/thermal_grid_tier1.npz \\
    --metrics-dir results/reports/ \\
    --output-dir results/figures/ \\
    --dashboard
        """
    )

    parser.add_argument('--tier0-grid', type=str,
                        help='Path to Tier 0 thermal grid .npz')
    parser.add_argument('--tier1-grid', type=str,
                        help='Path to Tier 1 thermal grid .npz')
    parser.add_argument('--interface-grid', type=str,
                        help='Path to interface thermal grid .npz')
    parser.add_argument('--metrics-dir', type=str,
                        help='Directory containing metrics_iter*.json files')
    parser.add_argument('--output-dir', type=str, default='results/figures/',
                        help='Output directory for plots')
    parser.add_argument('--dashboard', action='store_true',
                        help='Generate composite dashboard')
    parser.add_argument('--format', choices=['png', 'pdf'], default='png',
                        help='Output format (default: png)')
    parser.add_argument('--verbose', '-v', action='store_true')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    global FIG_FORMAT
    FIG_FORMAT = args.format

    os.makedirs(args.output_dir, exist_ok=True)

    # Load thermal grids
    grid_tier0 = None
    grid_tier1 = None
    grid_interface = None

    if args.tier0_grid and Path(args.tier0_grid).exists():
        grid_tier0 = load_thermal_grid(args.tier0_grid)
    if args.tier1_grid and Path(args.tier1_grid).exists():
        grid_tier1 = load_thermal_grid(args.tier1_grid)
    if args.interface_grid and Path(args.interface_grid).exists():
        grid_interface = load_thermal_grid(args.interface_grid)

    # Plot individual tier heatmaps
    if grid_tier0:
        plot_thermal_heatmap(
            grid_tier0,
            os.path.join(args.output_dir, f'thermal_tier0.{FIG_FORMAT}'),
            title='Tier 0 (Bottom Die) Temperature'
        )
    if grid_tier1:
        plot_thermal_heatmap(
            grid_tier1,
            os.path.join(args.output_dir, f'thermal_tier1.{FIG_FORMAT}'),
            title='Tier 1 (Top Die) Temperature'
        )
    if grid_interface:
        plot_thermal_heatmap(
            grid_interface,
            os.path.join(args.output_dir, f'thermal_interface.{FIG_FORMAT}'),
            title='Bonding Interface Temperature'
        )

    # Plot dual-tier comparison
    if grid_tier0 and grid_tier1:
        plot_dual_tier_heatmap(
            grid_tier0, grid_tier1,
            os.path.join(args.output_dir, f'thermal_dual_tier.{FIG_FORMAT}')
        )
        plot_temperature_difference(
            grid_tier0, grid_tier1,
            os.path.join(args.output_dir, f'thermal_cross_tier_gradient.{FIG_FORMAT}')
        )

    # Load and plot convergence metrics
    metrics_history = []
    if args.metrics_dir and Path(args.metrics_dir).exists():
        for f in sorted(Path(args.metrics_dir).glob('metrics_iter*.json')):
            try:
                with open(f) as fp:
                    metrics_history.append(json.load(fp))
            except (json.JSONDecodeError, IOError):
                continue

    if metrics_history:
        plot_convergence(
            metrics_history,
            os.path.join(args.output_dir, f'convergence.{FIG_FORMAT}')
        )

    # Dashboard
    if args.dashboard and grid_tier0 and grid_tier1:
        plot_dashboard(
            grid_tier0, grid_tier1, metrics_history,
            os.path.join(args.output_dir, f'dashboard.{FIG_FORMAT}')
        )

    logger.info("All plots generated.")


if __name__ == "__main__":
    main()
