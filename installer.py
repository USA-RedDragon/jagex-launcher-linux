import argparse
import asyncio
from pathlib import Path
import traceback

from jagex.download import AsyncDownloader

def cleanup():
    for p in Path(".").glob("*.solidpiece"):
        p.unlink()

async def start(target, hash="", save_version=False):
    # Download the metafile and it's pieces
    downloader = AsyncDownloader(target=target, hash=hash)
    try:
        metafile = await downloader.run()
    except Exception as e:
        raise e
    finally:
        await downloader.stop()

    print(f"Extracted Jagex Launcher {metafile.version}")
    if save_version:
        with open(".version", "w") as f:
            f.write(metafile.version)

async def main():
    try:
        parser = argparse.ArgumentParser(
                    prog='installer.py',
                    description='Downloads the Jagex Launcher binaries',
                    epilog='This script is not affiliated with Jagex.')
        parser.add_argument('-t', '--target', type=str, default='launcher-win.production', help='The target version to download')
        parser.add_argument('-s', '--hash', type=str, default='', help='The hash of the metafile to download. Overrides --target')
        parser.add_argument('-v', '--save-version', action='store_true', default=False, help='Save the version number to a file called .version')
        args = parser.parse_args()
        await start(args.target, hash=args.hash, save_version=args.save_version)
    except Exception as e:
        traceback.print_exception(
            type(e),
            value=e,
            tb=e.__traceback__
        )
    finally:
        print("Cleaning up...")
        cleanup()

asyncio.run(main())
