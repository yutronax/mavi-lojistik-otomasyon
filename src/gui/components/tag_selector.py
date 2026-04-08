import tkinter as tk
from tkinter import ttk

class TagSelector(tk.Frame):
    """
    Tag-based selection widget with autocomplete.
    Shows selected items as removable tags (small boxes with X button).
    """
    def __init__(self, parent, available_values, bg='white', **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self.available_values = sorted(available_values) if available_values else []
        self.selected_tags = []
        self.bg_color = bg
        
        # Container for tags
        self.tags_frame = tk.Frame(self, bg=bg)
        self.tags_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Input frame
        input_frame = tk.Frame(self, bg=bg)
        input_frame.pack(fill=tk.X)
        
        # Autocomplete entry
        self.entry = ttk.Combobox(input_frame, values=self.available_values, 
                                   state='normal', width=20)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.entry.bind('<Return>', self.add_tag_from_entry)
        self.entry.bind('<KeyRelease>', self.filter_suggestions)
        self.entry.bind('<<ComboboxSelected>>', self.add_tag_from_entry)
        
        # Add button
        add_btn = tk.Button(input_frame, text="➕", bg='#28a745', fg='white',
                           command=self.add_tag_from_entry, width=3)
        add_btn.pack(side=tk.LEFT)
        
    def _tr_upper(self, text):
        """Turkish-friendly uppercase conversion"""
        if not text: return ""
        text = text.replace('i', 'İ').replace('ı', 'I')
        return text.upper()

    def filter_suggestions(self, event=None):
        """Filter dropdown suggestions based on input"""
        if event and event.keysym in ('Return', 'Up', 'Down', 'Left', 'Right', 'Tab', 'Escape'):
            return
            
        value = self._tr_upper(self.entry.get())
        if value == '':
            self.entry['values'] = self.available_values
        else:
            # Filter: starts with OR contains (Turkish friendly)
            filtered = [v for v in self.available_values if value in self._tr_upper(v)]
            self.entry['values'] = filtered
            
            # Auto-open dropdown if there are matches
            if filtered:
                # Use after to prevent focus issues
                self.after(10, lambda: self.entry.event_generate('<Down>'))
            
    def add_tag_from_entry(self, event=None):
        """Add tag from entry value"""
        value = self.entry.get().strip().upper()
        
        if not value:
            return
            
        # Only allow values from available_values
        if value not in [v.upper() for v in self.available_values]:
            # Try to find exact match
            matches = [v for v in self.available_values if v.upper() == value]
            if not matches:
                self.entry.delete(0, tk.END)
                return
            value = matches[0]
        else:
            # Get canonical value
            value = next(v for v in self.available_values if v.upper() == value)
        
        # Don't add duplicates
        if value not in self.selected_tags:
            self.selected_tags.append(value)
            self.render_tags()
        
        self.entry.delete(0, tk.END)
        self.entry['values'] = self.available_values
        return "break"
    
    def render_tags(self):
        """Render all tags"""
        # Clear existing tags
        for widget in self.tags_frame.winfo_children():
            widget.destroy()
        
        # Render each tag
        for tag_value in self.selected_tags:
            tag_frame = tk.Frame(self.tags_frame, bg='#3b82f6', relief='raised', 
                                borderwidth=1, padx=6, pady=4)
            tag_frame.pack(side=tk.LEFT, padx=2, pady=2)
            
            # Tag label
            label = tk.Label(tag_frame, text=tag_value, bg='#3b82f6', fg='white',
                           font=('Segoe UI', 9))
            label.pack(side=tk.LEFT, padx=(0, 4))
            
            # Remove button
            remove_btn = tk.Button(tag_frame, text="✕", bg='#3b82f6', fg='white',
                                   command=lambda v=tag_value: self.remove_tag(v),
                                   font=('Segoe UI', 8, 'bold'),
                                   borderwidth=0, cursor='hand2',
                                   activebackground='#2563eb')
            remove_btn.pack(side=tk.LEFT)
    
    def remove_tag(self, value):
        """Remove a tag"""
        if value in self.selected_tags:
            self.selected_tags.remove(value)
            self.render_tags()
    
    def get_values(self):
        """Get selected values as list"""
        return self.selected_tags.copy()
    
    def set_values(self, values):
        """Set selected values"""
        self.selected_tags = []
        if values:
            for v in values:
                v_str = str(v).upper()
                # Find canonical value
                canonical = next((av for av in self.available_values if av.upper() == v_str), None)
                if canonical and canonical not in self.selected_tags:
                    self.selected_tags.append(canonical)
        self.render_tags()
    
    def clear(self):
        """Clear all tags"""
        self.selected_tags = []
        self.render_tags()
        self.entry.delete(0, tk.END)
