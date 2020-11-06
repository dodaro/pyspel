from pyspel import *


@atom
class Color:
    value: any


@atom
class Node:
    value: int


@atom
class Edge:
    node1: Node
    node2: Node


@atom
class Assign:
    node: Node
    color: Color

"""
class Empty:
    pass

Empty = create_atom(Empty)
e = Empty()
"""

p = Problem()
# create facts
for assignment in range(1, 4):
    p += Node(assignment)

p += Edge(Node(1), Node(2))
p += Edge(Node(2), Node(3))
p += Color((0, 0, 255))
p += Color((255, 0, 0))
p += Color((0, 255, 0))
#p += Color("blue")
#p += Color("red")
#p += Color("green")



# guess exactly one color for each node
with Node() as n, Color() as c:
    p += When(n).guess({Assign(n, c): c}, exactly=1)

# check that each node is assigned to exactly one color (not needed, already specified in choice rule)
with Node() as n, Color() as c:
    p += When(n).holds(Count({c: Assign(n, c)}) == 1)

# two nodes assigned with the same color cannot be linked
with Node() as n1, Node() as n2, Color() as c1, Color() as c2:
    p += When(Assign(n1, c1), Assign(n2, c2), Edge(n1, n2), n1.value < n2.value).holds(c1.value != c2.value)

solver = SolverWrapper(solver_path="/usr/local/bin/clingo")

try:
    with asp_time_limit(seconds=10):
        res = solver.solve(program=p)
        if res.status == Result.HAS_SOLUTION:
            assert len(res.answers) == 1
            answer = res.answers[0]
            result = answer.get_atom_occurrences(Assign())
            print("Found solution: ")
            for assignment in result:
                print("Node %s to color %s" % (assignment.node.value.value, str(assignment.color.value)))
        elif res.status == Result.NO_SOLUTION:
            print("No solution found!")
        else:
            print("Unknown")
except TimeoutException as e:
    print("Timed out!")