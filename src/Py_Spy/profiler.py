import cProfile
import re
import yappi
import pstats
import io
import importlib.util
# import re
import subprocess
from memory_profiler import memory_usage, profile
import sys
from line_profiler import LineProfiler
from memory_profiler import profile
import json
import threading
import time
import traceback
from collections import Counter
import os

from typing import Dict, List, Any, Optional

# def precise_sleep(interval):
#     start = time.perf_counter()
#     while True:
#         elapsed = time.perf_counter() - start
#         remaining = interval - elapsed
#         if remaining <= 0:
#             break
#         time.sleep(remaining * 0.5)

import ctypes

class Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]

libc = ctypes.CDLL("libc.so.6")
libc.nanosleep.argtypes = [ctypes.POINTER(Timespec), ctypes.POINTER(Timespec)]

def nanosleep(ns):
    req = Timespec()
    req.tv_sec = ns // 1_000_000_000
    req.tv_nsec = ns % 1_000_000_000
    rem = Timespec()
    libc.nanosleep(req, rem)

class ThreadSampler:
    def __init__(self, interval=1e-3, fine_grained=False):
        self.interval = interval  # Sampling interval (seconds)
        self.running = False      # Flag to control the sampling thread's state
        self.samples = []         # List of collected samples
        self.sampling_thread = None  # Thread object that performs sampling
        self.fine_grained = fine_grained  # Whether to use fine-grained sampling
        self.call_stack_data = []  # Stores call stack information for fine-grained sampling
        self.current_stack = []    # Current call stack for fine-grained sampling

    def _trace_calls(self, frame, event, arg):
        """
        Trace function to track function calls and returns for building call stack.
        """
        if event == 'call':
            # Get the current function information
            func_name = frame.f_code.co_name
            file_name = frame.f_code.co_filename
            line_number = frame.f_lineno
            
            # Update the current call stack
            self.current_stack.append(func_name)
            
            # Record call information
            call_info = {
                'function': func_name,
                'file': file_name,
                'line': line_number,
                'stack': list(self.current_stack)  # Copy the current call stack
            }
            self.call_stack_data.append(call_info)
            
        elif event == 'return':
            # Update the call stack when the function returns
            func_name = frame.f_code.co_name
            if self.current_stack and self.current_stack[-1] == func_name:
                self.current_stack.pop()
        
        return self._trace_calls

    def sample(self):
        if self.fine_grained:
            sys.settrace(self._trace_calls)
        else:
            while self.running:
                sample = []
                # Get current frames of all threads
                for thread_id, frame in sys._current_frames().items():
                    # Skip the current thread (the sampler itself)
                    if threading.get_ident() == thread_id:
                        continue
                    
                    # Find the corresponding thread's name
                    thread_name = "Unknown"
                    for t in threading.enumerate():
                        if t.ident == thread_id:
                            thread_name = t.name
                            break
                    
                    # Extract call stack
                    stack = traceback.extract_stack(frame)
                    # Format stack into FlameGraph-compatible format (e.g., "func(file:lineno") 
                    formatted_stack = ";".join([
                        f"{frame.name}({os.path.basename(frame.filename)}:{frame.lineno})"
                        for frame in stack
                    ])
                    
                    # Prepend thread name as the root of the stack
                    formatted_stack = f"Thread-{thread_name};{formatted_stack}"
                    sample.append(formatted_stack)
                
                self.samples.extend(sample)
                time.sleep(self.interval)  # Wait for the sampling interval
                # precise_sleep(self.interval)  # Use precise sleep to reduce timing errors
                # nanosleep(int(self.interval * 1_000_000_000))  # Use nanosleep for better precision

    def start(self):
        """Start sampling thread or settrace"""
        self.running = True
        if not self.fine_grained:
            self.sampling_thread = threading.Thread(target=self.sample, daemon=True)
            self.sampling_thread.start()
        else:
            self.sample()

    def stop(self):
        """Stop sampling and wait for thread termination or reset settrace"""
        self.running = False
        if self.fine_grained:
            sys.settrace(None)
        else:
            if self.sampling_thread:
                self.sampling_thread.join(timeout=1.0)  # Set timeout in case thread hangs

    def save_to_flamegraph_file(self, filename):
        if self.fine_grained:
            # Process call_stack_data for fine-grained sampling
            counter = Counter([";".join(call_info['stack']) for call_info in self.call_stack_data])
        else:
            # Aggregate stack samples by count
            counter = Counter(self.samples)
        
        with open(filename, "w") as f:
            for stack, count in counter.items():
                f.write(f"{stack} {count}\n")
        print(f"Saved FlameGraph data to '{filename}', {len(counter)} unique stacks, "
              f"{sum(counter.values())} total samples.")
        return counter

class PerformanceAnalyzer:
    def __init__(self, mthread=False, fine_grained=False):
        self.profiler = cProfile.Profile()
        self.line_profiler = LineProfiler()
        self.memory_profile_results = []  # Stores memory profiling results
        self.target_module = None
        self.file_path = None
        self.fine_grained = fine_grained
        self.call_stack_data = []  # Stores call stack information
        self.current_stack = []    # Current call stack
        self.mthread = mthread

    def load_module_from_file(self, file_path: str) -> Optional[Any]:
        """
        Dynamically loads a Python module from the specified file path.
        :param file_path: Path to the Python code file.
        :return: Loaded module object (returns None if failed).
        """
        try:
            spec = importlib.util.spec_from_file_location("dynamic_module", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.target_module = module
            self.file_path = file_path
            return module
        except Exception as e:
            print(f"Failed to load file: {e}")
            return None

    def _get_functions_from_module(self) -> List[str]:
        """
        Extracts all function names from the module.
        :return: List of function names.
        """
        if not self.target_module:
            return []
        return [func for func in dir(self.target_module) 
                if callable(getattr(self.target_module, func)) 
                and not func.startswith("__")]

    def analyze_file(self, file_path: str, mode: str) -> Dict[str, Any]:
        """
        Performs performance analysis based on the file path and mode.
        :param file_path: Path to the Python code file.
        :param mode: Analysis mode (function/line/memory).
        :return: Analysis results in JSON format.
        """
        module = self.load_module_from_file(file_path)
        if not module:
            return {"error": "Failed to load file"}

        # Call different analysis methods based on the mode
        if mode == "function":
            return self._analyze_function_level(module)
        elif mode == "line":
            return self._analyze_line_level(module)
        elif mode == "memory":
            return self._analyze_memory_level(module)
        else:
            return {"error": "Unsupported analysis mode"}

    def _trace_calls(self, frame, event, arg):
        """
        Trace function to track function calls and returns for building call stack.
        """
        if event == 'call':
            # Get the current function information
            func_name = frame.f_code.co_name
            file_name = frame.f_code.co_filename
            line_number = frame.f_lineno
            
            # Update the current call stack
            self.current_stack.append(func_name)
            
            # Record call information
            call_info = {
                'function': func_name,
                'file': file_name,
                'line': line_number,
                'stack': list(self.current_stack)  # Copy the current call stack
            }
            self.call_stack_data.append(call_info)
            
        elif event == 'return':
            # Update the call stack when the function returns
            func_name = frame.f_code.co_name
            if self.current_stack and self.current_stack[-1] == func_name:
                self.current_stack.pop()
        
        return self._trace_calls
    
    def _calculate_call_chain_counts(self, call_stacks):
        """
        Calculate the number of calls in the call chain.
        
        :param call_stacks: Call stack list containing information for each call (function name, call chain, etc.).
        :return: Dictionary containing call chains and their occurrence counts.
        """
        call_chain_counts = {}

        for entry in call_stacks:
            # Convert stack to a tuple (immutable type) to use as a dictionary key
            call_chain = tuple(entry['stack'])
            
            if call_chain not in call_chain_counts:
                call_chain_counts[call_chain] = 0
            call_chain_counts[call_chain] += 1

        return call_chain_counts

    def _build_call_tree(self, samples_counter):
        """
        Build a call tree from the sampled data.
        Args:
            samples_counter: A Counter object containing call stacks and their frequencies.
        Returns:
            A tree structure representing the call hierarchy.
        """
        tree = {}

        for stack, count in samples_counter.items():
            stack_parts = stack.split(";")
            current_node = tree

            # Build the tree hierarchy based on stack levels
            for part in stack_parts:
                if part not in current_node:
                    current_node[part] = {"count": 0, "children": {}}
                current_node[part]["count"] += count
                current_node = current_node[part]["children"]

        return tree

    def _print_call_tree(self, tree, indent="", is_last=True):
        """
        Print the call tree in a structured format.
        Args:
            tree: The constructed call tree.
            indent: Current indentation level for formatting.
            is_last: Whether the current node is the last in its level.
        """
        for i, (key, value) in enumerate(tree.items()):
            prefix = indent + ("└── " if is_last and i == len(tree) - 1 else "├── ")
            print(f"{prefix}{key} [{value['count']}]")
            # Recursively print child nodes
            child_count = len(value["children"])
            for j, (child_key, child_value) in enumerate(value["children"].items()):
                self._print_call_tree(
                    {child_key: child_value},
                    indent + ("    " if is_last and i == len(tree) - 1 else "│   "),
                    j == child_count - 1,
                )

    def _analyze_function_level(self, module) -> Dict[str, Any]:
        """
        Function-level performance analysis.
        """
        functions = self._get_functions_from_module()

        if self.mthread:
            self.fine_grained = False
        
        # Clear call stack data
        self.call_stack_data = []
        self.current_stack = []

        results = []
        call_chains = []
        
        # Start profiling
        sampler = ThreadSampler(fine_grained=self.fine_grained)
        sampler.start()

        if self.mthread:
            yappi.start(profile_threads=True, builtins=False)

        else:
            self.profiler.enable()
        
        # Execute the code
        exec(open(self.file_path).read(), module.__dict__)
        
        # Stop profiling
        sampler.stop()
        if self.mthread:
            yappi.stop()
            stats = yappi.get_func_stats()
            for func_stat in stats:
                if not any(item in func_stat.full_name for item in functions):
                    continue
                results.append({
                    "function": func_stat.full_name.split(" ")[-1],
                    "calls": func_stat.ncall,
                    "total_time": func_stat.ttot,
                    "average_time": func_stat.ttot / func_stat.ncall if func_stat.ncall > 0 else 0,
                    "line_number": func_stat.lineno
                    # "sub_calls": [(sub_call.full_name, sub_call.ncall, sub_call.ttot) for sub_call in func_stat.children]
                })

            # Clear Yappi stats
            yappi.clear_stats()

        else:
            self.profiler.disable()
            # Parse performance data
            stream = io.StringIO()
            stats = pstats.Stats(self.profiler, stream=stream)
            stats.strip_dirs().sort_stats('cumulative')

            # First pass: collect basic function information and build direct call relationships
            for func, (cc, nc, tt, ct, callers) in stats.stats.items():
                _, line_number, function_name = func
                if not any(item in function_name for item in functions):
                    continue
                results.append({
                    "function": function_name,
                    "calls": nc,
                    "total_time": ct,
                    "average_time": ct / nc if nc > 0 else 0,
                    "line_number": line_number,
                })

        # Generate FlameGraph data
        output_filename = f"{os.path.splitext(self.file_path)[0]}_flamegraph.txt"
        samples_counter = sampler.save_to_flamegraph_file(output_filename)

        for call_chain, count in samples_counter.items():
            # call_chain = call_chain.split(" ")[0]
            # call_chain = [
            #     next(func for func in functions if func in item)
            #     for item in call_chain.split(";")
            #     if any(func in item for func in functions) and 'Thread' not in item
            # ]            
            
            if len(call_chain) > 0:
                call_chains.append({
                    "chain": call_chain.split(";"),
                    "count": count,
                    "percentage": (count / sum(samples_counter.values())) * 100
                })

        # Build call tree
        call_tree = self._build_call_tree(samples_counter)
        print("\nCall Tree:")
        self._print_call_tree(call_tree)

        return {
            "mode": "function",
            "file": self.file_path,
            "results": results,
            "call_chains": call_chains
        }

    def _analyze_line_level(self, module=None):
        """
        Analyze the line-level performance of code.      
 
        Args:
            module: The loaded Python module object.
            
        Returns:
            dict: A dictionary containing the line-level analysis results in the following format:
            {
                "mode": "line",
                "file": filename,
                "results": [
                    {
                        "line_number": Line number,
                        "hits": Number of calls,
                        "total_time": Total execution time,
                        "per_hit": Average time per call,
                        "percent_time": Percentage of total time,
                        "code": Code content,
                        "function": Function name it belongs to
                    },
                    ...
                ]
            }
        """
            
        # Get all functions in the module
        functions = self._get_functions_from_module()
        
        # Add the @profile decorator to each function
        for func_name in functions:
            func = getattr(self.target_module, func_name)
            if callable(func):
                self.line_profiler.add_function(func)
        
        # If no functions are found, try executing the file's content directly
        if not functions:
            # Execute the file's content
            self.line_profiler.enable()
            exec(open(self.file_path).read(), self.target_module.__dict__)
            self.line_profiler.disable()
        else:
            # Execute each function
            self.line_profiler.enable()
            for func_name in functions:
                try:
                    func = getattr(self.target_module, func_name)
                    if callable(func):
                        func()
                except Exception as e:
                    # Ignore execution errors and continue analyzing other functions
                    pass
            self.line_profiler.disable()
        
        # Collect analysis results
        import io
        output = io.StringIO()
        self.line_profiler.print_stats(stream=output)
        
        # Parse the output results
        results = []
        lines = output.getvalue().split('\n')
        
        # Skip the header information and parse statistical data line by line
        current_function = None
        for line in lines:
            # Detect function name lines
            if line.strip().startswith('Function'):
                current_function = line.split("Function: ")[1].split(" at ")[0].strip()
                continue
            
            # Parse statistical data lines
            if re.match(r'\s+\d+', line):
                parts = line.strip().split()
                if len(parts) >= 6:
                    try:
                        line_num = int(parts[0])
                        hits = int(parts[1])
                        time = float(parts[2]) * 1e-09
                        per_hit = float(parts[3]) * 1e-09
                        percent = float(parts[4].strip('%'))
                        code = ' '.join(parts[5:])
                        
                        results.append({
                            "line_number": line_num,
                            # "hits": hits,
                            # "total_time": time,
                            "time": per_hit,
                            "percent": percent,
                            "code": code,
                            "function": current_function
                        })
                    except (ValueError, IndexError):
                        # Skip lines that cannot be parsed
                        pass
        
        # Return the analysis results
        return {
            "mode": "line",
            "file": self.file_path,
            "results": results
        }
    
    def _analyze_memory_level(self, module=None):
        """
        Analyze the memory usage of the code.
        
        Args:
            module: The loaded Python module object.
            
        Returns:
            dict: A dictionary containing the memory analysis results in the following format:
            {
                "mode": "memory",
                "file": filename,
                "results": [
                    {
                        "line_number": Line number,
                        "memory_usage": Memory usage in MB,
                        "code": Code content
                    },
                    ...
                ]
            }
        """
        results = []
        output_stream = io.StringIO()
        # Profile memory usage for each function
        functions = self._get_functions_from_module()
        for func_name in functions:
            func = getattr(self.target_module, func_name)
            if callable(func):
                # Decorate the function with @profile
                profiled_func = profile(func, stream=output_stream)
                # Execute the function to trigger memory profiling
                profiled_func()
                
                output = output_stream.getvalue()
                lines = output.splitlines()
            
                results.append({
                    "function": func_name,
                    "memory_usage": lines
                })
        
        filtered_results = []
        
        for item in results:
            function_name = item['function']
            memory_lines = item['memory_usage']
            
            filtered_lines = []
            for line in memory_lines:
                # Look for lines that start with a number (line number)
                if line.strip() and line.strip()[0].isdigit():
                    filtered_lines.append(line)
            
            # Find the section that matches the current function
            # Look for the line that defines the current function
            relevant_lines = []
            found_function = False
            for line in filtered_lines:
                if f'def {function_name}(' in line:
                    found_function = True
                if found_function:
                    relevant_lines.append(line)
                    # Check if this is a return line (simple heuristic for end of function)
                    if 'return' in line:
                        break
            
            filtered_results.append({
                'function': function_name,
                'memory_usage': relevant_lines
            })

            parsed_results = []
            
            for item in filtered_results:
                function_name = item['function']
                memory_lines = item['memory_usage']
                
                parsed_lines = []
                for line in memory_lines:
                    # Skip lines that aren't data lines (don't start with line number)
                    if not line.strip() or not line.strip()[0].isdigit():
                        continue
                    
                    # Split into components (assuming fixed-width formatting)
                    line_num = line[:8].strip()
                    mem_usage = line[8:19].strip()
                    increment = line[19:32].strip()
                    occurrences = line[32:44].strip()
                    content = line[44:].strip()
                    
                    parsed_lines.append({
                        'Line': line_num,
                        'Mem usage': mem_usage,
                        'Increment': increment,
                        'Occurrences': occurrences,
                        'Line Contents': content
                    })
                
                parsed_results.append({
                    'function': function_name,
                    'memory_usage': parsed_lines
                })

                # try:
                #     # Execute the function and capture memory usage
                #     mem_usage = memory_usage((profiled_func, (), {}), interval=0.01, timeout=1)
                #     results.append({
                #         "function": func_name,
                #         "memory_usage": max(mem_usage)
                #     })
                # except Exception as e:
                #     print(f"Failed to profile memory usage for function {func_name}: {e}")
        # If no functions are found, profile the entire script
        if not functions:
            try:
                # Execute the entire script in a subprocess with memory profiling
                result = subprocess.run(
                    ["mprof", "run", "--python", self.file_path],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    # Parse the memory profile output
                    # mprof_file = "mprofile_*.dat"
                    mem_usage = memory_usage((exec, (open(self.file_path).read(), module.__dict__)), interval=0.1, timeout=1)
                    results.append({
                        "file": self.file_path,
                        "memory_usage": max(mem_usage) if mem_usage else 0
                    })
                else:
                    print(f"Failed to profile memory usage for the entire script: {result.stderr}")
            except Exception as e:
                print(f"Failed to profile memory usage for the entire script: {e}")
        return {
            "mode": "memory",
            "file": self.file_path,
            "results": parsed_results
        }


# Test code
if __name__ == "__main__":
    mthread = False
    # mthread = True
    analyzer = PerformanceAnalyzer(mthread, fine_grained=True)
    # if mthread:
    #     result = analyzer.analyze_file("../../data/sample_code/multi.py", "function")
    # else:
    #     result = analyzer.analyze_file("../../data/sample_code/example2.py", "function")
    result = analyzer.analyze_file("../../data/sample_code/example2.py", "memory")
    print(json.dumps(result, indent=4))