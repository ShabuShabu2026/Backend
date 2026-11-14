import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

FILES = (
    ("https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF", "dem/LDEM_80S_80MPP_ADJ.TIF", 189158392),
    ("https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608.IMG", "baseline/AVGVISIB_85S_060M_201608.IMG", 51166728),
    ("https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608.LBL", "baseline/AVGVISIB_85S_060M_201608.LBL", None),
    ("https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.IMG", "baseline/AVGVISIB_85S_060M_201608_EARTH.IMG", 51166728),
    ("https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.LBL", "baseline/AVGVISIB_85S_060M_201608_EARTH.LBL", None),
)


def download(url: str, target: Path, expected_size: int | None) -> None:
    if target.is_file() and (target.stat().st_size == expected_size if expected_size is not None else target.stat().st_size > 0):
        print(f"Skipping {target}", flush=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".part")
    try:
        print(f"Downloading {url}", flush=True)
        request = Request(url, headers={"User-Agent": "LunarVisibilityBackend/1.0"})
        with urlopen(request, timeout=120) as response:
            if response.headers.get_content_type().lower() == "text/html":
                raise ValueError(f"HTML response instead of file: {url}")
            with temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        size = temporary.stat().st_size
        if (expected_size is not None and size != expected_size) or size == 0:
            raise ValueError(f"Size mismatch for {target}: expected {expected_size}, got {size}")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))
    failed = False
    for url, relative, size in FILES:
        try:
            download(url, data_dir / relative, size)
        except (OSError, URLError, ValueError) as exc:
            print(f"Warning: {exc}", file=sys.stderr, flush=True)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
