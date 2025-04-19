import ast
from typing import Dict, List, Any, Union, Optional
import json
import os
from pathlib import Path

# Optimization Rules Library (Sprint 2 + Sprint 3)
OPTIMIZATION_RULES = {
    "loop_optimization": {
        "description": "Optimize loops to reduce unnecessary iterations.",
        "check": lambda node: isinstance(node, ast.For) and isinstance(node.iter, ast.Call) and node.iter.func.id == 'range' and len(node.iter.args) > 1 and node.iter.args[0].n == 0 and node.iter.args[1].n == 1,
        "suggestion": "Remove the unnecessary range with start 0 and stop 1."
    },
    "redundant_calculation": {
        "description": "Avoid redundant calculations inside loops.",
        "check": lambda node: isinstance(node, ast.For) and any(isinstance(sub_node, ast.BinOp) and isinstance(sub_node.left, ast.Name) and isinstance(sub_node.right, ast.Num) for sub_node in ast.walk(node)),
        "suggestion": "Move the redundant calculation outside the loop."
    },
    "cache_suggestion": {
        "description": "Cache function results if the same function is called multiple times with the same arguments.",
        "check": lambda node: isinstance(node, ast.Call) and isinstance(node.func, ast.Name),
        "suggestion": "Consider using functools.lru_cache to cache the function results."
    },
    "function_call_optimization": {
        "description": "Optimize function calls to reduce overhead.",
        "check": lambda stats: stats.get("total_time", 0) > 0.005 and stats.get("calls", 0) > 1,
        "suggestion": "Consider optimizing the function or reducing the number of calls."
    },
    "line_optimization": {
        "description": "Optimize lines with high execution time.",
        "check": lambda stats: stats.get("percent_time", 0) > 10,
        "suggestion": "Review and optimize this line of code."
    },
    "memory_optimization": {
        "description": "Optimize memory usage in functions.",
        "check": lambda stats: float(stats.get("Mem usage", "0").split()[0]) if stats.get("Mem usage", "0").strip() else 0 > 48,
        "suggestion": "Review and optimize memory usage in this function."
    },
    "list_to_generator": {
        "description": "Replace list operations with generators to reduce memory usage if the list is not reused extensively.",
        "check": lambda node: isinstance(node, ast.ListComp) or (isinstance(node, ast.For) and isinstance(node.body[0], ast.Assign) and isinstance(node.body[0].value, ast.List)),
        "suggestion": "Convert list comprehensions to generator expressions or use generator functions instead of creating lists."
    },
    "dict_optimization": {
        "description": "When a dictionary has consecutive integer keys starting from 0, consider using a list for better access performance.",
        "check": lambda node: isinstance(node, ast.Dict) and all(isinstance(key, ast.Num) for key in node.keys) and sorted([key.n for key in node.keys]) == list(range(len(node.keys))),
        "suggestion": "Convert the dictionary to a list."
    },
    "delayed_import_optimization": {  # Sprint 3新增规则
        "description": "Optimize delayed imports to improve startup performance.",
        "check": lambda node: isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom),
        "suggestion": "Consider moving imports inside functions if they're not needed at startup."
    },
    "exception_handling_optimization": {  # Sprint 3新增规则
        "description": "Optimize exception handling to avoid performance penalties.",
        "check": lambda node: isinstance(node, ast.Try) and len(node.handlers) > 0,
        "suggestion": "Avoid broad exception handling; use specific exceptions where possible."
    }
}

class ASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.suggestions = []
        self.parent = None
        self.current_function = None

    def visit_FunctionDef(self, node):
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function

    def generic_visit(self, node):
        old_parent = self.parent
        self.parent = node
        for rule_name, rule in OPTIMIZATION_RULES.items():
            if rule_name in ["loop_optimization", "redundant_calculation", "cache_suggestion", "list_to_generator", "dict_optimization", "delayed_import_optimization", "exception_handling_optimization"]:
                if rule["check"](node):
                    suggestion = {
                        "rule": rule_name,
                        "description": rule["description"],
                        "suggestion": rule["suggestion"],
                        "line": node.lineno if hasattr(node, 'lineno') else None
                    }
                    if self.current_function:
                        suggestion["function"] = self.current_function
                    self.suggestions.append(suggestion)
        super().generic_visit(node)
        self.parent = old_parent

def load_custom_rules(custom_rules_path: str) -> Dict:
    """Sprint 3新增：加载用户自定义规则"""
    if not os.path.exists(custom_rules_path):
        return {}
    
    with open(custom_rules_path, 'r') as f:
        custom_rules = json.load(f)
    
    # 验证规则格式
    validated_rules = {}
    for rule_name, rule in custom_rules.items():
        if "description" in rule and "check" in rule and "suggestion" in rule:
            try:
                # 将字符串形式的检查函数转换为lambda表达式
                check_func = eval(f"lambda node: {rule['check']}")
                validated_rules[rule_name] = {
                    "description": rule["description"],
                    "check": check_func,
                    "suggestion": rule["suggestion"]
                }
            except:
                print(f"Warning: Invalid check function for custom rule '{rule_name}'")
    
    return validated_rules

def generate_optimization_suggestions(
    code: str, 
    analysis_results: List[Dict[str, Any]],
    custom_rules_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Sprint 3增强：支持用户自定义规则和更详细的建议输出"""
    suggestions = []
    
    # 加载用户自定义规则
    custom_rules = {}
    if custom_rules_path:
        custom_rules = load_custom_rules(custom_rules_path)
    
    try:
        # AST Analysis
        tree = ast.parse(code)
        visitor = ASTVisitor()
        visitor.visit(tree)
        suggestions.extend(visitor.suggestions)

        for result in analysis_results:
            mode = result.get("mode")
            if mode == "function":
                func_results = result["results"]
                for func_stats in func_results:
                    for rule_name, rule in {**OPTIMIZATION_RULES, **custom_rules}.items():
                        if rule_name == "function_call_optimization" and rule["check"](func_stats):
                            suggestions.append({
                                "rule": rule_name,
                                "description": rule["description"],
                                "suggestion": rule["suggestion"],
                                "function": func_stats["function"],
                                "line": func_stats["line_number"],
                                "details": {
                                    "total_time": func_stats["total_time"],
                                    "calls": func_stats["calls"],
                                    "average_time": func_stats["average_time"]
                                }
                            })
            elif mode == "line":
                line_results = result["results"]
                for line_stats in line_results:
                    for rule_name, rule in {**OPTIMIZATION_RULES, **custom_rules}.items():
                        if rule_name == "line_optimization" and rule["check"](line_stats):
                            suggestions.append({
                                "rule": rule_name,
                                "description": rule["description"],
                                "suggestion": rule["suggestion"],
                                "function": line_stats["function"],
                                "line": line_stats["line_number"],
                                "details": {
                                    "total_time": line_stats["total_time"],
                                    "percent_time": line_stats["percent_time"],
                                    "code": line_stats["code"]
                                }
                            })
            elif mode == "memory":
                mem_results = result["results"]
                for mem_stats in mem_results:
                    for mem_usage in mem_stats["memory_usage"]:
                        for rule_name, rule in {**OPTIMIZATION_RULES, **custom_rules}.items():
                            if rule_name == "memory_optimization" and rule["check"](mem_usage):
                                suggestions.append({
                                    "rule": rule_name,
                                    "description": rule["description"],
                                    "suggestion": rule["suggestion"],
                                    "function": mem_stats["function"],
                                    "line": int(mem_usage["Line"]),
                                    "details": {
                                        "memory_usage": mem_usage["Mem usage"],
                                        "increment": mem_usage["Increment"],
                                        "line_contents": mem_usage["Line Contents"]
                                    }
                                })

    except SyntaxError as e:
        print(f"Syntax error in code: {e}")
    
    # 按严重程度排序建议
    suggestions.sort(key=lambda x: x.get("details", {}).get("total_time", 0), reverse=True)
    return suggestions

def format_suggestions(suggestions: List[Dict[str, Any]]) -> str:
    """Sprint 3新增：格式化优化建议为可读报告"""
    report = "Optimization Suggestions Report\n"
    report += "=" * 50 + "\n\n"
    
    for idx, suggestion in enumerate(suggestions, 1):
        report += f"Suggestion #{idx}\n"
        report += "-" * 50 + "\n"
        report += f"Rule: {suggestion['rule']}\n"
        report += f"Description: {suggestion['description']}\n"
        report += f"Suggestion: {suggestion['suggestion']}\n"
        
        if "function" in suggestion:
            report += f"Function: {suggestion['function']}\n"
        
        if "line" in suggestion:
            report += f"Line: {suggestion['line']}\n"
        
        if "details" in suggestion:
            report += "\nDetails:\n"
            for key, value in suggestion["details"].items():
                report += f"  {key}: {value}\n"
        
        report += "\n"
    
    return report

# Test code
if __name__ == "__main__":
    code = """
import time

def process_data():
    data = [x * 2 for x in range(100000)]
    return sum(data)


def call_process_data_0():
    process_data()
    return


def call_process_data_1():
    call_process_data_0()
    return


call_process_data_1()
    """

    analysis_results = [
        {
            "mode": "function",
            "file": "example.py",
            "results": [
                {
                    "function": "process_data",
                    "calls": 2,
                    "total_time": 0.008573634,
                    "average_time": 0.004286817,
                    "line_number": 1
                },
                {
                    "function": "call_process_data_0",
                    "calls": 2,
                    "total_time": 0.009381238,
                    "average_time": 0.004690619,
                    "line_number": 5
                },
                {
                    "function": "call_process_data_1",
                    "calls": 1,
                    "total_time": 0.004725731,
                    "average_time": 0.004725731,
                    "line_number": 9
                }
            ],
            "call_chains": [
                {
                    "chain": [
                        "call_process_data_1"
                    ],
                    "count": 1,
                    "self_time": 3.511200000000034e-05,
                    "children": [
                        1
                    ]
                },
                {
                    "chain": [
                        "call_process_data_1",
                        "call_process_data_0"
                    ],
                    "count": 2,
                    "self_time": 0.000403802,
                    "children": [
                        0
                    ]
                },
                {
                    "chain": [
                        "call_process_data_1",
                        "call_process_data_0",
                        "process_data"
                    ],
                    "count": 2,
                    "self_time": 0.004286817,
                    "children": []
                },
                {
                    "chain": [
                        "call_process_data_0"
                    ],
                    "count": 2,
                    "self_time": 0.000403802,
                    "children": [
                        0
                    ]
                },
                {
                    "chain": [
                        "call_process_data_0",
                        "process_data"
                    ],
                    "count": 2,
                    "self_time": 0.004286817,
                    "children": []
                }
            ]
        },
        {
            "mode": "line",
            "file": "../../data/sample_code/example2.py",
            "results": [
                {
                    "line_number": 4,
                    "hits": 3,
                    "total_time": 0.025817778000000003,
                    "per_hit": 0.009000000000000001,
                    "percent_time": 96.8,
                    "code": "data = [x * 2 for x in range(100000)]",
                    "function": "process_data"
                },
                {
                    "line_number": 6,
                    "hits": 3,
                    "total_time": 0.000845025,
                    "per_hit": 0.000281675,
                    "percent_time": 3.2,
                    "code": "return sum(data)",
                    "function": "process_data"
                },
                {
                    "line_number": 9,
                    "hits": 2,
                    "total_time": 0.018829629,
                    "per_hit": 0.009000000000000001,
                    "percent_time": 100.0,
                    "code": "process_data()",
                    "function": "call_process_data_0"
                },
                {
                    "line_number": 10,
                    "hits": 2,
                    "total_time": 8.410000000000001e-07,
                    "per_hit": 4.2050000000000004e-07,
                    "percent_time": 0.0,
                    "code": "return",
                    "function": "call_process_data_0"
                },
                {
                    "line_number": 13,
                    "hits": 1,
                    "total_time": 0.009482121000000001,
                    "per_hit": 0.009000000000000001,
                    "percent_time": 100.0,
                    "code": "call_process_data_0()",
                    "function": "call_process_data_1"
                },
                {
                    "line_number": 14,
                    "hits": 1,
                    "total_time": 8e-08,
                    "per_hit": 8e-08,
                    "code": "return",
                    "function": "call_process_data_1"
                }
            ]
        },
        {
            "mode": "memory",
            "file": "../../data/sample_code/example2.py",
            "results": [
                {
                    "function": "call_process_data_0",
                    "memory_usage": [
                        {
                            "Line": "8",
                            "Mem usage": "47.4 MiB",
                            "Increment": "47.4 MiB",
                            "Occurrences": "1",
                            "Line Contents": "def call_process_data_0():" 
                        },
                        {
                            "Line": "9",
                            "Mem usage": "47.7 MiB",
                            "Increment": "0.3 MiB",
                            "Occurrences": "1",
                            "Line Contents": "process_data()"
                        },
                        {
                            "Line": "10",
                            "Mem usage": "47.7 MiB",
                            "Increment": "0.0 MiB",
                            "Occurrences": "1",
                            "Line Contents": "return"
                        }
                    ]
                },
                {
                    "function": "call_process_data_1",
                    "memory_usage": [
                        {
                            "Line": "12",
                            "Mem usage": "47.7 MiB",
                            "Increment": "47.7 MiB",
                            "Occurrences": "1",
                            "Line Contents": "def call_process_data_1():" 
                        },
                        {
                            "Line": "13",
                            "Mem usage": "47.7 MiB",
                            "Increment": "0.0 MiB",
                            "Occurrences": "1",
                            "Line Contents": "call_process_data_0()"
                        },
                        {
                            "Line": "14",
                            "Mem usage": "47.7 MiB",
                            "Increment": "0.0 MiB",
                            "Occurrences": "1",
                            "Line Contents": "return"
                        }
                    ]
                },
                {
                    "function": "process_data",
                    "memory_usage": [
                        {
                            "Line": "3",
                            "Mem usage": "47.7 MiB",
                            "Increment": "47.7 MiB",
                            "Occurrences": "1",
                            "Line Contents": "def process_data():" 
                        },
                        {
                            "Line": "4",
                            "Mem usage": "49.5 MiB",
                            "Increment": "1.8 MiB",
                            "Occurrences": "100003",
                            "Line Contents": "data = [x * 2 for x in range(100000)]"
                        },
                        {
                            "Line": "5",
                            "Mem usage": "",
                            "Increment": "",
                            "Occurrences": "",
                            "Line Contents": " time.sleep(0.1)"
                        },
                        {
                            "Line": "6",
                            "Mem usage": "49.5 MiB",
                            "Increment": "0.0 MiB",
                            "Occurrences": "1",
                            "Line Contents": "return sum(data)"
                        }
                    ]
                }
            ]
        }
    ]

    # 示例：使用自定义规则文件
    custom_rules_path = "custom_rules.json"
    with open(custom_rules_path, 'w') as f:
        json.dump({
            "custom_rule_1": {
                "description": "Custom rule for detecting unused imports",
                "check": "isinstance(node, ast.Import) and len(node.names) > 0",
                "suggestion": "Consider removing unused imports to clean up the code."
            }
        }, f)
    
    suggestions = generate_optimization_suggestions(code, analysis_results, custom_rules_path)
    report = format_suggestions(suggestions)
    print(report)
