import shutil
import uuid
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlretrieve


class AssetStorage:
    """Filesystem storage for procedure-scoped media assets."""

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def procedure_dir(self, procedure_id: int) -> Path:
        d = self.root_dir / str(procedure_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "images").mkdir(exist_ok=True)
        (d / "videos").mkdir(exist_ok=True)
        return d

    def _ext_or_default(self, ext: str | None, default: str) -> str:
        if not ext:
            return default
        ext = ext.strip().lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        return ext

    def make_asset_path(
        self,
        procedure_id: int,
        kind: str,
        ext: str | None = None,
        prefix: str | None = None,
    ) -> Path:
        proc = self.procedure_dir(procedure_id)
        sub = "images" if kind == "image" else "videos"
        default_ext = ".png" if kind == "image" else ".mp4"
        final_ext = self._ext_or_default(ext, default_ext)
        stem_prefix = prefix or kind
        stem = f"{stem_prefix}_{uuid.uuid4().hex[:10]}"
        return proc / sub / f"{stem}{final_ext}"

    def copy_imported_file(
        self,
        procedure_id: int,
        src_path: Path,
        kind: str,
        ext: str | None = None,
    ) -> Path:
        src = Path(src_path)
        final_ext = ext or src.suffix or (".png" if kind == "image" else ".mp4")
        dest = self.make_asset_path(
            procedure_id=procedure_id,
            kind=kind,
            ext=final_ext,
            prefix="imported",
        )
        shutil.copy2(src, dest)
        return dest

    def copy_asset_variant(
        self,
        procedure_id: int,
        source_asset_path: Path,
        kind: str,
        prefix: str,
    ) -> Path:
        src = Path(source_asset_path)
        dest = self.make_asset_path(
            procedure_id=procedure_id,
            kind=kind,
            ext=src.suffix,
            prefix=prefix,
        )
        shutil.copy2(src, dest)
        return dest

    def download_to_asset(
        self,
        procedure_id: int,
        kind: str,
        remote_url: str,
        ext_hint: str | None = None,
        prefix: str = "generated",
    ) -> Path:
        if not ext_hint:
            parsed = urlparse(remote_url)
            ext_hint = Path(parsed.path).suffix
        dest = self.make_asset_path(procedure_id, kind, ext=ext_hint, prefix=prefix)
        urlretrieve(remote_url, dest)
        return dest

    def delete_file_if_exists(self, path: Path) -> None:
        p = Path(path)
        if p.exists() and p.is_file():
            p.unlink()

    def delete_procedure_dir(self, procedure_id: int) -> None:
        p = self.root_dir / str(procedure_id)
        if p.exists():
            shutil.rmtree(p)
