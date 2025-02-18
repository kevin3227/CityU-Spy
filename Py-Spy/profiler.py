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
        self.profiler.enable()
        exec(open(self.file_path).read(), module.__dict__)
        self.profiler.disable()

        # Parse performance data
        stream = io.StringIO()
        stats = pstats.Stats(self.profiler, stream=stream)
        stats.strip_dirs().sort_stats('cumulative')

        
        results = []
        for func, (cc, nc, tt, ct, _) in stats.stats.items():
        # for func, (cc, _, tt, ct, _) in stats.stats.items():
            _, line_number, function_name = func
            if line_number == 0 or function_name[0] == '<': continue
            if function_name == '__init__': break
            results.append({
                "function": function_name,
                "calls": nc,
                "total_time": ct,
                "average_time": ct / nc if nc > 0 else 0,
                "line_number": line_number,
            })

        return {
            "mode": "function",
            "file": self.target_module.__file__,
            "results": results  # Use filtered results
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
