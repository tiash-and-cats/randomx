import shlex
import getopt
import hack
import leetspeak
import sys
import time
from utils import hackerprint

env = {"PATH": "/bin:/usr/bin:/usr/local/bin", "SHELL": "Do you really need to know?", "0": "/bin/sh", "HOME": "/root"}

fs = {
    "": {
        "type": "folder",
        "subfs": {
            "bin": {
                "type": "folder",
                "subfs": {
                    "sh": {
                        "type": "file",
                        "content": 'eÈÝãV\x8bº\x03\xa0äM#ãöéÝ¤\x02ô«¨\x9c\x8b\'p<À\x81?ì}YôJ\x10/Æ\x8d¨Új\x17¤Úå\x14õx°½W\x85i\x1a}\x13ÿ\x94V²b2\x0cñ\x90/0-\x10Ï\x1d\x00Ó\x8aónË1\x13\x81äõÔ¢\t\x92«å\x12\x864\x14Õ\x90\x1fÀ5J\x92/Õy;<Ýp5\x93ð-\x8d£\x98\x9fý¦\x87\xadÎÅõuV\x80\x1dM\x8agæ^»\x8e#ã\x0bG\x1e$º8h\\\x8aÁ²È\x85O\xa0%ø`í_»0Þ\'wt¶,±"?Ôä¡~q\x9br\x9bÅ\x99+~r\x12ê¡\x1f,©\n\x01Zµ\x9f}XCKñè¶¶CÝ2=\x8eÂ·\x15\x0bù\x1b5wv\x02õ\x1couTo¼\x02\x84rû°]¶Àn\x89g\x1a²í\x90O\x7f~7N1\x13\x8c¼rEb=xñWüìÒ\x05\x1aô\x17à\x13Ü\x94ñ}Å^\x1alÜ«ô¡%L~µE§KS~\x90Øz\x01\x06\x15¢\x11¿ê\x05\x13Ú\x1d\x18"\x1fJ\x16Ð\x82[\x14\x97ô<5Þ8\x90Æò\x0eÎ\x9cI}Øâ+¸3\x1aR\x03pÐöW¨,à\x08kéÃ½5c`\x90*ÐgCQªü\x00\x9bs@åUC\x04¡K\x11_,¨F{dG3¼\x81±ÞèHú-¼aÚ°h\xadËø50ôcH-\x14\x84$ê6\x13Áø±3=|\x98µÿ«ãÚ\x82\x07À*æ¤&(?7Õ\x8bã\x9d\x10\x890/·`\tAÕXg+\x0eUYEÐ.\x98·N1D\x1cP%E\x93\x87¯ÎL<NÏ$\x12ÙZ}K?Ón{xF\x88Jrr\x03\x04*\x90\x08¦³\x98<Õ£]7æ\x8f±6s*é\x08\x7fY\x14ºç9\x0b:öµ$õaÎ~\x9b\x1aO\x1dÐ:äXú\x13(Êö§=ò\x8bS\x9fYLÊo,2«æÊ\\\x90s\x06¨[¦ú\x83R\x9e\x9eÆMk½G^³\x89ÅH\x0eeI\'#/è#\x1dßâ}-¢áå¶Ó\x96ÃÖ£³d$\x9bá9·\x19 ×\x00Ë\x18Vr\x0ezÝV³Ç\x9a\'(8vñP\x16pP¦`ÂCD\x86\x11¯De\x19=\x86vé)\x9d@^Z\x1cw\x031Z\x18ì?Î®ô\x06\x88t\x00h¸,×\x83ðÎ¸AB¤\'n!ß\x15"\x84\xadO\x9c\x05\x94\x04yPfÁé²¨L\x94V\x9d\x8a\x91~üG3\x14I§ËÇO-\x82\\F\x83\xa0ø\x1b\x8dT£ú\x1fæ\xad¯[øuõWL\x1c´%;?ÆÜk¨Û0´Ís\x0e1J{Ô4\x10ù¹P\xad^×ÃJÿø³\x05»R\x82_~{0\x16\x8eQX«G±Üö\xa0Ç\x16ß%üÙ\x97\x9b!\x1dY3Í£\x1b\x18âéà\x89C~´\x7fsÄJAy0\x813Uô¯\x1auYg÷\x7fÈYù\x02æòÿL\x1eêeò\x96¦\x90\x83\x88«^8\x0bßÛ1Ù\x877©º4Q¥+uÉÈF\x074n¶\x8a6Q\x81:è\t»\x1cA¾wåP\x07t&\x844~í¥\xad\x99~\x02ý\x17ú\x8aæð\rX¢R(\x18\x99ÂÙVEÐ\x9d¬¶\'\x9c\x1f#&Ë(whÓ"\x7fóJ·bá"Þ\x07è\x10m¾\x16\x0b\x17v3Öä\x99\x92ØðºøFx\x84QÑ!\x05<\x10×\x03þ6DôÕ\x18\x9e|S\x0f?rPÛ÷ÂB\x89çá\x8b\x18H~\x1cÂ\x82Ã¿\x96ª\x94þ\xa0\x0e!e\x9b\xa0ÂË4\x8bÈ0ëu\x07\x89§dSêÔ¡¾0þ'
                    },
                    "cat": {
                        "type": "file",
                        "content": '2\x04$É\'%â#6îÒýR#´µÕ\x0bû\x89\x92vo{ü1;\x86\x92¿4\xad²]p\x04v\\Ù=)\x0bë¯^ª"I¢\x82Æ\x9a]Ó\x98\x06Üc§\x19o\x94B\x98ä`h±±\x90\x03Ôü\x9b\x80æU4"â\x99\x9a×\x92\x9b\tH&»\x80Æ\x0cg=iæÍ£\tMÖñ{¢ò!å\x1eL\t4£ÆµÀ\x0eÁ2\x10oüiÉ\x11öáë_%°I\x80\x02Ì{v·á$ÒJ9Þ\x9a·\tn©æßè\x1c\x8a\x86L°^Ç\xadnc, ðôB\\·Þ¶\x9aþº,Y:Mªó4\tP\x95/:Òu]ÍG|K\x90`Æ\x1ee$Í\x16ÁqþÞSËå^¼]\x8cb\x01y*\x06S¢\x95\x0e§\x13\x038Õ#º \x1e\x08\x88íH\x8eNË\x80sÅ\'\x1d¹§å#Ë|3hÌ\x10S\x9cw×·\x17sìÃ·4\x0fÃ8ðâ\x0c;cZ¯2Lo\x0f\x9fp\x13\x85\x1dÐ\xadþÕ\x0e®LE^Ôâ7A#\x85Ô\xa0¤!\xa0µnãº\x9eB2½Ý¨\xa0w\x8edß`,\x8e.Í)\x16Ay\x02Ë.Ù\x9f\x04d ü2ÌùñKòL\x99îX5@ \x02TÄ\x04Q±çz\x85ÿ.ÈzFa@kX\x1bE7\x95ç\x8fÔÅ\x9c³\x1c\x1b´\x8ea°\x88\x07\x8as\x8c\x05Ç¦\x00Ã¨\\\x96¸\xa0ÙßÝ\x11ß\x07\x8d\x9e\xad@}\x81PY®¤A\x85\x17\\î«ÝP±es?ÙÍ\x99Ö\x13¶\\ßÜ~ÔmçÅ\x19\x18\x1c\x8dñ\x1bÒXø\x981HXN\x10Ö¦Þ\x9c&ò|hé\x87Æï!ä)\x87\x86nS\x90Û"!ó\x915\x1cÀÃe\x15_ÅÌn\x8d$îÀòß8\x1b \x0bÓk'
                    }
                }
            },
            "usr": {
                "type": "folder",
                "subfs": {
                    "bin": {"type": "folder", "subfs": {}},
                    "local": {
                        "type": "folder",
                        "subfs": {
                            "bin": {"type": "folder", "subfs": {}},
                        }
                    }
                }
            },
            "root": {
                "type": "folder",
                "subfs": {
                    "hack.sh": {
                        "type": "file",
                        "content": """#!/bin/sh
# Do you really need to know what's in the script?
# What's in the script are trade secrets, son. You don't need to know.
#                                                      - signed, Chief Hacker"""
                    },
                    "leetspeak.sh": {
                        "type": "file",
                        "content": """#!/bin/sh
# What's in this script are EVEN BIGGER trade secrets than ./hack.sh. You REALLY don't need to know.
#                                                      - signed, Chief Hacker"""
                    }
                }
            }
        }
    }
}

current_dir = ["", "root"]

def normalize_path(path_str):
    global current_dir

    # Normalize slashes and split
    parts = [p for p in path_str.split("/") if p]

    # Absolute path? Start fresh
    if parts and parts[0] == "":
        resolved = parts[1:]
    else:
        resolved = current_dir.copy()

    for part in parts:
        if part == ".":
            continue
        elif part == "..":
            if len(resolved) > 1:
                resolved.pop()
        else:
            resolved.append(part)

    return resolved

def resolve_path(path_list):
    node = fs
    for part in path_list:
        if not node:
            return None
        if part in node:
            node = node[part]
        elif isinstance(node, dict) and "subfs" in node and part in node["subfs"]:
            node = node["subfs"][part]
        else:
            return None
    return node

def parse_cmd(cmd):
    if cmd.find("#") > -1:
        cmd = cmd[:cmd.find("#")]
    cmd = shlex.split(cmd)
    cmd = [x if not x.startswith("$") else env.get(x[1:], "") for x in cmd]
    return cmd

def hack_sh(args):
    usage = lambda: print("Usage: hack -s <ip>")
    try:
        opts, args = getopt.getopt(args, "s:")
    except getopt.GetoptError as e:
        usage()
        print("Error:", e)
        return
    opts = dict(opts)
    if "-s" not in opts:
        usage()
        return
    ip = opts["-s"]
    print(f"Connecting to {ip}...")
    time.sleep(1)
    if not ip == "124.23.76.135":
        print("Could not find a security vulnerability on IP", opts["-s"])
        return
    print("Exploiting buffer overflow...")
    time.sleep(2)
    if hack.hack() == "Victory":
        hackerprint("""
\tCongrats! You did it!
\tThe pros can take this from here. Well done!

\t\t\t\t\tsigned, Chief Hacker
""")
        sys.exit(0)

def leetspeak_sh(args):
    try:
        opts, args = getopt.getopt(args, "m:")
    except getopt.GetoptError as e:
        print("Error:", e)
        return
    opts = dict(opts)
    leetspeak.main(opts)

def exec_cmd(cmd):
    global current_dir
    if not cmd:
        return
    if cmd[0] == "sh":
        shell()
    elif cmd[0] == "cat":
        print(resolve_path(normalize_path(cmd[1]))["content"])
    elif cmd[0] == "cd":
        current_dir = normalize_path(cmd[1])
    elif cmd[0] == "./hack.sh" and current_dir == ["", "root"]:
        hack_sh(cmd[1:])
    elif cmd[0] == "./leetspeak.sh" and current_dir == ["", "root"]:
        leetspeak_sh(cmd[1:])
    elif cmd[0] == "ls":
        print(*resolve_path(current_dir)["subfs"].keys(), sep="\n")
    elif cmd[0] == "echo":
        print(*cmd[1:])
    elif cmd[0] == "exit":
        return -1
#
def shell():
    while True:
        cmd = input(f"\x1b[32mroot@localhost\x1b[0m:\x1b[33m{'/'.join(current_dir)}\x1b[0m$ ")
        if exec_cmd(parse_cmd(cmd)) == -1:
            return -1