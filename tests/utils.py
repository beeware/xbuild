import tarfile
from collections import namedtuple

VersionInfo = namedtuple(
    "_VersionInfo", ["major", "minor", "micro", "releaselevel", "serial"]
)


def _make_archive(tmp_path, name, files):
    """Create a .tar.gz at tmp_path/name containing the given
    {relative_path: content} files, and return its Path."""
    src_dir = tmp_path / "_src_for_archive"
    src_dir.mkdir()
    for rel_path, content in files.items():
        full = src_dir / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

    archive_path = tmp_path / name
    with tarfile.open(archive_path, "w:gz") as tar:
        for rel_path in files:
            tar.add(src_dir / rel_path, arcname=rel_path)

    return archive_path
