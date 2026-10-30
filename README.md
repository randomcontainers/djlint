# djlint

Container images with [djLint](https://djlint.com/), the linter and formatter for HTML templates written for Django, Jinja, Nunjucks, Twig, Handlebars, Liquid, Go templates and other template languages. djLint is installed from PyPI into a virtual environment on Ubuntu or Alpine. The images are rebuilt when djLint publishes a release and when the base image changes, for `linux/amd64` and `linux/arm64`.

This is an unofficial build, not affiliated with or endorsed by the djLint project. Report problems with the image in this repository and problems with djLint itself in the [djLint issue tracker](https://github.com/djlint/djLint/issues).

## Quick start

Lint every `.html` file in the current directory and below:

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" ghcr.io/randomcontainers/djlint .
```

Without a profile, djLint runs only its HTML rules, whose codes start with `H`. Name the template language to add the rules for template tags, such as `T001` for `{{x}}` without spaces:

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" \
  ghcr.io/randomcontainers/djlint --profile=django templates
```

The profiles are `django`, `jinja`, `nunjucks`, `handlebars`, `liquid`, `golang`, `angular`, `tera`, `askama` and `html`. `-e` checks files with another extension, such as `-e html.j2` or `-e jinja`.

`--check` prints a diff for each template the formatter would change, without changing it. `--reformat` rewrites them in place:

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" ghcr.io/randomcontainers/djlint --check .
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" ghcr.io/randomcontainers/djlint --reformat .
```

Add `--format-css` and `--format-js` to also format the contents of `<style>` and `<script>` tags.

djLint exits with 1 when it finds a problem or a template that needs formatting, with 2 on a usage error, on a failure such as a file that is not UTF-8, or when the paths match no files, and with 0 otherwise. `--warn` reports the problems and exits with 0.

Format a template from standard input, without mounting anything. The result goes to standard output:

```sh
docker run --rm -i ghcr.io/randomcontainers/djlint - --reformat < page.html > formatted.html
```

The output has colors only when the container has a terminal (`docker run -t`). In a GitHub Actions workflow, pass `--github-output` to print the findings as workflow commands, which show up as annotations. djLint picks that format by itself when `GITHUB_ACTIONS` is set, and `docker run` does not pass it into the container unless you add `-e GITHUB_ACTIONS`. `--sarif` prints the findings as SARIF 2.1.0 for code scanning:

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" \
  ghcr.io/randomcontainers/djlint --sarif . > djlint.sarif
```

## Configuration

djLint looks for its settings starting at the first path you pass and going up to `/`. It stops at the first directory that holds `.git`, `.hg`, `pyproject.toml`, `djlint.toml`, `.djlint.toml` or `.djlintrc`, and reads the `[tool.djlint]` table of `pyproject.toml` there, or else `djlint.toml` or `.djlint.toml`, or else `.djlintrc`, which is JSON. Directories above the mount are not in the container, so mount the directory that holds the file, usually the root of your repository. `--configuration path/to/file`, with the file under `/work`, adds settings from another file; the project's own file wins where both set the same thing, unless you also pass `--prefer-configuration`.

The [djLint documentation](https://djlint.com/docs/configuration/) lists the settings, such as `profile`, `ignore`, `indent` and `max_line_length`. In the project root, an `.editorconfig` section for HTML files with `indent_size` or `max_line_length` sets the defaults for those two, and `--use-gitignore` skips the paths that `.gitignore` matches.

## What is in the image

- `djlint` in `/usr/local/bin`, linked from a virtual environment in `/usr/local/lib/djlint` that uses the distro's `python3`.
- djLint's wheels for Linux, which upstream compiles with [mypyc](https://mypyc.readthedocs.io/). The compiled code of every djLint module except `__main__`, together with mypyc's runtime, is one shared library in the virtual environment's `site-packages` directory, named `<hash>__mypyc.cpython-*.so`. The `.so` files in `site-packages/djlint/` are small modules that load it, and the `.py` files next to them are the source it was compiled from.
- Its dependencies click, regex, PyYAML, pathspec and json5; jsbeautifier and cssbeautifier, which format CSS and JavaScript; and EditorConfig, which they use. All are installed from `requirements.lock`.
- pip, which stays in the virtual environment.

## Default or slim

djLint's default image adds no other tools, so `latest` and `slim` are the same image, with the contents listed above. Use `latest` to run it and the `slim` tags as a base for your own image.

## Tags

`<version>` is a djLint release such as `1.47.0`. `<minor>` and `<major>` are its shorter forms, `1.47` and `1`, and follow the newest release in that series. Each row lists the default tag and its `slim` twin, which point to the same image.

| Tags | Base |
|---|---|
| `latest`, `slim` | Ubuntu |
| `<version>`, `<version>-slim` | Ubuntu |
| `<minor>`, `<minor>-slim`, `<major>`, `<major>-slim` | Ubuntu |
| `ubuntu`, `slim-ubuntu` | Ubuntu |
| `<version>-ubuntu`, `<version>-slim-ubuntu` | Ubuntu |
| `<minor>-ubuntu`, `<minor>-slim-ubuntu`, `<major>-ubuntu`, `<major>-slim-ubuntu` | Ubuntu |
| `<version>-ubuntu26.04`, `<version>-slim-ubuntu26.04` | Ubuntu 26.04 |
| `alpine`, `slim-alpine` | Alpine |
| `<version>-alpine`, `<version>-slim-alpine` | Alpine |
| `<minor>-alpine`, `<minor>-slim-alpine`, `<major>-alpine`, `<major>-slim-alpine` | Alpine |
| `<version>-alpine3.24`, `<version>-slim-alpine3.24` | Alpine 3.24 |

The images are currently built on Ubuntu 26.04 and Alpine 3.24. Tags without a distro version move to the next distro release when the project does; tags ending in `ubuntu26.04` or `alpine3.24` stay on that release and are no longer rebuilt once the project moves to the next one. Every tag of the current djLint version, including the exact version, is rebuilt in place (see [Updates](#updates)), so pin a digest when you need the same bytes every time.

## Platforms

`linux/amd64` and `linux/arm64`, for both Ubuntu and Alpine. Both are built natively on GitHub-hosted runners, without emulation. The same `requirements.lock` is installed on all four combinations of distro and architecture. djLint, regex and PyYAML come as glibc (`manylinux`) wheels on Ubuntu and musl (`musllinux`) wheels on Alpine; the other packages are pure Python.

## Files and permissions

The working directory is `/work`. The image runs as UID 1000, and any other UID works too: `HOME` is then `/`, and caches go to `/cache`, which anyone can write to. Linting and `--check` only read files, so the mount can be read-only (`-v "$PWD:/work:ro"`); `--reformat` needs it writable. djLint can read and write only the files its UID has access to, so run it as your own user:

| Runtime | Flag |
|---|---|
| Docker on Linux (rootful), GitHub Actions | `--user "$(id -u):$(id -g)"` |
| Rootless Podman | `--userns=keep-id` |
| Rootless Docker | `--user 0:0` (root in the container is your user on the host) |
| Docker Desktop on macOS or Windows | none, file ownership is mapped for you |

## Extending the slim image

Use a `slim` tag as the base for your own image. `slim`, `slim-ubuntu` and `slim-alpine` follow new djLint releases and are rebuilt when its locked Python dependencies or the distro change. djLint runs from a virtual environment in `/usr/local/lib/djlint`; the `python3` on `PATH` is the distro's interpreter and cannot import djLint. The distro packages djLint needs are listed in `/usr/local/share/randomcontainers/djlint/runtime-deps`. Switch to root to install more, then back:

```dockerfile
FROM ghcr.io/randomcontainers/djlint:slim-ubuntu@sha256:...
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*
USER 1000:1000
```

On Alpine, use `apk add --no-cache git`. The entrypoint is `["tini", "--", "djlint"]`; set your own `ENTRYPOINT` if your image runs a script. To pick up new djLint releases and base image fixes, let Dependabot or Renovate update the digest in your `FROM` line.

## Verifying

Each image has a build provenance attestation from this repository's GitHub Actions run, signed by the shared build workflow in `randomcontainers/ci`:

```sh
gh attestation verify oci://ghcr.io/randomcontainers/djlint:latest \
  --repo randomcontainers/djlint --signer-repo randomcontainers/ci
```

Each platform image also carries an SPDX SBOM that lists the distro and Python packages in it with their versions:

```sh
docker buildx imagetools inspect ghcr.io/randomcontainers/djlint:latest --format '{{ json .SBOM }}'
```

djLint and its Python dependencies are installed from [`requirements.lock`](requirements.lock), which pins every package to a version and its SHA-256 hashes, and pip refuses anything else. The URL and hash of each installed wheel are in `/usr/local/share/randomcontainers/djlint/source`, and the installed versions in `buildinfo` next to it.

## Updates

The project checks [djLint on PyPI](https://pypi.org/project/djlint/) every 15 minutes. A release is picked up once it is 24 hours old and PyPI holds a provenance attestation for each of its files showing it was published from the [djlint/djLint](https://github.com/djlint/djLint) repository. The new version and a regenerated `requirements.lock` are then committed together and the images are rebuilt. Only the newest release is built; tags of older versions stay as they were last built. Dependency versions in the lock must have been on PyPI for at least a day. The lock is also regenerated weekly at the same djLint version, so new releases of its other dependencies reach the current tags between djLint releases. When a new lock would change the version of PyYAML, jsbeautifier or cssbeautifier, the update, including a new djLint release, waits until their license files are refreshed by hand (see [Building](#building)).

The images of the current version are also rebuilt when the Ubuntu or Alpine base image changes and at least every 7 days, so distro security fixes reach the current tags.

## Building

```sh
docker build -f Dockerfile.ubuntu --target slim --build-arg VERSION=<version> -t djlint:local .
```

Use `Dockerfile.alpine` for the Alpine image. `<version>` must be the version pinned in `requirements.lock`; the build stops otherwise.

The command that produced `requirements.lock` is on its second line; it resolves for Python 3.14, the version on both bases. To regenerate the lock at the version in `package.yml`, run `rc lock requirements.lock` in this directory. `rc` is the command-line tool of [randomcontainers/ci](https://github.com/randomcontainers/ci), and it needs uv on `PATH`. If a new lock changes the version of PyYAML, jsbeautifier or cssbeautifier, run `python3 scripts/bundled-licenses.py` to refresh `licenses/`. The build fails until those files match the installed packages.

## Licenses

djLint is licensed under the [GNU General Public License, version 3 or later](https://github.com/djlint/djLint/blob/master/LICENSE) (GPL-3.0-or-later). Its compiled code is the shared library described in [What is in the image](#what-is-in-the-image), and the `.py` files in `site-packages/djlint/` are the source it was compiled from. The wheel they were installed from is named in `/usr/local/share/randomcontainers/djlint/source`. The configuration the wheels are compiled with, `pyproject.toml` and `mypy.ini`, is in djLint's source release on [PyPI](https://pypi.org/project/djlint/#files) and at the matching tag of [djlint/djLint](https://github.com/djlint/djLint). The shared library also contains mypyc's runtime, which is under the MIT, PSF-2.0 and BSD-2-Clause licenses; djLint ships those texts as `LICENSE-THIRD-PARTY`, which the image has in `/usr/local/share/randomcontainers/djlint/licenses/djlint/`.

The image adds click (BSD-3-Clause), regex (Apache-2.0, with code from CPython under the CNRI Python license), PyYAML (MIT), pathspec (MPL-2.0), json5 (Apache-2.0), jsbeautifier and cssbeautifier (MIT), EditorConfig (BSD-2-Clause, with two files under PSF-2.0) and pip (MIT), which includes packages under the Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MIT, MPL-2.0 and PSF-2.0 licenses. The complete SPDX expression is in the image's `org.opencontainers.image.licenses` label, and each package's license files are in `/usr/local/share/randomcontainers/djlint/licenses/`.

regex's license file says that the code it took from CPython's `re` module is under CNRI's Python 1.6 license, but the file contains only the Apache-2.0 text. The CNRI license agreement that CPython ships, the one for Python 1.6.1, is in djLint's `LICENSE-THIRD-PARTY`.

djLint's `reformat.py` says much of its code was borrowed from [HTMLBeautify](https://github.com/rareyman/HTMLBeautify), which is licensed under the Creative Commons Attribution-ShareAlike 3.0 Unported License. Only a few short lines of HTMLBeautify are left in djLint, such as `for item in rawcode_flat_list:`, so the image's label follows djLint's GPL-3.0-or-later and does not add CC-BY-SA-3.0.

Three wheels leave out a license text, so this repository adds them in [`licenses/`](licenses/). PyYAML's extension module links a static build of libyaml (MIT), and its wheel includes only PyYAML's own license; the image has libyaml's in `/usr/local/share/randomcontainers/djlint/licenses/PyYAML/bundled/libyaml/`. jsbeautifier and cssbeautifier are built from the js-beautify repository, whose license file their wheels do not include; the image has it in `/usr/local/share/randomcontainers/djlint/licenses/jsbeautifier/` and `/usr/local/share/randomcontainers/djlint/licenses/cssbeautifier/`. The `SOURCES` file next to each names where the text comes from.

The files in this repository are available under the MIT license, see [LICENSE](LICENSE), except the license texts in `licenses/`, which keep their own terms.

## Requesting a tool

To suggest another tool, use the [Request a tool](https://github.com/randomcontainers/.github/issues/new?template=tool-request.yml) form.
