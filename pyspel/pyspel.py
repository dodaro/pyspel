import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from dataclasses import field
import os
import json
from time import sleep
from types import FunctionType, CodeType
from typing import Any, ClassVar

__version__ = "1.0.2"

invalid_exit_codes = {1, 65}


def abs_v(value):
    return Term(ObjectVariable(f'|{value}|'))


def domain(min_, max_):
    return Term(ObjectVariable(f'{min_}..{max_}'))


def _get_terms(predicate_name, atom_name):
    count_o = 0
    count_c = 0
    atom_name = atom_name.replace(predicate_name, '', 1)
    if atom_name.endswith('.'):
        atom_name = atom_name[:-1]
    if atom_name[0] == '(' and atom_name[-1] == ')':
        atom_name = atom_name[1:-1]

    elements = []
    my_string = ""
    ignore = False
    for i in range(0, len(atom_name)):
        my_string += atom_name[i]
        if atom_name[i] == '"' and not ignore:
            ignore = True
        elif atom_name[i] == '"' and ignore:
            ignore = False
        if ignore:
            continue
        if atom_name[i] == "(":
            count_o += 1
        elif atom_name[i] == ")":
            count_c += 1
        elif atom_name[i] == "," and count_o == count_c:
            elements.append(my_string[:-1])
            my_string = ""
        if (i + 1) == len(atom_name):
            elements.append(my_string)
            my_string = ""
    return elements


def _run_solver(rules, solver_path, options, timeout):
    filename = tempfile.gettempdir() + os.path.sep + "pyspel_tmp_program_%s" % uuid.uuid4()
    output_filename = tempfile.gettempdir() + os.path.sep + "pyspel_tmp_program_%s.json" % uuid.uuid4()
    with open(filename, "w+") as f:
        f.write(rules)
        f.close()
    out = open(output_filename, "w")

    if solver_path is None:
        commands = ["clingo"]
    else:
        commands = [solver_path]
    commands.extend(options)
    commands.append(filename)
    solver = subprocess.Popen(commands, stdin=None, stdout=out, stderr=subprocess.PIPE)
    killed = False
    exit_code = 1
    try:
        stdout, stderr = solver.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        solver.terminate()
        sleep(3)
        solver.kill()
        stdout, stderr = solver.communicate()
        exit_code = 11
        killed = True
    out.close()

    if not killed:
        exit_code = solver.returncode
    os.remove(filename)
    output = ""
    with open(output_filename, "r") as o:
        output = "\n".join(o.readlines())
    os.remove(output_filename)
    return output, stderr.decode(), exit_code, killed


@dataclass(frozen=True)
class ObjectVariable:
    value: str = field(default_factory=lambda: f'X{uuid.uuid4().hex}')

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.__str__()


@dataclass(frozen=True)
class Term:
    value: Any = field(default_factory=lambda: ObjectVariable())

    def __str__(self):
        assert self.value is not None
        if isinstance(self.value, str):
            return f'"{self.value}"'
        return str(self.value)

    def __repr__(self):
        return self.__str__()

    @classmethod
    def _op(cls, term1, term2, operator):
        return Literal(Atom(Predicate(f"{term1} {operator} {term2}")), True)

    @classmethod
    def _arithmetic(cls, term1, term2, operator):
        return Term(ObjectVariable(value=f"({term1} {operator} {term2})"))

    def __eq__(self, other):
        return Term._op(self, other, "=")

    def __ne__(self, other):
        return Term._op(self, other, "!=")

    def __lt__(self, other):
        return Term._op(self, other, "<")

    def __le__(self, other):
        return Term._op(self, other, "<=")

    def __gt__(self, other):
        return Term._op(self, other, ">")

    def __ge__(self, other):
        return Term._op(self, other, ">=")

    def __add__(self, other):
        if not isinstance(other, Term):
            other = Term(other)
        return Term._arithmetic(self.value, other.value, "+")

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if not isinstance(other, Term):
            other = Term(other)
        return Term._arithmetic(self.value, other.value, "-")

    def __rsub__(self, other):
        if not isinstance(other, Term):
            other = Term(other)
        return Term._arithmetic(other.value, self.value, "-")

    def __mul__(self, other):
        if not isinstance(other, Term):
            other = Term(other)
        return Term._arithmetic(self.value, other.value, "*")

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if not isinstance(other, Term):
            other = Term(other)
        return Term._arithmetic(self.value, other.value, "/")

    def __rtruediv__(self, other):
        if not isinstance(other, Term):
            other = Term(other)
        return Term._arithmetic(other.value, self.value, "/")

    def __mod__(self, other):
        if not isinstance(other, Term):
            other = Term(other)
        return Term._arithmetic(self.value, other.value, "\\")

    def __pow__(self, power, modulo=None):
        if not isinstance(power, Term):
            power = Term(power)
        return Term._arithmetic(self.value, power, "**")


@dataclass(frozen=True)
class Predicate:
    name: str


class Atom:
    __predicate: Predicate

    def __init__(self, predicate):
        self.__predicate = predicate

    @property
    def predicate(self):
        return self.__predicate

    def create_atom_from_str(self, atom_name):
        if not isinstance(atom_name, str):
            raise ValueError("Expected string")
        my_terms = _get_terms(predicate_name=self.predicate.name, atom_name=atom_name)
        assert len(my_terms) <= len(self.__dict__) - 1
        i = 0
        terms = []
        for term in self.__dict__:
            if isinstance(self.__dict__[term], Term):
                if my_terms[i].startswith('"'):
                    terms.append(my_terms[i][1:-1])
                else:
                    try:
                        element = int(my_terms[i])
                    except ValueError:
                        element = eval(my_terms[i])
                    terms.append(element)
                i += 1
            elif isinstance(self.__dict__[term], Atom):
                terms.append(self.__dict__[term].create_atom_from_str(my_terms[i]))
                i += 1
            elif not isinstance(self.__dict__[term], Predicate):
                terms.append(self.__dict__[term])
        res = type(self)(*terms)
        return res

    def to_python_class(self):
        terms = []
        for term in self.__dict__:
            t = self.__dict__[term]
            if isinstance(t, Term):
                terms.append(t.value)
            elif isinstance(t, Atom):
                terms.append(t.to_python_class())
            elif not isinstance(t, Predicate):
                terms.append(t.name)
        name = self.predicate.name[0].upper() + self.predicate.name[1:]
        cls = globals()[name]
        obj = cls()
        args = getattr(cls, '__annotations__', {})
        new_args = {}
        count = 0
        for i in args:
            new_args[i] = terms[count]
            setattr(obj, f'{i}', terms[count])
            count += 1
        return obj

    def __str__(self):
        terms = []
        for term in self.__dict__:
            if isinstance(self.__dict__[term], Term):
                terms.append(f"{self.__dict__[term]}")
            elif isinstance(self.__dict__[term], Atom):
                terms.append(str(self.__dict__[term]))

        res = self.predicate.name
        if len(terms) > 0:
            res += "(%s)" % ', '.join(terms)
        return res

    def __hash__(self):
        return hash((self.predicate, str(self.__dict__)))

    def __eq__(self, other):
        return (self.predicate, str(self.__dict__)) == (other.__predicate, str(other.__dict__))

    def __repr__(self):
        return str(self)

    def __invert__(self):
        return Literal(self, False)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass


class Literal:

    def __init__(self, atom_name, positive):
        self.__atom = atom_name
        if positive:
            self.__polarity = ''
        else:
            self.__polarity = 'not '

    def __invert__(self):
        self.__polarity += 'not '
        return self

    def __str__(self):
        return self.__polarity + str(self.__atom)

    def __repr__(self):
        return str(self)


class ConditionalLiteral:

    def __init__(self, elements_):
        self.__elements = elements_

    @classmethod
    def _process_dict(cls, element_):
        if not isinstance(element_, dict):
            return None
        all_elements = []
        for element in element_:
            if isinstance(element_[element], tuple):
                element_[element] = str(element_[element])[1:-1]
            if type(element) is tuple:
                res = ""
                for i in element:
                    res += f"{i},"
                res = res[:-1]
                all_elements.append("%s : %s" % (res, element_[element]))
            else:
                all_elements.append("%s : %s" % (element, element_[element]))
        return "; ".join(all_elements)

    def __str__(self):
        if isinstance(self.__elements, list):
            if len(self.__elements) == 0:
                return None
            s = ConditionalLiteral._process_dict(self.__elements[0])
            for element in range(1, len(self.__elements)):
                s += "; %s" % ConditionalLiteral._process_dict(self.__elements[element])
        else:
            s = ConditionalLiteral._process_dict(self.__elements)
        return "%s" % s


class Aggregate(Atom):

    def __init__(self, aggregate_set, aggregate_type):
        Atom.__init__(self, '')
        if aggregate_type is None or aggregate_type != 'count' and aggregate_type != 'sum' and aggregate_type != 'min' and aggregate_type != 'max':
            raise ValueError(f"Unexpected type {aggregate_type} for aggregate")
        if aggregate_type == 'count' and not isinstance(aggregate_set, dict) and not isinstance(aggregate_set, set):
            raise ValueError(f"Expected dictionary or set as set for {aggregate_type}, got {type(aggregate_set)}")
        if aggregate_type != 'count' and not isinstance(aggregate_set, dict):
            raise ValueError(f"Expected dictionary as set for {aggregate_type}, got {type(aggregate_set)}")
        self.aggregate_type = aggregate_type
        self.aggregate_set = aggregate_set
        self.operator = None
        self.bound = None

    def __str__(self):
        op_ = f" {self.operator}"
        bound_ = f" {self.bound}"
        if self.operator is None:
            op_ = ""
            bound_ = ""
        elif self.bound is None:
            raise ValueError("Missing bound")
        if isinstance(self.aggregate_set, dict):
            elements = [{element: self.aggregate_set[element]} for element in self.aggregate_set]
            return "#%s{%s}%s%s" % (self.aggregate_type, str(ConditionalLiteral(elements)), op_, bound_)
        else:
            return "#%s%s%s%s" % (self.aggregate_type, self.aggregate_set, op_, bound_)

    def __repr__(self):
        return str(self)

    def _op(self, term, operator):
        self.operator = operator
        self.bound = term

    def __eq__(self, other):
        self._op(other, "=")
        return self

    def __ne__(self, other):
        self._op(other, "!=")
        return self

    def __lt__(self, other):
        self._op(other, "<")
        return self

    def __le__(self, other):
        self._op(other, "<=")
        return self

    def __gt__(self, other):
        self._op(other, ">")
        return self

    def __ge__(self, other):
        self._op(other, ">=")
        return self


class Count(Aggregate):

    def __init__(self, elements):
        Aggregate.__init__(self, aggregate_set=elements, aggregate_type="count")


class Sum(Aggregate):

    def __init__(self, elements):
        Aggregate.__init__(self, aggregate_set=elements, aggregate_type="sum")


class Min(Aggregate):

    def __init__(self, elements):
        Aggregate.__init__(self, aggregate_set=elements, aggregate_type="min")


class Max(Aggregate):

    def __init__(self, elements):
        Aggregate.__init__(self, aggregate_set=elements, aggregate_type="max")


class Definition:

    def __init__(self):
        self._body = []

    def when(self, *condition):
        assert isinstance(condition, tuple)
        for element in condition:
            if isinstance(element, dict):
                self._body.append(ConditionalLiteral(element))
            elif isinstance(element, list):
                self._body.extend(element)
            elif isinstance(element, Atom) or isinstance(element, Literal) or isinstance(element, ConditionalLiteral):
                self._body.append(element)
            else:
                raise ValueError(f"Unexpected element of type {type(element)} in when condition")
        return self

    def get_body(self):
        if len(self._body) >= 1:
            body = str(self._body[0])
            for i in range(1, len(self._body)):
                body += f"; {str(self._body[i])}"
            return body
        else:
            return ""

    def get_head(self):
        raise ValueError("Cannot use get_head of Definition class. Use Guess, Define, or Assert")

    def check(self, solver_path=None):
        (stdout, stderr, exit_code, killed) = _run_solver(rules=str(self), solver_path=solver_path, options=["--text"], timeout=None)
        if exit_code in invalid_exit_codes:
            raise ValueError(f"ASP Error: {stderr}")
        return self

    def __str__(self):
        head = self.get_head()
        if head is None:
            head = ""
        separator = ""
        body = self.get_body()
        if body != "":
            separator = " :- "

        return f"{head}{separator}{body}."

    def __repr__(self):
        return str(self)


class Guess(Definition):
    def __init__(self, head, exactly=None, at_least=None, at_most=None):
        Definition.__init__(self)
        if head is None:
            raise ValueError("Unexpected empty head set for Guess")
        if isinstance(head, dict):
            if len(head) == 0:
                raise ValueError("Unexpected empty head set for Guess")
            self._head = ConditionalLiteral(head)
        elif isinstance(head, set):
            self._head = head
        elif isinstance(head, Atom):
            self._head = head
        else:
            raise ValueError(f"Expected dict, set, or Atom as head for guess, got {type(head)}")
        self.exactly = exactly
        self.at_least = at_least
        self.at_most = at_most
        if self.exactly is not None and (self.at_least is not None or self.at_most is not None):
            raise ValueError("Error while building guess: exactly is incompatible with at_least and at_most")

    def get_head(self):
        if isinstance(self._head, set):
            tmp = ';'.join([str(el) for el in self._head])
            my_head = f"{{{tmp}}}"
        else:
            my_head = f"{{{self._head}}}"

        if self.exactly is not None:
            head = f"{my_head} = {self.exactly}"
        elif self.at_least is not None and self.at_most is not None:
            head = f"{self.at_least} <= {my_head} <= {self.at_most}"
        elif self.at_least is not None:
            head = f"{self.at_least} <= {my_head}"
        elif self.at_most is not None:
            head = f"{my_head} <= {self.at_most}"
        else:
            head = f"{my_head}"
        return head


class Define(Definition):
    def __init__(self, *head):
        assert isinstance(head, tuple)
        if head is None or len(head) == 0:
            raise ValueError("Expected head")
        Definition.__init__(self)
        self._head = []
        for element in head:
            if isinstance(element, dict):
                self._head.append(ConditionalLiteral(element))
            else:
                self._head.append(element)

    def get_head(self):
        head = str(self._head[0])
        for i in range(1, len(self._head)):
            head += f" | {str(self._head[i])}"
        return head


class Assert(Definition):

    def __init__(self, *disjunction):
        Definition.__init__(self)
        self.disjunction = disjunction
        self._soft = False
        self.weight = None
        self.level = None
        self.terms = []

        for el in self.disjunction:
            if el is None or el is False:
                if len(self.disjunction) != 1:
                    raise ValueError("Unexpected None or False element")
            else:
                if not isinstance(el, Atom) and not isinstance(el, Literal):
                    raise ValueError("Unexpected element of type %s" % type(el))
                self.when(~el)

    def get_head(self):
        return None

    def otherwise(self, weight, level, *terms):
        self._soft = True
        self.weight = weight
        self.level = level
        if self.weight is None:
            raise ValueError("Unexpected None weight")
        if self.level is None:
            raise ValueError("Unexpected None level")
        for i in terms:
            self.terms.append(str(i))
        return self

    def __str__(self):
        if self._soft:
            return f" :~ {self.get_body()}. [{self.weight}@{self.level}, {','.join(self.terms)}]"
        else:
            return Definition.__str__(self)


class When:

    def __init__(self, *condition):
        assert isinstance(condition, tuple)
        self._condition = condition

    def and_also(self, *condition):
        assert isinstance(condition, tuple)
        self._condition += condition
        return self

    def holds(self, *disjunction):
        return Assert(*disjunction).when(*self._condition)

    def define(self, *head):
        return Define(*head).when(*self._condition)

    def guess(self, head, exactly=None, at_least=None, at_most=None):
        return Guess(head, exactly, at_least, at_most).when(*self._condition)


def _print_warning(stderr):
    print("ASP warning message:", file=sys.stderr)
    for line in stderr.splitlines():
        print(line, file=sys.stderr)


class Problem:
    ASP_CORE = 0
    GRINGO = 1

    def __init__(self):
        self.rules = []

    def add(self, *definitions):
        for i in definitions:
            self.__add(i)

    def __add(self, definition):
        if issubclass(type(definition), Atom):
            definition = Define(definition)
        if not isinstance(definition, Definition) and not isinstance(definition, str):
            raise ValueError("Expected rule, got %s" % type(definition))
        self.rules.append(definition)

    def check(self, solver_path=None):
        (stdout, stderr, exit_code, killed) = _run_solver(rules=str(self), solver_path=solver_path, options=["--text"], timeout=None)
        if exit_code in invalid_exit_codes:
            raise ValueError(f"ASP Error: {stderr}")
        elif len(stderr) != 0:
            _print_warning(stderr)

    def __str__(self):
        res = ""
        for i in self.rules:
            res += "%s\n" % (str(i))
        return res

    def __repr__(self):
        return self.__str__()

    def __iadd__(self, other):
        if isinstance(other, tuple) or isinstance(other, list):
            for el in other:
                self.add(el)
        else:
            self.add(other)
        return self

    def possible_instances(self, atom_name, solver_path=None):
        if not isinstance(atom_name, Atom):
            raise ValueError(f"Expected atom, got {type(atom_name)}")
        (stdout, stderr, exit_code, killed) = _run_solver(rules=str(self), solver_path=solver_path, options=["--output=smodels"], timeout=None)
        if exit_code in invalid_exit_codes:
            raise ValueError(f"ASP Error: {stderr}")
        elif len(stderr) != 0:
            _print_warning(stderr)

        all_atoms = []
        lines = stdout.splitlines()
        start_atoms = False
        for line in lines:
            if line == "0" and not start_atoms:
                start_atoms = True
            elif line == "0" and start_atoms:
                break
            elif start_atoms:
                all_atoms.append(line.split(" ", 1)[1])
        a = Answer(all_atoms, [], False)
        return a.get_atom_occurrences(atom_name)


class Answer:

    def __init__(self, answer_set, costs, optimal):
        self._answer_set = answer_set
        self.costs = costs
        self.optimal = optimal

    def get_atom_occurrences(self, atom_name):
        if not isinstance(atom_name, Atom):
            raise ValueError("Expected atom as parameter")
        res = []
        for at in self._answer_set:
            if at.startswith(atom_name.predicate.name):
                res.append(atom_name.create_atom_from_str(at))
        return res

    def get_class_occurrences(self, atom_name):
        if not isinstance(atom_name, Atom):
            raise ValueError("Expected atom as parameter")
        res = []
        for at in self._answer_set:
            if at.startswith(atom_name.predicate.name):
                res.append(atom_name.create_atom_from_str(at).to_python_class())
        return res


class ASPUtilities:

    @classmethod
    def process_asp_facts(cls, filename, atoms, solver_path=None):
        if not isinstance(atoms, list):
            raise ValueError("Expected list as parameter")
        for atom_ in atoms:
            if not isinstance(atom_, Atom):
                raise ValueError(f"Expected list of atoms as parameter, got {type(atom_)}")

        instance = open(filename, "r")
        (stdout, stderr, exit_code, killed) = _run_solver(rules='\n'.join(instance.readlines()), solver_path=solver_path, options=["--outf=2"], timeout=None)
        res = json.loads(stdout)
        if res['Result'] == 'SATISFIABLE':
            costs = []
            assert len(res['Call'][0]['Witnesses']) == 1
            answer_set = res['Call'][0]['Witnesses'][0]
            output = []
            if 'Value' in answer_set:
                answer = Answer(answer_set['Value'], costs, False)
                for atom_name in atoms:
                    output.extend(answer.get_atom_occurrences(atom_name=atom_name))
            return output


class Result:
    NO_SOLUTION = 1
    HAS_SOLUTION = 2
    UNKNOWN = 3

    def __init__(self, status):
        self.answers = []
        self.status = status

    def add_answer(self, answer):
        self.answers.append(answer)


class SolverWrapper:

    def __init__(self, solver_path=None):
        self._solver_path = solver_path
        self.killed = False

    def solve(self, problem, options=None, print_solver_output=False, timeout=None):
        self.killed = False
        if options is None:
            options = []
        if not isinstance(options, list):
            raise ValueError("Expected list of options, but received a %s" % (type(options)))
        for opt in options:
            if "--outf" in opt:
                raise ValueError("Option --outf is reserved")

        options.append("--outf=2")
        options.append("--quiet=0,1")
        (stdout, stderr, exit_code, killed) = _run_solver(str(problem), self._solver_path, options, timeout=timeout)
        self.killed = killed
        if print_solver_output:
            print(stdout)
        if exit_code in invalid_exit_codes:
            raise ValueError(f"ASP Error: {stderr}")
        elif len(stderr) != 0:
            _print_warning(stderr)

        res = json.loads(stdout)
        if res['Result'] == 'UNSATISFIABLE':
            return Result(Result.NO_SOLUTION)
        elif res['Result'] == 'SATISFIABLE':
            r = Result(Result.HAS_SOLUTION)
            costs = []
            for answer_set in res['Call'][0]['Witnesses']:
                if 'Value' in answer_set:
                    r.add_answer(Answer(answer_set['Value'], costs, False))
                if 'Costs' in answer_set:
                    for cost in answer_set['Costs']:
                        costs.append(cost)
                    costs = [].copy()
            return r
        elif res['Result'] == 'OPTIMUM FOUND':
            r = Result(Result.HAS_SOLUTION)
            costs = []
            for answer_set in res['Call'][0]['Witnesses']:
                if 'Value' in answer_set:
                    r.add_answer(Answer(answer_set['Value'], costs, True))
                if 'Costs' in answer_set:
                    for cost in answer_set['Costs']:
                        costs.append(cost)
                    costs = [].copy()
            return r
        else:
            return Result(Result.UNKNOWN)


def __create_atom(cls: ClassVar):
    class_name = cls.__name__
    predicate_name = class_name[0].lower() + class_name[1:]
    globals()[cls.__name__] = cls
    annotations = getattr(cls, '__annotations__', {})
    init_args = list(f'{a}' for a in annotations)
    globals_ = {k: v for k, v in globals().items() if k[0:2] == '__' or k[0].isupper()}
    for i in ["_as", "_", "__registered"]:
        if i in init_args:
            raise ValueError(f"{i} is a reserved keyword in pyspel, please use another name in class {class_name}")
    init_args.append("_as")
    init_args.append("_")

    def init_arg(arg: str, typ: type):
        ret = []
        if typ is int or typ is str or typ is bool or typ is any or typ is tuple:
            ret.append(f'if {arg} is not None:')
            if typ is not any:
                ret.append(f'    if not isinstance({arg},Term) and not isinstance({arg},{typ.__name__}):')
                ret.append(f'        raise ValueError(f"Expected element of type {typ.__name__}, got {{type({arg})}}")')
            ret.append(f'    self.{arg} = Term({arg})')
            ret.append('else:')
            ret.append(f'    self.{arg} = Term()')
        else:
            ret.append(f'if {arg} is not None:')
            ret.append(f'    if not isinstance({arg},Term) and not isinstance({arg},{typ.__name__}):')
            ret.append(f'        raise ValueError(f"Expected element of type {typ.__name__}, got {{type({arg})}}")')
            ret.append(f'    if not isinstance({arg},Term) and not isinstance({arg},Atom):')
            ret.append(
                f'        raise ValueError(f"{typ.__name__} is not an atom, did you forget the annotation @atom?")')
            ret.append(f'    self.{arg} = {arg}')
            ret.append('else:')
            ret.append(f'    self.{arg} = {typ.__name__}()')
        return ret

    def has_method(method: str) -> bool:
        return getattr(cls, method, None) != getattr(object, method, None)

    def create_method(sig: str, body: list, defaults: list) -> FunctionType:
        str_body = '\n    '.join(body)

        code = compile(f"{sig}\n    {str_body}", f'<pyspel|constructor of {class_name}|>', "exec")
        c = None
        for co_const in code.co_consts:
            if isinstance(co_const, CodeType):
                c = co_const
                break
        f = FunctionType(c, globals_)
        f.__defaults__ = tuple(defaults)
        return f

    def create_load_store_methods():
        body_store = [f"if _as is not None and not isinstance(_as, str):",
                      f'    raise ValueError(f"Expected str for _as, got {{type(_as)}}")',
                      f"if _as is None or len(_as) == 0:",
                      f'    _as = "__default__"',
                      f'{class_name}.__registered[_as]=self',
                      f'return self']
        setattr(cls, "s", create_method(sig="def s(self, _as):", body=body_store, defaults=[None]))

        body_load = [f"if _ is not None and not isinstance(_, str):",
                     f'    raise ValueError(f"Expected str for _, got {{type(_)}}")',
                     f"if _ is None or len(_) == 0:",
                     f'    _ = "__default__"',
                     f"if _ not in {class_name}.__registered:",
                     f'    raise ValueError(f"{{_}} is not registered, did you forget to use _as before?")',
                     f'return {class_name}.__registered[_]']
        setattr(cls, "l", classmethod(create_method(sig="def l(cls, _):", body=body_load, defaults=[None])))

    def create_new_object():
        if has_method('__init__'):
            raise ValueError("cannot process classes with __init__() constructor")
        inherit = f'Atom.__init__(self, predicate=Predicate("{predicate_name}"))'

        body = [f'if _as is not None and not isinstance(_as, str):',
                f'    raise ValueError(f"Expected str for _as, got {{type(_as)}}")',
                f'if _ is not None and not isinstance(_, str):',
                f'    raise ValueError(f"Expected str for _, got {{type(_)}}")',
                f'if _ is not None and _as is not None:',
                f'    raise ValueError(f"Expected at most one element between _ and _as")',
                f'if _as is not None:',
                f'    if len(_as) == 0:',
                f'        _as = "__default__"',
                f'    {class_name}.__registered[_as]=self',
                f'if _ is not None:',
                f'    if len(_) == 0:',
                f'        _ = "__default__"',
                f'    if _ not in {class_name}.__registered:',
                f'        raise ValueError(f"{{_}} is not registered, did you forget to use _as before?")']
        for arg in init_args:
            if arg != "_" and arg != "_as":
                body.append(f'    if {arg} is not None:')
                body.append(f'        raise ValueError("if _ is used all parameters must be None")')
                body.append(f'    self.{arg} = {class_name}.__registered[_].{arg}')
        body.append(f'    return')
        if len(init_args) > 0:
            args = 'self, ' + ', '.join(init_args)
            sig = f"def __init__({args}):"
            for k, v in annotations.items():
                body.extend(init_arg(k, v))
        else:
            sig = f"def __init__(self):"
        str_body = '\n    '.join(body)
        code = compile(f"{sig}\n    {inherit}\n    {str_body}", f'<pyspel|constructor of {class_name}|>', "exec")

        c = None
        for co_const in code.co_consts:
            if isinstance(co_const, CodeType):
                c = co_const
                break
        f = FunctionType(c, globals_)
        f.__defaults__ = tuple([None for _ in init_args])
        setattr(cls, "__registered", dict())
        setattr(cls, "__init__", f)
        create_load_store_methods()

        my_dict = {}
        for el in cls.__dict__:
            if el != "__dict__":
                my_dict[el] = cls.__dict__[el]
        return type(class_name, (Atom,), my_dict)

    return create_new_object()


def atom(cls: ClassVar) -> ClassVar:
    cls = __create_atom(cls)
    globals()[cls.__name__] = cls
    return cls


def var(name: str) -> Term:
    if not isinstance(name, str):
        raise ValueError(f"Expected str for name, got {type(name)}")
    if len(name) == 0:
        raise ValueError("Name cannot be empty")
    return Term(ObjectVariable("VAR_" + name))


def hide() -> Term:
    return Term(ObjectVariable("_"))
