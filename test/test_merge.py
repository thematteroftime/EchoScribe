import os
import shutil
from src.buffer import MemoryBuffer
from src.merge import MergeManager

def test_merge_basic(tmp_path):
    archive = str(tmp_path / "archive")
    buf = MemoryBuffer(100)
    buf.add(1, "one")
    buf.add(2, "two")
    mgr = MergeManager(buf, archive, interval=1, disk_threshold_gb=0)
    # give thread time to run timed merge
    import time
    time.sleep(2)
    files = os.listdir(archive)
    assert any(f.startswith("full_") for f in files)
    mgr.stop()
