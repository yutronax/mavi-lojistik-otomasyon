import tkinter as tk
from tkinter import ttk

class AutocompleteEntry(ttk.Combobox):
    """
    A Combobox that filters its values based on user input.
    """
    def __init__(self, parent, completevalues=None, placeholder=None, force_uppercase=True, **kwargs):
        super().__init__(parent, **kwargs)
        self.completevalues = sorted(completevalues) if completevalues else []
        self.force_uppercase = force_uppercase
        self._completion_list = self.completevalues
        self['values'] = self._completion_list
        
        if placeholder:
            self.set(placeholder)
        
        self.bind('<KeyRelease>', self.handle_keyrelease, add='+')
        self.bind('<FocusIn>', self.handle_focus)
        
    def handle_focus(self, event):
        """When focused, if empty or full list, ensure full list is available"""
        if self.get() == '':
             self['values'] = self.completevalues
             
    def _match(self, value, item):
        """Check if value matches item, ignoring case and Turkish character differences"""
        from src.utils.common import normalize_turkish_text
        return normalize_turkish_text(value) in normalize_turkish_text(item)

    def handle_keyrelease(self, event):
        """Filter values on key release"""
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab'):
            return
            
        value = self.get()
        
        # Rule: Force Turkish Uppercase
        if self.force_uppercase:
            from src.utils.common import normalize_turkish_text
            import tkinter as tk
            current_pos = self.index(tk.INSERT)
            norm_value = normalize_turkish_text(value)
            if value != norm_value:
                self.set(norm_value)
                self.icursor(current_pos)
            value = norm_value

        if value == '':
            self['values'] = self.completevalues
        else:
            # Custom filtering with Turkish character tolerance
            if ',' in value:
                # Get the last part
                parts = value.rsplit(',', 1)
                last_part = parts[-1].strip()
                
                filtered = [
                    item for item in self.completevalues 
                    if self._match(last_part, item)
                ]
                self['values'] = filtered
            else:
                filtered = [
                    item for item in self.completevalues 
                    if self._match(value, item)
                ]
                self['values'] = filtered

        # Logic to open dropdown if results exist?
        if self['values']:
             self.after(50, lambda: self.event_generate('<Down>'))
