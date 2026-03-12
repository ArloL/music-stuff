from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from music_stuff.lib.lib_clonefile import clonefile


def test_clonefile_success(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("hello")
    dst = tmp_path / "dst.txt"

    clonefile(src, dst)

    assert dst.read_text() == "hello"


def test_clonefile_removes_existing_dst(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("new content")
    dst = tmp_path / "dst.txt"
    dst.write_text("old content")

    clonefile(src, dst)

    assert dst.read_text() == "new content"


def test_clonefile_raises_on_failure():
    with pytest.raises(OSError):
        clonefile(Path("/nonexistent/src"), Path("/nonexistent/dst"))
