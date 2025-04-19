import time
import random

def nested_function_1():
    time.sleep(random.uniform(0.01, 0.05))  # Simulate some work
    nested_function_2()
    nested_function_3()

def nested_function_2():
    time.sleep(random.uniform(0.01, 0.03))  # Simulate some work
    nested_function_4()
    nested_function_5()

def nested_function_3():
    time.sleep(random.uniform(0.01, 0.02))  # Simulate some work
    nested_function_6()

def nested_function_4():
    time.sleep(random.uniform(0.01, 0.01))  # Simulate some work

def nested_function_5():
    time.sleep(random.uniform(0.01, 0.01))  # Simulate some work

def nested_function_6():
    time.sleep(random.uniform(0.01, 0.01))  # Simulate some work

def deep_nested_function():
    time.sleep(random.uniform(0.01, 0.02))  # Simulate some work
    deep_nested_function_2()

def deep_nested_function_2():
    time.sleep(random.uniform(0.01, 0.02))  # Simulate some work
    deep_nested_function_3()

def deep_nested_function_3():
    time.sleep(random.uniform(0.01, 0.02))  # Simulate some work
    deep_nested_function_4()

def deep_nested_function_4():
    time.sleep(random.uniform(0.01, 0.02))  # Simulate some work

def long_running_function():
    time.sleep(random.uniform(0.1, 0.3))  # Simulate some work

def memory_intensive_function():
    list_ = [x for x in range(100000)]  # Memory-intensive operation
    data = [x * 2 for x in range(100000)]  # Memory-intensive operation
    time.sleep(random.uniform(0.01, 0.02))  # Simulate some work

def main():
    for _ in range(5):
        nested_function_1()
        deep_nested_function()
        long_running_function()
        memory_intensive_function()

main()
