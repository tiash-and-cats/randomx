import os
import sys
import shutil
import shlex
import subprocess
import collections
import getopt
import random
import re
import glob

BLOCKS = {"{": "}", "[": "]"}

RE_VARIABLE = "[a-zA-Z0-9-_]+"
RE_VAR_INTERPOLATION = r"\$(%s)|\${(%s)}" % (RE_VARIABLE, RE_VARIABLE)
RE_PROC_COMMAND = r"(?s)proc\s(?P<name>%s)\s*{(?P<body>.*)}" % RE_VARIABLE
RE_THEN_COMMAND = r"(?s)then\s*{(?P<body>.*)}"
RE_FOREVER_COMMAND = r"(?s)forever\s*{(?P<body>.*)}"
RE_TRY_COMMAND = r"(?s)try\s*{(?P<body>.*)}"
RE_BLOCKS = r"({.*?}|\[.*?])"

gvarses = collections.ChainMap({
    "SHELL": "dosh"
}, os.environ)

gprocs = collections.ChainMap()

shopt = {
    "quit-undefined-var": "0",
    "quit-invalid-expr": "0",
    "debug": "0",
    "condt-flag": "0",
}

def split_cmds(cmd_list):
    cmds = []
    cmd_str = ""
    blockq = collections.deque()
    for c in cmd_list:
        if c in BLOCKS:
            blockq.append(c)
        if blockq and c == BLOCKS[blockq[-1]]:
            blockq.pop()
        if not blockq and c in (";", "\n"):
            cmds.append(cmd_str)
            cmd_str = ""
            continue
        cmd_str += c
    if cmd_str.strip():
        raise Exception("incomplete command! oh no")
    return cmds

def nonzero(v):
    return v not in ("0", 0)

def num(s):
    if isinstance(s, (int, float)): return s
    try:
        return int(s, 0)
    except:
        try:
            return float(s)
        except:
            if s.endswith("H"):
                return int(s.removesuffix("H"), 16)
            elif s.endswith("o"):
                return int(s.removesuffix("o"), 😎
    raise ValueError("invalid number literal")

def eval_expr(expr, varses, procs):
    old_expr = expr
    expr = shlex.split(expr)
    stack = collections.deque()
    for val in expr:
        try:
            match val:
                case "+":
                    stack.append(num(stack.pop()) + num(stack.pop()))
                case "-":
                    n1 = num(stack.pop()); n2 = num(stack.pop())
                    stack.append(n2 - n1)
                case "*":
                    stack.append(num(stack.pop()) * num(stack.pop()))
                case "/":
                    n1 = num(stack.pop()); n2 = num(stack.pop())
                    stack.append(n2 / n1)
                case "lt":
                    n1 = num(stack.pop()); n2 = num(stack.pop())
                    stack.append(int(n2 < n1))
                case "gt":
                    n1 = num(stack.pop()); n2 = num(stack.pop())
                    stack.append(int(n2 > n1))
                case "lt=":
                    n1 = num(stack.pop()); n2 = num(stack.pop())
                    stack.append(int(n2 <= n1))
                case "gt=":
                    n1 = num(stack.pop()); n2 = num(stack.pop())
                    stack.append(int(n2 >= n1))
                case "==":
                    stack.append(int(stack.pop() == stack.pop()))
                case "!=" | "<>" | "<=>":
                    stack.append(int(stack.pop() != stack.pop()))
                case "and":
                    stack.append(int(nonzero(stack.pop()) and nonzero(stack.pop())))
                case "or":
                    stack.append(int(nonzero(stack.pop()) or nonzero(stack.pop())))
                case "not":
                    stack.append(int(not nonzero(stack.pop())))
                case "dec":
                    stack.append(num(stack.pop()))
                case "rand":
                    n1 = num(stack.pop()) # max
                    n2 = num(stack.pop()) # min
                    stack.append(random.randint(n2, n1))
                case "$":
                    with open(".doshtemp0", "w+") as f:
                        sys.stdout = f
                        run_cmd(str(stack.pop()) + "\n", varses.new_child(), procs.new_child())
                        f.seek(0)
                        stack.append(f.read())
                        sys.stdout = sys.__stdout__
                case "get":
                    i = stack.pop()
                    v = stack.pop()
                    try:
                        i = int(num(i))
                        l = shlex.split(v)
                        stack.append(l[i])
                    except ValueError:
                        d = dict([shlex.split(x) for x in shlex.split(v)])
                        stack.append(d[i])
                case "len":
                    l = shlex.split(stack.pop())
                    stack.append(len(l))
                case "range":
                    j = int(num(stack.pop()))
                    i = int(num(stack.pop()))
                    l = shlex.split(stack.pop())
                    stack.append(shlex.join(l[i:j]))
                case "join":
                    s = stack.pop()
                    l = shlex.split(stack.pop())
                    stack.append(s.join(l))
                case "range":
                    s1 = stack.pop(); s2 = stack.pop()
                    stack.append(s2.split(s1))
                case "glob":
                    stack.append(shlex.join(glob.glob(stack.pop())))
                case _:
                    stack.append(preprocess(val, varses, procs))
        except IndexError as e:
            raise Exception("invalid expression syntax in: " + old_expr)
        except ValueError as e:
            raise Exception("invalid list")
    return stack[-1]

def preprocess(cmd_str, varses, procs):
    def handle_var(match):
        var = match.groups()[0]
        if var in varses:
            return str(varses[var])
        elif shopt["quit-undefined-var"] != "0":
            raise Exception(f"variable {var} is not defined")
        else:
            return ""
        
    # Split the string into blocks and non-blocks
    # Example: 'echo $VAR {do not $SUB}' -> ['echo $VAR ', '{do not $SUB}']
    parts = re.split(RE_BLOCKS, cmd_str, flags=re.DOTALL)
    
    new_parts = []
    for part in parts:
        if part.startswith(("{", "[")):
            # It's a block! Do NOT interpolate variables here.
            # But wait: if it's a math block [], we DO want to eval_expr.
            if part.startswith("["):
                # Remove the brackets, eval the inside, then put back
                expr_content = part[1:-1]
                new_parts.append(str(eval_expr(expr_content, varses, procs)))
            else:
                # It's a {} block, keep it exactly as is (literal)
                new_parts.append(part)
        else:
            # It's plain text! Safe to interpolate variables.
            interpolated = re.sub(RE_VAR_INTERPOLATION, handle_var, part)
            new_parts.append(interpolated)
            
    return "".join(new_parts)

def exec_one(cmd_str, varses, procs):
    cmd_str = cmd_str.strip()
    if not cmd_str: return 0
    status = 1
    cmd_str = preprocess(cmd_str, varses, procs)
    file = None
    if ">" in cmd_str and "{" not in cmd_str:
        cmd_str, filename = cmd_str.split(">", 1)
        sys.stdout = file = open(filename.strip(), "w")
    if (status := handle_external_cmd(cmd_str)) is None:
        status = handle_builtin_cmd(cmd_str, varses, procs)
    if file:
        file.close()
        sys.stdout = sys.__stdout__
    return status

def run_external_cmd(args, file=sys.stdout):
    p = subprocess.Popen(args, env=os.environ)
    for line in p.stdout:
        file.write(line)
        file.flush()
    p.communicate()

def handle_external_cmd(cmd_str):
    toks = shlex.split(cmd_str)
    exe = ""
    if not (exe := shutil.which(toks[0])):
        return None
    return subprocess.run([exe, *toks[1:]], env=os.environ, stdout=sys.stdout, stderr=sys.stderr, stdin=sys.stdin).returncode

def handle_builtin_cmd(cmd_str, varses, procs):
    if cmd_str.startswith("#"): return 0
    cmd, *args = cmd_str.split(maxsplit=1)
    if args: args = args[0]
    else: args = ""
    if cmd in procs:
        run_cmd(procs[cmd], varses.new_child(), procs.new_child())
        return 0
    match cmd:
        case "set":
            stuff, val = [x.strip() for x in args.split("=", 1)]
            *unparsed_opts, var = stuff.split()
            opts, _ = getopt.getopt(unparsed_opts, 'sge')
            if not re.match(RE_VARIABLE, var):
                print(f"dosh: set: variable name is invalid ({var})", file=sys.stderr)
                return 1
            if ("-s", "") in opts:
                shopt[var] = val
            elif ("-g", "") in opts:
                gvarses[var] = val
            elif ("-e", "") in opts:
                os.environ[var] = val
            else:
                varses[var] = val
            return 0
        case "echo":
            opts, args = getopt.getopt(shlex.split(args), 'n')
            if ('-n', '') not in opts:
                print(*args)
            else:
                print(*args, end="")
            return 0
        case "cd":
            os.chdir(args)
            return 0
        case "who":
            return 0
        case "proc":
            match = re.match(RE_PROC_COMMAND, cmd_str)
            if not match:
                print("dosh: proc: invalid declaration", file=sys.stderr)
                return 1
            procs[match["name"]] = match["body"]
            return 0
        case "then":
            match = re.match(RE_THEN_COMMAND, cmd_str)
            if not match:
                print("dosh: then: invalid syntax", file=sys.stderr)
                return 1
            if nonzero(shopt["condt-flag"]):
                return run_cmd(match["body"], varses.new_child(), procs.new_child())
            return 0
        case "if":
            shopt["condt-flag"] = str(eval_expr(args, varses, procs))
            return 0
        case "else":
            shopt["condt-flag"] = str(int(not nonzero(shopt["condt-flag"])))
            return 0
        case "elif":
            shopt["condt-flag"] = str(int((not nonzero(shopt["condt-flag"])) and nonzero(eval_expr(args, varses, procs))))
            return 0
        case "then":
            match = re.match(RE_THEN_COMMAND, cmd_str)
            if not match:
                print("dosh: then: invalid syntax", file=sys.stderr)
                return 1
            if nonzero(shopt["condt-flag"]):
                run_cmd(match["body"], varses.new_child(), procs.new_child())
            return 0
        case "read":
            try:
                # 'p:' means -p requires an argument
                opts, remainder = getopt.getopt(shlex.split(args), 'p:')
                
                prompt = ""
                for opt, val in opts:
                    if opt == '-p':
                        prompt = val
                
                if not remainder:
                    print("dosh: read: missing variable name", file=sys.stderr)
                    return 1
                
                var_name = remainder[0]
                varses[var_name] = input(prompt)
                return 0
                
            except getopt.GetoptError as e:
                print(f"dosh: read: {e}", file=sys.stderr)
                return 1
            except (EOFError, KeyboardInterrupt):
                return 1
        case "forever":
            match = re.match(RE_FOREVER_COMMAND, cmd_str)
            if not match:
                print("dosh: forever: invalid syntax", file=sys.stderr)
                return 1
            r = 0
            while r != -1:
                r = run_cmd(match["body"], varses.new_child(), procs.new_child())
                if r != 0:
                    return r
            return 0
        case "break":
            return -1
        case "source":
            with open(args.strip()) as f:
                run_cmd(f.read() + "\n", varses, procs)
        case "incr":
            opts, args = getopt.getopt(shlex.split(args), 'g')
            glob = ("-g", "") in opts
            if not args:
                print(f"dosh: incr: variable name is missing", file=sys.stderr)
                return 1
            var = args[0]
            if not re.match(RE_VARIABLE, var):
                print(f"dosh: incr: variable name is invalid ({var})", file=sys.stderr)
                return 1
            if var not in varses:
                print(f"dosh: incr: variable {var} does not exist", file=sys.stderr)
                return 1
            if not glob:
                varses[var] = num(varses[var]) + 1
            else:
                gvarses[var] = num(gvarses[var]) + 1
            return 0
        case "decr":
            opts, args = getopt.getopt(shlex.split(args), 'g')
            glob = ("-g", "") in opts
            if not args:
                print(f"dosh: incr: variable name is missing", file=sys.stderr)
                return 1
            var = args[0]
            if not re.match(RE_VARIABLE, var):
                print(f"dosh: incr: variable name is invalid ({var})", file=sys.stderr)
                return 1
            if var not in varses:
                print(f"dosh: incr: variable {var} does not exist", file=sys.stderr)
                return 1
            if not glob:
                varses[var] = num(varses[var]) - 1
            else:
                gvarses[var] = num(gvarses[var]) - 1
            return 0
        case "try":
            match = re.match(RE_TRY_COMMAND, cmd_str)
            if not match:
                print("dosh: try: invalid syntax", file=sys.stderr)
                return 1
            if run_cmd(match["body"], varses.new_child(), procs.new_child()) != 0:
                shopt["condt-flag"] = "1"
            else:
                shopt["condt-flag"] = "0"
            return 0
        case "append":
            args = shlex.split(args)
            assert len(args) == 2, "append: expected two arguments (list and item)"
            lname, v = args
            l = shlex.split(varses[lname])
            l.append(v)
            varses[lname] = shlex.join(l)
        case "setitem":
            args = shlex.split(args)
            assert len(args) == 3, "setitem: expected three arguments (dict, key, and value)"
            dname, k, v = args
            d = dict([shlex.split(x) for x in shlex.split(varses[dname])])
            d[k] = v
            varses[dname] = shlex.join([shlex.join(x) for x in d.items()])
        case _:
            print(f"dosh: command {cmd} does not exist as an runnable file or builtin command.", file=sys.stderr)
            return 1

def run_cmd(cmds, varses=gvarses, procs=gprocs):
    try:
        for cmd_str in split_cmds(cmds):
            res = exec_one(cmd_str, varses, procs)
            if res != 0:
                return res
        return 0
    except Exception as e:
        print("dosh:", e, file=sys.stderr)
        if nonzero(shopt["debug"]):
            import traceback
            traceback.print_exception(e)
        return 1

if _name_ == "_main_":
    while True:
        print(os.getcwd())
        cmd_list = ""
        while True:
            cmd_list += input(">>> ") + "\n"
            try:
                split_cmds(cmd_list)
                break
            except:
                continue
        try:
            run_cmd(cmd_list)
        except BaseException:
            pass
        print()