import pytest
from ../src.recommender import generate_optimization_suggestions, ASTVisitor, OPTIMIZATION_RULES
import ast


# Testing the ASTVisitor Class
def test_ast_visitor():
    code = """
def test_function():
    for i in range(10):
        result = 2 + 3
        print(result)
    """
    tree = ast.parse(code)
    visitor = ASTVisitor()
    visitor.visit(tree)
    assert isinstance(visitor.suggestions, list)


# Test the generate_optimization_suggestions function under function-level analysis results
def test_generate_optimization_suggestions_function_analysis():
    code = """
def process_data():
    pass

def call_process_data_0():
    process_data()

def call_process_data_1():
    call_process_data_0()
    """
    analysis_result = {
        "mode": "function",
        "file": "example.py",
        "results": [
            {
                "function": "process_data",
                "calls": 20,
                "total_time": 2.5,
                "average_time": 0.125,
                "line_number": 1
            },
            {
                "function": "call_process_data_0",
                "calls": 20,
                "total_time": 2.5,
                "average_time": 0.125,
                "line_number": 5
            },
            {
                "function": "call_process_data_1",
                "calls": 10,
                "total_time": 1.5,
                "average_time": 0.15,
                "line_number": 9
            }
        ],
        "call_chains": []
    }
    suggestions = generate_optimization_suggestions(code, analysis_result)
    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert 'rule' in suggestion
        assert 'description' in suggestion
        assert'suggestion' in suggestion
        if suggestion['rule'] == 'function_call_optimization':
            function_names = [res["function"] for res in analysis_result["function"]["results"]]
            assert suggestion['function'] in function_names
            line_numbers = [res["line_number"] for res in analysis_result["function"]["results"]]
            assert suggestion['line'] in line_numbers


# Test the generate_optimization_suggestions function under line-by-line analysis results
def test_generate_optimization_suggestions_line_analysis():
    code = """
def process_data():
    data = [x * 2 for x in range(100000)]
    return sum(data)

def call_process_data_0():
    process_data()
    return

def call_process_data_1():
    call_process_data_0()
    return
    """
    analysis_result = {
        "mode": "line",
        "file": "example.py",
        "results": [
            {
                "line_number": 2,
                "hits": 150,
                "total_time": 0.5,
                "per_hit": 0.0033,
                "percent_time": 60,
                "code": "data = [x * 2 for x in range(100000)]",
                "function": "process_data"
            },
            {
                "line_number": 3,
                "hits": 150,
                "total_time": 0.1,
                "per_hit": 0.00067,
                "percent_time": 12,
                "code": "return sum(data)",
                "function": "process_data"
            },
            {
                "line_number": 6,
                "hits": 100,
                "total_time": 0.3,
                "per_hit": 0.003,
                "percent_time": 36,
                "code": "process_data()",
                "function": "call_process_data_0"
            },
            {
                "line_number": 7,
                "hits": 100,
                "total_time": 0.000001,
                "per_hit": 0.00000001,
                "percent_time": 0,
                "code": "return",
                "function": "call_process_data_0"
            },
            {
                "line_number": 10,
                "hits": 50,
                "total_time": 0.2,
                "per_hit": 0.004,
                "percent_time": 40,
                "code": "call_process_data_0()",
                "function": "call_process_data_1"
            },
            {
                "line_number": 11,
                "hits": 50,
                "total_time": 0.000001,
                "per_hit": 0.00000001,
                "percent_time": 0,
                "code": "return",
                "function": "call_process_data_1"
            }
        ]
    }
    suggestions = generate_optimization_suggestions(code, analysis_result)
    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert 'rule' in suggestion
        assert 'description' in suggestion
        assert'suggestion' in suggestion
        if suggestion['rule'] == 'line_optimization':
            line_numbers = [res["line_number"] for res in analysis_result["line"]["results"]]
            assert suggestion['line'] in line_numbers
            function_names = [res["function"] for res in analysis_result["line"]["results"]]
            assert suggestion['function'] in function_names


# Test the generate_optimization_suggestions function under memory analysis results
def test_generate_optimization_suggestions_memory_analysis():
    code = """
def process_data():
    data = [x * 2 for x in range(100000)]
    result = sum(data)
    return result
    """
    analysis_result = {
        "mode": "memory",
        "file": "example.py",
        "results": [
            {
                "line_number": 2,
                "memory_usage": 150,
                "increment": 100,
                "code": "data = [x * 2 for x in range(100000)]",
                "function": "process_data"
            },
            {
                "line_number": 3,
                "memory_usage": 200,
                "increment": 50,
                "code": "result = sum(data)",
                "function": "process_data"
            }
        ]
    }
    suggestions = generate_optimization_suggestions(code, analysis_result)
    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert 'rule' in suggestion
        assert 'description' in suggestion
        assert'suggestion' in suggestion
        if suggestion['rule'] == 'memory_optimization':
            function_names = [res["function"] for res in analysis_result["memory"]["results"]]
            assert suggestion['function'] in function_names


# Test code syntax errors
def test_generate_optimization_suggestions_syntax_error():
    code = """
def invalid_function():
    if x = 1:  
        print("Hello")
    """
    analysis_result = {}
    suggestions = generate_optimization_suggestions(code, analysis_result)
    assert isinstance(suggestions, list)


# Test that all analysis modes exist
def test_generate_optimization_suggestions_all_modes():
    code = """
def process_data():
    data = [x * 2 for x in range(100000)]
    return sum(data)

def call_process_data_0():
    process_data()
    return

def call_process_data_1():
    call_process_data_0()
    return
    """
    analysis_result = {
        "function": {
            "mode": "function",
            "file": "example.py",
            "results": [
                {
                    "function": "process_data",
                    "calls": 20,
                    "total_time": 2.5,
                    "average_time": 0.125,
                    "line_number": 1
                },
                {
                    "function": "call_process_data_0",
                    "calls": 20,
                    "total_time": 2.5,
                    "average_time": 0.125,
                    "line_number": 5
                },
                {
                    "function": "call_process_data_1",
                    "calls": 10,
                    "total_time": 1.5,
                    "average_time": 0.15,
                    "line_number": 9
                }
            ],
            "call_chains": []
        },
        "line": {
            "mode": "line",
            "file": "example.py",
            "results": [
                {
                    "line_number": 2,
                    "hits": 150,
                    "total_time": 0.5,
                    "per_hit": 0.0033,
                    "percent_time": 60,
                    "code": "data = [x * 2 for x in range(100000)]",
                    "function": "process_data"
                },
                {
                    "line_number": 3,
                    "hits": 150,
                    "total_time": 0.1,
                    "per_hit": 0.00067,
                    "percent_time": 12,
                    "code": "return sum(data)",
                    "function": "process_data"
                },
                {
                    "line_number": 6,
                    "hits": 100,
                    "total_time": 0.3,
                    "per_hit": 0.003,
                    "percent_time": 36,
                    "code": "process_data()",
                    "function": "call_process_data_0"
                },
                {
                    "line_number": 7,
                    "hits": 100,
                    "total_time": 0.000001,
                    "per_hit": 0.00000001,
                    "percent_time": 0,
                    "code": "return",
                    "function": "call_process_data_0"
                },
                {
                    "line_number": 10,
                    "hits": 50,
                    "total_time": 0.2,
                    "per_hit": 0.004,
                    "percent_time": 40,
                    "code": "call_process_data_0()",
                    "function": "call_process_data_1"
                },
                {
                    "line_number": 11,
                    "hits": 50,
                    "total_time": 0.000001,
                    "per_hit": 0.00000001,
                    "percent_time": 0,
                    "code": "return",
                    "function": "call_process_data_1"
                }
            ]
        },
        "memory": {
            "mode": "memory",
            "file": "example.py",
            "results": [
                {
                    "line_number": 2,
                    "memory_usage": 150,
                    "increment": 100,
                    "code": "data = [x * 2 for x in range(100000)]",
                    "function": "process_data"
                },
                {
                    "line_number": 3,
                    "memory_usage": 200,
                    "increment": 50,
                    "code": "result = sum(data)",
                    "function": "process_data"
                }
            ]
        }
    }
    suggestions = generate_optimization_suggestions(code, analysis_result)
    assert isinstance(suggestions, list)


# Test the case of empty code and empty analysis results
def test_generate_optimization_suggestions_empty_input():
    code = ""
    analysis_result = {}
    suggestions = generate_optimization_suggestions(code, analysis_result)
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0
