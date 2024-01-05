#!/usr/bin/env python3
# sync_media/sync_media.py
# Copyright (C) 2023  1F616EMO
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
# USA

import os
import os.path
from typing import Generator

from hashlib import file_digest

import click
import requests

from click import echo

HEXDIGIT = "0123456789abcdef"


def iter_mth(data: bytes) -> Generator[str, None, None]:
    """Iterate through a index.mth and yield string hashes

    Parameters
    ----------
    data : bytes
        The index.mth

    Yields
    ------
    str
        String hashes

    Raises
    ------
    RuntimeError
        If the index.mth is invalid.
    """
    if data[0:6] != b"MTHS\x00\x01":
        raise RuntimeError("Invalid index.mth")
    for i in range(6, len(data), 20):
        yield data[i:i+20].hex()


@click.command()
@click.option('--delete/--no-delete', default=True, help="Whether to delete files not found in index.mth.")
@click.option('--generate/--no-generate', default=False, help="Whether to regenerate index.mth. If not, use remote index.mth.")
@click.option('--redownload/--no-redownload', default=False, help="Whether to re-download all files found")
@click.argument('media_index')
@click.argument('destination')
def main(delete: bool, generate: bool, redownload: bool, media_index: str, destination: str):
    """Download or sync a Minetest media server."""

    list_files = os.listdir(destination)

    if media_index[-1] != "/":
        media_index += "/"
    mth_url = media_index + "index.mth"

    # We use POST to match official behaviour
    mth_r = requests.post(mth_url, timeout=60)
    mth_bytes = mth_r.content

    found_count = 0
    download_count = 0

    for file_hash in iter_mth(mth_bytes):
        found_count += 1

        echo(f"Processing {file_hash}")
        if file_hash in list_files:
            echo("\tFile found in directory")
            list_files.remove(file_hash)
            if not redownload:
                continue

        download_count += 1

        with open(os.path.join(destination, file_hash), "wb") as media_f:
            with requests.get(media_index + file_hash, timeout=60, stream=True) as media_r:
                with click.progressbar(length=int(media_r.headers.get('content-length', "0")),
                                       label="\tDownloading file") as pbar:
                    for part in media_r.iter_content(chunk_size=None):
                        media_f.write(part)
                        pbar.update(len(part))

    delete_count = 0

    if delete:
        for file_name in list_files:
            if len(file_name) != 40 or not any(c in HEXDIGIT for c in file_name):
                continue
            delete_count += 1
            echo(f"Deleting {file_name}")
            os.remove(os.path.join(destination, file_name))

    if generate:
        echo("Generating index.mth")
        with open(os.path.join(destination, "index.mth"), "wb") as mth_f:
            mth_f.write(b"MTHS\x00\x01")
            with os.scandir(destination) as it:
                for entry in it:
                    if len(entry.name) != 40 or not any(c in HEXDIGIT for c in entry.name) or not entry.is_file():
                        continue
                    echo(f"\tHashing {entry.name}")
                    with open(entry.path, "rb") as f:
                        digest = file_digest(f, "sha1")
                        mth_f.write(digest.digest())
    else:
        echo("Writing remote index.mth")
        with open(os.path.join(destination, "index.mth"), "wb") as mth_f:
            mth_f.write(mth_bytes)

    echo(
        f"Done, found {found_count}, downloaded {download_count}, deleted {delete_count}")


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
