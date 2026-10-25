"""The stack's failure report: the child's own words, never a TypeError.

A stack that cannot start is the one moment its log matters. The log is held
by an open file object rather than by a path — ``os.fdopen`` names the object
after its descriptor, an integer — so reading it must not go through ``Path``:
the helper would raise before it could show why the api or the web server died.
"""

import os
import subprocess
import sys
import tempfile

from app.kernel.testing import stack


def test_a_dead_child_is_reported_with_its_own_output() -> None:
    fd, _ = tempfile.mkstemp(prefix="narrare-log-")
    log = os.fdopen(fd, "w+b")
    try:
        process = subprocess.Popen(
            [sys.executable, "-c", "print('port 3100 is already bound')"],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        process.wait()
        process._log_file = log  # type: ignore[attr-defined]
        report = stack._read_log(process)  # pyright: ignore[reportPrivateUsage]  what a failed start shows
        assert "port 3100 is already bound" in report
    finally:
        log.close()
