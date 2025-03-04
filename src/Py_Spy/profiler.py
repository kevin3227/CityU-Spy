import cProfile
import os
import pstats
import io
import importlib.util
import re
import sys
from line_profiler import LineProfiler
from memory_profiler import profile
import json
from typing import Dict, List, Any, Optional

class PerformanceAnalyzer:
    def __init__(self):
        self.profiler = cProfile.Profile()
        self.line_profiler = LineProfiler()
        self.memory_profile_results = []
        self.target_module = None
        self.file_path = None
        self.call_stack_data = []  # Stores call stack information
        self.current_stack = []    # Current call stack

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

    def _analyze_function_level(self, module) -> Dict[str, Any]:
        """
        Function-level performance analysis.
        """
        def should_include_function(func_name: str) -> bool:
            """
            Determines whether this function should be included in the analysis results.
            """
            # Filters out the following types of functions:
            exclusions = [
                '<built-in',
                '<method',
                '<module>',
                '<listcomp>',
                '__init__',
                'decode',
                '<'  # Filters out all special functions starting with '<'
            ]
            return not any(func_name.startswith(exc) for exc in exclusions)

        # Clear call stack data
        self.call_stack_data = []
        self.current_stack = []
        
        # Start tracing and profiling
        sys.settrace(self._trace_calls)
        self.profiler.enable()
        
        # Execute the code
        exec(open(self.file_path).read(), module.__dict__)
        
        # Stop tracing
        self.profiler.disable()
        sys.settrace(None)

        # Parse performance data
        stream = io.StringIO()
        stats = pstats.Stats(self.profiler, stream=stream)
        stats.strip_dirs().sort_stats('cumulative')

        results = []
        call_chains = []
        
        # Extract function-level performance data and assign indices
        function_indices = {}  # Map function names to their indices in results
        average_time_map = {}  # Map function names to their total time
        call_count_map = {}    # Map function names to their call count
        direct_calls = {}      # Map of direct caller-callee relationships

        # First pass: collect basic function information and build direct call relationships
        for func, (cc, nc, tt, ct, callers) in stats.stats.items():
            _, line_number, function_name = func
            
            # Add filtering condition
            if not should_include_function(function_name):
                continue
                
            function_indices[function_name] = len(results)
            call_count_map[function_name] = nc
            average_time_map[function_name] = ct / nc if nc > 0 else 0
            
            # Record direct caller-callee relationships
            for caller, caller_stats in callers.items():
                _, _, caller_name = caller
                # Add filtering condition
                if not should_include_function(caller_name):
                    continue
                if caller_name not in direct_calls:
                    direct_calls[caller_name] = set()
                direct_calls[caller_name].add(function_name)
            
            results.append({
                "function": function_name,
                "calls": nc,
                "total_time": ct,
                "average_time": ct / nc if nc > 0 else 0,
                "line_number": line_number,
            })

        def print_call_tree(func_name, indent=0, visited=None, chain=None):
            """
            Prints the function call tree.
            """
            if visited is None:
                visited = set()
            if chain is None:
                chain = []
                
            if func_name in visited:
                print("  " * indent + f"└── {func_name} (recursive call)")
                return
                
            visited.add(func_name)
            chain.append(func_name)
            
            # Print current function
            prefix = "  " * indent + "└── " if indent > 0 else ""
            print(f"{prefix}{func_name}")
            
            # Recursively print called functions
            callees = direct_calls.get(func_name, set())
            for callee in callees:
                if callee not in visited and should_include_function(callee):
                    print_call_tree(callee, indent + 1, visited.copy(), chain.copy())

        def build_call_chains(func_name, current_chain=None, visited=None):
            """
            Builds the call chains.
            """
            if visited is None:
                visited = set()
            if current_chain is None:
                current_chain = []
                
            if func_name in visited:
                return
                
            visited.add(func_name)
            current_chain.append(func_name)
            
            # Get directly called functions
            callees = direct_calls.get(func_name, set())
            
            # Create list of indices for current chain's children
            children_indices = []
            for callee in callees:
                if callee in function_indices and should_include_function(callee):
                    children_indices.append(function_indices[callee])
            
            # Calculate self_time
            self_time = average_time_map[func_name]
            for callee in callees:
                if callee in average_time_map and should_include_function(callee):
                    self_time -= average_time_map[callee]
            
            # Add current call chain
            call_chains.append({
                "chain": current_chain.copy(),
                "count": 0,  # Updated with actual call chain counts later
                "self_time": self_time,
                "children": children_indices
            })
            
            # Create new call chains for each called function
            for callee in callees:
                if callee not in visited and should_include_function(callee):
                    build_call_chains(callee, current_chain.copy(), visited.copy())
            
            current_chain.pop()
            visited.remove(func_name)

        # Find all root functions and build call chains
        print("\nCall Tree:")
        print("==========")
        
        # Find all function calls that appear in the code
        root_functions = set()
        for func_name in function_indices:
            if not should_include_function(func_name):
                continue
            # A function is a root if it's never called by others
            # or if it's called directly in the main scope
            is_called = False
            for callers in direct_calls.values():
                if func_name in callers:
                    is_called = True
                    break
            
            if not is_called:
                root_functions.add(func_name)
            
        # Add functions that are called directly (even if they're also called by other functions)
        for func, (cc, nc, tt, ct, callers) in stats.stats.items():
            _, _, func_name = func
            if not should_include_function(func_name):
                continue
            
            # Check if this function is called directly from main
            for caller in callers:
                _, _, caller_name = caller
                if not should_include_function(caller_name):
                    root_functions.add(func_name)
                    break

        # Build and print call chains for all root functions
        for func_name in root_functions:
            if should_include_function(func_name):
                print_call_tree(func_name)
                build_call_chains(func_name)

        # Process and filter call stack information
        call_stacks = []
        for call_info in self.call_stack_data:
            func_name = call_info['function']
            if should_include_function(func_name):
                # Filter special functions from the call stack
                filtered_stack = [f for f in call_info['stack'] if should_include_function(f)]
                if filtered_stack:  # Add only if the filtered call stack is not empty
                    call_stacks.append({
                        "function": func_name,
                        "stack": filtered_stack,
                        "line": call_info['line']
                    })
        
        # Calculate the number of calls in the call chain
        call_chain_counts = self._calculate_call_chain_counts(call_stacks)
        
        # Update the count field in call_chains
        for call_chain in call_chains:
            chain_tuple = tuple(call_chain["chain"])
            if chain_tuple in call_chain_counts:
                call_chain["count"] = call_chain_counts[chain_tuple]

        return {
            "mode": "function",
            "file": self.target_module.__file__,
            "results": results,
            "call_chains": call_chains,
            "call_stacks": call_stacks
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
                            "hits": hits,
                            "total_time": time,
                            "per_hit": per_hit,
                            "percent_time": percent,
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


# Test code
if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()
    result = analyzer.analyze_file("../../data/sample_code/example2.py", "function")
    print(json.dumps(result, indent=4))