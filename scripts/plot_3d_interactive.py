#!/usr/bin/env python3
"""
plot_3d_interactive.py — Interactive 3D Thermal Visualization

Generates an interactive 3D volumetric surface rendering of the Face-to-Face (F2F)
3D-IC stackup (Tier 0, Interface, Tier 1) using Plotly and exports it to HTML.

Usage:
    python3 scripts/plot_3d_interactive.py \
        --tier0-grid results/thermal/thermal_grid_tier0.npz \
        --tier1-grid results/thermal/thermal_grid_tier1.npz \
        --interface-grid results/thermal/thermal_grid_interface.npz \
        --output results/figures/thermal_3d_interactive.html
"""

import os
import sys
import argparse
import numpy as np
import plotly.graph_objects as go


def load_grid(path: str):
    """Load a thermal grid from .npz file."""
    data = np.load(path)
    return {
        'tier': int(data['tier']),
        'rows': int(data['rows']),
        'cols': int(data['cols']),
        'x_min': float(data['x_min']),
        'y_min': float(data['y_min']),
        'x_max': float(data['x_max']),
        'y_max': float(data['y_max']),
        'temperatures': data['temperatures'],
    }


def generate_interactive_3d(tier0_path: str, tier1_path: str, interface_path: str, output_path: str):
    """Create and save interactive 3D thermal visualization."""
    t0_data = load_grid(tier0_path)
    t1_data = load_grid(tier1_path)
    intf_data = load_grid(interface_path)

    t0_temps = t0_data['temperatures']
    t1_temps = t1_data['temperatures']
    intf_temps = intf_data['temperatures']

    rows, cols = t0_temps.shape
    x = np.linspace(t0_data['x_min'], t0_data['x_max'], cols)
    y = np.linspace(t0_data['y_min'], t0_data['y_max'], rows)
    X, Y = np.meshgrid(x, y)

    # Physical Z offsets (in micrometers for visual proportion)
    z_tier0 = np.full((rows, cols), 0.0)       # Z = 0 µm (Tier 0 Active)
    z_intf = np.full((rows, cols), 150.0)      # Z = 150 µm (F2F Bonding Interface)
    z_tier1 = np.full((rows, cols), 300.0)     # Z = 300 µm (Tier 1 Active)

    # Find global temperature bounds for uniform color scale
    t_min = min(float(np.min(t0_temps)), float(np.min(t1_temps)), float(np.min(intf_temps)))
    t_max = max(float(np.max(t0_temps)), float(np.max(t1_temps)), float(np.max(intf_temps)))

    fig = go.Figure()

    # Surface 1: Tier 0 (Bottom Active Die)
    fig.add_trace(go.Surface(
        x=X, y=Y, z=z_tier0,
        surfacecolor=t0_temps,
        colorscale='Turbo',
        cmin=t_min, cmax=t_max,
        name='Tier 0 (Bottom Die)',
        colorbar=dict(
            title=dict(text="Temperature (°C)", font=dict(size=14)),
            thickness=20, len=0.75, x=1.05
        ),
        hovertemplate='<b>Tier 0 (Bottom)</b><br>X: %{x:.1f} µm<br>Y: %{y:.1f} µm<br>Temp: %{surfacecolor:.2f} °C<extra></extra>',
        showscale=True,
    ))

    # Surface 2: F2F Bonding Interface (Center)
    fig.add_trace(go.Surface(
        x=X, y=Y, z=z_intf,
        surfacecolor=intf_temps,
        colorscale='Turbo',
        cmin=t_min, cmax=t_max,
        name='F2F Hybrid Bonding Interface',
        opacity=0.85,
        hovertemplate='<b>F2F Bonding Interface</b><br>X: %{x:.1f} µm<br>Y: %{y:.1f} µm<br>Temp: %{surfacecolor:.2f} °C<extra></extra>',
        showscale=False,
    ))

    # Surface 3: Tier 1 (Upper Active Die)
    fig.add_trace(go.Surface(
        x=X, y=Y, z=z_tier1,
        surfacecolor=t1_temps,
        colorscale='Turbo',
        cmin=t_min, cmax=t_max,
        name='Tier 1 (Upper Die)',
        hovertemplate='<b>Tier 1 (Upper)</b><br>X: %{x:.1f} µm<br>Y: %{y:.1f} µm<br>Temp: %{surfacecolor:.2f} °C<extra></extra>',
        showscale=False,
    ))

    # Add interactive Layer Toggle Buttons & Camera View Presets
    updatemenus = [
        dict(
            type="buttons",
            direction="left",
            buttons=[
                dict(
                    args=[{"visible": [True, True, True]}],
                    label="Full 3D Stack",
                    method="update"
                ),
                dict(
                    args=[{"visible": [True, False, False]}],
                    label="Tier 0 (Bottom)",
                    method="update"
                ),
                dict(
                    args=[{"visible": [False, True, False]}],
                    label="F2F Interface",
                    method="update"
                ),
                dict(
                    args=[{"visible": [False, False, True]}],
                    label="Tier 1 (Upper)",
                    method="update"
                ),
            ],
            pad={"r": 10, "t": 10},
            showactive=True,
            x=0.05,
            xanchor="left",
            y=1.12,
            yanchor="top",
            font=dict(color="#ffffff", size=12),
            bgcolor="rgba(40,40,40,0.85)",
            bordercolor="#666666"
        ),
        dict(
            type="buttons",
            direction="left",
            buttons=[
                dict(
                    args=[{"scene.camera": dict(eye=dict(x=1.6, y=-1.6, z=1.2), center=dict(x=0, y=0, z=-0.1))}],
                    label="3D Isometric",
                    method="relayout"
                ),
                dict(
                    args=[{"scene.camera": dict(eye=dict(x=0.0, y=0.0, z=2.5), center=dict(x=0, y=0, z=0))}],
                    label="Top-Down (2D)",
                    method="relayout"
                ),
                dict(
                    args=[{"scene.camera": dict(eye=dict(x=2.5, y=0.0, z=0.2), center=dict(x=0, y=0, z=0))}],
                    label="Side Profile",
                    method="relayout"
                ),
            ],
            pad={"r": 10, "t": 10},
            showactive=True,
            x=0.95,
            xanchor="right",
            y=1.12,
            yanchor="top",
            font=dict(color="#ffffff", size=12),
            bgcolor="rgba(40,40,40,0.85)",
            bordercolor="#666666"
        )
    ]

    # Layout styling
    fig.update_layout(
        title=dict(
            text="<b>Ariane-136 3D-IC Face-to-Face (F2F) Volumetric Thermal Distribution</b><br>"
                 f"<sup>Steady-State PACT Simulation: T_min = {t_min:.1f}°C, T_max = {t_max:.1f}°C, ΔT_cross-tier = {abs(np.max(t0_temps)-np.max(t1_temps)):.2f}°C</sup>",
            font=dict(size=18, family="Arial, sans-serif"),
            x=0.5, xanchor='center'
        ),
        updatemenus=updatemenus,
        scene=dict(
            xaxis=dict(title='X Position (µm)', gridcolor='#444', showbackground=True, backgroundcolor='#1e1e1e'),
            yaxis=dict(title='Y Position (µm)', gridcolor='#444', showbackground=True, backgroundcolor='#1e1e1e'),
            zaxis=dict(
                title='3D Stackup Layers',
                tickvals=[0, 150, 300],
                ticktext=['Tier 0 (Active)', 'F2F Interface', 'Tier 1 (Active)'],
                gridcolor='#444', showbackground=True, backgroundcolor='#1a1a1a'
            ),
            camera=dict(
                eye=dict(x=1.6, y=-1.6, z=1.2),
                center=dict(x=0, y=0, z=-0.1)
            ),
            aspectratio=dict(x=1, y=1, z=0.6)
        ),
        paper_bgcolor='#121212',
        font=dict(color='#ffffff'),
        margin=dict(l=20, r=20, t=110, b=20),
        legend=dict(x=0.05, y=0.95, bgcolor='rgba(30,30,30,0.8)', bordercolor='#555')
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fig.write_html(output_path, include_plotlyjs='cdn')
    print(f"✓ Interactive 3D thermal visualizer generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Interactive 3D Thermal Visualization")
    parser.add_argument('--tier0-grid', default='results/thermal/thermal_grid_tier0.npz',
                        help='Path to Tier 0 thermal grid .npz')
    parser.add_argument('--tier1-grid', default='results/thermal/thermal_grid_tier1.npz',
                        help='Path to Tier 1 thermal grid .npz')
    parser.add_argument('--interface-grid', default='results/thermal/thermal_grid_interface.npz',
                        help='Path to Interface thermal grid .npz')
    parser.add_argument('--output', default='results/figures/thermal_3d_interactive.html',
                        help='Path to output HTML visualizer')

    args = parser.parse_args()
    generate_interactive_3d(args.tier0_grid, args.tier1_grid, args.interface_grid, args.output)


if __name__ == '__main__':
    main()
