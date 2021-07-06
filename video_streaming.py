from pyspel import *


@atom
class Resolution:
    value: int


@atom
class Bandwidth:
    value: int


@atom
class Video:
    type: str


@atom
class BitRate:
    value: int


@atom
class Sat:
    value: int


@atom
class User:
    id: int
    video: Video
    resolution: Resolution
    bandwidth: Bandwidth
    max_sat: Sat
    max_bit: BitRate


@atom
class MaxRepresentation:
    value: int


@atom
class F:
    video: Video
    resolution: Resolution
    bit_rate: BitRate
    sat_value: Sat


@atom
class R:
    video: Video
    resolution: Resolution
    bit_rate: BitRate
    sat_value: Sat


@atom
class GlobalCapacity:
    value: int


@atom
class FractionUser:
    value: int


@atom
class Assign:
    user: User
    bit_rate: BitRate
    sat_value: Sat


def process(result, process_line, predicate_names):
    for predicate_name in predicate_names:
        if process_line.startswith(f"{predicate_name}("):
            process_line = process_line[:-1]
            process_line = process_line.replace(f"{predicate_name}(", "(")
            result[predicate_name].append(eval(process_line))


if len(sys.argv) != 2:
    print(f"Usage: python3 {sys.argv[0]} asp_instance", file=sys.stderr)
    exit(1)

p = Problem()
instance = open(sys.argv[1], "r")
predicates = ["f", "user", "global_capacity", "fraction_user", "max_representations"]
result = {}
for predicate_name in predicates:
    result[predicate_name] = []

for line in instance.readlines():
    process(result, line.strip(), predicates)

for i in result:
    if i == "f":
        for read_line in result[i]:
            p += F(video=Video(read_line[0]), resolution=Resolution(int(read_line[1])), bit_rate=BitRate(int(read_line[2])), sat_value=Sat(int(read_line[3])))
    elif i == "user":
        for read_line in result[i]:
            p += User(id=int(read_line[0]), video=Video(read_line[1]), resolution=Resolution(int(read_line[2])), bandwidth=Bandwidth(int(read_line[3])), max_sat=Sat(int(read_line[4])), max_bit=BitRate(int(read_line[5])))
    elif i == "global_capacity":
        assert len(result[i]) == 1
        p += GlobalCapacity(value=int(result[i][0]))
    elif i == "fraction_user":
        assert len(result[i]) == 1
        p += FractionUser(value=int(result[i][0]))
    elif i == "max_representations":
        assert len(result[i]) == 1
        p += MaxRepresentation(value=int(result[i][0]))

# { r(VIDEO, RESOLUTION, BITRATE, SAT_VALUE) : f(VIDEO, RESOLUTION, BITRATE, SAT_VALUE), user(_,VIDEO, RESOLUTION, BANDWIDTH,MAX_SAT, MAX_BIT), BITRATE <= MAX_BIT } = M :- max_representations(M).
with R() as r, F(video=r.video, resolution=r.resolution, bit_rate=r.bit_rate, sat_value=r.sat_value) as f, User(video=r.video, resolution=r.resolution) as user, MaxRepresentation(var("max")) as m:
    p += Guess({r: (f, user, r.bit_rate.value <= user.max_bit.value)}, exactly=m.value).when(m)

# { assign(USER_ID, VIDEO_TYPE, RESOLUTION, BITRATE,SAT): f(VIDEO_TYPE, RESOLUTION, BITRATE,SAT), BITRATE <= MAX_BIT } :-  user(USER_ID, VIDEO_TYPE, RESOLUTION, BANDWIDTH, MAX_SAT, MAX_BIT).
with User() as user, F(video=user.video, resolution=user.resolution) as f, Assign(user=user, bit_rate=f.bit_rate, sat_value=f.sat_value) as a:
    p += Guess({a: (f, f.bit_rate.value <= user.max_bit.value)}).when(user)

# :- assign(USER_ID, VIDEO_TYPE, RESOLUTION, BITRATE,SAT), not r(VIDEO_TYPE, RESOLUTION, BITRATE, SAT).
with Assign() as a, R(video=a.user.video, resolution=a.user.resolution, bit_rate=a.bit_rate, sat_value=a.sat_value) as r:
    p += Assert(r).when(a)

# :- global_capacity(G), G < #sum{BITRATE, USER_ID : assign(USER_ID,_,_, BITRATE,_) }.
with GlobalCapacity() as g, Assign() as a:
    p += Assert(Sum({(a.bit_rate.value, a.user.id): a}) < g.value).when(g)

# :- fraction_user(F), F > #count{USER_ID : assign(USER_ID,_,_,_,_) }.
with FractionUser() as f, Assign() as a:
    p += Assert(False).when(f, f.value > Count({a.user.id: a}))

# :~ assign(USER_ID, _, _, BITRATE, SAT_VALUE), user(USER_ID, _, _,_, BEST_SAT, _). [BEST_SAT-SAT_VALUE@1,USER_ID ,assign]
with User(video=hide(), resolution=hide(), bandwidth=hide(), max_bit=hide()) as user, Assign(user=user) as a:
    p += Assert(False).when(user, a).otherwise(user.max_sat.value-a.sat_value.value, 1, user.id, "assign")

print(p)

solver = SolverWrapper(solver_path="/usr/local/bin/clingo")
res = solver.solve(problem=p, timeout=30)
if res.status == Result.HAS_SOLUTION:
    assert len(res.answers) >= 1
    answer = res.answers[-1]
    result = answer.get_atom_occurrences(Assign())
    print(f"Found solution with cost {answer.costs}: ")
    for assignment in result:
        print(f"{assignment.user.id}: {assignment.bit_rate} - {assignment.sat_value}")
elif res.status == Result.NO_SOLUTION:
    print("No solution found!")
else:
    print("Unknown")
