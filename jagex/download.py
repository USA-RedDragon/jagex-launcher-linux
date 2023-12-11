import aiohttp
from aiohttp_retry import RetryClient, RandomRetry
import asyncio
import base64
import errno
import gzip
from hashlib import sha256
import io
import json
import os
from pathlib import Path

from .metafile import parse_metafile

url_template = "https://jagex.akamaized.net/direct6/launcher-win/pieces/{}/{}.solidpiece"

class AsyncDownloader():
    def __init__(self, target="launcher-win.production", hash="", max_concurrency=8, attempts=2):
        self._client = RetryClient(
            client_session=aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=max_concurrency, force_close=True),
                headers={"User-Agent": ""},
            ),
            retry_options=RandomRetry(
                attempts=attempts,
            ),
        )
        self._target = target
        self._hash = hash
        self._tasks = []

    async def _fetch(self, url):
        async with self._client.get(url) as response:
            return await response.read()

    def _mkdir_p(self, path):
        try:
            parent_path = Path(path)
            os.makedirs(parent_path.parent.absolute(), exist_ok=True)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else: raise

    async def run(self):
        if self._hash == "":
            self._hash = await self._get_latest_metafile_hash()
        print(f"Latest metafile hash: {self._hash}")

        metafile = parse_metafile(
            await self._fetch(f"https://jagex.akamaized.net/direct6/launcher-win/metafile/{self._hash}/metafile.json")
        )
        print(f"Metafile refers to version {metafile.version}")

        for digest in metafile.pieces.digests:
            digest_string = base64.b64decode(digest).hex()

            self._tasks.append(
                asyncio.ensure_future(
                    self._download_gzip_deflate_and_validate(
                        url_template.format(digest_string[0:2], digest_string),
                        digest_string + ".solidpiece",
                        digest_string
                    )
                )
            )

        while len(self._tasks) > 0:
            done, tasks = await asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)
            for f in done:
                await f
            self._tasks = tasks

        self._combine_and_extract(metafile)

        return metafile

    def _combine_and_extract(self, metafile):
        # Create an in-memory file to hold the combined file
        with io.BytesIO() as combined_file:
            # Unpack pieces into the combined file
            for item in metafile.pieces.digests:
                digest_string = base64.b64decode(item).hex()
                with open("{}.solidpiece".format(digest_string), 'rb') as temp_file:
                    content = temp_file.read()
                    combined_file.write(content)
            # Reset the file pointer to the beginning of the file
            combined_file.seek(0)
            # Unpack the combined file into individual files
            for file in metafile.files:
                print('Building {} by splitting off {} bytes of the combined zip'.format(file.name, file.size))
                file_output = combined_file.read(file.size)
                # Make sure the directory we are writing to exists
                self._mkdir_p(file.name)
                with open(file.name, 'wb') as output:
                    output.write(file_output)

        print("Downloaded and unpacked {} files".format(len(metafile.files)))

    async def stop(self):
        await self._client.close()

    async def _get_latest_metafile_hash(self) -> str:
        catalog_raw = await self._fetch("https://jagex.akamaized.net/direct6/launcher-win/alias.json")
        catalog = json.loads(catalog_raw)

        if self._target not in catalog:
            raise Exception(f"Failed to find {self._target} in catalog")

        return catalog[self._target]

    async def _download_gzip_deflate_and_validate(self, url, filename, digest):
        print("Downloading file from: {}".format(url))
        response = await self._fetch(url)
        # Remove the first 6 bytes from the file. There is a set of what appear to be proprietary magic bytes placed here in the header, I assume something Solid State Network's DIRECT protocol uses.
        content = response[6:]

        with open(filename, 'wb') as f:
            f.write(content)
        try:
            with gzip.open(filename, 'rb') as compressed_file:
                # Read and decompress the data
                decompressed_data = compressed_file.read()
        except gzip.BadGzipFile:
            return
        # Save the decompressed data to an output file
        with open(filename, 'wb') as output_file:
            output_file.write(decompressed_data)

        # Validate the the checksum matches what is expected in the validated JWT
        with open(filename, 'rb') as file_to_hash:
            # Validate the digest
            checksum = sha256(file_to_hash.read()).hexdigest()
            if checksum != digest:
                raise Exception("For {} expected a checksum of {}, but got {}.".format(filename, digest, checksum))
