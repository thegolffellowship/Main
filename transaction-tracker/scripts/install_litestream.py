#!/usr/bin/env python3
"""Print the path of a usable Litestream binary, fetching it ONCE if needed.

The binary is pinned (version + sha256) and cached on the persistent volume
(<volume>/bin/litestream), so a deploy never re-downloads it and the build
system is untouched. Stdlib only. On any failure: say why on stderr, print
nothing, exit 1 — the caller then simply runs without replication.
"""
import hashlib, io, os, shutil, stat, sys, tarfile, urllib.request

VERSION = "v0.3.13"
SHA256 = "eb75a3de5cab03875cdae9f5f539e6aedadd66607003d9b1e7a9077948818ba0"
URL = ("https://github.com/benbjohnson/litestream/releases/download/"
       f"{VERSION}/litestream-{VERSION}-linux-amd64.tar.gz")


def bin_dir() -> str:
    db = os.environ.get("DATABASE_PATH") or "/data/transactions.db"
    return os.path.join(os.path.dirname(db), "bin")


def main() -> int:
    env = os.environ.get("LITESTREAM_BIN")
    if env and os.access(env, os.X_OK):
        print(env); return 0
    dest = os.path.join(bin_dir(), "litestream")
    if os.access(dest, os.X_OK):
        print(dest); return 0
    on_path = shutil.which("litestream")
    if on_path:
        print(on_path); return 0
    if os.environ.get("LITESTREAM_NO_FETCH") == "1":
        print("litestream: not installed and LITESTREAM_NO_FETCH=1", file=sys.stderr)
        return 1
    try:
        os.makedirs(bin_dir(), exist_ok=True)
        data = urllib.request.urlopen(URL, timeout=60).read()
        got = hashlib.sha256(data).hexdigest()
        if got != SHA256:
            print(f"litestream: checksum mismatch ({got[:12]}…), not installing", file=sys.stderr)
            return 1
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            member = next(m for m in tf.getmembers() if m.name.endswith("litestream") and m.isfile())
            tmp = dest + ".part"
            with tf.extractfile(member) as src, open(tmp, "wb") as out:
                shutil.copyfileobj(src, out)
        os.chmod(tmp, os.stat(tmp).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(tmp, dest)
        print(dest); return 0
    except Exception as e:  # noqa: BLE001 — never block the app
        print(f"litestream: could not install ({type(e).__name__}: {e})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
