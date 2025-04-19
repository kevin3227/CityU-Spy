#!/usr/bin/env python3
"""
CLI module for Py-Spy performance analysis tool.

This module provides a command line interface for analyzing Python code performance,
including function-level timing, line-level profiling, and memory usage analysis.
"""

import argparse
import json
import os
import sys
from typing import Optional, Dict, Any

from profiler import PerformanceAnalyzer


class PySpyCLI:
    """Command Line Interface for Py-Spy performance analysis tool."""

    def __init__(self):
        self.parser = self._create_parser()
        self.args = None
        self.analyzer = None

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create and configure the argument parser."""
        parser = argparse.ArgumentParser(
            prog="py-spy",
            description="Python Code Performance Analysis Tool",
            epilog="Visit https://github.com/kevin3227/Py-Spy for more information."
        )

        # Required arguments
        parser.add_argument(
            "file_path",
            type=str,
            help="Path to the Python file to analyze"
        )

        # Analysis modes
        parser.add_argument(
            "-m", "--mode",
            choices=["function", "line", "memory", "all"],
            default="function",
            help="Analysis mode (default: function)"
        )

        # Output options
        parser.add_argument(
            "-o", "--output",
            type=str,
            help="Output file path for saving results"
        )

        parser.add_argument(
            "--format",
            choices=["json", "text", "html"],
            default="json",
            help="Output format (default: json)"
        )

        # Analysis options
        parser.add_argument(
            "--multithread",
            action="store_true",
            help="Enable multithread analysis"
        )

        parser.add_argument(
            "--fine-grained",
            action="store_true",
            help="Enable fine-grained sampling (more precise but slower)"
        )

        # Visualization options
        parser.add_argument(
            "--flamegraph",
            action="store_true",
            help="Generate flamegraph visualization"
        )

        parser.add_argument(
            "--callgraph",
            action="store_true",
            help="Generate call graph visualization"
        )

        return parser

    def validate_args(self) -> bool:
        """Validate command line arguments."""
        if not os.path.exists(self.args.file_path):
            print(f"Error: File not found - {self.args.file_path}", file=sys.stderr)
            return False
            
        if not self.args.file_path.endswith('.py'):
            print("Error: Input file must be a Python file (.py)", file=sys.stderr)
            return False
            
        return True

    def run_analysis(self) -> Optional[Dict[str, Any]]:
        """Run the performance analysis based on command line arguments."""
        try:
            self.analyzer = PerformanceAnalyzer(
                mthread=self.args.multithread,
                fine_grained=self.args.fine_grained
            )

            if self.args.mode == "all":
                # Run all analysis modes
                results = {
                    "function": self.analyzer.analyze_file(self.args.file_path, "function"),
                    "line": self.analyzer.analyze_file(self.args.file_path, "line"),
                    "memory": self.analyzer.analyze_file(self.args.file_path, "memory")
                }
            else:
                # Run single analysis mode
                results = self.analyzer.analyze_file(self.args.file_path, self.args.mode)

            return results
        except Exception as e:
            print(f"Analysis failed: {str(e)}", file=sys.stderr)
            return None

    def format_results(self, results: Dict[str, Any]) -> str:
        """Format analysis results based on requested output format."""
        if self.args.format == "json":
            return json.dumps(results, indent=4)
        elif self.args.format == "text":
            return self._format_text(results)
        elif self.args.format == "html":
            return self._format_html(results)
        return ""

    def _format_text(self, results: Dict[str, Any]) -> str:
        """Format results as human-readable text."""
        output = []
        
        if isinstance(results, dict) and "mode" in results:
            # Single mode results
            output.append(self._format_single_mode_text(results))
        elif isinstance(results, dict):
            # Multiple mode results ("all" mode)
            for mode, result in results.items():
                output.append(f"=== {mode.upper()} ANALYSIS ===")
                output.append(self._format_single_mode_text(result))
                output.append("")
        
        return "\n".join(output)

    def _format_single_mode_text(self, result: Dict[str, Any]) -> str:
        """Format single analysis mode results as text."""
        output = []
        mode = result.get("mode", "unknown")
        file_path = result.get("file", "unknown")
        
        output.append(f"Performance Analysis Report ({mode} mode)")
        output.append(f"File: {file_path}")
        output.append("=" * 80)
        
        if mode == "function":
            output.append("Function-Level Performance:")
            output.append("{:<30} {:<10} {:<12} {:<12} {}".format(
                "Function", "Calls", "Total Time", "Avg Time", "Line"
            ))
            output.append("-" * 80)
            
            for func in result.get("results", []):
                output.append("{:<30} {:<10} {:<12.6f} {:<12.6f} {}".format(
                    func.get("function", ""),
                    func.get("calls", 0),
                    func.get("total_time", 0),
                    func.get("average_time", 0),
                    func.get("line_number", "")
                ))
                
            if "call_chains" in result:
                output.append("\nCall Chains:")
                for chain in result["call_chains"]:
                    output.append(f"  {' -> '.join(chain.get('chain', []))} "
                                f"[{chain.get('count', 0)} calls, "
                                f"{chain.get('percentage', 0):.2f}%]")
        
        elif mode == "line":
            output.append("Line-Level Performance:")
            output.append("{:<6} {:<15} {:<15} {:<20} {:<10} {}".format(
                "Line", "Time (s)", "Percent", "Function", "Code"
            ))
            output.append("-" * 80)
            
            for line in result.get("results", []):
                code_preview = line.get("code", "")[:40]
                if len(code_preview) >= 40:
                    code_preview += "..."
                
                output.append("{:<6} {:<15.6f} {:<15.2f}% {:<20} {}".format(
                    line.get("line_number", ""),
                    line.get("time", 0),
                    line.get("percent", 0),
                    line.get("function", ""),
                    code_preview
                ))
        
        elif mode == "memory":
            output.append("Memory Usage Analysis:")
            for func in result.get("results", []):
                output.append(f"\nFunction: {func.get('function', '')}")
                output.append("{:<8} {:<15} {:<15} {:<12} {}".format(
                    "Line", "Mem Usage", "Increment", "Calls", "Code"
                ))
                output.append("-" * 80)
                
                for mem in func.get("memory_usage", []):
                    code_preview = mem.get("Line Contents", "")[:30]
                    output.append("{:<8} {:<15} {:<15} {:<12} {}".format(
                        mem.get("Line", ""),
                        mem.get("Mem usage", ""),
                        mem.get("Increment", ""),
                        mem.get("Occurrences", ""),
                        code_preview
                    ))
        
        return "\n".join(output)

    def _format_html(self, results: Dict[str, Any]) -> str:
        """Format results as HTML."""
        # This would be expanded to create a full HTML report
        # For now, just wrap the JSON in HTML tags
        return f"""
        <html>
        <head><title>Py-Spy Performance Report</title></head>
        <body>
            <pre>{json.dumps(results, indent=4)}</pre>
        </body>
        </html>
        """

    def generate_visualizations(self, results: Dict[str, Any]) -> None:
        """Generate requested visualizations."""
        if self.args.output:
            base_name = os.path.splitext(self.args.output)[0]
        else:
            base_name = os.path.splitext(self.args.file_path)[0]
        
        if self.args.flamegraph:
            if self.analyzer and hasattr(self.analyzer, 'save_to_flamegraph_file'):
                flame_path = f"{base_name}_flamegraph.txt"
                self.analyzer.save_to_flamegraph_file(flame_path)
                print(f"Flamegraph data saved to {flame_path}")
            
            # Here you would add code to convert the flamegraph data to an image
            # This might involve calling external tools like FlameGraph.pl
            
        if self.args.callgraph:
            callgraph_path = f"{base_name}_callgraph.png"
            print(f"Call graph would be saved to {callgraph_path}")
            # Actual call graph generation code would go here

    def save_results(self, output: str) -> None:
        """Save results to output file if specified."""
        if self.args.output:
            try:
                with open(self.args.output, 'w') as f:
                    f.write(output)
                print(f"Results saved to {self.args.output}")
            except IOError as e:
                print(f"Error saving results: {str(e)}", file=sys.stderr)

    def run(self) -> None:
        """Run the CLI application."""
        self.args = self.parser.parse_args()
        
        if not self.validate_args():
            sys.exit(1)
            
        results = self.run_analysis()
        if not results:
            sys.exit(1)
            
        formatted_output = self.format_results(results)
        print(formatted_output)
        
        if self.args.output:
            self.save_results(formatted_output)
            
        if self.args.flamegraph or self.args.callgraph:
            self.generate_visualizations(results)


def main():
    """Entry point for the CLI application."""
    cli = PySpyCLI()
    cli.run()


if __name__ == "__main__":
    main()

