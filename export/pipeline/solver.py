import json
import argparse
import os
import numpy as np

# Design choice: nearest-neighbour construction + 2-opt local search.
# Optimality is irrelevant — we only need a valid Hamiltonian cycle for the ZKP.
# This keeps the solver dependency-free (pure Python/numpy).

def nearest_neighbour(matrix, start=0):
    n = len(matrix)
    visited = [False] * n
    path = [start]
    visited[start] = True
    for _ in range(n - 1):
        current = path[-1]
        best, best_cost = -1, float('inf')
        for j in range(n):
            if not visited[j] and matrix[current][j] < best_cost:
                best, best_cost = j, matrix[current][j]
        path.append(best)
        visited[best] = True
    return path

def two_opt(matrix, path):
    n = len(path)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                a, b = path[i - 1], path[i]
                c, d = path[j], path[(j + 1) % n]
                delta = (matrix[a][c] + matrix[b][d]) - (matrix[a][b] + matrix[c][d])
                if delta < 0:
                    path[i:j + 1] = path[i:j + 1][::-1]
                    improved = True
    return path

def cycle_cost(matrix, path):
    n = len(path)
    return sum(matrix[path[i]][path[(i + 1) % n]] for i in range(n))

def solve(matrix, two_opt_max_n=1000):
    # 2-opt is O(N^2) per sweep, run to convergence -> too slow in pure Python for
    # large N. Optimality is irrelevant (the ZKP only needs a *valid* Hamiltonian
    # cycle; the threshold is just 1.1x whatever tour we find), so above
    # two_opt_max_n we keep the nearest-neighbour tour and skip the refinement.
    path = nearest_neighbour(matrix)
    if len(matrix) <= two_opt_max_n:
        path = two_opt(matrix, path)
    return path

def main():
    parser = argparse.ArgumentParser(description="Solve TSP and output Hamiltonian cycle.")
    parser.add_argument("--json", required=True, help="Instance JSON from instance_gen.py")
    parser.add_argument("--out", type=str, default="data/path.json", help="Output path JSON")
    args = parser.parse_args()

    with open(args.json, 'r') as f:
        instance = json.load(f)

    matrix = instance["matrix"]
    path = solve(matrix)
    cost = cycle_cost(matrix, path)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(path, f)

    print(f"Cycle cost: {cost}  |  path: {path}")

if __name__ == "__main__":
    main()
