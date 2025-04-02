import threading
import time

def worker(num):
    for _ in range(3):
        print(f"Thread {num}: Working...")
        time.sleep(0.1)

def start_threads():
    threads = []
    for i in range(3):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

worker(3)
start_threads()