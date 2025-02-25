import ast
import json
from typing import Dict, List, Any, Optional

# 构建初步的优化规则库，添加详细修改建议
OPTIMIZATION_RULES = {
    "loop_optimization": {
        "description": "Avoid unnecessary calculations inside loops. Move invariant calculations outside the loop.",
        "check": lambda node: isinstance(node, ast.For) or isinstance(node, ast.While),
        "suggestion": "If there are calculations that don't depend on the loop variable, move them outside the loop. For example, if you have a constant value calculation like 'result = 2 + 3' inside a loop, move it before the loop."
    },
    "redundant_calculation": {
        "description": "Avoid redundant calculations. If a value is calculated multiple times with the same input, consider caching it.",
        "check": lambda node: isinstance(node, ast.BinOp) and isinstance(getattr(node, 'parent', None), ast.For),
        "suggestion": "Identify calculations that are repeated with the same input. You can store the result of the first calculation in a variable and reuse it instead of recalculating. For example, if you have 'result = 2 + 3' multiple times, calculate it once and reuse the variable."
    },
    "cache_suggestion": {
        "description": "Consider using caching for functions with expensive calculations. You can use functools.lru_cache for simple cases.",
        "check": lambda node: isinstance(node, ast.FunctionDef),
        "suggestion": "If the function performs expensive calculations and the same input is likely to be used multiple times, you can use the 'functools.lru_cache' decorator. For example, add '@functools.lru_cache(maxsize=128)' above the function definition."
    },
    "function_call_optimization": {
        "description": "If a function is called frequently and has a high execution time, consider optimizing its implementation or reducing the number of calls.",
        "check": lambda func_stats: func_stats["total_time"] > 1 and func_stats["calls"] > 10,
        "suggestion": "Review the function implementation to see if there are any inefficiencies. You can also try to reduce the number of calls by caching intermediate results or refactoring the code to call the function less frequently."
    },
    "line_optimization": {
        "description": "Lines with high execution time or a large number of hits should be carefully examined. Look for inefficient algorithms or redundant operations.",
        "check": lambda line_stats: line_stats["percent_time"] > 50 or line_stats["hits"] > 100,
        "suggestion": "Analyze the code on this line to find inefficient algorithms or redundant operations. You may need to rewrite the code using more efficient data structures or algorithms. For example, if you are using a slow search algorithm, consider using a faster one like binary search if applicable."
    },
    "memory_optimization": {
        "description": "Functions with high memory usage may need optimization. Check for large data structures or memory leaks.",
        "check": lambda mem_stats: mem_stats["max_memory_usage"] > 100,
        "suggestion": "Review the function to identify large data structures that can be optimized. You can try to reduce the size of these data structures or release memory more quickly. Also, check for memory leaks by ensuring that all resources are properly released after use."
    }
}


class ASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.suggestions = []
        self.parent = None

    def generic_visit(self, node):
        # 设置当前节点的父节点
        old_parent = self.parent
        self.parent = node
        for rule_name, rule in OPTIMIZATION_RULES.items():
            if rule_name in ["loop_optimization", "redundant_calculation", "cache_suggestion"] and rule["check"](node):
                self.suggestions.append({
                    "rule": rule_name,
                    "description": rule["description"],
                    "suggestion": rule["suggestion"],
                    "line": node.lineno if hasattr(node, 'lineno') else None
                })
        super().generic_visit(node)
        self.parent = old_parent


def generate_optimization_suggestions(code: str, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    生成优化建议
    :param code: 要分析的 Python 代码
    :param analysis_results: 第一组代码生成的性能分析结果
    :return: 优化建议列表
    """
    suggestions = []
    try:
        # AST 分析
        tree = ast.parse(code)
        visitor = ASTVisitor()
        visitor.visit(tree)
        suggestions.extend(visitor.suggestions)

        # 基于函数级分析结果生成建议
        if "function" in analysis_results:
            func_results = analysis_results["function"]["results"]
            for func_stats in func_results:
                for rule_name, rule in OPTIMIZATION_RULES.items():
                    if rule_name == "function_call_optimization" and rule["check"](func_stats):
                        suggestions.append({
                            "rule": rule_name,
                            "description": rule["description"],
                            "suggestion": rule["suggestion"],
                            "function": func_stats["function"],
                            "line": func_stats["line_number"]
                        })

        # 基于逐行分析结果生成建议
        if "line" in analysis_results:
            line_results = analysis_results["line"]["results"]
            for line_stats in line_results:
                for rule_name, rule in OPTIMIZATION_RULES.items():
                    if rule_name == "line_optimization" and rule["check"](line_stats):
                        suggestions.append({
                            "rule": rule_name,
                            "description": rule["description"],
                            "suggestion": rule["suggestion"],
                            "line": line_stats["line_number"],
                            "function": line_stats["function"]
                        })

        # 基于内存分析结果生成建议
        if "memory" in analysis_results:
            mem_results = analysis_results["memory"]["results"]
            for mem_stats in mem_results:
                for rule_name, rule in OPTIMIZATION_RULES.items():
                    if rule_name == "memory_optimization" and rule["check"](mem_stats):
                        suggestions.append({
                            "rule": rule_name,
                            "description": rule["description"],
                            "suggestion": rule["suggestion"],
                            "function": mem_stats["function"]
                        })

    except SyntaxError as e:
        print(f"Syntax error in code: {e}")
    return suggestions


# 为了测试，模拟第一组代码的分析结果
def mock_analysis_results():
    return {
        "function": {
            "mode": "function",
            "file": "example.py",
            "results": [
                {
                    "function": "test_function",
                    "calls": 20,
                    "total_time": 2.5,
                    "average_time": 0.125,
                    "line_number": 5
                }
            ]
        },
        "line": {
            "mode": "line",
            "file": "example.py",
            "results": [
                {
                    "line_number": 10,
                    "hits": 150,
                    "total_time": 0.5,
                    "per_hit": 0.0033,
                    "percent_time": 60,
                    "code": "for i in range(10):",
                    "function": "test_function"
                }
            ]
        },
        "memory": {
            "mode": "memory",
            "file": "example.py",
            "results": [
                {
                    "function": "test_function",
                    "max_memory_usage": 150
                }
            ]
        }
    }


if __name__ == "__main__":
    code = """
def test_function():
    for i in range(10):
        result = 2 + 3
        print(result)
    """
    analysis_results = mock_analysis_results()
    suggestions = generate_optimization_suggestions(code, analysis_results)
    print(json.dumps(suggestions, indent=4))
