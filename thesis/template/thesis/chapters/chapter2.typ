#import "/theme/headings.typ": *

#chapter([Background], label: <chap:background>)

#section([The Travelling Salesman Problem], label: <sec:tsp>)

The problem this thesis proves a property of is the Travelling Salesman Problem. This section states it in general terms and records the facts the later arguments rely on: its definition, the two forms it takes, why it is hard, and how it is solved in practice. The freight carrier of @sec:motivation was one instance of it, described in words; here we give the general problem and its formal shape.

#subsection([Definition], label: <sub:tsp-def>)

An instance of the problem is a complete weighted graph: a set of $N$ nodes and, for every pair of nodes $i$ and $j$, a cost $c(i, j)$ of travelling between them. We take the costs to be symmetric, so that $c(i, j) = c(j, i)$, matching the road-distance setting the problem is named for. A _tour_, or _Hamiltonian cycle_, is an ordering of the nodes that visits each exactly once and returns to where it began. Its cost is the sum of the costs of the $N$ edges it traverses.

The problem takes two forms, and the difference between them is central to this thesis. The _optimization_ form asks for a tour of least cost. The _decision_ form fixes a threshold $T$ and asks only whether a tour of cost at most $T$ exists. The name usually evokes the optimization form, but the decision form is the one we prove a statement about: the carrier claims her route stays under budget, not that it is the cheapest route possible. We made this choice precise in @sub:formulation, where it appears as proving feasibility rather than optimality.

The problem is old and thoroughly studied. Dantzig, Fulkerson, and Johnson put it on its modern computational footing in 1954, solving a 49-city instance by methods that became a root of integer programming @dantzig1954. It has served as a benchmark for combinatorial optimization ever since, and the standard account of its computational study is the monograph of Applegate and co-authors @applegate2006.

#subsection([Why It Is Hard], label: <sub:tsp-hardness>)

The problem resists brute force. A tour is an ordering of the $N$ nodes, so for symmetric costs the number of distinct tours grows like $(N - 1)! \/ 2$ --- already astronomical for a few dozen nodes, and hopeless to enumerate beyond that. Nor is there a known shortcut. The decision form is NP-complete and the optimization form NP-hard @karp1972: no algorithm is known that solves every instance in time polynomial in $N$, and it is widely believed none exists. Solving large instances exactly is therefore out of reach, which is why the methods that scale give up the guarantee of an exact answer.

#subsection([Solving It in Practice], label: <sub:tsp-solving>)

The methods that address the problem fall into two families. _Exact_ methods, such as branch-and-bound and cutting-plane algorithms, return a provably optimal tour, but their running time climbs steeply with $N$ and reaches a ceiling beyond which they are impractical. _Heuristic_ methods give up the optimality guarantee in exchange for speed: a tour is built quickly, for instance by repeatedly walking to the nearest unvisited node, and then improved by local search such as 2-opt or the Lin--Kernighan algorithm @lin1973. The tour they return is usually good and rarely optimal, which for most purposes is a worthwhile trade.

One technique deserves singling out, because it is the idea the later chapters take up: _decomposition_. Instead of solving the whole instance at once, one partitions the nodes into smaller groups, solves a tour within each group, and joins the partial tours into a single one @karp1977. The gain is large precisely because the cost of solving grows so steeply with size: replacing one big instance with several small ones cuts the total work sharply, and the savings dwarf the cost of joining the pieces. The joined tour is generally suboptimal, but a good tour found fast is, again, usually worth more than the optimal one found slowly. Decomposition is, in short, a standard and effective way to bring a hard instance within reach.
