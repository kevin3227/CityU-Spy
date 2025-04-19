# """Command-line interface for performance analysis tool.

# This module provides the command-line interface for analyzing Python code performance,
# comparing results, and generating various reports and visualizations.
# """

# import argparse
# import json
# import os
# from datetime import datetime
# import sys  
# sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# import sys
# from pathlib import Path
# from .profiler import PerformanceAnalyzer
# from .visualizer import (
#     generate_flamegraph,
#     generate_callgraph,
#     generate_performance_report,
#     generate_performance_trend
# )


# def save_performance_data(file_path: str, data: dict) -> None:
#     """Save performance data to a JSON file.

#     Args:
#         file_path: Path where the JSON file will be saved.
#         data: Dictionary containing performance metrics.

#     Raises:
#         PermissionError: If the file cannot be written.
#     """
#     with open(file_path, "w") as f:
#         json.dump(data, f, indent=4)
#     print(f"Performance data saved to {file_path}")


# def compare_performance_data(file1: str, file2: str, output_path: str) -> None:
#     """Compare performance metrics between two analysis runs.

#     Args:
#         file1: Path to first performance data file.
#         file2: Path to second performance data file.
#         output_path: Directory where comparison results will be saved.

#     Raises:
#         FileNotFoundError: If either input file doesn't exist.
#         ValueError: If performance data format is invalid.
#     """
#     with open(file1, "r") as f1, open(file2, "r") as f2:
#         data1 = json.load(f1)
#         data2 = json.load(f2)
    
#     comparison_result = {
#         "metadata": {
#             "comparison_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#             "file1": file1,
#             "file2": file2
#         },
#         "performance_comparison": {
#             "file1_metrics": data1.get("performance", {}),
#             "file2_metrics": data2.get("performance", {}),
#             "difference": calculate_performance_difference(
#                 data1.get("performance", {}),
#                 data2.get("performance", {})
#             )
#         }
#     }
    
#     comparison_file = os.path.join(output_path, "comparison_result.json")
#     with open(comparison_file, "w") as f:
#         json.dump(comparison_result, f, indent=4)
#     print(f"Comparison result saved to {comparison_file}")


# def calculate_performance_difference(metrics1: dict, metrics2: dict) -> dict:
#     """Calculate differences between performance metrics.
    
#     Args:
#         metrics1: First set of performance metrics.
#         metrics2: Second set of performance metrics.
    
#     Returns:
#         Dictionary containing calculated differences.
#     """
#     return {
#         key: {
#             "absolute": metrics2.get(key, 0) - metrics1.get(key, 0),
#             "relative": (metrics2.get(key, 0) - metrics1.get(key, 0)) / 
#                        metrics1.get(key, 1) * 100 if metrics1.get(key, 0) != 0 else 0
#         }
#         for key in set(metrics1.keys()).union(metrics2.keys())
#     }


# def main() -> None:
#     """Command-line interface for performance analysis tool."""
#     parser = argparse.ArgumentParser(
#         description="Python Code Performance Analysis Tool",
#         formatter_class=argparse.ArgumentDefaultsHelpFormatter
#     )
#     parser.add_argument(
#         "file_path",
#         type=str,
#         help="Path to the Python script to analyze"
#     )
#     parser.add_argument(
#         "--mode",
#         choices=["function", "line"],
#         default="function",
#         help="Analysis granularity level"
#     )
#     parser.add_argument(
#         "--output",
#         type=str,
#         default="result.json",
#         help="Output file for analysis results"
#     )
#     parser.add_argument(
#         "--generate-flamegraph",
#         action="store_true",
#         help="Generate flame graph visualization"
#     )
#     parser.add_argument(
#         "--generate-callgraph",
#         action="store_true",
#         help="Generate call graph visualization"
#     )
#     parser.add_argument(
#         "--output-path",
#         type=str,
#         default="results",
#         help="Output directory for generated files"
#     )
#     parser.add_argument(
#         "--save-data",
#         action="store_true",
#         help="Save performance metrics to file"
#     )
#     parser.add_argument(
#         "--compare-data",
#         type=str,
#         help="Compare with another performance data file"
#     )
#     parser.add_argument(
#         "--generate-report",
#         action="store_true",
#         help="Generate HTML performance report"
#     )
#     parser.add_argument(
#         "--generate-trend",
#         action="store_true",
#         help="Generate performance trend chart"
#     )
#     parser.add_argument(
#         "--data-files",
#         nargs="+",
#         help="List of performance data files for reporting"
#     )
    
#     args = parser.parse_args()
    
#     try:
#         # Ensure output directory exists
#         os.makedirs(args.output_path, exist_ok=True)
        
#         # Initialize analyzer
#         analyzer = PerformanceAnalyzer()
        
#         # Perform analysis
#         result = analyzer.analyze_file(args.file_path, args.mode)
#         result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
#         # Save results
#         with open(args.output, "w") as f:
#             json.dump(result, f, indent=4)
#         print(f"Analysis completed. Results saved to {args.output}")
        
#         # Generate visualizations
#         if args.generate_flamegraph:
#             generate_flamegraph(args.file_path, args.output_path)
        
#         if args.generate_callgraph:
#             generate_callgraph(args.output, args.output_path)
        
#         # Save performance data
#         if args.save_data:
#             save_performance_data(
#                 os.path.join(args.output_path, "performance_data.json"),
#                 result
#             )
        
#         # Compare data
#         if args.compare_data:
#             compare_performance_data(
#                 args.output,
#                 args.compare_data,
#                 args.output_path
#             )
        
#         # Generate reports
#         if args.generate_report and args.data_files:
#             generate_performance_report(args.data_files, args.output_path)
        
#         if args.generate_trend and args.data_files:
#             generate_performance_trend(args.data_files, args.output_path)
    
#     except Exception as e:
#         print(f"Error: {str(e)}")
#         exit(1)


# if __name__ == "__main__":
#     main()
