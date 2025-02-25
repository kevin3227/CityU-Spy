import cProfile
import pstats
import io
import importlib.util
# import ast
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
        # elif mode == "memory":
        #     return self._analyze_memory_usage(module)
        else:
            return {"error": "Unsupported analysis mode"}

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
                '<'  # Filter out all special functions starting with '<'
            ]
            return not any(func_name.startswith(exc) for exc in exclusions)

        self.profiler.enable()
        exec(open(self.file_path).read(), module.__dict__)
        self.profiler.disable()

        # Parse performance data
        stream = io.StringIO()
        stats = pstats.Stats(self.profiler, stream=stream)
        stats.strip_dirs().sort_stats('cumulative')

        results = []
        call_chains = []
        
        # Extract function-level performance data and assign indices
        function_indices = {}  # Map function names to their indices in results
        average_time_map = {}   # Map function names to their total time
        call_count_map = {}   # Map function names to their call count
        direct_calls = {}     # Map of direct caller-callee relationships

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
            calls = call_count_map.get(func_name, 0)
            time = average_time_map.get(func_name, 0)
            print(f"{prefix}{func_name} (calls: {calls}, time: {time:.6f}s)")
            
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
                "count": call_count_map[func_name],
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

        return {
            "mode": "function",
            "file": self.target_module.__file__,
            "results": results,
            "call_chains": call_chains
        }

    def _analyze_line_level(self, module) -> Dict[str, Any]:
        """
        Line-by-line performance analysis.
        """
        # Get all functions from the module
        functions = self._get_functions_from_module()
        
        # Add a line_profiler decorator to each function
        for func_name in functions:
            func = getattr(self.target_module, func_name)
            self.line_profiler.add_function(func)
        
        # Execute all callable functions in the module
        self.line_profiler.enable_by_count()
        exec(open(self.file_path).read(), module.__dict__)
        self.line_profiler.disable_by_count()

        # Parse line-by-line performance data
        # self.line_profiler.print_stats()
        stream = io.StringIO()
        self.line_profiler.print_stats(stream=stream)
        stats = stream.getvalue()

        # Parse stats and generate JSON-formatted results
        results = []
        current_function = None
        for line in stats.splitlines():
            if line.startswith("File:"):
                # Parse file path
                file_path = line.split("File: ")[1].strip()
            elif line.startswith("Function:"):
                # Parse function name
                current_function = line.split("Function: ")[1].split(" at ")[0].strip()
            elif line.strip().startswith("Line #"):
                # Skip the header
                continue
            elif line.strip() and current_function:
                # Parse each line of performance data
                parts = line.strip().split()
                if len(parts) >= 6:
                    line_number = int(parts[0])
                    hits = int(parts[1])
                    total_time = float(parts[2])
                    per_hit = float(parts[3])
                    percent_time = float(parts[4])
                    code = " ".join(parts[5:])
                    results.append({
                        "line_number": line_number,
                        "hits": hits,
                        "total_time": total_time,
                        "per_hit": per_hit,
                        "percent_time": percent_time,
                        "code": code,
                        "function": current_function
                    })

        return {
            "mode": "line",
            "file": file_path,
            "results": results
        }


# Test code
if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()
    
    result = analyzer.analyze_file("example.py", "function")
    print(json.dumps(result, indent=4))
