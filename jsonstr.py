ESC_TABLE = {
    **{
        x: rf"\u{hex(ord(x))[2:].rjust(4, '0')}"
        for x in map(chr, range(0, 0x20))
    },
    "\b": r"\b",
    "\f": r"\f",
    "\n": r"\n",
    "\r": r"\r",
    "\t": r"\t",
    "\\": "\\\\",
    '"': "\\\"",
    "/": r"\/",  # optional
}

def dumps(obj, *, indent=0, _prvidt=0, replacer=None):
    if indent:
        indents = "\n" + (" " * indent)
        endidnt = "\n" + (" " * _prvidt)
        pad = " "
    else:
        indents = pad = endidnt = ""
    
    if isinstance(obj, str):
        return '"' + "".join(ESC_TABLE.get(x, x) for x in obj) + '"'
    elif obj is None:
        return "null"
    elif isinstance(obj, (bool, int, float)):
        return str(obj).lower()
    elif isinstance(obj, list):
        return "[" + indents + ("," + indents).join(
            dumps(x, indent=indent*2, _prvidt=indent, replacer=replacer)
            for x in obj
        ) + endidnt + "]"
    elif isinstance(obj, dict):
        if not all(isinstance(k, str) for k in obj.keys()):
            raise ValueError("all keys must be strings")
        
        return "{" + indents + ("," + indents).join(
            dumps(k, indent=indent*2, _prvidt=indent, replacer=replacer) \
            + ":" + pad + \
            dumps(v, indent=indent*2, _prvidt=indent, replacer=replacer)
            for k, v in obj.items()
        ) + endidnt + "}"
    else:
        if replacer:
            x = replacer(obj)
            if not isinstance(x, (
                str, type(None), bool, int, float, list, dict
            )):
                raise TypeError(
                    f"replacer returned unsupported type {type(obj)}"
                )
            
            return dumps(x, indent=indent, _prvidt=_prvidt)
            
        raise TypeError(f"unsupported object type {type(obj)}")