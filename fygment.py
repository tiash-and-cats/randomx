"""A simple syntax highlighter for Python code."""
import tokenize
import io
import keyword
import builtins
import html

RESET          = -1
IDENTIFIER     = -2
KEYWORD        = -3
BUILTIN        = -4
SYNTAX_ERROR   = -5
TEXT_PROCESSOR = -6
SOFT_KEYWORD   = -7
ATTRIBUTE      = -8

def theme(colors):
    colors[tokenize.FSTRING_START] = colors[tokenize.FSTRING_MIDDLE] = \
        colors[tokenize.FSTRING_END] = colors[tokenize.TSTRING_START] = \
        colors[tokenize.TSTRING_MIDDLE] = colors[tokenize.TSTRING_END] = \
        colors[tokenize.STRING]
    
    return colors

ANSI_COLORS = theme({
    tokenize.COMMENT: "\x1b[31m",   # red
    tokenize.STRING:  "\x1b[32m",   # green
    tokenize.NUMBER:  "\x1b[33m",   # yellow
    tokenize.OP:      "\x1b[37m",   # white
    
    RESET:            "\x1b[0m",    # reset
    IDENTIFIER:       "\x1b[37m",   # white
    KEYWORD:          "\x1b[1;34m", # bright blue
    BUILTIN:          "\x1b[36m",   # cyan

    SYNTAX_ERROR:     "\x1b[1;31m", # bright red
    TEXT_PROCESSOR:   lambda x: x,
})

PYGMENTS_HTML_COLORS = theme({
    tokenize.COMMENT: '<span class="c">',   # Comment
    tokenize.STRING:  '<span class="s">',   # Literal.String
    tokenize.NUMBER:  '<span class="m">',   # Literal.Number
    tokenize.OP:      '<span class="o">',   # Operator
    
    RESET:            '</span>',
    IDENTIFIER:       '<span class="nv">',  # Name.Variable
    KEYWORD:          '<span class="k">',   # Keyword
    SOFT_KEYWORD:     '<span class="kp">',  # Keyword.Pseudo
    BUILTIN:          '<span class="nb">',  # Name.Builtin
    ATTRIBUTE:        '<span class="na">',  # Name.Attribute

    SYNTAX_ERROR:     '<span class="err">', # Error
    TEXT_PROCESSOR:   html.escape,
})

NORESET = {tokenize.FSTRING_START, tokenize.TSTRING_START}
BUILTINS = set(dir(builtins))

def highlight(src, *, colors=ANSI_COLORS):
    """Syntax-highlight src as Python code.""" 
    try:
        # flatten into list of chars
        out = [colors[TEXT_PROCESSOR](x) for x in src]
        seq = 0

        # precompute line starts so we can map (line, col) => absolute index
        line_starts = []
        pos = 0
        for line in src.splitlines(True):
            line_starts.append(pos)
            pos += len(line)

        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))

        for i, tok in enumerate(toks):
            ttype, tstring, (sline, scol), (eline, ecol), _ = tok
            
            if ttype in {0, tokenize.DEDENT, tokenize.NL, tokenize.NEWLINE}:
                continue
            
            if ttype == tokenize.NAME:
                if keyword.iskeyword(tstring):
                    color = colors[KEYWORD]
                elif keyword.issoftkeyword(tstring):
                    color = colors.get(SOFT_KEYWORD, colors[KEYWORD])
                elif tstring in BUILTINS:
                    color = colors[BUILTIN]
                elif toks[i-1].exact_type == tokenize.DOT:
                    color = colors.get(ATTRIBUTE, colors[IDENTIFIER])
                else:
                    color = colors[IDENTIFIER]
            else:
                color = colors.get(ttype, "")

            # convert (line, col) to absolute index
            start = line_starts[sline-1] + scol
            end   = line_starts[eline-1] + ecol

            # insert color and reset with seq offset
            out.insert(seq + start, color)
            seq += 1
            if ttype not in NORESET and color:
                out.insert(seq + end, colors[RESET])
                seq += 1

        return "".join(out)
    except:
        return f"{colors[SYNTAX_ERROR]}{src}{colors[RESET]}"