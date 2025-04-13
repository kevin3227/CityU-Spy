import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
from profiler import PerformanceAnalyzer
from collections import defaultdict
import traceback # For printing detailed error stack traces

# --- Helper function: Get a consistent color for a function name ---
def get_color(func_name, color_map):
    """Assigns a consistent, somewhat warm-toned random color to a function name."""
    if func_name not in color_map:
        # Generate warm tones: R > G > B (general tendency)
        # Limit B's max value, increase R's min value
        r = random.uniform(0.6, 1.0)  # Red component higher (0.6 to 1.0)
        g = random.uniform(0.3, 0.6)  # Green component moderate (0.3 to 0.6)
        b = random.uniform(0.0, 0.3)  # Blue component lower (0.0 to 0.4)

        # Could slightly adjust components to avoid being too saturated or dim
        # E.g., ensure the sum of components is within a specific range, but this adds complexity

        color_map[func_name] = (r, g, b)
    return color_map[func_name]

# --- Recursive defaultdict factory for flame graph data ---
def flame_node_factory():
    """Creates the default node structure for the flame graph data tree."""
    # The factory returns a dictionary containing 'count' and 'children'.
    # 'children' itself needs to be a defaultdict using the same factory.
    return {'count': 0, 'children': defaultdict(flame_node_factory)}

class PerformanceGUI:
    def __init__(self, master):
        self.master = master
        master.title("Python Performance Analysis Tool") # Set window title
        master.geometry("1200x800") # Set window size

        # Initialize the performance analyzer
        self.analyzer = PerformanceAnalyzer()
        self.current_data = None # Current analysis result
        self.function_color_map = {} # Store function color mapping

        # Create UI components
        self.create_widgets()

    def create_widgets(self):
        # --- Top control bar ---
        control_frame = ttk.Frame(self.master)
        control_frame.pack(pady=10, fill=tk.X, padx=10) # Use pack layout, fill X direction

        # File selection button and entry field
        self.file_path = tk.StringVar() # Tkinter variable to store file path
        ttk.Button(control_frame, text="Select File", command=self.select_file).pack(side=tk.LEFT, padx=5)
        self.file_entry = ttk.Entry(control_frame, textvariable=self.file_path, width=50) # File path entry field
        self.file_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True) # Fill available space

        # Analysis mode selection dropdown
        self.mode_var = tk.StringVar(value="function") # Mode variable, default is "function"
        self.mode_combo = ttk.Combobox(control_frame, textvariable=self.mode_var,
                                      values=["function", "line"], state="readonly") # Read-only dropdown
        self.mode_combo.pack(side=tk.LEFT, padx=5)
        self.mode_combo.bind("<<ComboboxSelected>>", self.on_mode_change) # Bind mode change event

        # Start analysis button
        ttk.Button(control_frame, text="Start Analysis", command=self.run_analysis).pack(side=tk.LEFT, padx=5)

        # --- Results display area (using Notebook) ---
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(pady=5, padx=10, fill=tk.BOTH, expand=True) # Fill and expand

        # Flame Graph tab
        self.flame_frame = ttk.Frame(self.notebook) # Container Frame for the flame graph
        # Store the Frame's ID for later reference
        self._flame_frame_id = self.flame_frame._w
        self.notebook.add(self.flame_frame, text="Flame Graph") # Add to Notebook
        self.setup_flame_graph() # Setup the flame graph canvas

        # Raw Data tab
        raw_data_frame = ttk.Frame(self.notebook) # Container Frame for raw data, facilitates adding scrollbar
        self._raw_data_frame_id = raw_data_frame._w # Store ID
        self.notebook.add(raw_data_frame, text="Raw Data")
        self.raw_data_text = tk.Text(raw_data_frame, wrap=tk.WORD, relief=tk.SUNKEN, borderwidth=1) # Raw data text area, word wrap
        raw_scrollbar = ttk.Scrollbar(raw_data_frame, orient="vertical", command=self.raw_data_text.yview) # Vertical scrollbar
        self.raw_data_text.configure(yscrollcommand=raw_scrollbar.set) # Update scrollbar when text scrolls
        raw_scrollbar.pack(side=tk.RIGHT, fill=tk.Y) # Place scrollbar on the right, fill Y direction
        self.raw_data_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) # Place text area on the left, fill and expand

        # Disable flame graph tab initially based on mode
        self.on_mode_change()

    def on_mode_change(self, event=None):
        """Enable/disable the flame graph tab based on the selected mode."""
        try:
            # Use the previously saved IDs to reference the tabs
            flame_tab_id = self._flame_frame_id
            raw_data_tab_id = self._raw_data_frame_id
        except AttributeError:
             # If frame IDs haven't been saved yet (shouldn't happen unless called mid-init), skip
             print("Warning: on_mode_change called before Frame IDs were fully initialized.")
             return

        if self.mode_var.get() == "function":
            self.notebook.tab(flame_tab_id, state="normal") # Enable flame graph tab
        else:
            # If the flame graph tab is currently selected and mode changes to non-function, switch to the raw data tab
            try:
                current_tab_id = self.notebook.select() # Get the ID of the currently selected tab (Note: returns widget ID)
                if current_tab_id == flame_tab_id:
                    # Directly select the raw data tab
                    self.notebook.select(raw_data_tab_id)
            except tk.TclError as e:
                 # Notebook might not be fully initialized or in an unusual state
                 print(f"Error switching tabs: {e}")
                 pass

            self.notebook.tab(flame_tab_id, state="disabled") # Disable flame graph tab

    def select_file(self):
        """Open a file dialog to select a Python file."""
        file_path = filedialog.askopenfilename(
            title="Select Python File",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        if file_path:
            self.file_path.set(file_path) # Update file path variable

    def run_analysis(self):
        """Execute the performance analysis."""
        file_path = self.file_path.get()
        mode = self.mode_var.get()

        if not file_path:
            messagebox.showwarning("Warning", "Please select a Python file first.")
            return

        # Clear previous results
        self.raw_data_text.delete(1.0, tk.END) # Clear raw data text area
        if hasattr(self, 'ax') and self.ax: # Check if ax exists
             self.ax.clear() # Clear matplotlib plot area
             try:
                 self.canvas.draw_idle() # Attempt non-blocking redraw of canvas
             except AttributeError:
                 pass # Ignore if canvas hasn't been created yet
        self.current_data = None # Clear current data
        self.function_color_map = {} # Reset color map
        if hasattr(self, 'tooltip'): # Hide any existing tooltip
            self.tooltip.hide_tip()

        try:
            # --- Execute performance analysis ---
            print(f"Starting analysis: File='{file_path}', Mode='{mode}'") # Debug info
            result = self.analyzer.analyze_file(file_path, mode)
            self.current_data = result # Store analysis result
            print("Analysis complete.") # Debug info

            # Check for errors returned by the analyzer
            if isinstance(result, dict) and "error" in result:
                 error_msg = f"Analyzer returned error: {result['error']}"
                 print(error_msg) # Debug info
                 messagebox.showerror("Analysis Error", error_msg)
                 # Show the original error message even if analysis failed
                 self.raw_data_text.insert(tk.END, json.dumps(result, indent=4, ensure_ascii=False)) # Use ensure_ascii=False for potential non-ASCII paths/names
                 return # Stop further processing on error

            # --- Update UI ---
            # Display raw data (JSON format)
            self.raw_data_text.insert(tk.END, json.dumps(result, indent=4, ensure_ascii=False))

            # If in function mode, update the flame graph
            if mode == "function":
                 print("Mode is 'function', preparing to update flame graph...") # Debug info
                 self.update_flame_graph()
            else:
                 # In other modes, clear the flame graph area and show a message
                 if hasattr(self, 'ax') and self.ax:
                     self.ax.clear()
                     self.ax.text(0.5, 0.5, "Flame graph is only available in 'function' mode",
                                  ha='center', va='center', fontsize=12, color='gray')
                     self.ax.set_xticks([])
                     self.ax.set_yticks([])
                     self.canvas.draw_idle() # Non-blocking redraw
                 print("Mode is not 'function', flame graph not generated.") # Debug info

        except Exception as e:
            # Catch other potential exceptions during analysis or UI update
            error_msg = f"An unexpected error occurred during analysis execution: {str(e)}"
            print(f"Runtime error: {error_msg}\n{traceback.format_exc()}") # Debug info
            messagebox.showerror("Runtime Error", error_msg)
            self.raw_data_text.insert(tk.END, error_msg)
            # Print detailed traceback to the raw data area for debugging
            self.raw_data_text.insert(tk.END, f"\n\nDetailed Error Information:\n{traceback.format_exc()}")

    def setup_flame_graph(self):
        """Set up the Matplotlib canvas for the flame graph."""
        try:
            # Create Matplotlib figure and axes
            # Using constrained_layout=True helps automatically adjust layout to prevent label overlap
            self.fig, self.ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
            # self.fig.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.1) # Usually not needed with constrained_layout=True

            # Create Tkinter canvas embedding the Matplotlib figure
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.flame_frame)
            self.canvas_widget = self.canvas.get_tk_widget() # Get the Tkinter canvas widget
            self.canvas_widget.pack(fill=tk.BOTH, expand=True) # Fill and expand

            # --- Add tooltip ---
            self.tooltip = Tooltip(self.canvas_widget) # Create Tooltip instance
            # Connect mouse motion event to the handler function
            self.canvas.mpl_connect('motion_notify_event', self.on_motion)
            self.active_bars = [] # Stores info about drawn rectangles (for tooltip hit detection)
            print("Flame graph canvas setup complete.") # Debug info
        except Exception as e:
            print(f"Error setting up flame graph: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Initialization Error", f"Failed to set up flame graph canvas: {e}")
            # Consider disabling related features or providing a default view

    def _build_flame_data(self):
        """Process profiler results to build the data structure for flame graph generation."""
        if not self.current_data or self.current_data.get("mode") != "function":
            print("_build_flame_data: No valid data or incorrect mode.") # Debug info
            return None, 0

        call_chains = self.current_data.get("call_chains", [])
        if not call_chains:
            print("_build_flame_data: 'call_chains' is empty.") # Debug info
            return None, 0
        print(f"_build_flame_data: Received {len(call_chains)} raw call_chains entries.")

        # Filter for leaf node call chains (those without children) and their call counts
        endpoint_chains = []
        for idx, chain_info in enumerate(call_chains):
            # Add checks to ensure chain_info is a dictionary and contains necessary keys
            if not isinstance(chain_info, dict):
                print(f"  Warning: call_chain at index {idx} is not a dictionary: {chain_info}")
                continue
            if not chain_info.get("chain"):
                print(f"  Warning: call_chain at index {idx} is missing 'chain' key: {chain_info}")
                continue

            # Filter condition: 'chain' exists, 'count'>0, and 'children' does not exist or is an empty list/set
            is_endpoint = (chain_info.get("count", 0) > 0 and
                           not chain_info.get("children")) # children can be None, [], or set()

            if is_endpoint:
                 endpoint_chains.append({
                    "stack": tuple(chain_info["chain"]), # Use tuple as key because lists are unhashable
                    "count": chain_info["count"]
                })

        if not endpoint_chains:
             print("_build_flame_data: No valid leaf node call chains found.") # Debug info
             # Print some raw data to help diagnose
             if call_chains:
                 print("  Raw call_chains (sample):", call_chains[:min(5, len(call_chains))])
             return None, 0
        print(f"_build_flame_data: Found {len(endpoint_chains)} leaf node call chains.") # Debug info

        # --- Sort call chains ---
        # Sorting ensures similar call stacks are adjacent horizontally in the flame graph, improving visual clarity
        endpoint_chains.sort(key=lambda x: x["stack"])

        # --- Initialize aggregated data defaultdict using the recursive factory ---
        flame_data = defaultdict(flame_node_factory)
        total_count = 0 # Total call count for leaf nodes

        # Iterate through sorted leaf node call chains to build the aggregated tree
        for item in endpoint_chains:
            stack = item["stack"]
            count = item["count"]
            current_level = flame_data # Start from the root node

            # Traverse functions in the call stack level by level
            for i, func_name in enumerate(stack):
                # Access the node; if it doesn't exist, defaultdict automatically creates it using flame_node_factory
                node = current_level[func_name]
                # Add the count of the current path to all nodes it passes through
                node['count'] += count

                # If it's the last function in the current call chain (leaf node)
                if i == len(stack) - 1:
                    total_count += count # Accumulate the total count of leaf nodes

                # Move to the children dictionary of the next level (guaranteed to be a defaultdict)
                current_level = node['children']

        # Check the result of data building
        if not flame_data:
            print("_build_flame_data: flame_data is still empty after building.") # Debug info
            return None, 0
        if total_count <= 0: # Check if total_count is positive
            print(f"_build_flame_data: total_count ({total_count}) is invalid after building.") # Debug info
            # Print some built data to help diagnose
            print("  Built flame_data (sample):", dict(list(flame_data.items())[:2]))
            return None, 0

        print(f"_build_flame_data: Building complete. Total Count: {total_count}") # Debug info
        return flame_data, total_count

    def _draw_flame_recursive(self, data, level, start_x, total_width_param):
        """Recursively draw the rectangular bars of the flame graph."""
        current_x = start_x # Starting X coordinate for drawing at the current level
        # Sort function names at the current level to ensure consistent drawing order
        sorted_funcs = sorted(data.keys())

        for func_name in sorted_funcs:
            node = data[func_name]
            width = node['count'] # Width of the rectangle equals the node's accumulated call count
            if width <= 0: continue # Skip bars with zero or negative width

            color = get_color(func_name, self.function_color_map) # Get the color for this function

            # --- Draw the rectangle bar ---
            try:
                bar = self.ax.barh(level,          # Y coordinate (call stack depth)
                               width,          # Width (call count)
                               left=current_x, # Starting X position
                               height=1.0,     # Rectangle height (set to 1.0 for no vertical gaps)
                               color=color,    # Fill color
                               edgecolor=color, # Edge color (same as fill for solid look)
                               linewidth=0,    # Edge width (0 for no visible border)
                               label=func_name)# Label (though legend is usually hidden)
            except Exception as draw_err:
                print(f"Error drawing rectangle bar: Function='{func_name}', Level={level}, Error: {draw_err}")
                print(f"  Parameters: level={level}, width={width}, left={current_x}")
                continue # Skip drawing faulty bars

            # --- Store rectangle info for tooltip ---
            # Ensure total_width_param is greater than 0 to avoid division by zero
            percentage = (width / total_width_param * 100) if total_width_param > 0 else 0
            # Get the bounding box of the rectangle (for hit detection)
            try:
                bbox = bar[0].get_bbox()
            except IndexError:
                print(f"Warning: Could not get bounding box for function '{func_name}'.")
                bbox = None # Or create a default empty Bbox object

            if bbox: # Only add info if bbox was successfully obtained
                 bar_info = {
                    'rect': bbox,
                    'label': f"{func_name}\nCalls: {width}\nPercentage: {percentage:.1f}%" # Updated label text
                }
                 self.active_bars.append(bar_info)

            # --- Add text label inside the rectangle (if wide enough) ---
            # Use total_width_param to calculate relative width
            # Adjust threshold, e.g., show text only if relative width > 0.5%
            if total_width_param > 0 and (width / total_width_param > 0.005):
                # Heuristic method to estimate fittable characters (may need tuning)
                # Consider using figure width instead of total width percentage?
                # fig_width_pixels = self.fig.get_window_extent().width
                # bar_width_pixels = (width / total_width_param) * fig_width_pixels * (self.ax.get_position().width) # Approximation
                # max_text_len = int(bar_width_pixels / 7) # Assuming avg char width ~7 pixels

                # Simplified: Still based on relative width, but adjusted coefficient
                max_text_len = int(width / total_width_param * 200) + 1 # Increase base length
                display_name = func_name
                # Truncate if function name is too long
                if len(display_name) > max_text_len and max_text_len > 3:
                     display_name = display_name[:max_text_len-3] + "..."
                elif max_text_len <= 3 and len(display_name) > 3: # Extreme case
                     display_name = display_name[:1] + ".."

                # Determine text color (black or white) based on background brightness
                text_color = 'black' if (color[0]*0.299 + color[1]*0.587 + color[2]*0.114) > 0.6 else 'white'
                try:
                    self.ax.text(current_x + width / 2, # X coordinate (centered)
                                 level,               # Y coordinate
                                 display_name,        # Text to display
                                 ha='center',         # Horizontal alignment
                                 va='center',         # Vertical alignment
                                 color=text_color,    # Text color
                                 fontsize=8,          # Slightly smaller font size
                                 clip_on=True)        # Clip text exceeding axes bounds
                except Exception as text_err:
                     print(f"Error drawing text label: Function='{func_name}', Error: {text_err}")

            # --- Recursively draw child nodes ---
            # If the current node has children (children dictionary is not empty)
            children_data = node.get('children')
            if children_data: # Ensure children dictionary is not empty
                # level+1 means going deeper in the call stack
                # start_x remains the same because children stack on top of the parent, starting at the same X
                # Pass the same total_width_param
                self._draw_flame_recursive(children_data, level + 1, current_x, total_width_param)

            # Update the starting X coordinate for the next sibling rectangle
            current_x += width

    def update_flame_graph(self):
        """Generate and display the flame graph."""
        if not hasattr(self, 'ax') or not self.ax:
             print("Flame graph axes (ax) not initialized, cannot update.")
             return

        self.ax.clear() # Clear previous plot content
        self.active_bars = [] # Clear list of rectangle info for tooltips
        if hasattr(self, 'tooltip'):
            self.tooltip.hide_tip() # Hide any existing old tooltip

        print("Starting to build flame graph data...") # Debug info
        try:
            flame_data, total_count = self._build_flame_data()
        except Exception as build_err:
            print(f"Error building flame graph data: {build_err}\n{traceback.format_exc()}")
            messagebox.showerror("Data Processing Error", f"Failed to build flame graph data: {build_err}")
            return # Cannot continue

        # Check if the build result is valid
        if not flame_data or total_count <= 0: # Ensure total_count is positive
            err_msg = "Not enough function call data to generate flame graph"
            if total_count == 0 and flame_data:
                 err_msg += " (Total call count is zero)"
            print(f"Cannot generate flame graph: Data valid={bool(flame_data)}, Total count={total_count}") # Debug info
            self.ax.text(0.5, 0.5, err_msg,
                         ha='center', va='center', fontsize=12, color='gray')
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            self.canvas.draw_idle()
            return

        # --- Calculate maximum call stack depth ---
        max_depth = -1 # Initialize to -1, so root node (level 0) is handled correctly
        def find_depth(data, current_depth):
            nonlocal max_depth
            if not data: return # Stop recursion if children dictionary is empty
            max_depth = max(max_depth, current_depth) # Update max depth
            for func in data:
                 children_data = data[func].get('children')
                 if children_data: # Recurse only if children exist and are not empty
                    find_depth(children_data, current_depth + 1)

        find_depth(flame_data, 0) # Start calculating from the root node (level 0)

        # --- Start recursive drawing ---
        print(f"Starting to draw flame graph. Max Depth: {max_depth}, Leaf Node Total Count: {total_count}") # Debug info
        try:
            # Start drawing from root (level 0), starting X=0, pass total width
            self._draw_flame_recursive(flame_data, 0, 0, total_count)
        except Exception as draw_fatal_err:
             print(f"Critical error during flame graph drawing: {draw_fatal_err}\n{traceback.format_exc()}")
             messagebox.showerror("Drawing Error", f"A critical error occurred while drawing the flame graph: {draw_fatal_err}")
             # Even on error, try to configure axes and display canvas, part of the graph might be drawn
             pass # Continue to subsequent configuration code

        # --- Configure axes ---
        self.ax.set_xlabel(f"Call Count (Leaf Node Total: {total_count})") # X-axis label
        self.ax.set_ylabel("Call Stack Depth") # Y-axis label
        self.ax.set_xlim(0, total_count) # X-axis range
        # Y-axis range, leave some margin (-0.5 to max_depth + 0.5)
        # If max_depth is still -1 (e.g., only one root node), set a reasonable default range
        effective_max_depth = max(0, max_depth) # Ensure at least 0
        self.ax.set_ylim(-0.5, effective_max_depth + 0.5)
        # Ensure Y-axis ticks are integers
        self.ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
        # Invert Y axis so stack grows upwards (optional, standard flame graph is root at bottom)
        # self.ax.invert_yaxis() # Uncomment for root-at-top view

        self.ax.set_title("Function Call Flame Graph (by Call Count)") # Chart title
        self.ax.tick_params(axis='x', bottom=True, top=False, labelbottom=True) # Ensure bottom X-axis ticks are visible
        self.ax.get_yaxis().set_visible(False) # Hide Y axis labels and ticks

        # --- Refresh canvas display ---
        try:
            self.canvas.draw_idle() # Use non-blocking draw
            print("Flame graph drawing complete and display requested.") # Debug info
        except Exception as e:
            print(f"Error refreshing canvas: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Drawing Error", f"An error occurred while refreshing the flame graph display: {e}")

    def on_motion(self, event):
        """Handle mouse motion events for displaying tooltips."""
        # Check if event occurred within axes, active_bars list is not empty,
        # and event coordinates (xdata, ydata) are valid
        if (event.inaxes == self.ax and
                self.active_bars and
                event.xdata is not None and event.ydata is not None): # Check if coordinates are valid
            # Check active_bars in reverse order (to prioritize topmost rectangles)
            matched = False
            for bar_info in reversed(self.active_bars):
                # Check if the mouse coordinates are within the rectangle's bounding box
                try:
                    # Bbox.contains() needs x and y coordinates as arguments
                    # event.xdata and event.ydata are mouse positions in data coordinates
                    contains = bar_info['rect'].contains(event.xdata, event.ydata)

                    if contains:
                        # If hit, show the tooltip
                        if hasattr(self, 'tooltip'):
                            self.tooltip.show_tip(bar_info['label'], event.x, event.y)
                        matched = True
                        break # Stop after finding the first match
                except AttributeError:
                    # bar_info['rect'] might be invalid or non-existent
                    # print(f"Warning: Error processing bar_info: {bar_info}") # Optional debug info
                    continue
                except Exception as e:
                    # Catch other potential errors during contains check
                    print(f"Error during contains check in mouse motion event: {e}")
                    continue

            if not matched:
                # If loop finishes without matching any bar, hide the tip
                if hasattr(self, 'tooltip'):
                    self.tooltip.hide_tip()
        else:
            # If mouse is not inside any rectangle, or not within axes, or coordinates are invalid, hide tooltip
            if hasattr(self, 'tooltip'):
                self.tooltip.hide_tip()


# --- Simple Tooltip Class ---
class Tooltip:
    def __init__(self, widget):
        self.widget = widget # The Tkinter widget this tooltip is attached to (canvas_widget here)
        self.tip_window = None # Toplevel window instance (for displaying the tip)
        self.id = None # Used for scheduling
        self.x = self.y = 0 # Mouse coordinates
        self.text = "" # Tooltip content

    def show_tip(self, text, x, y):
        """Display tooltip text near the mouse cursor."""
        self.text = text
        # If a tip window already exists or there's no text
        if self.tip_window or not self.text:
            # If window exists, try to update the text (it might have been destroyed by rapid movement)
            if self.tip_window:
                 try:
                     # Check if the window still exists
                     if self.tip_window.winfo_exists():
                         self.label.config(text=self.text) # Update label content
                         return # Update successful, no need to recreate
                     else:
                         # Window no longer exists, clear reference
                         self.tip_window = None
                 except tk.TclError: # Window was already destroyed
                     self.tip_window = None # Clear reference
                     # Don't return, allow recreation below
            # If text is empty, hide and return
            if not self.text:
                 self.hide_tip()
                 return

        # --- Create a new tooltip window ---
        # Check if the parent widget still exists
        try:
            if not self.widget.winfo_exists():
                 return # Parent widget destroyed, cannot show tip
        except tk.TclError:
            return # Parent widget destroyed

        # Get mouse coordinates relative to the screen
        try:
             x_root, y_root = self.widget.winfo_pointerxy()
        except tk.TclError:
             return # Failed to get mouse position

        # Create a new Toplevel window
        try:
            self.tip_window = tw = tk.Toplevel(self.widget)
        except tk.TclError as e:
             print(f"Failed to create Toplevel window: {e}")
             self.tip_window = None
             return # Fail gracefully if creation fails

        # Make the window frameless (no title bar or borders)
        tw.wm_overrideredirect(True)
        # Keep window on top (optional)
        tw.wm_attributes("-topmost", True)
        # Set window position (slightly below and to the right of the cursor)
        # Basic positioning
        new_x = x_root + 15
        new_y = y_root + 10

        # --- Boundary check to prevent tooltip going off-screen ---
        # (This is a simplified check, might need adjustments based on font/content)
        try:
            screen_width = self.widget.winfo_screenwidth()
            screen_height = self.widget.winfo_screenheight()
        except tk.TclError:
            # If screen dimensions can't be obtained, use default position
            screen_width, screen_height = 800, 600 # Assumed values

        # Estimate tooltip size (more accurate calculation might require rendering first)
        lines = text.split('\n')
        # Estimate width considering potentially wider CJK characters (less relevant now but kept logic)
        # Using a simple estimation based on max line length and avg char width
        est_width = len(max(lines, key=len)) * 8 + 15 # Estimate width
        est_height = len(lines) * 18 + 10           # Estimate height

        if new_x + est_width > screen_width: # If right edge goes off-screen
            new_x = x_root - est_width - 10    # Move to the left of the cursor
        if new_y + est_height > screen_height: # If bottom edge goes off-screen
            new_y = y_root - est_height - 10   # Move above the cursor
        # Ensure it doesn't move off-screen (left/top)
        new_x = max(0, new_x)
        new_y = max(0, new_y)

        tw.wm_geometry(f"+{int(new_x)}+{int(new_y)}") # Set window geometry

        # Add a Label widget to the window to display the text
        try:
            self.label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                                  background="#ffffe0", # Light yellow background
                                  relief=tk.SOLID, borderwidth=1, # With border
                                  font=("TkDefaultFont", 9)) # Use default Tk font
            self.label.pack(ipadx=2, ipady=1) # Label size adjusts to text, add padding
        except tk.TclError as e:
            print(f"Failed to create Label: {e}")
            self.hide_tip() # Hide window if label creation fails

    def hide_tip(self):
        """Hide the tooltip window."""
        tw = self.tip_window
        self.tip_window = None # Clear reference
        if tw:
            try:
                # Check if the window still exists
                if tw.winfo_exists():
                    tw.destroy() # Destroy the window
            except tk.TclError:
                pass # Ignore errors if window was already destroyed


# --- Main program entry point ---
if __name__ == "__main__":
    try:
        root = tk.Tk() # Create the main window
        app = PerformanceGUI(root) # Instantiate the GUI application
        root.mainloop() # Start the Tkinter event loop
    except Exception as main_err:
        print(f"Error in application main loop: {main_err}\n{traceback.format_exc()}")
        # Try to show error message even without GUI running properly
        try:
             import tkinter.messagebox
             tkinter.messagebox.showerror("Critical Error", f"Application encountered a critical error:\n{main_err}")
        except:
             pass # If even messagebox fails, error is already printed
