import pathlib
import requests
import zipfile
import subprocess

BASE_DIR = pathlib.Path.cwd()
FILES_DIR = BASE_DIR / "FILES"
SED_FILE = BASE_DIR / "base.sed"

def download_and_extract_embed(version: str, arch: str = "amd64") -> None:
    """Download and extract the Windows embed distribution into FILES_DIR."""
    url = f"https://www.python.org/ftp/python/{version}/python-{version}-embed-{arch}.zip"
    target = BASE_DIR / f"python-{version}-embed-{arch}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {url}...")
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    with open(target, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    print("Extracting embed distribution...")
    with zipfile.ZipFile(target, "r") as zf:
        zf.extractall(FILES_DIR)

def build_sed(output_name: str, pyz_file: pathlib.Path) -> None:
    """Generate a SED file for IExpress that bundles embed + pyz."""
    files = list(FILES_DIR.glob("*"))
    iex_base = [
        "[Version]",
        "Class=IEXPRESS",
        "SEDVersion=3",
        "[Options]",
        "PackagePurpose=Install",
        "ShowInstallProgramWindow=1",
        "HideExtractAnimation=1",
        "UseLongFileName=1",
        "InsideCompressed=0",
        "CAB_FixedSize=0",
        "CAB_ResvCodeSigning=0",
        "RebootMode=I",
        f"TargetName={output_name}.exe",
        "FriendlyName=PythonApp",
        f"AppLaunched=python.exe {pyz_file.name}",
        "PostInstallCmd=",
        "SourceFiles=SourceFiles",
        "[Strings]",
    ]

    for idx, f in enumerate(files):
        iex_base.append(f'FILE{idx}="{f.name}"')

    iex_base.append("[SourceFiles]")
    iex_base.append(f'SourceFiles0="{FILES_DIR}"')
    iex_base.append("[SourceFiles0]")
    for idx in range(len(files)):
        iex_base.append(f"%FILE{idx}%=")

    SED_FILE.write_text("\n".join(iex_base), encoding="utf-8")

def run_iexpress():
    subprocess.run(["iexpress", "/N", str(SED_FILE)], check=True)

def main():
    version = input("Python version (e.g. 3.15.0rc2): ").strip()
    pyz_name = input("Path to your .pyz file: ").strip()
    output_name = input("Output EXE name (without .exe): ").strip()

    pyz_file = pathlib.Path(pyz_name)
    if not pyz_file.exists():
        raise FileNotFoundError(f"{pyz_file} not found")

    target_pyz = FILES_DIR / pyz_file.name
    target_pyz.parent.mkdir(parents=True, exist_ok=True)
    target_pyz.write_bytes(pyz_file.read_bytes())

    download_and_extract_embed(version)

    build_sed(output_name, target_pyz)
    # run_iexpress()

    # SED_FILE.unlink(missing_ok=True)

if __name__ == "__main__":
    main()