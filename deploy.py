"""
deploy.sh: Deploy a static site in seconds

Wanna deploy? Just:
    - choose a provider and use the 'login' command to save the API
      token (it is never sent to a server except for the actual 
      process of deployment)
    - command 'deploy now'! (defaults to netlify, though you can
      change the default)
"""

import functools
import argparse
import tempfile
import tomllib
import hashlib
import tarfile
import io
import base64
import random
import shutil
import json
import sys

from pathlib import Path

try:
    import requests
except ModuleNotFoundError:
    print("deploy.sh requires the requests module.", file=sys.stderr)
    print("install it using pip: pip install requests", file=sys.stderr)
    print("(or any package manager of your choice)", file=sys.stderr)
    sys.exit(1)

def arcprovider(tp, prov):
    def inner(name, tok, dir):
        print("making .zip... ", end="", flush=True)
        zipp = Path(tempfile.gettempdir()) / str(random.randint(1, 10000))
        zipp = Path(shutil.make_archive(zipp, tp, dir))
        print("done!")
        
        try:
            prov(name, tok, dir, zipp)
        finally:
            zipp.unlink()

    return inner

zipprovider = functools.partial(arcprovider, "zip")

BAR = chr(9608)

def progress_bar(txt, progress, total):
    """
    Based on Progress Bar Simulation, by Al Sweigart al@inventwithpython.com
    available at https://nostarch.com/big-book-small-python-programming
    """
    if len(txt) > 50:
        txt = txt[:47] + "..."

    bar = ''  # The progress bar will be a string value.
    bar += '['  # Create the left end of the progress bar.

    # Make sure that the amount of progress is between 0 and total:
    if progress > total:
        progress = total
    if progress < 0:
        progress = 0

    # Calculate the number of "bars" to display:
    bars = int((progress / total) * 30)

    bar += BAR * bars  # Add the progress bar.
    bar += ' ' * (30 - bars)  # Add empty space.
    bar += ']'  # Add the right end of the progress bar.

    # Calculate the percentage complete:
    pcent = round(progress / total * 100, 1)
    bar += ' ' + str(pcent).rjust(5) + '%'  # Add percentage.

    # Add the numbers:
    bar += ' ' + str(progress) + '/' + str(total)

    print("\r\x1b[2K" + txt.ljust(max(30, len(txt) + 5)) + bar, end="")

class providers:
    @zipprovider
    def netlify(name, tok, dir, zipp):
        site_id = None
        
        print("checking sites...")
        res = requests.get(
            "https://api.netlify.com/api/v1/sites",
            headers={
                "Authorization": f"Bearer {tok}"
            }
        )
        res.raise_for_status()
        
        if not any(x["name"] == name for x in res.json()):
            print("creating site... ", end="", flush=True)
            res = requests.post(
                "https://api.netlify.com/api/v1/sites",
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": "application/json"
                },
                json={
                    "name": name
                }
            )
            
            if res.status_code >= 400:
                print("failed!", res.text, file=sys.stderr)
                return 1
            
            site_id = res.json()["id"]
            
            print("done!")
        else:
            site, *_ = (x for x in res.json() if x["name"] == name)
            site_id = site["id"]
        
        with open(zipp, "rb") as f:
            size = Path(zipp).stat().st_size
            print("deploying... ", end="", flush=True)
            requests.post(
                f"https://api.netlify.com/api/v1/sites/{site_id}/deploys",
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": "application/zip",
                    "Content-Length": str(size),
                },
                data=f.read()
            ).raise_for_status()
            print("done!")
        
    @staticmethod
    def vercel(name, tok, dir):
        # setup global headers
        headers = {
            "Authorization": f"Bearer {tok}"
        }
        
        # look up Team ID (or fallback to Personal Account if empty)
        print("checking scope... ", end="", flush=True)
        res = requests.get("https://api.vercel.com/v2/teams", headers=headers)
        res.raise_for_status()
        teams = res.json().get("teams", [])
        
        # if teams exist, use the first one
        # otherwise omit teamId for personal account
        team_id = teams[0]["id"] if teams else None
        query_param = f"?teamId={team_id}" if team_id else ""
        print("done!")
        
        # check if project exists
        print("checking projects... ", end="", flush=True)
        search_url = f"https://api.vercel.com/v11/projects{query_param}&search={name}"
        res = requests.get(search_url, headers=headers)
        res.raise_for_status()
        projects = res.json().get("projects", [])
        print("done!")
        
        if projects:
            project_id = projects[0]["id"]
        else:
            # create project if missing
            print("creating project... ", end="", flush=True)
            create_url = f"https://api.vercel.com/v11/projects{query_param}"
            res = requests.post(
                create_url,
                headers={**headers, "Content-Type": "application/json"},
                json={"name": name}
            )
            res.raise_for_status()
            project_id = res.json()["id"]
            print("done!")
        
        # read, hash, and upload individual files
        print("processing and uploading files... ", end="", flush=True)
        files_payload = []
        
        for i, path in enumerate(Path(dir).rglob("*")):
            if path.is_file():
                with open(path, "rb") as f:
                    file_bytes = f.read()
                
                # calculate SHA-1 digest required by Vercel
                sha1_hash = hashlib.sha1(file_bytes).hexdigest()
                file_size = len(file_bytes)
                relative_path = path.relative_to(dir).as_posix()
                
                # upload the file binary content to Vercel's cache file store
                # Vercel bypasses uploading if the server already contains
                # this exact SHA-1 digest
                upload_url = f"https://api.vercel.com/v2/files{query_param}"
                upload_headers = {
                    **headers,
                    "x-vercel-digest": sha1_hash,
                    "Content-Type": "application/octet-stream"
                }
                upload_res = requests.post(upload_url, headers=upload_headers, data=file_bytes)
                upload_res.raise_for_status()
                
                # Save metadata mapping for deployment payload
                files_payload.append({
                    "file": relative_path,
                    "sha": sha1_hash,
                    "size": file_size
                })
                
                print(f"\rprocessing and uploading files... file {i}", end="")
                
        print(", done!")

        # trigger deployment with files metadata payload
        print("creating deployment... ", end="", flush=True)
        deploy_url = f"https://api.vercel.com/v13/deployments{query_param}"
        res = requests.post(
            deploy_url,
            headers={**headers, "Content-Type": "application/json"},
            json={
                "name": name,
                "project": project_id,
                "files": files_payload,
                "projectSettings": {
                    "framework": None
                }
            }
        )
        res.raise_for_status()
        deployment_data = res.json()
        print("done!")
        print()
        
        print("deployment id:", deployment_data['id'])
        print("deployment url:", f"https://{deployment_data['url']}")
        print()
        
        print("to get a better URL, open the dashboard to make this",
              "deployment a production deployment.")

    @staticmethod
    def shipstatic(name, tok, dir):
        print("collecting files... ", end="", flush=True)

        files_payload = []
        checksums = []

        import hashlib
        for path in Path(dir).rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                relpath = path.relative_to(dir).as_posix()
                with open(path, "rb") as f:
                    files_payload.append(("files[]", (relpath, f.read())))
                md5 = hashlib.md5(path.read_bytes()).hexdigest()
                checksums.append(md5)
        
        print("done!")
        print("uploading... ", end="", flush=True)

        data = {
            "checksums": json.dumps(checksums),
            "labels": '["deploysh"]',
            "via": "deploy.sh"
        }

        headers = {
            "Authorization": f"Bearer {tok}",
            
            # don't create duplicates
            "Idempotency-Key": str(hash(tuple(checksums)))
        }

        res = requests.post(
            "https://api.shipstatic.com/deployments",
            headers=headers,
            files=files_payload,
            data=data
        )
        res.raise_for_status()
        info = res.json()
        
        print("done!", info.get("url", "<no url returned>"))
        print("getting pretty domain... ", end="", flush=True)
        
        dpid, _ = info["deployment"].split(".", 1)
        del headers["Idempotency-Key"]
        
        res = requests.put(
            f"https://api.shipstatic.com/domains/{name}.shipstatic.com",
            headers=headers,
            json={"deployment": dpid}
        )
        res.raise_for_status()
        info = res.json()
        
        print("done!", "https://" + info.get("domain", "<no url returned>"))

    @staticmethod
    def surge(name, tok, dir):
        print("NOTE: deploy.sh is merely a deployment script. To do more",
              "with surge.sh, use the official CLI (npm install -g surge to",
              "install)", file=sys.stderr)
        
        
        print("packing project... ", end="", flush=True)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for path in Path(dir).rglob("*"):
                if path.is_file() and not path.name.startswith("."):
                    # Surge strips the first path segment, so add a prefix
                    arcname = f"{name}/{path.relative_to(dir).as_posix()}"
                    tar.add(path, arcname=arcname)
        buf.seek(0)
        size = len(buf.getvalue())
        file_count = sum(1 for _ in Path(dir).rglob("*") if _.is_file())

        print("done!")
        print("uploading... ", end="", flush=True)
        headers = {
            "Content-Type": "application/gzip",
            "Accept": "application/x-ndjson",
            "version": "1.0.0",
            "file-count": str(file_count),
            "project-size": str(size),
            "message": \
                f"deploy.sh deployment: {file_count} files, {size} bytes",
        }

        res = requests.put(
            f"https://surge.surge.sh/{name}.surge.sh",
            headers=headers,
            data=buf.getvalue(),
            auth=("token", tok),
            stream=True
        )

        if res.status_code >= 400:
            print("failed!", res.text, file=sys.stderr)
            return 1
        
        print("done!")

        print("now deploying...\n")
        for line in res.iter_lines(chunk_size=None):
            if not line:
                continue
            msg = json.loads(line.decode("utf-8"))
            
            match msg.get("type"):
                case "progress":
                    if "end" in msg:
                        print(f"\r\x1b[2K{msg["id"]} done, {msg["written"]
                              }/{msg["total"]}")
                    else:
                        progress_bar(f"{msg["id"]} progress", msg["written"],
                                     msg["total"])
                    
                case "cert":
                    print("certificate issued by", msg["data"]["issuer"] + ",",
                          "expires in", msg["data"]["expiresInWords"])
                    
                case "info":
                    print(f"\ndone! https://{name}.surge.sh/")
                    break        

    @staticmethod
    def ipfs_pinata(name, tok, dir):
        print("collecting files... ", end="", flush=True)

        url = "https://uploads.pinata.cloud/v3/files"
        headers = {"Authorization": f"Bearer {tok}"}
        files = []

        # Walk the directory and add each file with prefixed path
        for path in Path(dir).rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                relpath = path.relative_to(dir).as_posix()
                files.append(("file", (f"{name}/{relpath}", open(path, "rb"))))

        print("done!")
        print("uploading... ", end="", flush=True)

        payload = {
            "network": "public",
            "name": name
        }

        res = requests.post(url, headers=headers, data=payload, files=files)
        res.raise_for_status()
        info = res.json()

        print("done!")
        print()
        print("cid:", info["data"]["cid"])
        print("url:", f"https://ipfs.io/ipfs/{info["data"]['cid']}/")
        print("    ", f"https://dget.top/ipfs/{info["data"]['cid']}/")
        print("    ", f"https://4everland.io/ipfs/{info["data"]['cid']}/")
        print("    ", f"https://storry.tv/ipfs/{info["data"]['cid']}/")
        print("    ", f"ipfs://{info["data"]['cid']}/")

    @staticmethod
    def neocities(name, tok, dir):
        print("collecting files...")

        files_payload = []
        for path in Path(dir).rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                relpath = path.relative_to(dir).as_posix()
                
                if path.name.rsplit(".", 1)[-1] not in (
                    # from https://neocities.org/site_files/allowed_types
                    "apng", "asc", "atom", "avif", "bin", "cjs", "css", "csv",
                    "dae", "eot", "epub", "geojson", "gif", "glb", "glsl",
                    "gltf", "gpg", "htm", "html", "ico", "jpeg", "jpg", "js",
                    "json", "jxl", "key", "kml", "knowl", "less", "manifest",
                    "map", "markdown", "md", "mf", "mid", "midi", "mjs", "mtl",
                    "obj", "opml", "osdx", "otf", "pdf", "pgp", "pls", "png",
                    "py", "rdf", "resolveHandle", "rss", "sass", "scss", "sf2",
                    "svg", "text", "toml", "ts", "tsv", "ttf", "txt", "webapp",
                    "webmanifest", "webp", "woff", "woff2", "xcf", "xml", "xsl",
                    "xslt", "yaml", "yml"
                ):
                    print("skipping", relpath + ":", "unsupported filetype")
                else:
                    files_payload.append((relpath, open(path, "rb")))

        print("done collecting files!")
        print("uploading... ", end="", flush=True)

        res = requests.post(
            "https://neocities.org/api/upload",
            headers={
                "Authorization": f"Bearer {tok}"
            },
            files=files_payload
        )
        res.raise_for_status()
        print("done!")
        print(f"site url: https://{name}.neocities.org/")

PROVIDERS = list(filter(lambda x: not x.startswith("_"), dir(providers)))

commands = {}

class _basecommand_meta(type):
    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if cls.__name__.startswith("_"): return
        
        commands[cls.__name__] = cls()
        return

class _basecommand(metaclass=_basecommand_meta):    
    def init(self, subp):
        pass
        
    def run(self, args):
        raise NotImplementedError
#
class login(_basecommand):
    """
    Configure tokens.
    """
    
    @staticmethod
    def load():
        path = Path.home() / ".dontdeploysecrets.json"
        
        if not path.is_file():
            data = {p: None for p in PROVIDERS}
            with open(path, "w") as f:
                json.dump(data, f)
            return data
        else:
            with open(path) as f:
                return {
                    k: v for k, v in json.load(f).items() if k in PROVIDERS
                }

    @staticmethod
    def save(data):
        with open(Path.home() / ".dontdeploysecrets.json", "w") as f:
            json.dump(data, f)

    def init(self, subp):
        subp.add_argument("provider", choices=PROVIDERS, help="Provider name.")
        subp.add_argument("tokstring", help="Access token.")
    
    def run(self, args):
        data = login.load()
        data[args.provider] = args.tokstring
        login.save(data)

def confload():
    path = Path.home() / ".deploy.toml"
    
    if not path.is_file():
        data = {
            "defaults": {
                "provider": "netlify"
            }
        }
        return data
    else:
        with open(path, "rb") as f:
            return tomllib.load(f)

class logout(_basecommand):
    """
    Remove a stored token for a provider.
    """

    def init(self, subp):
        subp.add_argument("provider", choices=PROVIDERS, help="Provider name.")

    def run(self, args):
        data = login.load()
        if data.get(args.provider):
            data[args.provider] = None
            login.save(data)
            print(f"logged out: {args.provider}.")
        else:
            print(f"not logged in: {args.provider}.")

class now(_basecommand):
    """
    Deploy NOW!
    
    The default provider is by default "netlify". You can change this in two
    ways. The first is to use the -p option to change it for one command.
    
    The second is to create a ~/.deploy.toml file, and set defaults.provider
    to your desired provider.
    """
    
    def init(self, subp):
        conf = confload()
        
        subp.add_argument(
            "-C", "--dir", default=".", type=Path, 
            help="Which folder to deploy."
        )
        subp.add_argument(
            "-n", "--name", default=None, help="Name of the site."
        )
        subp.add_argument(
            "-p", "--provider", choices=PROVIDERS,
            default=confload()["defaults"]["provider"],
            help="Provider name."
        )
    
    def run(self, args):
        args.dir = args.dir.resolve()
        name = args.name or args.dir.name
        tok = login.load()[args.provider]
        
        print("using provider:", args.provider)
        print()
        
        try:
            return getattr(providers, args.provider)(name, tok, args.dir)
        except requests.exceptions.HTTPError as e:
            raise ValueError(f"{e} ({e.response.text})")
#
class whoami(_basecommand):
    """Show which providers are configured."""
    def run(self, args):
        data = login.load()
        
        data["netlify (default)"] = data["netlify"]
        del data["netlify"]
        
        data = dict(sorted(data.items()))
        
        pad = len(max(data.keys(), key=len)) + 4
        
        for provider, tok in data.items():
            status = "logged in" if tok else "not logged in"
            print(f"{provider.rjust(pad)}: {status}")

def main():
    parser = argparse.ArgumentParser(
        prog="deploy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__
    )
    sub = parser.add_subparsers(dest="command", required=True)
    
    for k, v in commands.items():
        v.init(sub.add_parser(
            k, help=v.__doc__.strip().split("\n")[0], 
            description=v.__doc__
        ))
    
    args = parser.parse_args()
    
    return commands[args.command].run(args)
#
if __name__ == "__main__":
    sys.exit(main())