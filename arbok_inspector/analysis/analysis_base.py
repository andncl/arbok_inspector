"""Module containing AnalysisBase class"""

class AnalysisBase:
    """Base class for analysis classes"""
    run_id = None
    xr_data = None

    def find_axis_from_keyword(self, keyword: str) -> str:
        """
        Find the axis corresponding to a keyword in the analysis
        Args:
            keyword (str): Keyword to search for
        Returns:
            axis (int): Axis corresponding to keyword
        """
        axes = []
        for axis in self.xr_data.dims:
            if keyword in axis:
                axes.append(axis)
        if len(axes) == 0:
            raise ValueError(
                f"Axis not found for keyword {keyword}. "
                f"Dims are {self.xr_data.dims}"
                )
        elif len(axes) > 1:
            raise ValueError(
                f"More than one axis found for keyword {keyword}: {axes}")
        else:
            return axes[0]
