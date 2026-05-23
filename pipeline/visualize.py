import json
import argparse
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

# --- AESTHETIC CONFIGURATION (Edit here to change the style) ---
CONFIG = {
    "node_fill": "#1d4ed8",      # Dark Vivid Blue
    "node_edge": "black",        # Node outline
    "node_size": 140,            # Node marker size
    "node_outline_width": 0.9,   # Node outline thickness
    
    "tour_cmap": "autumn",       # Gradient: Red to Yellow
    "tour_width": 1.8,           # Path line thickness
    "tour_alpha": 1.0,           # Path opacity
    "tour_range": (0.1, 0.9),    # Skip extremes of colormap for visibility
    
    "arrow_size": 11,            # Triangular arrow size (squared for 's' parameter)
    "start_highlight": "red",    # Color for the start node highlight ring
    "start_ring_scale": 2.25,    # Size of the start highlight relative to node_size
    
    "title_size": 20,            # Plot title font size
    "label_size": 16,            # Axis label font size
    "tick_size": 14,             # Axis tick label font size
    "label_pad": 15,             # Padding for X-axis label
    "legend_y_offset": -0.15,    # Legend vertical position
    "legend_size": 14,           # Legend font size
    "legend_padding": 0.8,       # Padding inside legend frame
    
    "board_edge_width": 2.5,     # Boundary line thickness
    "font_family": "DejaVu Sans",
    "math_font": "stixsans",
}

def calculate_metrics(matrix, path, multiplier):
    # Hamiltonian cycle: n edges including the return edge path[-1] → path[0]
    cost = sum(matrix[path[i]][path[(i + 1) % len(path)]] for i in range(len(path)))
    return int(cost), int(cost * multiplier)

def plot_instance(instance, path=None, cost=None, threshold=None, output_file=None):
    nodes = np.array(instance["nodes"])
    grid_size = instance["metadata"].get("grid_size", 1000)
    
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": [CONFIG["font_family"]], "mathtext.fontset": CONFIG["math_font"]})
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_aspect('equal')

    # 1. Background (Small instances only)
    if len(nodes) < 15:
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                ax.plot([nodes[i, 0], nodes[j, 0]], [nodes[i, 1], nodes[j, 1]], color='#d8dee9', alpha=0.3, linewidth=0.5, zorder=1)

    # 2. Path and Legend Proxies
    proxies = []
    if path and len(path) > 1:
        pts = nodes[path]
        segments = np.concatenate([pts[:-1].reshape(-1, 1, 2), pts[1:].reshape(-1, 1, 2)], axis=1)
        colors = plt.get_cmap(CONFIG["tour_cmap"])(np.linspace(*CONFIG["tour_range"], len(segments)))

        ax.add_collection(LineCollection(segments, colors=colors, linewidths=CONFIG["tour_width"], alpha=CONFIG["tour_alpha"], zorder=2))

        # Directional Arrows
        mid = (pts[:-1] + pts[1:]) / 2
        dx, dy = np.diff(pts[:, 0]), np.diff(pts[:, 1])
        angles = np.degrees(np.arctan2(dy, dx))
        step = max(1, len(nodes) // 10)
        for i in range(0, len(segments), step):
            ax.scatter(mid[i, 0], mid[i, 1], marker=(3, 0, angles[i]-90), s=CONFIG["arrow_size"]**2, color=colors[i], zorder=2.1)

        # Start Highlight
        ax.scatter(pts[0, 0], pts[0, 1], s=CONFIG["node_size"] * CONFIG["start_ring_scale"], facecolors='none', edgecolors=CONFIG["start_highlight"], linewidth=2, zorder=5)
        
        proxies = [Line2D([0], [0], marker='o', color='w', markeredgecolor=CONFIG["start_highlight"], markeredgewidth=2, markersize=12, label='Start Node'),
                   Line2D([0], [0], color=plt.get_cmap(CONFIG["tour_cmap"])(0.5), linewidth=CONFIG["tour_width"], label='Tour Path')]

    # 3. Nodes and Boundary
    ax.scatter(nodes[:, 0], nodes[:, 1], s=CONFIG["node_size"], c=CONFIG["node_fill"], edgecolors=CONFIG["node_edge"], linewidths=CONFIG["node_outline_width"], zorder=4)
    ax.add_patch(patches.Rectangle((0, 0), grid_size, grid_size, linewidth=CONFIG["board_edge_width"], edgecolor='black', facecolor='none', zorder=0))

    # 4. Decoration
    title = f"Instance (N={len(nodes)})"
    if cost: title += f"\nCost: {cost} | Threshold: {threshold}"
    ax.set_title(title, fontsize=CONFIG["title_size"], fontweight='bold', pad=20)
    ax.set_xlabel("X Coordinate", fontsize=CONFIG["label_size"], labelpad=CONFIG["label_pad"])
    ax.set_ylabel("Y Coordinate", fontsize=CONFIG["label_size"])
    ax.tick_params(labelsize=CONFIG["tick_size"])
    ax.grid(False)
    
    ax.legend(handles=proxies, loc='upper center', bbox_to_anchor=(0.5, CONFIG["legend_y_offset"]), 
              ncol=2, frameon=True, fontsize=CONFIG["legend_size"], borderpad=CONFIG["legend_padding"])
    
    pad = grid_size * 0.05
    ax.set_xlim(-pad, grid_size + pad); ax.set_ylim(-pad, grid_size + pad)

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {output_file}")
    else:
        plt.show()

def main():
    parser = argparse.ArgumentParser(description="Visualize TSP.")
    parser.add_argument("--json", required=True, help="Instance JSON")
    parser.add_argument("--path", help="Path JSON")
    parser.add_argument("--multiplier", type=float, default=1.1, help="Cost multiplier")
    parser.add_argument("--out", help="Output image path")
    args = parser.parse_args()
    
    with open(args.json, 'r') as f:
        inst = json.load(f)
    
    path, cost, threshold = None, None, None
    if args.path:
        with open(args.path, 'r') as f:
            path = json.load(f)
        cost, threshold = calculate_metrics(inst["matrix"], path, args.multiplier)
    
    plot_instance(inst, path, cost, threshold, args.out)

if __name__ == "__main__":
    main()
