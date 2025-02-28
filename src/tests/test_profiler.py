import pstats
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
