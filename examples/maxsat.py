from pyspel.pyspel import *

"""
clauses(C) :- clause(C).
clauses(C) :- weightedClause(C,W).

literal(X) :- clauses(C), inClause(C,X).

pVar(X)     :- vars(X), literal(X), Y = -X, not literal(Y).
{ pVar(X) } :- vars(X), literal(X), Y = -X, literal(Y).
nVar(X)     :- vars(X), not pVar(X).

satisfied(C) :- clauses(C), inClause(C,X), pVar(X).
satisfied(C) :- clauses(C), inClause(C,Y), nVar(X), Y = -X.

:- clause(C), not satisfied(C).
:~ weightedClause(C,W), not satisfied(C). [W@1,C]
"""


"""
vars(1..49691).
clause(1).
inClause(1,1).
weightedClause(150938,1).
"""


@atom
class Clause:
    id: int


@atom
class Vars:
    id: int


@atom
class InClause:
    clause: int
    literal: int


@atom
class WeightedClause:
    clause: int
    weight: int


@atom
class Assignment:
    variable: Vars


if len(sys.argv) != 2:
    print(f"Usage: python3 {sys.argv[0]} asp_instance", file=sys.stderr)
    exit(1)

filename = sys.argv[1]
clingo = "/usr/local/bin/clingo"
output = ASPUtilities.process_asp_facts(filename=filename, atoms=[Vars(), Clause(), InClause(), WeightedClause()], solver_path=clingo)
clauses = []
weighted_clauses = []
in_clauses = []
clause2lits = {}
vars = []

weighted_ids = {}
for atom in output:
    if type(atom) == Clause:
        clauses.append(atom)
    elif type(atom) == WeightedClause:
        weighted_clauses.append(atom)
        weighted_ids[atom.clause.value] = atom.weight.value
    elif type(atom) == InClause:
        clause_id = atom.clause.value
        if clause_id not in clause2lits:
            clause2lits[clause_id] = []
        if atom.literal.value > 0:
            lit = ~Assignment(Vars(atom.literal.value))
        else:
            lit = Assignment(Vars(-atom.literal.value))
        clause2lits[clause_id].append(lit)
        in_clauses.append(atom)
    elif type(atom) == Vars:
        vars.append(atom)

p = Problem()
p += vars

with Vars() as v:
    p += Guess({Assignment(variable=v)}).when(v)

for clause in clause2lits:
    literals = clause2lits[clause]
    weight = None
    if clause in weighted_ids:
        weight = weighted_ids[clause]
    if weight is None:
        p += Assert(*literals)
    else:
        p += Assert(*literals).otherwise(weight, 1, clause)

solver = SolverWrapper(solver_path=clingo)
res = solver.solve(problem=p, options=["--opt-strategy=usc"], timeout=10)
if res.status == Result.HAS_SOLUTION:
    assert len(res.answers) >= 1
    answer = res.answers[-1]
    result = answer.get_atom_occurrences(Assignment())
    print("Found solution: ")
    trueVars = []
    falseVars = []
    for assignment in result:
        trueVars.append(assignment.variable.id.value)
    for var in vars:
        if var.id.value not in trueVars:
            falseVars.append(var.id.value)
    print(f"T: {trueVars}")
    print(f"F: {falseVars}")
    print(f"Cost: {answer.costs}")
elif res.status == Result.NO_SOLUTION:
    print("No solution found!")
else:
    print("Unknown")
