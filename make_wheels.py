#!/usr/bin/env python

# Copyright (c) 2024 Maksym Kondratenko
# SPDX-License-Identifier: BSD-2-Clause

import hashlib
import os
import shutil
import sys
import zipfile
import re
import semver
from base64 import urlsafe_b64encode
from email.message import EmailMessage
from pathlib import Path

from sh import gpg, shasum, wget


def read_chunks(file, size=8192):
    """Yield pieces of data from a file-like object until EOF."""
    while True:
        chunk = file.read(size)
        if not chunk:
            break
        yield chunk


def make_message(headers, payload=None):
    """Create an Email Message with headers and an optional payload"""
    msg = EmailMessage()
    for name, value in headers.items():
        if isinstance(value, list):
            for value_part in value:
                msg[name] = value_part
        else:
            msg[name] = value
    if payload:
        msg.set_payload(payload)
    return msg


def rehash(path, blocksize=1 << 20):
    """Return (hash, length) for path using hashlib.sha256()"""
    h = hashlib.sha256()
    length = 0
    with open(path, "rb") as f:
        for block in read_chunks(f, size=blocksize):
            length += len(block)
            h.update(block)
    digest = "sha256=" + urlsafe_b64encode(h.digest()).decode("latin1").rstrip("=")
    return (digest, str(length))


def normalize(arg):
    """Normalize string to be used as part of wheel file name"""
    return re.sub(r"[-_.]+", "_", str(arg), flags=re.UNICODE)


TERRAFORM_URL = (
    "https://releases.hashicorp.com/terraform/{0!s}/terraform_{0!s}_{1!s}.zip"
)
TERRAFORM_SHA256_URL = (
    "https://releases.hashicorp.com/terraform/{0!s}/terraform_{0!s}_SHA256SUMS"
)
TERRAFORM_SIGS_URL = (
    "https://releases.hashicorp.com/terraform/{0!s}/terraform_{0!s}_SHA256SUMS.sig"
)

# Use git tag as the package version and the major.minor.patch portion as the terraform version.
GIT_TAG = os.getenv("GIT_TAG", "1.5.7-rc0")
GIT_SEMVER = semver.Version.parse(GIT_TAG)
PACKAGE_VERSION = ".".join([normalize(n) for n in GIT_SEMVER.to_tuple() if n])
TERRAFORM_VERSION = str(GIT_SEMVER.finalize_version())

PACKAGE_NAME = "terraform-binary-wheel"
PACKAGE_WHEELNAME = "-".join([normalize(PACKAGE_NAME), PACKAGE_VERSION])

PYTHON_TAGS = ["py2", "py3"]
ABI_TAGS = ["none"]
PY_PLATFORM_TF_ARCH = {
    "manylinux_2_5_x86_64.musllinux_1_1_x86_64": "linux_amd64",
    "manylinux_2_5_i686.musllinux_1_1_i686": "linux_386",
    "manylinux_2_5_aarch64.musllinux_1_1_aarch64": "linux_arm64",
    "linux_armv6l.linux_armv7l": "linux_arm",
    "macosx_11_0_x86_64": "darwin_amd64",
    "macosx_11_0_arm64": "linux_arm64",
    "win_amd64": "windows_amd64",
    "win32": "windows_386",
}

LICENSE = Path("LICENSE").absolute()
README = Path("README.md").absolute()
HASHICORP_GPG = Path("hashicorp.gpg").absolute()

PACKAGE_METADATA_MSG = make_message(
    {
        "Metadata-Version": "2.1",
        "Name": PACKAGE_NAME,
        "Version": PACKAGE_VERSION,
        "Summary": "Python wrapper around invoking terraform (https://www.terraform.io/)",
        "Home-Page": "https://github.com/c0m1c5an5/terraform-py",
        "Author": "Maksym Kondratenko",
        "Author-Email": "m.kondratenko.ua@gmail.com",
        "License-File": LICENSE.name,
        "Classifier": [
            "Topic :: Utilities",
            "Topic :: System :: Software Distribution",
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 3",
            "Operating System :: POSIX :: Linux",
            "Operating System :: Microsoft :: Windows",
            "Operating System :: MacOS",
        ],
        "Requires-Python": ">=2",
        "Description-Content-Type": "text/markdown",
    },
    README.read_text(),
)

BUILD_DIR = Path("build").absolute()
BUILD_DIR.mkdir(exist_ok=True)

terraform_sha256_url = TERRAFORM_SHA256_URL.format(TERRAFORM_VERSION)
terraform_sigs_url = TERRAFORM_SIGS_URL.format(TERRAFORM_VERSION)

terraform_sha256 = BUILD_DIR.joinpath(Path(terraform_sha256_url).name)
terraform_sigs = BUILD_DIR.joinpath(Path(terraform_sigs_url).name)

wget(terraform_sha256_url, "-O", terraform_sha256, _out=sys.stdout, _err=sys.stderr)
wget(terraform_sigs_url, "-O", terraform_sigs, _out=sys.stdout, _err=sys.stderr)

gpg(
    "--no-default-keyring",
    "--keyring",
    HASHICORP_GPG,
    "--verify",
    terraform_sigs,
    terraform_sha256,
    _cwd=BUILD_DIR,
    _out=sys.stdout,
    _err=sys.stderr,
)

platform_zip = {}
for platform, terraform_arch in PY_PLATFORM_TF_ARCH.items():
    terraform_zip_url = TERRAFORM_URL.format(TERRAFORM_VERSION, terraform_arch)
    terraform_zip = BUILD_DIR.joinpath(Path(terraform_zip_url).name)
    wget(terraform_zip_url, "-O", terraform_zip, _out=sys.stdout, _err=sys.stderr)
    platform_zip[platform] = terraform_zip

shasum(
    "--algorithm",
    "256",
    "--ignore-missing",
    "--check",
    terraform_sha256,
    _cwd=BUILD_DIR,
    _out=sys.stdout,
    _err=sys.stderr,
)

for platform, terraform_zip in platform_zip.items():
    wheel_name = "-".join(
        [PACKAGE_WHEELNAME, ".".join(PYTHON_TAGS), ".".join(ABI_TAGS), platform]
    )

    wheel_tree = BUILD_DIR.joinpath(wheel_name)
    wheel_tree.mkdir(exist_ok=True)
    terraform_src = terraform_zip.with_suffix("")

    shutil.unpack_archive(
        filename=terraform_zip, extract_dir=terraform_src, format="zip"
    )

    wheel_data = wheel_tree.joinpath("{!s}.data".format(PACKAGE_WHEELNAME))
    wheel_scripts = wheel_data.joinpath("scripts")

    wheel_info = wheel_tree.joinpath("{!s}.dist-info".format(PACKAGE_WHEELNAME))
    package_metadata = wheel_info.joinpath("METADATA")
    wheel_metadata = wheel_info.joinpath("WHEEL")
    wheel_record = wheel_info.joinpath("RECORD")

    wheel_data.mkdir(exist_ok=True)
    wheel_scripts.mkdir(exist_ok=True)
    wheel_info.mkdir(exist_ok=True)

    terraform_src_binary = terraform_src.joinpath("terraform")
    if not terraform_src_binary.exists():
        terraform_src_binary = terraform_src.joinpath("terraform.exe")

    terraform_binary = wheel_scripts.joinpath(terraform_src_binary.name)

    shutil.copy(terraform_src_binary, terraform_binary)
    os.chmod(terraform_binary, 493)

    shutil.copy(LICENSE, wheel_info)

    with package_metadata.open("w") as f:
        f.write(PACKAGE_METADATA_MSG.as_string())

    tags = []
    for python_tag in PYTHON_TAGS:
        for abi_tag in ABI_TAGS:
            tags.append("-".join([python_tag, abi_tag, platform]))

    wheel_metadata_msg = make_message(
        {
            "Wheel-Version": "1.0",
            "Generator": "bdist_wheel 1.0",
            "Root-Is-Purelib": "false",
            "Tag": tags,
        }
    )

    with wheel_metadata.open("w") as f:
        f.write(wheel_metadata_msg.as_string())

    wheel_record_entries = {}
    for f in wheel_tree.glob("**/*"):
        if f.is_file():
            wheel_record_entries[str(f.relative_to(wheel_tree))] = rehash(f)

    wheel_record_entries[str(wheel_record.relative_to(wheel_tree))] = ("", "")
    wheel_record_lines = [
        ",".join([k, *v]) + "\n" for k, v in wheel_record_entries.items()
    ]

    with wheel_record.open("w") as f:
        f.writelines(wheel_record_lines)

    wheel_file = Path("{!s}.whl".format(wheel_tree))

    with zipfile.ZipFile(
        wheel_file, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        for f in wheel_tree.glob("**/*"):
            if f.is_file():
                zf.write(f, f.relative_to(wheel_tree))
