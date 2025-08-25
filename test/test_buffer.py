import threading
from src.buffer import MemoryBuffer

def test_buffer_basic():
    buf = MemoryBuffer(10)
    buf.add(1, "a")
    buf.add(2, "b")
    assert buf.size() == 2
    items = buf.consume_all()
    assert items[1] == "a" and items[2] == "b"
    assert buf.size() == 0

def test_buffer_concurrent():
    buf = MemoryBuffer(1000)
    def writer(start):
        for i in range(start, start+100):
            buf.add(i, f"t{i}")
    threads = [threading.Thread(target=writer, args=(i*100,)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert buf.size() == 500
    items = buf.consume_all()
    assert len(items) == 500
