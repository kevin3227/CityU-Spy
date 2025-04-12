"""Performance visualization tools.

This module provides functions for generating various performance visualizations
including flame graphs, call graphs, performance reports, and trend analysis.
"""

import json
import os
import subprocess
import matplotlib.pyplot as plt
from datetime import datetime


def generate_flamegraph(file_path: str, output_path: str) -> None:
    """Generate a flame graph visualization using pyflame.

    Args:
        file_path: Path to the Python script to analyze.
        output_path: Directory where the flame graph will be saved.

    Raises:
        subprocess.CalledProcessError: If pyflame command fails.
        FileNotFoundError: If the input file doesn't exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")
    
    subprocess.run(["pyflame", "-o", f"{output_path}/flamegraph.svg", file_path], check=True)
    print(f"Flame graph generated at {output_path}/flamegraph.svg")


def generate_callgraph(file_path: str, output_path: str) -> None:
    """Generate a call graph visualization using gprof2dot and Graphviz.

    Args:
        file_path: Path to the profiling data file.
        output_path: Directory where the call graph will be saved.

    Raises:
        subprocess.CalledProcessError: If gprof2dot or dot commands fail.
        FileNotFoundError: If the input file doesn't exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")
    
    subprocess.run([
        "gprof2dot", "-f", "pstats", file_path, 
        "-o", f"{output_path}/callgraph.dot"
    ], check=True)
    subprocess.run([
        "dot", "-Tpng", f"{output_path}/callgraph.dot", 
        "-o", f"{output_path}/callgraph.png"
    ], check=True)
    print(f"Call graph generated at {output_path}/callgraph.png")


def generate_performance_report(file_list: list, output_path: str) -> None:
    """Generate an HTML performance comparison report.

    Args:
        file_list: List of paths to performance data files.
        output_path: Directory where the report will be saved.
    """
    report_file = os.path.join(output_path, "performance_report.html")
    
    with open(report_file, "w") as f:
        f.write("""<html>
        <head>
            <title>Performance Report</title>
            <style>
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                th { background-color: #4CAF50; color: white; }
            </style>
        </head>
        <body>
            <h1>Performance Report</h1>
            <table>
                <tr>
                    <th>File</th>
                    <th>Timestamp</th>
                    <th>Mode</th>
                    <th>Performance Metrics</th>
                </tr>""")
        
        for file in file_list:
            with open(file, "r") as data_file:
                data = json.load(data_file)
                f.write(f"""
                <tr>
                    <td>{os.path.basename(file)}</td>
                    <td>{data.get('timestamp', 'N/A')}</td>
                    <td>{data.get('mode', 'N/A')}</td>
                    <td>{json.dumps(data.get('performance', {}), indent=2)}</td>
                </tr>""")
        
        f.write("</table></body></html>")
    print(f"Performance report generated at {report_file}")


def generate_performance_trend(file_list: list, output_path: str) -> None:
    """Generate a performance trend visualization.

    Args:
        file_list: List of paths to performance data files.
        output_path: Directory where the trend chart will be saved.
    """
    dates = []
    performance_values = []
    
    for file in file_list:
        with open(file, "r") as data_file:
            data = json.load(data_file)
            dates.append(datetime.strptime(
                data["timestamp"], "%Y-%m-%d %H:%M:%S"
            ))
            # Use total execution time as performance metric
            performance_values.append(
                data.get("performance", {}).get("total_time", 0)
            )
    
    plt.figure(figsize=(12, 6))
    plt.plot(dates, performance_values, marker="o", linestyle="-")
    plt.xlabel("Date")
    plt.ylabel("Total Execution Time (seconds)")
    plt.title("Performance Trend Over Time")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    trend_file = os.path.join(output_path, "performance_trend.png")
    plt.savefig(trend_file, dpi=300)
    plt.close()
    print(f"Performance trend chart generated at {trend_file}")