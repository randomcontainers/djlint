"""Collect the license files that three locked wheels leave out.

Usage: bundled-licenses.py

jsbeautifier and cssbeautifier are built from the python/ directory of the
js-beautify repository, and its license file sits at the root of that
repository, so neither their wheels nor their source releases contain it.
For each of the two this reads the version pinned in requirements.lock,
checks that the locked wheel still has no license file, resolves the tag
v<version> of js-beautify to a commit, checks that the package's
__init__.py and __version__.py at that commit match the wheel, and writes
LICENSE from that commit and a SOURCES file to licenses/<name>-<version>/.

PyYAML's Linux wheels link a static build of libyaml into their extension
module but include PyYAML's own license only. This reads the PyYAML version
from requirements.lock, checks in PyYAML's source release that libyaml is
still built as a static library, reads the libyaml tag the wheels are built
from in PyYAML's CI workflow at the same tag, checks that the extension
module of each Linux wheel the images install reports that libyaml version,
checks that the license file in libyaml's release archive matches the one at
that tag in libyaml's repository, and writes the file and the URLs to
licenses/pyyaml-<version>/bundled/.

Run it whenever requirements.lock changes the version of jsbeautifier,
cssbeautifier or PyYAML.
"""

import hashlib
import io
import json
import pathlib
import re
import shutil
import sys
import tarfile
import textwrap
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

BEAUTIFIERS = ("jsbeautifier", "cssbeautifier")
JSB_REPO = "https://github.com/beautifier/js-beautify"
JSB_REF = "https://api.github.com/repos/beautifier/js-beautify/git/ref/tags/v{version}"
JSB_TAG = "https://api.github.com/repos/beautifier/js-beautify/git/tags/{sha}"
JSB_FILE = "https://raw.githubusercontent.com/beautifier/js-beautify/{commit}/{path}"
# Lines the MIT license text must still contain, so that a change of terms
# is looked at before it reaches the images.
JSB_LICENSE_LINES = (
    "The MIT License (MIT)",
    "Permission is hereby granted, free of charge, to any person obtaining a copy",
)

PYYAML_WORKFLOW = "https://raw.githubusercontent.com/yaml/pyyaml/{version}/.github/workflows/ci.yaml"
LIBYAML_REPO = "https://github.com/yaml/libyaml"
LIBYAML_ARCHIVE = "https://github.com/yaml/libyaml/releases/download/{ref}/yaml-{ref}.tar.gz"
LIBYAML_FILE = "https://raw.githubusercontent.com/yaml/libyaml/{ref}/{name}"
LIBYAML_LICENSE_FILES = ["License"]

# The PyYAML wheels installed on Ubuntu and Alpine.
PLATFORMS = (
    r"manylinux\S*_x86_64",
    r"manylinux\S*_aarch64",
    r"musllinux_\d+_\d+_x86_64",
    r"musllinux_\d+_\d+_aarch64",
)

# File names that count as license files in a wheel's .dist-info directory.
LICENSE_NAMES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def fetch_checked(item):
    data = fetch(item["url"])
    if hashlib.sha256(data).hexdigest() != item["digests"]["sha256"]:
        sys.exit(f"{item['url']} does not match its SHA-256 on PyPI")
    return data


def read(tar, path):
    try:
        return tar.extractfile(path).read()
    except KeyError:
        sys.exit(f"{path} is not in its archive")


def locked(lock, name):
    pattern = rf"^{re.escape(name)}==([^\s;]+)[^\\\n]*?((?:\s*\\\n\s*--hash=sha256:[0-9a-f]{{64}})+)"
    match = re.search(pattern, lock, re.M | re.I)
    if not match:
        sys.exit(f"requirements.lock does not pin {name}")
    return match.group(1), set(re.findall(r"sha256:([0-9a-f]{64})", match.group(2)))


def has_license_file(wheel):
    for path in wheel.namelist():
        parts = path.split("/")
        if len(parts) < 2 or not parts[0].endswith(".dist-info"):
            continue
        if parts[1] == "licenses" or parts[-1].upper().startswith(LICENSE_NAMES):
            return True
    return False


def tag_commit(version):
    ref = json.loads(fetch(JSB_REF.format(version=version)))["object"]
    if ref["type"] == "tag":
        ref = json.loads(fetch(JSB_TAG.format(sha=ref["sha"])))["object"]
    if ref["type"] != "commit" or not re.fullmatch(r"[0-9a-f]{40}", ref["sha"]):
        sys.exit(f"js-beautify tag v{version} does not point to a commit")
    return ref["sha"]


def beautifier_files(name, version, hashes):
    release = json.loads(fetch(f"https://pypi.org/pypi/{name}/{version}/json"))
    wheels = [f for f in release["urls"] if f["packagetype"] == "bdist_wheel" and f["digests"]["sha256"] in hashes]
    if len(wheels) != 1:
        sys.exit(f"expected one wheel of {name} {version} with a hash listed in requirements.lock, found {len(wheels)}")
    with zipfile.ZipFile(io.BytesIO(fetch_checked(wheels[0]))) as wheel:
        if has_license_file(wheel):
            print(f"{wheels[0]['filename']} has a license file, so {name} {version} needs no copy")
            return None
        sources = {path: wheel.read(f"{name}/{path}") for path in ("__init__.py", "__version__.py")}

    commit = tag_commit(version)
    for path, data in sources.items():
        if fetch(JSB_FILE.format(commit=commit, path=f"python/{name}/{path}")) != data:
            sys.exit(f"{name}/{path} in the {name} {version} wheel differs from js-beautify v{version}")
    text = fetch(JSB_FILE.format(commit=commit, path="LICENSE"))
    missing = [line for line in JSB_LICENSE_LINES if line not in text.decode()]
    if missing:
        sys.exit(f"LICENSE at js-beautify v{version} no longer contains: {'; '.join(missing)}")

    intro = (
        f"{name} {version} is built from the python/ directory of the js-beautify "
        "repository. Its wheel and source release on PyPI leave out the repository's "
        "license file, the MIT license. LICENSE is that file at the tag below, whose "
        f"python/{name}/__init__.py and __version__.py match the wheel's."
    )
    sources = [textwrap.fill(intro, 76), "", f"js-beautify v{version}", f"  {JSB_REPO}/tree/v{version}"]
    sources.append(f"  commit {commit}")
    return {"LICENSE": text, "SOURCES": ("\n".join(sources) + "\n").encode()}


def workflow_default(text, variable):
    """The fallback value of `VARIABLE: ${{ inputs.x || 'value' }}` in the workflow's env."""
    match = re.search(rf"^\s*{variable}:.*\|\|\s*'([^']+)'", text, re.M)
    if not match:
        sys.exit(f"PyYAML's CI workflow does not set {variable}")
    return match.group(1)


def pyyaml_files(lock, pyyaml):
    match = re.search(r"--python-version 3\.(\d+)", lock)
    if not match:
        sys.exit("requirements.lock does not name the Python version it resolves for")
    python = f"cp3{match.group(1)}"

    release = json.loads(fetch(f"https://pypi.org/pypi/PyYAML/{pyyaml}/json"))
    sdists = [f for f in release["urls"] if f["packagetype"] == "sdist"]
    if len(sdists) != 1:
        sys.exit(f"PyYAML {pyyaml} has {len(sdists)} source releases on PyPI")
    sdist = sdists[0]
    with tarfile.open(fileobj=io.BytesIO(fetch_checked(sdist))) as tar:
        script = read(tar, f"pyyaml-{pyyaml}/packaging/build/libyaml.sh").decode()
    if "--enable-shared=no" not in script:
        sys.exit(f"PyYAML {pyyaml} packaging/build/libyaml.sh no longer builds a static libyaml")

    workflow = fetch(PYYAML_WORKFLOW.format(version=pyyaml)).decode()
    repo = workflow_default(workflow, "LIBYAML_REPO")
    if repo != LIBYAML_REPO:
        sys.exit(f"PyYAML {pyyaml} builds libyaml from {repo}, not {LIBYAML_REPO}")
    ref = workflow_default(workflow, "LIBYAML_REF")
    if not re.fullmatch(r"\d+\.\d+\.\d+", ref):
        sys.exit(f"PyYAML {pyyaml} builds libyaml at {ref!r}, which is not a release tag")

    # libyaml's yaml_get_version_string() returns this string, so every
    # extension module linked with that release contains it.
    marker = re.compile(rb"(?<![0-9.])" + re.escape(ref.encode()) + rb"\x00")
    for platform in PLATFORMS:
        pattern = re.compile(rf"pyyaml-{re.escape(pyyaml)}-{python}-{python}-{platform}\.whl", re.I)
        wheels = [f for f in release["urls"] if pattern.fullmatch(f["filename"])]
        if len(wheels) != 1:
            sys.exit(f"PyYAML {pyyaml} has {len(wheels)} {python} wheels for {platform}")
        with zipfile.ZipFile(io.BytesIO(fetch_checked(wheels[0]))) as wheel:
            modules = [n for n in wheel.namelist() if re.fullmatch(r"yaml/_yaml\.[^/]*\.so", n)]
            if len(modules) != 1 or not marker.search(wheel.read(modules[0])):
                sys.exit(f"{wheels[0]['filename']} does not contain libyaml {ref}")

    url = LIBYAML_ARCHIVE.format(ref=ref)
    data = fetch(url)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        texts = {name: read(tar, f"yaml-{ref}/{name}") for name in LIBYAML_LICENSE_FILES}
    # The release archive has no published checksum, so compare its license
    # files with the ones at the tag the wheels are built from.
    for name, text in texts.items():
        if fetch(LIBYAML_FILE.format(ref=ref, name=name)) != text:
            sys.exit(f"{name} in {url} differs from {name} at libyaml tag {ref}")

    intro = (
        f"PyYAML {pyyaml} links a static build of libyaml into its extension module "
        "yaml._yaml. Its Linux wheels are built by PyYAML's CI workflow, which checks "
        f"out {LIBYAML_REPO} at the tag {ref} and configures it with "
        "--enable-shared=no (packaging/build/libyaml.sh in the PyYAML source release). "
        "The archive below is libyaml's release of that tag. libyaml is licensed under "
        "the MIT license; its license file is in the libyaml directory."
    )
    sources = [textwrap.fill(intro, 76), "", f"PyYAML {pyyaml}", f"  {sdist['url']}"]
    sources.append(f"  sha256:{sdist['digests']['sha256']}")
    sources += [f"libyaml {ref}", f"  {url}", f"  sha256:{hashlib.sha256(data).hexdigest()}"]

    files = {f"bundled/libyaml/{name}": text for name, text in texts.items()}
    files["bundled/SOURCES"] = ("\n".join(sources) + "\n").encode()
    return files


def main():
    lock = (ROOT / "requirements.lock").read_text()
    collected = {}
    for name in BEAUTIFIERS:
        version, hashes = locked(lock, name)
        collected[(name, version)] = beautifier_files(name, version, hashes)
    pyyaml, _ = locked(lock, "pyyaml")
    collected[("pyyaml", pyyaml)] = pyyaml_files(lock, pyyaml)

    base = ROOT / "licenses"
    for name, version in collected:
        for old in base.glob(f"{name}-*"):
            if old.is_dir():
                shutil.rmtree(old)
    for (name, version), files in collected.items():
        if not files:
            continue
        out = base / f"{name}-{version}"
        for filename, text in files.items():
            target = out / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text)
            print(f"wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
