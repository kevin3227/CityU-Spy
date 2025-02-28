import math
import types
from unittest.mock import patch, MagicMock, call, mock_open
import pytest
from ..profiler import PerformanceAnalyzer


@pytest.fixture
def analyzer():
    return PerformanceAnalyzer()


@patch("importlib.util.spec_from_file_location")
@patch("importlib.util.module_from_spec")
def test_load_module_from_file_success(mock_module_from_spec, mock_spec_from_file_location, analyzer):
    mock_spec = MagicMock()
    mock_loader = MagicMock()
    mock_spec.loader = mock_loader
    mock_spec_from_file_location.return_value = mock_spec

    mock_module = MagicMock()
    mock_module_from_spec.return_value = mock_module

    result = analyzer.load_module_from_file("test_load_module.py")

    mock_spec_from_file_location.assert_called_once_with("dynamic_module", "test_load_module.py")
    mock_module_from_spec.assert_called_once_with(mock_spec)
    mock_loader.exec_module.assert_called_once_with(mock_module)
    assert result is mock_module
    assert analyzer.target_module is mock_module
    assert analyzer.file_path == "test_load_module.py"


@patch("importlib.util.spec_from_file_location")
def test_load_module_from_file_spec_not_found_error(mock_spec_from_file_location, analyzer):
    mock_spec_from_file_location.return_value = None
    result = analyzer.load_module_from_file("nonexistent.py")
    assert result is None
    assert analyzer.target_module is None
    assert analyzer.file_path is None


@patch("importlib.util.spec_from_file_location")
@patch("importlib.util.module_from_spec")
@patch("builtins.print")
def test_load_module_from_file_module_execution_failure(mock_print, mock_module_from_spec,
                                                        mock_spec_from_file_location, analyzer):
    mock_spec = MagicMock()
    mock_loader = MagicMock()
    mock_spec.loader = mock_loader
    mock_spec_from_file_location.return_value = mock_spec
    error_msg = "Simulated syntax error"
    mock_loader.exec_module.side_effect = SyntaxError(error_msg)
    mock_module = MagicMock()
    mock_module_from_spec.return_value = mock_module

    result = analyzer.load_module_from_file("invalid_module.py")
    assert result is None
    assert analyzer.target_module is None
    assert analyzer.file_path is None
    mock_print.assert_called_once_with(f"Failed to load file: {error_msg}")


@patch("importlib.util.spec_from_file_location")
@patch("builtins.print")
def test_load_module_from_file_general_exception_handling(mock_print, mock_spec_from_file_location, analyzer):
    mock_spec_from_file_location.side_effect = PermissionError("Access denied")
    result = analyzer.load_module_from_file("unexpected_error.py")

    assert result is None
    mock_print.assert_called_once_with("Failed to load file: Access denied")


def test_load_module_from_file_module_real(analyzer):
    module = analyzer.load_module_from_file("data/sample_code/example1.py")
    assert module is not None
    assert module.__name__ == "dynamic_module"
    assert module.hello() == "Hello, World!"


def test_no_target_module(analyzer):
    analyzer.target_module = None
    assert analyzer._get_functions_from_module() == []


def test_standard_functions(analyzer):
    mock_module = types.ModuleType("mock_module")
    mock_module.func1 = lambda: None
    mock_module.func2 = lambda x: x + 1
    mock_module._helper = lambda: None
    mock_module.__init__ = lambda self: None
    mock_module.__private = lambda: None
    mock_module.data = [1, 2, 3]

    analyzer.target_module = mock_module
    result = analyzer._get_functions_from_module()
    assert set(result) is not None
    assert "__init__" not in set(result)
    assert "__private" not in set(result)
    assert set(result) == {'func1', 'func2', '_helper'}


@pytest.fixture
def test_analyzer():
    analyzer = PerformanceAnalyzer()
    analyzer.file_path = "test_module.py"
    mock_module = types.ModuleType("test_module")
    mock_module.__file__ = "test_module.py"
    analyzer.target_module = mock_module
    return analyzer


class TestAnalyzeFunctionLevel:

    @patch("cProfile.Profile")
    @patch("pstats.Stats")
    @patch("builtins.open", new_callable=mock_open, read_data="print('test')")
    def test_basic_function_analysis(self, mock_open_file, mock_pstats, mock_profile, test_analyzer):
        mock_pstats_instance = MagicMock()
        mock_pstats.return_value = mock_pstats_instance
        mock_pstats_instance.stats = {
            ('~', 0, '<built-in method time.sleep>'): (12, 12, 1.834176333, 1.834176333,
                                                       {('test_module.py', 4, 'task_alpha'): (
                                                           2, 2, 0.6056140830000001, 0.6056140830000001),
                                                           ('test_module.py', 10, 'beta_worker'): (
                                                               2, 2, 0.40229445900000005, 0.40229445900000005),
                                                           ('test_module.py', 15, 'gamma_processor'): (
                                                               3, 3, 0.46218887500000005, 0.46218887500000005),
                                                           ('test_module.py', 20, 'delta_engine'): (
                                                               2, 2, 0.20709337400000002, 0.20709337400000002),
                                                           ('test_module.py', 25, 'epsilon_helper'): (
                                                               3, 3, 0.156985542, 0.156985542)}),
            ('test_module.py', 4, 'task_alpha'): (2, 2, 8.545800000000001e-05, 1.632308708,
                                                  {('test_module.py', 1, '<module>'): (
                                                      2, 2, 8.545800000000001e-05, 1.632308708)}),
            ('test_module.py', 10, 'beta_worker'): (2, 2, 3.0166000000000002e-05, 0.609456917,
                                                    {('test_module.py', 4, 'task_alpha'): (
                                                        2, 2, 3.0166000000000002e-05, 0.609456917)}),
            ('test_module.py', 15, 'gamma_processor'): (3, 3, 0.00010287500000000001, 0.619812584,
                                                        {('test_module.py', 1, '<module>'): (
                                                            1, 1, 1.1375e-05, 0.20266033400000003),
                                                            ('test_module.py', 4, 'task_alpha'): (
                                                                2, 2, 9.15e-05, 0.41715225)}),
            ('test_module.py', 20, 'delta_engine'): (2, 2, 2.3876000000000003e-05, 0.20713229200000002, {
                ('test_module.py', 10, 'beta_worker'): (2, 2, 2.3876000000000003e-05, 0.20713229200000002)}),
            ('test_module.py', 27, '<listcomp>'): (3, 3, 0.00042495900000000004, 0.00042495900000000004, {
                ('test_module.py', 25, 'epsilon_helper'): (3, 3, 0.00042495900000000004, 0.00042495900000000004)}),
            ('test_module.py', 25, 'epsilon_helper'): (
                3, 3, 0.000110333, 0.157520834,
                {('test_module.py', 15, 'gamma_processor'): (3, 3, 0.000110333, 0.157520834)}),
            ('test_module.py', 1, '<module>'): (1, 1, 2.1833000000000003e-05, 1.8349908750000001, {})
        }

        result = test_analyzer._analyze_function_level(test_analyzer.target_module)
        assert result["mode"] == "function"
        assert result["file"] == "test_module.py"
        assert isinstance(result["results"], list)
        assert len(result["results"]) == 5
        result_names = [r["function"] for r in result["results"]]
        assert "task_alpha" in result_names
        assert "gamma_processor" in result_names
        assert "epsilon_helper" in result_names
        assert "<built-in method time.sleep>" not in result_names
        assert "listcomp_func" not in result_names

        func_alpha_data = next(r for r in result["results"] if r["function"] == "task_alpha")
        assert func_alpha_data["calls"] == 2
        assert func_alpha_data["line_number"] == 4

        func_beta_data = next(r for r in result["results"] if r["function"] == "beta_worker")
        assert func_beta_data["calls"] == 2
        assert math.isclose(func_beta_data["total_time"], 0.609456917)
        assert math.isclose(func_beta_data["average_time"], 0.3047284585)
        assert func_beta_data["line_number"] == 10

        func_gamma_data = next(r for r in result["results"] if r["function"] == "gamma_processor")
        assert func_gamma_data["calls"] == 3
        assert math.isclose(func_gamma_data["total_time"], 0.619812584)
        assert func_gamma_data["line_number"] == 15

        assert isinstance(result["call_chains"], list)
        assert len(result["call_chains"]) > 0
        assert any("task_alpha" in str(caller) for caller in result["call_chains"])
        assert any("delta_engine" in str(caller) for caller in result["call_chains"])
        assert any("epsilon_helper" in str(caller) for caller in result["call_chains"])
        assert any("<listcomp>" not in str(caller) for caller in result["call_chains"])

    @patch("cProfile.Profile")
    @patch("pstats.Stats")
    @patch("builtins.open", new_callable=mock_open, read_data="print('test')")
    def test_time_calculation_accuracy(self, mock_open_file, mock_pstats, mock_profile, test_analyzer):
        test_stats = {
            ("time_test.py", 10, "time_func"): (3, 4, 1.2, 2.4, {})
        }
        mock_pstats_instance = MagicMock()
        mock_pstats.return_value = mock_pstats_instance
        mock_pstats_instance.stats = test_stats

        result = test_analyzer._analyze_function_level(test_analyzer.target_module)
        func_data = result["results"][0]
        assert func_data["total_time"] == 2.4
        assert func_data["average_time"] == 2.4 / 4
        assert func_data["function"] == "time_func"
        assert func_data["line_number"] == 10

    @patch("cProfile.Profile")
    @patch("pstats.Stats")
    @patch("builtins.open", new_callable=mock_open, read_data="print('test')")
    def test_call_chain_generation(self, mock_open_file, mock_pstats, mock_profile, test_analyzer):
        mock_pstats_instance = MagicMock()
        mock_pstats.return_value = mock_pstats_instance
        mock_pstats_instance.stats = {
            ("main.py", 10, "deep_help"): (2, 2, 0.2, 0.1, {
                ("main.py", 5, "helper"): (2, 2, 0.8, 0.5,)
            }),
            ("main.py", 5, "helper"): (2, 2, 0.8, 0.5, {
                ("main.py", 4, "root_func"): (1, 1, 1, 1.6)
            }),
            ("main.py", 4, "root_func"): (1, 1, 1, 1.5, {})
        }
        result = test_analyzer._analyze_function_level(test_analyzer.target_module)
        root_chain = next(chain for chain in result["call_chains"] if chain["chain"] == ["root_func"])
        help_chain = next(chain for chain in result["call_chains"] if chain["chain"] == ["root_func", "helper"])
        assert root_chain["children"] == [1]
        assert help_chain["self_time"] == (0.5 - 0.1) / 2

    @patch("cProfile.Profile")
    @patch("pstats.Stats")
    @patch("builtins.open", new_callable=mock_open, read_data="print('test')")
    @patch("builtins.print")
    def test_call_tree_printing(self, mock_print, mock_open_file, mock_pstats, mock_profile, test_analyzer):
        mock_pstats_instance = MagicMock()
        mock_pstats.return_value = mock_pstats_instance
        mock_pstats_instance.stats = {
            ("test_module.py", 5, "child_func"): (1, 1, 0.2, 0.2, {
                ("test_module.py", 10, "parent_func"): (1, 1, 0.2, 0.4)
            }),
            ("test_module.py", 10, "parent_func"): (1, 2, 0.4, 0.8, {})
        }

        test_analyzer._analyze_function_level(test_analyzer.target_module)
        expected_calls = [
            call("\nCall Tree:"),
            call("=========="),
            call("parent_func (calls: 2, time: 0.400000s)"),
            call("  └── child_func (calls: 1, time: 0.200000s)")
        ]
        mock_print.assert_has_calls(expected_calls, any_order=False)
