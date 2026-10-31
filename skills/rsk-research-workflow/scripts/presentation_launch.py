"""Run one prepared tool with the native Windows platform fallback, not WMI."""

import os
import platform
import runpy
import sys
from pathlib import Path


def main():
    if os.name == 'nt' and hasattr(platform, '_wmi'):
        # platform.py already falls back to native Windows APIs on OSError.
        # Avoid an unbounded WMI service query during dependency imports.
        platform._wmi = None
        platform._uname_cache = None
    script = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(script.parent))
    sys.argv = sys.argv[1:]
    runpy.run_path(str(script), run_name='__main__')


if __name__ == '__main__':
    main()
