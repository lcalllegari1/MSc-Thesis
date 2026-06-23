import json
import random
import argparse
import numpy as np
import os

# Design choice: Hamiltonian CYCLE (n edges, path returns to start node).
# The adjacency matrix is symmetric (undirected complete graph).
# Edge costs are Euclidean distances scaled to integers.

def generate_instance(n, grid_size=1000, precision=1000, seed=42):
    random.seed(seed)
    np.random.seed(seed)

    nodes = np.random.uniform(0, grid_size, size=(n, 2))
    diff = nodes[:, np.newaxis, :] - nodes[np.newaxis, :, :]
    dist_matrix = np.sqrt(np.sum(diff**2, axis=-1))
    scaled_matrix = np.floor(dist_matrix * precision).astype(int)

    return {
        "metadata": {"n": n, "grid_size": grid_size, "precision": precision, "seed": seed},
        "nodes": nodes.tolist(),
        "matrix": scaled_matrix.tolist(),
    }

def save_dat(matrix, filename):
    with open(filename, 'w') as f:
        f.write(f"{len(matrix)}\n")
        for row in matrix:
            f.write(" ".join(map(str, row)) + "\n")

def main():
    parser = argparse.ArgumentParser(description="Generate TSP instances.")
    parser.add_argument("-n", type=int, default=10, help="Number of nodes")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--out", type=str, default="data/instance.json", help="JSON path")
    parser.add_argument("--dat", type=str, default="data/matrix.dat", help="DAT path")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    os.makedirs(os.path.dirname(args.dat), exist_ok=True)

    instance = generate_instance(args.n, seed=args.seed)

    with open(args.out, 'w') as f:
        json.dump(instance, f, indent=2)
    save_dat(instance["matrix"], args.dat)

    print(f"Generated {args.n} nodes.")

if __name__ == "__main__":
    main()
