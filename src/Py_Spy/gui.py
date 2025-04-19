import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from profiler import PerformanceAnalyzer
from collections import defaultdict
import ast
from typing import Dict, List, Any, Optional, Callable
from recommender import ASTVisitor, RuleManager, CustomRuleBuilder

class PerformanceGUI:
    def __init__(self, master):
        self.master = master
        master.title("CityU-Spy —— Python performance analysis tool")
        master.geometry("1000x600")
        # Bind the "X" button (window close) event
        self.master.protocol("WM_DELETE_WINDOW", self.close_application)
        # Initialize performance analyzer
        self.analyzer = None
        self.current_data = None
        self.source_code_text = None
        self.result_text = None
        self.hover_text = None
        self.function_rects = []
        # Rule Manager
        self.rule_manager = RuleManager()
        # Create UI components
        self.create_widgets()

    def create_widgets(self):
        # Top control panel
        control_frame = ttk.Frame(self.master)
        control_frame.pack(pady=10, fill=tk.X)

        # Settings button
        ttk.Button(control_frame, text="⚙️", command=self.open_settings_dialog, width=2).pack(side=tk.LEFT, padx=5)

        # File selection
        self.file_path = tk.StringVar()
        ttk.Button(control_frame, text="Choose file: ", command=self.select_file).pack(side=tk.LEFT, padx=5)
        ttk.Entry(control_frame, textvariable=self.file_path, width=30).pack(side=tk.LEFT, padx=5)

        # Analysis mode selection
        self.mode_var = tk.StringVar(value="function")
        mode_combobox = ttk.Combobox(control_frame, textvariable=self.mode_var, width=10,
                                    values=["function", "line", "memory"], state="readonly")
        mode_combobox.pack(side=tk.LEFT, padx=5)
        mode_combobox.bind("<<ComboboxSelected>>", self.update_tab_layout)

        # Options for analysis
        self.mthread_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(control_frame, text="Multithreaded", variable=self.mthread_var).pack(side=tk.LEFT, padx=5)
        
        self.fine_grained_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(control_frame, text="Fine-grained", variable=self.fine_grained_var).pack(side=tk.LEFT, padx=5)

        # Analysis button & loading indicator
        self.analyze_button = ttk.Button(control_frame, text="Start", command=self.run_analysis)
        self.analyze_button.pack(side=tk.LEFT, padx=5)
        
        # Add suggestion button
        ttk.Button(control_frame, text="?", command=self.show_optimization_suggestions, 
                width=2).pack(side=tk.LEFT, padx=5)

        # Loading indicator (initially empty)
        self.loading_indicator_frame = ttk.Frame(control_frame)  # Container for loading bar
        self.loading_indicator = None  # Progressbar will be created when needed
        
        # Result display area
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs (will be updated based on mode selection)
        self.setup_tabs()

    def generate_optimization_suggestions(self) -> List[Dict[str, Any]]:
        if not self.current_data or not self.file_path.get():
            return []
        try:
            with open(self.file_path.get(), 'r') as f:
                code = f.read()
        except Exception:
            return []
        
        suggestions = []
        
        try:
            # AST Analysis
            tree = ast.parse(code)
            visitor = ASTVisitor(self.rule_manager)
            visitor.visit(tree)
            suggestions.extend(visitor.suggestions)

            for rule_name, rule in self.rule_manager.get_all_rules().items():
                if self.mode_var.get() == "function":
                    for result in self.current_data["results"]:
                        if not rule.get('is_ast_based', True) and rule["check"](result):
                            suggestions.append({
                                "rule": rule_name,
                                "description": rule["description"],
                                "suggestion": rule["suggestion"],
                                "function": result["function"],
                                "line": result.get("line_number")
                            })
                elif self.mode_var.get() == "line":
                    for result in self.current_data["results"]:
                        if rule_name == "line_optimization" and rule["check"](result):
                            suggestions.append({
                                "rule": rule_name,
                                "description": rule["description"],
                                "suggestion": rule["suggestion"],
                                "function": result["function"],
                                "line": result["line_number"]
                            })
                elif self.mode_var.get() == "memory":
                    for result in self.current_data["results"]:
                        for mem_usage in result["memory_usage"]:
                            if rule_name == "memory_optimization" and rule["check"](mem_usage):
                                suggestions.append({
                                    "rule": rule_name,
                                    "description": rule["description"],
                                    "suggestion": rule["suggestion"],
                                    "function": result["function"],
                                    "line": int(mem_usage["Line"])
                                })
        except SyntaxError as e:
            print(f"Syntax error in code: {e}")
        return suggestions

    def show_optimization_suggestions(self):
        if not self.current_data:
            messagebox.showinfo("No Analysis", "Please run analysis first to get optimization suggestions.")
            return
            
        suggestions = self.generate_optimization_suggestions()
        
        if not suggestions:
            messagebox.showinfo("No Suggestions", "No optimization suggestions found for current analysis.")
            return
            
        # Create a popup window with suggestions
        popup = tk.Toplevel(self.master)
        popup.title("Optimization Suggestions")
        popup.geometry("600x400")
        
        # Create a frame for the suggestions
        frame = ttk.Frame(popup)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create a scrollable text widget
        text = tk.Text(frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Insert suggestions into the text widget
        text.insert(tk.END, f"Found {len(suggestions)} optimization suggestions:\n\n")
        
        for idx, suggestion in enumerate(suggestions, 1):
            text.insert(tk.END, f"Suggestion {idx}:\n")
            text.insert(tk.END, f"Type: {suggestion['rule']}\n")
            text.insert(tk.END, f"Description: {suggestion['description']}\n")
            if 'line' in suggestion and suggestion['line']:
                text.insert(tk.END, f"Line: {suggestion['line']}\n")
            if 'function' in suggestion and suggestion['function']:
                text.insert(tk.END, f"Function: {suggestion['function']}\n")
            text.insert(tk.END, f"Suggestion: {suggestion['suggestion']}\n\n")
        
        # Make the text read-only
        text.config(state=tk.DISABLED)

    def clear_all_data(self):
        """Clear all existing data and visualizations"""
        # Clear current data
        self.current_data = None
        
        # Clear source code display if exists
        if self.source_code_text:
            self.source_code_text.delete(1.0, tk.END)
            self.source_code_text.tag_remove("highlight", "1.0", "end")
        
        # Clear result display if exists
        if self.result_text:
            self.result_text.delete(1.0, tk.END)
        
        # Clear flame graph if exists
        if hasattr(self, 'ax') and self.ax:
            self.ax.clear()
            if hasattr(self, 'canvas'):
                self.canvas.draw()

    def setup_tabs(self):
        # Clear all existing data before switching tabs
        self.clear_all_data()
        
        # Remove all existing tabs
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)

        # Create tabs based on current mode
        if self.mode_var.get() == "function":
            self.setup_function_mode_tabs()
        elif self.mode_var.get() == "memory":
            self.setup_memory_mode_tab()
        else:
            self.setup_line_mode_tab()
        
        # Reload source code if file is selected
        if self.file_path.get():
            self.load_source_code()

    def setup_function_mode_tabs(self):
        # Code/Result tab
        self.code_result_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.code_result_frame, text="Code")
        self.setup_code_result_view()

        # Flame graph tab
        self.flame_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.flame_frame, text="Flame graph")
        self.setup_flame_graph()

    def setup_line_mode_tab(self):
        # Only code/result tab in line mode
        self.code_result_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.code_result_frame, text="Code")
        self.setup_code_result_view()

    def setup_memory_mode_tab(self):
        # Only code/result tab in memory mode
        self.code_result_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.code_result_frame, text="Code")
        self.setup_code_result_view()

    def setup_code_result_view(self):
        # Clear existing widgets if they exist
        if hasattr(self, 'source_code_text') and self.source_code_text:
            self.source_code_text.destroy()
        if hasattr(self, 'result_text') and self.result_text:
            self.result_text.destroy()

        # Create a split view with source code on top and results on bottom
        paned_window = ttk.PanedWindow(self.code_result_frame, orient=tk.VERTICAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        # Top pane - Source code
        source_frame = ttk.Frame(paned_window)
        self.source_code_text = tk.Text(source_frame, wrap="none")
        scroll_y = ttk.Scrollbar(source_frame, orient="vertical", command=self.source_code_text.yview)
        scroll_x = ttk.Scrollbar(source_frame, orient="horizontal", command=self.source_code_text.xview)
        self.source_code_text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.source_code_text.pack(side="left", fill="both", expand=True)
        
        # Bind click event to source code
        self.source_code_text.bind("<Button-1>", self.on_source_code_click)
        
        # Bottom pane - Result display
        result_frame = ttk.Frame(paned_window)
        self.result_text = tk.Text(result_frame, wrap="word")
        result_scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=result_scroll.set)
        result_scroll.pack(side="right", fill="y")
        self.result_text.pack(side="left", fill="both", expand=True)
        
        paned_window.add(source_frame, weight=3)
        paned_window.add(result_frame, weight=2)
        
        if self.file_path.get():
            self.load_source_code()
        else:
            self.display_welcome_message()

    def display_welcome_message(self):
        welcome_message = (
            "Welcome to CityU-Spy — An experimental Python performance analysis tool!\n"
            "\n"
            "Usage:\n"
            "1. Choose a Python file to analyze.\n"
            "2. Select the analysis mode (Function, Line, Memory).\n"
            "3. Optionally configure analysis options (Multithreaded, Fine-grained).\n"
            "4. Click 'Start' to begin the analysis.\n"
            "5. View the results in the 'Code' tab.\n"
            "6. Use the '?' button to see optimization suggestions.\n"
            "\n"
            "Github:kevin3227/CityU-Spy"
        )
        
        self.source_code_text.delete(1.0, tk.END)
        self.source_code_text.insert(tk.END, welcome_message)
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, self._get_ascii_art())

    def _get_ascii_art(self):
        """Returns the ASCII art text for CityU-Spy"""
        return"""
                  ____ _ _         _   _      ____              
                 / ___(_) |_ _   _| | | |    / ___| _ __  _   _ 
                | |   | | __| | | | | | |____\___ \| '_ \| | | |
                | |___| | |_| |_| | |_| |_____|__) | |_) | |_| |
                 \____|_|\__|\__, |\___/     |____/| .__/ \__, |
                             |___/                 |_|    |___/ 
                                     .
                                    ":"
                                  ___:____     |"\/"|
                                ,'        `.    \  /
                                |  O        \___/  |
                ^~^~^~^~^~^~^~^~^~^~^~^~~^~^~^~^~^~^~^~^~^~^~^~^~
    """

    def load_source_code(self):
        try:
            # Clear before loading new content
            self.source_code_text.delete(1.0, tk.END)
            self.source_code_text.tag_remove("highlight", "1.0", "end")
            
            with open(self.file_path.get(), 'r') as f:
                self.source_code_text.insert(tk.END, f.read())
                self.highlight_code_lines()
        except Exception as e:
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"Error loading source code: {str(e)}")

    def highlight_code_lines(self):
        if not self.current_data or not self.source_code_text:
            return
            
        # Clear existing highlights
        self.source_code_text.tag_remove("highlight", "1.0", "end")
        
        mode = self.mode_var.get()
        
        if mode == "function":
            for result in self.current_data["results"]:
                if "line_number" in result:
                    function_name = result["function"]
                    line_num = int(result["line_number"])
                    
                    start_idx = self.source_code_text.index(f"{line_num}.0")
                    end_idx = self.source_code_text.index(f"{line_num + 1}.0")
                    
                    self.source_code_text.tag_add("highlight", start_idx, end_idx)
                    self.source_code_text.tag_config("highlight", background="lightyellow")
        
        elif mode == "line":
            for result in self.current_data["results"]:
                if "line_number" in result:
                    line_num = int(result["line_number"])
                    start_idx = self.source_code_text.index(f"{line_num}.0")
                    end_idx = self.source_code_text.index(f"{line_num + 1}.0")
                    
                    self.source_code_text.tag_add("highlight", start_idx, end_idx)
                    self.source_code_text.tag_config("highlight", background="lightyellow")
        
        elif mode == "memory":
            for result in self.current_data["results"]:
                for mem_usage in result.get("memory_usage", []):
                    line_num = int(mem_usage["Line"])
                    start_idx = self.source_code_text.index(f"{line_num}.0")
                    end_idx = self.source_code_text.index(f"{line_num + 1}.0")
                    
                    self.source_code_text.tag_add("highlight", start_idx, end_idx)
                    self.source_code_text.tag_config("highlight", background="lightyellow")

    def on_source_code_click(self, event):
        if not self.current_data or not self.source_code_text or not self.result_text:
            return
            
        index = self.source_code_text.index(f"@{event.x},{event.y}")
        line_num = int(index.split('.')[0])
        
        # Clear previous results
        self.result_text.delete(1.0, tk.END)
        
        if not self.current_data:
            return
            
        mode = self.mode_var.get()
        
        if mode == "function":
            # Find function containing this line
            for result in self.current_data["results"]:
                if "line_number" in result and int(result["line_number"]) == line_num:
                    self.result_text.insert(tk.END, f"Function: {result['function']}\n\n")
                    for key, value in result.items():
                        if key not in ["function", "line_number"]:
                            self.result_text.insert(tk.END, f"{key.replace('_', ' ').title()}: {value}\n")
                    break
        
        elif mode == "line":
            # Show line-level performance data
            for result in self.current_data["results"]:
                if "line_number" in result and int(result["line_number"]) == line_num:
                    self.result_text.insert(tk.END, f"Line {line_num}\n\n")
                    for key, value in result.items():
                        if key != "line_number":
                            self.result_text.insert(tk.END, f"{key.replace('_', ' ').title()}: {value}\n")
                    break
        
        elif mode == "memory":
            # Show memory usage data for the clicked line
            for result in self.current_data["results"]:
                for mem_usage in result.get("memory_usage", []):
                    if int(mem_usage["Line"]) == line_num:
                        self.result_text.insert(tk.END, f"Line {line_num}\n\n")
                        for key, value in mem_usage.items():
                            self.result_text.insert(tk.END, f"{key.replace('_', ' ').title()}: {value}\n")
                        break

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Python file", "*.py")])
        if file_path:
            self.file_path.set(file_path)
            # Clear existing data before loading new file
            self.clear_all_data()
            if self.source_code_text:
                self.load_source_code()

    def update_tab_layout(self, event=None):
        self.setup_tabs()

    def run_analysis(self):
        file_path = self.file_path.get()
        mode = self.mode_var.get()
        mthread = self.mthread_var.get()
        fine_grained = self.fine_grained_var.get()
        
        if not file_path:
            return  # No file selected, skip analysis

        try:
            # Clear existing results before new analysis
            self.clear_all_data()

            # Disable the analyze button during analysis
            self.analyze_button.config(state=tk.DISABLED)

            # Create and show the loading indicator (Progressbar)
            self.loading_indicator = ttk.Progressbar(
                self.loading_indicator_frame,
                mode="indeterminate",  # Infinite spinning animation
                length=100  # Width in pixels
            )
            self.loading_indicator.pack(side=tk.LEFT, padx=5)  # Place it to the right of the button
            self.loading_indicator_frame.pack(side=tk.LEFT, padx=5)  # Ensure it's visible
            self.loading_indicator.start(10)  # Start animation (speed: smaller = faster)

            # Run analysis in a thread to avoid freezing the UI
            import threading
            def perform_analysis():
                try:
                    self.analyzer = PerformanceAnalyzer(mthread=mthread, fine_grained=fine_grained)
                    self.current_data = self.analyzer.analyze_file(file_path, mode)

                    if mode == "function":
                        self.update_flame_graph()

                    if self.source_code_text:
                        self.load_source_code()
                        self.highlight_code_lines()

                except Exception as e:
                    if self.result_text:
                        self.result_text.delete(1.0, tk.END)
                        self.result_text.insert(tk.END, f"Analysis error: {str(e)}")
                finally:
                    # Stop and hide the loading indicator when analysis is done
                    self.master.after(0, lambda: self.stop_loading_indicator())
                    # Re-enable the analyze button
                    self.master.after(0, lambda: self.analyze_button.config(state=tk.NORMAL))

            # Start the analysis thread
            analysis_thread = threading.Thread(target=perform_analysis)
            analysis_thread.daemon = True  # End when main program exits
            analysis_thread.start()

        except Exception as e:
            # Handle UI errors (not analysis errors)
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"Failed to run analysis: {str(e)}")
            if hasattr(self, 'loading_indicator'):
                self.stop_loading_indicator()

    def stop_loading_indicator(self):
        """Stop and hide the loading indicator"""
        if hasattr(self, 'loading_indicator'):
            self.loading_indicator.stop()
            self.loading_indicator.pack_forget()  # Hide it
        self.loading_indicator_frame.pack_forget()  # Hide the container

    def _get_function_color(self, func_name):
        """Generate a consistent color for each function based on its name hash"""
        if not hasattr(self, '_color_map'):
            self._color_map = {}
        
        if func_name not in self._color_map:
            # Generate warm tones: R > G > B
            r = random.uniform(0.6, 1.0)  # Red component higher
            g = random.uniform(0.3, 0.6)  # Green component moderate
            b = random.uniform(0.0, 0.3)  # Blue component lower
            self._color_map[func_name] = (r, g, b)
        return self._color_map[func_name]

    def _build_flame_data(self):
        """Process profiler results to build the data structure for flame graph generation"""
        if not self.current_data or "call_chains" not in self.current_data:
            return None, 0

        call_chains = self.current_data["call_chains"]
        if not call_chains:
            return None, 0

        # Initialize flame graph data structure
        flame_data = defaultdict(lambda: {'count': 0, 'children': defaultdict(lambda: None)})
        total_percentage = sum(chain.get('percentage', 0) for chain in call_chains)

        for chain_data in call_chains:
            chain = chain_data["chain"]
            percentage = chain_data.get("percentage", 0)
            if percentage <= 0:
                continue

            # Traverse the call chain and build the flame data structure
            current_level = flame_data
            for func in chain:
                if current_level[func] is None:
                    current_level[func] = {'count': 0, 'children': defaultdict(lambda: None)}
                current_level[func]['count'] += percentage
                current_level = current_level[func]['children']

        return flame_data, total_percentage if total_percentage > 0 else 100.0

    def _draw_flame_recursive(self, data, level, start_x, total_width):
        """Recursively draw the flame graph from the processed data"""
        current_x = start_x
        for func_name, node_data in sorted(data.items(), key=lambda x: -x[1]['count']):
            if node_data is None:
                continue
                
            width = node_data['count']
            color = self._get_function_color(func_name)
            
            # Draw the rectangle
            rect = plt.Rectangle(
                (current_x, level),
                width,
                1,
                color=color,
                edgecolor='white'
            )
            self.ax.add_patch(rect)
            
            # Store info for tooltips
            self.function_rects.append({
                "rect": rect,
                "func": func_name,
                "percentage": width/total_width*100,
                "x_start": current_x,
                "depth": level,
                "width": width
            })
            
            # Add text label if there's enough space
            if width/total_width > 0.05:
                text_color = 'black' if (color[0]*0.299 + color[1]*0.587 + color[2]*0.114) > 0.6 else 'white'
                self.ax.text(
                    current_x + width/2,
                    level + 0.5,
                    func_name,
                    ha='center',
                    va='center',
                    color=text_color,
                    fontsize=8
                )
            
            # Recursively draw children
            if node_data['children']:
                self._draw_flame_recursive(node_data['children'], level + 1, current_x, total_width)
            
            current_x += width

    def setup_flame_graph(self):
        # Clear existing flame graph if it exists
        if hasattr(self, 'fig'):
            plt.close(self.fig)
        
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        
        # Clear existing canvas if it exists
        if hasattr(self, 'canvas'):
            self.canvas.get_tk_widget().destroy()
            
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.flame_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        # Initialize hover text
        self.hover_text = self.ax.text(0, 0, "", 
                                     va="bottom", ha="center",
                                     bbox=dict(boxstyle="round,pad=0.5", 
                                              fc="yellow", alpha=0.8),
                                     zorder=10)
        self.hover_text.set_visible(False)
        # Connect mouse events
        self.canvas.mpl_connect('motion_notify_event', self._on_flame_motion)
        self.canvas.mpl_connect('axes_leave_event', self._on_flame_leave)

    def update_flame_graph(self):
        if self.current_data is None or "call_chains" not in self.current_data:
            return
        self.ax.clear()
        self.function_rects = []
        
        flame_data, total_width = self._build_flame_data()
        if not flame_data:
            return
            
        self._draw_flame_recursive(flame_data, 0, 0.0, total_width)
        
        # Configure axes
        max_depth = max([r['depth'] for r in self.function_rects]) if self.function_rects else 0
        self.ax.set_xlim(0, total_width)
        self.ax.set_ylim(0, max_depth + 1)
        self.ax.set_xlabel("Time Percentage")
        self.ax.set_ylabel("Stack Depth")
        self.ax.set_title("Function Call Flame Graph")
        
        # Hide Y axis ticks
        self.ax.set_yticks([])
        
        # Reinitialize hover text after clearing the axes
        self.hover_text = self.ax.text(0, 0, "", 
                                     va="bottom", ha="center",
                                     bbox=dict(boxstyle="round,pad=0.5", 
                                              fc="yellow", alpha=0.8),
                                     zorder=10)
        self.hover_text.set_visible(False)
        
        self.canvas.draw()

    def _on_flame_motion(self, event):
        """Handle mouse movement over the flame graph"""
        if not hasattr(self, 'function_rects') or event.inaxes != self.ax:
            self.hover_text.set_visible(False)
            self.canvas.draw_idle()
            return
        
        # Find which rectangle the mouse is over
        for rect_info in self.function_rects:
            rect = rect_info["rect"]
            if (rect_info["x_start"] <= event.xdata <= rect_info["x_start"] + rect_info["width"] and
                rect_info["depth"] <= event.ydata <= rect_info["depth"] + 1):
                
                # Show hover text
                x = rect_info["x_start"] + rect_info["width"]/2
                y = rect_info["depth"] + 0.5
                
                perc_text = f"{rect_info['percentage']:.1f}%" 
                self.hover_text.set_text(f"{rect_info['func']}\n{perc_text}")
                self.hover_text.set_position((x, y))
                self.hover_text.set_visible(True)
                break
        else:
            self.hover_text.set_visible(False)
            
        self.canvas.draw_idle()

    def _on_flame_leave(self, event):
        """Handle when mouse leaves axes"""
        self.hover_text.set_visible(False)
        self.canvas.draw_idle()

    def close_application(self):
        """Gracefully close the application."""
        self.master.quit()
        self.master.destroy()

    def open_settings_dialog(self):
        """Open the settings dialog for rule management."""
        settings_dialog = tk.Toplevel(self.master)
        settings_dialog.title("Rules Management")
        settings_dialog.geometry("600x300")
        
        # Main container
        main_frame = ttk.Frame(settings_dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Rule type selection
        ttk.Label(control_frame, text="Rule Type:").pack(side=tk.LEFT)
        self.rule_type_var = tk.StringVar(value="AST")
        ttk.Combobox(control_frame, textvariable=self.rule_type_var, 
                    values=["AST", "Non-AST"], state="readonly", width=8).pack(side=tk.LEFT, padx=5)
        
        # Action buttons
        ttk.Button(control_frame, text="Add Rule", command=self.add_rule).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Edit Rule", command=self.edit_rule).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Delete Rule", command=self.delete_rule).pack(side=tk.LEFT, padx=5)
        
        # Rules list with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.rules_listbox = tk.Listbox(list_frame, height=20)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.rules_listbox.yview)
        self.rules_listbox.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.rules_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Populate the listbox
        self.update_rules_list()
        
        # Close button
        ttk.Button(main_frame, text="Close", command=settings_dialog.destroy).pack(pady=(10, 0))

    def update_rules_list(self):
        """Update the rules listbox with all available rules."""
        self.rules_listbox.delete(0, tk.END)
        
        for name, rule in self.rule_manager.get_all_rules().items():
            rule_type = "AST" if rule.get('is_ast_based', True) else "Non-AST"
            self.rules_listbox.insert(tk.END, f"{name} ({rule_type}): {rule['description']}")

    def add_rule(self):
        """Add a new rule of the selected type."""
        rule_type = self.rule_type_var.get()
        is_ast_based = (rule_type == "AST")
        
        rule_dialog = tk.Toplevel(self.master)
        rule_dialog.title(f"Add {rule_type} Rule")
        rule_dialog.geometry("500x400")
        
        # Rule fields
        ttk.Label(rule_dialog, text="Rule Name:").grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        name_var = tk.StringVar()
        ttk.Entry(rule_dialog, textvariable=name_var, width=40).grid(row=0, column=1, padx=10, pady=5)
        
        ttk.Label(rule_dialog, text="Description:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        desc_var = tk.StringVar()
        ttk.Entry(rule_dialog, textvariable=desc_var, width=40).grid(row=1, column=1, padx=10, pady=5)
        
        ttk.Label(rule_dialog, text="Suggestion:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        sugg_var = tk.StringVar()
        ttk.Entry(rule_dialog, textvariable=sugg_var, width=40).grid(row=2, column=1, padx=10, pady=5)
        
        ttk.Label(rule_dialog, text="Check Condition:").grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
        cond_var = tk.StringVar()
        cond_entry = ttk.Entry(rule_dialog, textvariable=cond_var, width=40)
        cond_entry.grid(row=3, column=1, padx=10, pady=5)
        
        # Additional field for AST rules
        node_var = tk.StringVar()
        if is_ast_based:
            ttk.Label(rule_dialog, text="AST Node Type (optional):").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
            ttk.Entry(rule_dialog, textvariable=node_var, width=40).grid(row=4, column=1, padx=10, pady=5)
        
        def submit_rule():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Error", "Rule name cannot be empty")
                return
            
            if name in self.rule_manager.get_all_rules():
                messagebox.showwarning("Error", f"Rule '{name}' already exists")
                return
            
            if not cond_var.get().strip():
                messagebox.showwarning("Error", "Check condition cannot be empty")
                return
            
            try:
                if is_ast_based:
                    rule = CustomRuleBuilder.build_ast_rule(
                        check_condition=cond_var.get(),
                        description=desc_var.get(),
                        suggestion=sugg_var.get(),
                        node_type=node_var.get() if node_var.get().strip() else None
                    )
                else:
                    rule = CustomRuleBuilder.build_non_ast_rule(
                        check_condition=cond_var.get(),
                        description=desc_var.get(),
                        suggestion=sugg_var.get()
                    )
                
                self.rule_manager.add_rule(
                    name,
                    rule['description'],
                    rule['check'],
                    rule['suggestion'],
                    rule['is_ast_based']
                )
                
                self.update_rules_list()
                rule_dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create rule: {str(e)}")
        
        ttk.Button(rule_dialog, text="Submit", command=submit_rule).grid(
            row=5 if is_ast_based else 4, 
            column=0, columnspan=2, pady=10
        )

    def edit_rule(self):
        """Edit an existing rule with direct lambda expression editing."""
        selected_index = self.rules_listbox.curselection()
        if not selected_index:
            messagebox.showwarning("No Selection", "Please select a rule to edit")
            return
        
        selected_text = self.rules_listbox.get(selected_index[0])
        rule_name = selected_text.split(" (")[0]
        rule = self.rule_manager.get_all_rules()[rule_name]
        
        rule_type = "AST" if rule.get('is_ast_based', True) else "Non-AST"
        is_ast_based = (rule_type == "AST")
        
        rule_dialog = tk.Toplevel(self.master)
        rule_dialog.title(f"Edit {rule_type} Rule")
        rule_dialog.geometry("600x275")
        
        # Rule fields in a grid layout
        frame = ttk.Frame(rule_dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Rule name (readonly)
        ttk.Label(frame, text="Rule Name:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Label(frame, text=rule_name).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Description
        ttk.Label(frame, text="Description:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        desc_entry = ttk.Entry(frame, width=50)
        desc_entry.insert(0, rule['description'])
        desc_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Suggestion
        ttk.Label(frame, text="Suggestion:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        sugg_entry = ttk.Entry(frame, width=50)
        sugg_entry.insert(0, rule['suggestion'])
        sugg_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Check condition - use Text widget for multiline editing
        ttk.Label(frame, text="Check Condition:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.NW)
        cond_text = tk.Text(frame, wrap=tk.WORD, width=50, height=6)
        cond_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=cond_text.yview)
        cond_text.configure(yscrollcommand=cond_scroll.set)
        
        # Get the lambda source code
        lambda_src = self.get_lambda_source(rule['check'])
        cond_text.insert("1.0", lambda_src)
        cond_text.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
        cond_scroll.grid(row=3, column=2, sticky=tk.NS)
        
        # Node type for AST rules
        node_var = tk.StringVar()
        if is_ast_based:
            ttk.Label(frame, text="AST Node Type (optional):").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
            node_entry = ttk.Entry(frame, textvariable=node_var, width=50)
            
            # Try to extract node type from lambda
            node_type = self.extract_node_type(rule['check'])
            if node_type:
                node_var.set(node_type)
                
            node_entry.grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Submit button
        def submit_edit():
            try:
                # Get the edited values
                new_desc = desc_entry.get()
                new_sugg = sugg_entry.get()
                new_cond = cond_text.get("1.0", tk.END).strip()
                
                # Remove any lambda prefix if present
                if new_cond.startswith("lambda stats:"):
                    new_cond = new_cond.split(':', 1)[1].strip()
                elif new_cond.startswith("lambda node:"):
                    new_cond = new_cond.split(':', 1)[1].strip()
                
                # Remove the old rule
                self.rule_manager.remove_rule(rule_name)
                
                # Convert condition text back to function
                if is_ast_based:
                    node_type = node_var.get() if node_var.get().strip() else None
                    new_rule = CustomRuleBuilder.build_ast_rule(
                        check_condition=new_cond,
                        description=new_desc,
                        suggestion=new_sugg,
                        node_type=node_type
                    )
                else:
                    new_rule = CustomRuleBuilder.build_non_ast_rule(
                        check_condition=new_cond,
                        description=new_desc,
                        suggestion=new_sugg
                    )
                
                # Add the new rule
                self.rule_manager.add_rule(
                    rule_name,
                    new_rule['description'],
                    new_rule['check'],
                    new_rule['suggestion'],
                    new_rule['is_ast_based']
                )
                
                self.update_rules_list()
                rule_dialog.destroy()
                messagebox.showinfo("Success", "Rule updated successfully")
                
            except Exception as e:
                # Restore original rule if update failed
                if rule_name not in self.rule_manager.get_all_rules():
                    self.rule_manager.add_rule(
                        rule_name,
                        rule['description'],
                        rule['check'],
                        rule['suggestion'],
                        rule['is_ast_based']
                    )
                messagebox.showerror("Error", f"Failed to update rule: {str(e)}")
        
        submit_btn = ttk.Button(frame, text="Save Changes", command=submit_edit)
        submit_btn.grid(row=5 if is_ast_based else 4, column=0, columnspan=2, pady=10)

    # Helper methods for lambda manipulation
    def get_lambda_source(self, lambda_func):
        """
        Retrieve the source code of a lambda function or the original condition string.
        
        Args:
            lambda_func: The lambda function to inspect
            
        Returns:
            str: The extracted condition string, or "True" if extraction fails
        """
        # First check if we have a saved original condition
        if hasattr(lambda_func, 'original_condition'):
            condition = lambda_func.original_condition
            # Ensure consistent return format
            if condition.startswith("lambda stats:"):
                return condition.split(':', 1)[1].strip()
            return condition
        
        # For directly defined lambda functions, attempt to get source code
        try:
            import inspect
            source = inspect.getsource(lambda_func).strip()
            
            # Handle lambda assigned to variable
            if '=' in source:
                source = source.split('=', 1)[1].strip()
            
            # Remove trailing comma if present
            if source.endswith(','):
                source = source[:-1].strip()
                
            # Extract the condition part
            if source.startswith('lambda'):
                return source.split(':', 1)[1].strip()
            
            return source
        except Exception as e:
            print(f"Warning: Failed to get lambda source code - {e}")
            return "True"  # Default fallback value

    def extract_node_type(self, lambda_func):
        """Extract AST node type from a lambda function's closure."""
        if not hasattr(lambda_func, '__closure__') or not lambda_func.__closure__:
            return None
        
        for cell in lambda_func.__closure__:
            if isinstance(cell.cell_contents, str):
                return cell.cell_contents
        return None

    def create_lambda_function(self, lambda_str, is_ast_based):
        """Convert lambda string back to a function."""
        try:
            # Clean up the input string
            lambda_str = lambda_str.strip()
            if lambda_str.startswith("lambda"):
                lambda_str = lambda_str.split('lambda', 1)[1].strip()
            if ':' in lambda_str:
                # Extract the condition part after the colon
                condition = lambda_str.split(':', 1)[1].strip()
            else:
                condition = lambda_str
            
            if is_ast_based:
                # For AST rules use 'node' as parameter
                return eval(f"lambda node: {condition}", {'ast': ast})
            else:
                # For non-AST rules use 'stats' as parameter
                return eval(f"lambda stats: {condition}")
        except Exception as e:
            raise ValueError(f"Invalid lambda expression: {str(e)}")

    def delete_rule(self):
        """Delete the selected rule."""
        selected_index = self.rules_listbox.curselection()
        if not selected_index:
            messagebox.showwarning("No Selection", "Please select a rule to delete")
            return
        
        selected_text = self.rules_listbox.get(selected_index[0])
        try:
            # Extract just the rule name part
            rule_name = selected_text.split(" (")[0]
            
            # Confirm deletion
            if messagebox.askyesno("Confirm Delete", f"Delete rule '{rule_name}'?"):
                # Double check the rule exists
                if rule_name in self.rule_manager.get_all_rules():
                    self.rule_manager.remove_rule(rule_name)
                    self.update_rules_list()
                else:
                    messagebox.showwarning("Error", f"Rule '{rule_name}' not found")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete rule: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PerformanceGUI(root)
    root.mainloop()
