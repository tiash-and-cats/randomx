"""A simple syntax highlighter for Python code."""
import tokenize, io, keyword, builtins

RESET       = -1
IDENTIFIER  = -2
KEYWORD     = -3
BUILTIN     = -4

COLORS = {
    tokenize.COMMENT: "\x1b[31m",   # red
    tokenize.STRING:  "\x1b[32m",   # green
    tokenize.NUMBER:  "\x1b[33m",   # yellow
    tokenize.OP:      "\x1b[37m",   # white
    
    RESET:            "\x1b[0m",    # reset
    IDENTIFIER:       "\x1b[37m",   # white
    KEYWORD:          "\x1b[1;34m", # bright blue
    BUILTIN:          "\x1b[36m",   # cyan
}

COLORS[tokenize.FSTRING_START] = COLORS[tokenize.FSTRING_MIDDLE] = \
    COLORS[tokenize.FSTRING_END] = COLORS[tokenize.TSTRING_START] = \
    COLORS[tokenize.TSTRING_MIDDLE] = COLORS[tokenize.TSTRING_END] = \
    COLORS[tokenize.STRING]

NORESET = {tokenize.FSTRING_START, tokenize.TSTRING_START}
BUILTINS = set(dir(builtins))

def highlight(src):
    """Syntax-highlight src as Python code.""" 
    try:
        # flatten into list of chars
        out = list(src)
        seq = 0

        # precompute line starts so we can map (line, col) → absolute index
        line_starts = []
        pos = 0
        for line in src.splitlines(True):
            line_starts.append(pos)
            pos += len(line)

        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            ttype, tstring, (sline, scol), (eline, ecol), _ = tok
            
            if ttype in {0, tokenize.DEDENT, tokenize.NL, tokenize.NEWLINE}:
                continue
            
            if ttype == tokenize.NAME:
                if keyword.iskeyword(tstring) or \
                   keyword.issoftkeyword(tstring):
                    color = COLORS[KEYWORD]
                elif tstring in BUILTINS:
                    color = COLORS[BUILTIN]
                else:
                    color = COLORS[IDENTIFIER]
            else:
                color = COLORS.get(ttype, "")

            # convert (line, col) to absolute index
            start = line_starts[sline-1] + scol
            end   = line_starts[eline-1] + ecol

            # insert color and reset with seq offset
            out.insert(seq + start, color)
            seq += 1
            if ttype not in NORESET:
                out.insert(seq + end, COLORS[RESET])
                seq += 1

        return "".join(out)
    except:
        return f"\x1b[1;31m{src}\x1b[0m"