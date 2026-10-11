import os
import sys
import tempfile
from pathlib import Path


def use_temporary_cwd():
    """Run a test module from an empty temporary directory.

    Several commands default to the workspace "." and create .wps-agent/ there; this keeps that
    state out of the repository checkout. Relative sys.path entries (PYTHONPATH=src, '') are made
    absolute first so lazy imports keep working after the chdir.
    """
    original = os.getcwd()
    sys.path[:] = [str(Path(entry or original).resolve()) if not os.path.isabs(entry or "") else entry for entry in sys.path]
    scratch = tempfile.TemporaryDirectory()
    os.chdir(scratch.name)

    def restore():
        os.chdir(original)
        scratch.cleanup()

    return restore
