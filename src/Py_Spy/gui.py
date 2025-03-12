import random
import tkinter as tk
from tkinter import ttk, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
from profiler import PerformanceAnalyzer


class PerformanceGUI:
    def __init__(self, master):
        self.master = master
        master.title("Python performance analysis tool")
        master.geometry("1200x800")

        # Initialize performance analyzer
        self.analyzer = PerformanceAnalyzer()
        self.current_data = None

        # Create UI components
        self.create_widgets()

    def create_widgets(self):
        # Top control panel
        control_frame = ttk.Frame(self.master)
        control_frame.pack(pady=10, fill=tk.X)

        # File selection
        self.file_path = tk.StringVar()
        ttk.Button(control_frame, text="Choose file: ", command=self.select_file).pack(side=tk.LEFT, padx=5)
        ttk.Entry(control_frame, textvariable=self.file_path, width=50).pack(side=tk.LEFT, padx=5)

        # Analysis mode selection
        self.mode_var = tk.StringVar(value="function")
        ttk.Combobox(control_frame, textvariable=self.mode_var,
                     values=["function", "line"], state="readonly").pack(side=tk.LEFT, padx=5)

        # Analysis button
        ttk.Button(control_frame, text="Start analyzing", command=self.run_analysis).pack(side=tk.LEFT, padx=5)

        # Result display area
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Flame graph tab
        self.flame_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.flame_frame, text="Flame graph")
        self.setup_flame_graph()

        # Raw data tab
        self.raw_data_text = tk.Text(self.notebook)
        self.notebook.add(self.raw_data_text, text="Original data")

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Python file", "*.py")])
        if file_path:
            self.file_path.set(file_path)

    def run_analysis(self):
        file_path = self.file_path.get()
        mode = self.mode_var.get()

        if not file_path:
            return

        try:
            # Execute performance analysis
            result = self.analyzer.analyze_file(file_path, mode)
            self.current_data = result

            # Update raw data display
            self.raw_data_text.delete(1.0, tk.END)
            self.raw_data_text.insert(tk.END, json.dumps(result, indent=4, ensure_ascii=False))

            # Update flame graph
            self.update_flame_graph()

        except Exception as e:
            self.raw_data_text.insert(tk.END, f"Analysis error: {str(e)}")

    def setup_flame_graph(self):
        # Create Matplotlib canvas
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.flame_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # def update_flame_graph(self):
    #     if self.current_data is None:
    #         return
    #
    #     self.ax.clear()
    #
    #     # Build mapping of functions to total runtime from analysis results
    #     func_times = {item["function"]: item["total_time"] for item in self.current_data["results"]}
    #
    #     # Define root nodes as chains with length 1
    #     root_chains = [cc["chain"] for cc in self.current_data["call_chains"] if len(cc["chain"]) == 1]
    #     if not root_chains:
    #         return
    #
    #     # Calculate overall total time as sum of root node runtimes
    #     overall_total = sum(func_times.get(chain[0], 0) for chain in root_chains)

        # Helper function to generate random warm colors
        def get_random_warm_color():
            r = random.randint(200, 255)
            g = random.randint(100, 200)
            b = random.randint(0, 100)
            return f"#{r:02x}{g:02x}{b:02x}"

        # Recursive function to plot flame graph
        def plot_chain(chain, x_start, depth, parent_total, parent_width):
            func = chain[-1]
            f_time = func_times.get(func, 0)
            width = (f_time / parent_total) * parent_width if parent_total > 0 else 0
            color = get_random_warm_color()
            # Use align='edge' to ensure consistent height and no gaps
            self.ax.barh(depth, width, left=x_start, height=1, color=color, edgecolor='white', align='edge')
            if width > 0.02:
                percent = (f_time / overall_total) * 100
                # Display function name and percentage in each block
                self.ax.text(x_start + width / 2, depth + 0.5, f"{func} ({percent:.1f}%)",
                             ha='center', va='center', fontsize=8, color='white')
            # Find direct child calls
            child_chains = [cc["chain"] for cc in self.current_data["call_chains"]
                            if len(cc["chain"]) == len(chain) + 1 and cc["chain"][:len(chain)] == chain]
            child_x = x_start
            for child_chain in child_chains:
                child_func = child_chain[-1]
                child_time = func_times.get(child_func, 0)
                child_width = (child_time / f_time) * width if f_time > 0 else 0
                plot_chain(child_chain, child_x, depth + 1, f_time, width)
                child_x += child_width

        # Draw root nodes at the bottom (depth=0)
        x_cursor = 0
        for chain in root_chains:
            func = chain[0]
            f_time = func_times.get(func, 0)
            # Root node width is proportional to its runtime
            root_width = (f_time / overall_total)
            plot_chain(chain, x_cursor, 0, overall_total, 1)
            x_cursor += root_width

        # Set x-axis to display runtime percentage (0~1)
        self.ax.set_xlim(0, 1)
        # Set y-axis range based on maximum call depth
        max_depth = max(len(chain) for chain in self.current_data["call_chains"])
        self.ax.set_ylim(0, max_depth)
        self.ax.set_xlabel("Run-time ratio")
        self.ax.set_ylabel("Stack depth")
        # Do not invert y-axis to keep root nodes at the bottom
        self.canvas.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = PerformanceGUI(root)
    root.mainloop()
