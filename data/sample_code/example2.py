import time

def process_data():
    data = [x * 2 for x in range(100000)]
    # time.sleep(0.1)
    return sum(data)

def call_process_data_0():
    process_data()
    return

def call_process_data_1():
    call_process_data_0()
    return

process_data()
call_process_data_0()
call_process_data_1()