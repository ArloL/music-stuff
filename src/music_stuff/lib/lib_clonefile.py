import shutil
import sys
from pathlib import Path

if sys.platform == "darwin":
    import ctypes
    import ctypes.util

    _libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    _libc.clonefile.restype = ctypes.c_int
    _libc.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]

    def clonefile(src: Path, dst: Path) -> None:
        """APFS copy-on-write clone via clonefile(2). Removes dst first if it exists."""
        dst.unlink(missing_ok=True)
        ret = _libc.clonefile(str(src).encode(), str(dst).encode(), 0)
        if ret != 0:
            raise OSError(ctypes.get_errno(), f"clonefile({src} -> {dst})")
else:

    def clonefile(src: Path, dst: Path) -> None:
        """Fallback file copy for non-macOS platforms."""
        dst.unlink(missing_ok=True)
        shutil.copy2(src, dst)
