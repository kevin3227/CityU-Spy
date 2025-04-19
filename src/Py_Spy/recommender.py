import ast
from typing import Dict, List, Any, Optional, Callable

class RuleManager:
    def __init__(self):
        """Initialize the rule manager with default rules."""
        self.rules = {
            "loop_optimization": {
                "description": "Optimize loops to reduce unnecessary iterations.",
                "check": lambda node: isinstance(node, ast.For) and isinstance(node.iter, ast.Call) and node.iter.func.id == 'range' and len(node.iter.args) > 1 and node.iter.args[0].n == 0 and node.iter.args[1].n == 1,
                "suggestion": "Remove the unnecessary range with start 0 and stop 1.",
                "is_ast_based": True
            },
            "cache_suggestion": {
                "description": "Cache function results if the same function is called multiple times with the same arguments.",
                "check": lambda node: isinstance(node, ast.Call) and isinstance(node.func, ast.Name),
                "suggestion": "Consider using functools.lru_cache to cache the function results.",
                "is_ast_based": True
            },
            "function_call_optimization": {
                "description": "Optimize function calls to reduce overhead.",
                "check": lambda stats: stats.get("calls", 0) > 3,
                "suggestion": "Consider optimizing the function or reducing the number of calls.",
                "is_ast_based": False
            }
        }
    
    def add_rule(self, 
                rule_name: str, 
                description: str,
                check_func: Callable[[Any], bool],
                suggestion: str,
                is_ast_based: bool = True):
        """
        Add a new rule (replaces if exists).
        """
        self.rules[rule_name] = {
            "description": description,
            "check": check_func,
            "suggestion": suggestion,
            "is_ast_based": is_ast_based
        }
    
    def remove_rule(self, rule_name: str):
        """Remove a rule."""
        if rule_name in self.rules:
            del self.rules[rule_name]
    
    def get_all_rules(self) -> Dict[str, Any]:
        """Get all rules."""
        return self.rules.copy()

    def get_ast_rules(self) -> Dict[str, Any]:
        """Get AST-based rules."""
        return {k: v for k, v in self.rules.items() if v.get('is_ast_based', True)}

    def get_non_ast_rules(self) -> Dict[str, Any]:
        """Get non-AST-based rules."""
        return {k: v for k, v in self.rules.items() if not v.get('is_ast_based', True)}

class CustomRuleBuilder:
    @staticmethod
    def build_ast_rule(check_condition: str, 
                      description: str, 
                      suggestion: str,
                      node_type: str = None):
        """
        Build an AST node check rule from a string condition.
        """
        def checker(node):
            if node_type and not isinstance(node, getattr(ast, node_type, None)):
                return False
            return eval(check_condition, {'node': node, 'ast': ast})
        
        checker.original_condition = check_condition
        
        return {
            "description": description,
            "check": checker,
            "suggestion": suggestion,
            "is_ast_based": True
        }

    @staticmethod
    def build_non_ast_rule(check_condition: str,
                        description: str,
                        suggestion: str):
        """
        Build a non-AST rule from a string condition.
        """
        try:
            # Directly compile the condition into a lambda function
            def checker(stats):
                return eval(check_condition, {'stats': stats})
        
            checker.original_condition = check_condition

            return {
                "description": description,
                "check": checker,
                "suggestion": suggestion,
                "is_ast_based": False
            }
        except Exception as e:
            raise ValueError(f"Invalid check condition: {str(e)}")


class ASTVisitor(ast.NodeVisitor):
    def __init__(self, rule_manager: RuleManager):
        self.suggestions = []
        self.current_function = None
        self.rule_manager = rule_manager

    def visit_FunctionDef(self, node):
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function

    def generic_visit(self, node):
        for rule_name, rule in self.rule_manager.get_ast_rules().items():
            try:
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
            except Exception as e:
                print(f"Error applying rule {rule_name}: {e}")
        
        super().generic_visit(node)

def generate_optimization_suggestions(
        code: str, 
        analysis_results: List[Dict[str, Any]],
        rule_manager: Optional[RuleManager] = None
    ) -> List[Dict[str, Any]]:
    """
    Generate optimization suggestions for the given code and analysis results.
    """
    if rule_manager is None:
        rule_manager = RuleManager()
    
    suggestions = []
    
    # AST Analysis
    try:
        tree = ast.parse(code)
        visitor = ASTVisitor(rule_manager)
        visitor.visit(tree)
        suggestions.extend(visitor.suggestions)
    except SyntaxError as e:
        print(f"Syntax error in code: {e}")

    # Performance/Memory Analysis
    for result in analysis_results:
        mode = result.get("mode")
        if mode == "function":
            for func_stats in result["results"]:
                for rule_name, rule in rule_manager.get_non_ast_rules().items():
                    try:
                        if rule["check"](func_stats):
                            suggestions.append({
                                "rule": rule_name,
                                "description": rule["description"],
                                "suggestion": rule["suggestion"],
                                "function": func_stats["function"],
                                "line": func_stats.get("line_number")
                            })
                    except Exception as e:
                        print(f"Error applying rule {rule_name}: {e}")
                        
        elif mode == "line":
            for line_stats in result["results"]:
                for rule_name, rule in rule_manager.get_non_ast_rules().items():
                    try:
                        if rule["check"](line_stats):
                            suggestions.append({
                                "rule": rule_name,
                                "description": rule["description"],
                                "suggestion": rule["suggestion"],
                                "function": line_stats["function"],
                                "line": line_stats["line_number"]
                            })
                    except Exception as e:
                        print(f"Error applying rule {rule_name}: {e}")
                        
        elif mode == "memory":
            for mem_stats in result["results"]:
                for mem_usage in mem_stats.get("memory_usage", []):
                    for rule_name, rule in rule_manager.get_non_ast_rules().items():
                        try:
                            if rule["check"](mem_usage):
                                suggestions.append({
                                    "rule": rule_name,
                                    "description": rule["description"],
                                    "suggestion": rule["suggestion"],
                                    "function": mem_stats["function"],
                                    "line": int(mem_usage.get("Line", 0))
                                })
                        except Exception as e:
                            print(f"Error applying rule {rule_name}: {e}")

    return suggestions
