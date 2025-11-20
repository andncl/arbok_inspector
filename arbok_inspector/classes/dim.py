"""Module for the Dim class."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nicegui.elements.html import Html
    from nicegui.elements.select import Select
    from nicegui.elements.slider import Slider

class Dim:
    """
    Class representing a dimension of the data
    """
    def __init__(self, name):
        """
       Constructor for Dim class
        
        Args:
            name (str): Name of the dimension
            
        Attributes:
            name (str): Name of the dimension
            option (str): Option for the dimension (average, select_value, x-axis, y-axis)
            select_index (int): Index of the selected value for select_value option
            ui_selector: Reference to the UI element for the dimension
        """
        self.name = name
        self.option: str | None = None
        self.select_index: int = 0
        self.ui_selector: Select | None = None
        self.slider: Slider | None = None
        self.select_label: Html | None = None

    def __str__(self):
        return self.name
