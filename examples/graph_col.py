from pyspel.pyspel import *


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


p = Problem()
nodes = [Node(value=i) for i in range(1, 4)]
edges = [Edge(Node(1), Node(2)), Edge(Node(2), Node(3))]
colors = [Color(value=i) for i in ["red", "green", "blue"]]

p += nodes
p += edges
p += colors


def test():
    def guess():
        return When(Node().s("n")).guess({Assign(Node.l("n"), Color().s("c")): Color.l("c")}, exactly=1)
    p1 = Problem()
    p1 += guess()
    res = solver.solve(problem=p1)
    all_assignments = []
    if res.status == Result.HAS_SOLUTION:
        assert len(res.answers) == 1
        answer = res.answers[0]
        all_assignments = answer.get_atom_occurrences(Assign())
    print(all_assignments)
    return None


def encoding1(problem):
    def guess():
        return When(Node().s("n")).guess({Assign(Node.l("n"), Color().s("c")): Color.l("c")}, exactly=1)

    # check that each node is assigned to exactly one color (not needed, already specified in choice rule)
    def check_node_assignment(node, color):
        return When(node).holds(Count({color: Assign(node, color)}) == 1)

    # two nodes assigned with the same color cannot be linked
    def check_edge_not_colored(node1, node2, color1, color2):
        return When(Assign(node1, color1), Assign(node2, color2), Edge(node1, node2), node1.value < node2.value).holds(color1.value != color2.value)

    problem += guess()
    problem += check_node_assignment(node=Node(), color=Color())
    problem += check_edge_not_colored(node1=Node(), node2=Node(), color1=Color(), color2=Color())


def encoding2(problem):
    # guess exactly one color for each node
    with Node() as n, Color() as c:
        problem += When(n).guess({Assign(n, c): c}, exactly=1)

    # check that each node is assigned to exactly one color (not needed, already specified in choice rule)
    with Node() as n, Color() as c:
        problem += When(n).holds(Count({c: Assign(n, c)}) == 1)

    # two nodes assigned with the same color cannot be linked
    with Node() as n1, Node() as n2, Color() as c1, Color() as c2:
        problem += When(Assign(n1, c1), Assign(n2, c2), Edge(n1, n2), n1.value < n2.value).holds(c1.value != c2.value)


def encoding_propositional(problem):
    for node in nodes:
        problem += Guess({Assign(node, color) for color in colors}, exactly=1)

    for node in nodes:
        problem += Assert(Count({Assign(node, color) for color in colors}) == 1)

    for edge in edges:
        for color in colors:
            problem += When(Assign(edge.node1, color)).and_also(Assign(edge.node2, color)).holds(False)


encoding1(problem=p)
print(p)
solver = SolverWrapper(solver_path="/usr/local/bin/clingo")
res = solver.solve(problem=p, timeout=10)
if res.status == Result.HAS_SOLUTION:
    assert len(res.answers) == 1
    answer = res.answers[0]
    result = answer.get_class_occurrences(Assign())
    print("Found solution: ")
    for assignment in result:
        print("assignment %s" % assignment)
        print("Node %s to color %s" % (assignment.node.value, str(assignment.color.value)))
elif res.status == Result.NO_SOLUTION:
    print("No solution found!")
else:
    print("Unknown")