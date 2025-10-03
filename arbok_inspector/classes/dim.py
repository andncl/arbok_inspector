"""Module for the Dim class."""

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
        self.option = None
        self.select_index = 0
        self.ui_selector = None

    def __str__(self):
        return self.name