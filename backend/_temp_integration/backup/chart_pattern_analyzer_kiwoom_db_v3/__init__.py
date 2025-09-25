"""Public API for chart_pattern_analyzer_kiwoom_db package.

This module forwards the most commonly used symbols so external code can
import them from the package root, e.g.

    from backend._temp_integration.chart_pattern_analyzer_kiwoom_db import run_full_analysis

Keep this file minimal to avoid import-time side-effects.
"""

from .run_full_analysis import run_full_analysis
from .trend import TrendDetector, MarketTrendInfo
from .patterns import (
    PatternManager,
    PatternDetector,
    HeadAndShouldersDetector,
    InverseHeadAndShouldersDetector,
    DoubleTopDetector,
    DoubleBottomDetector,
)

__all__ = [
    "run_full_analysis",
    "TrendDetector",
    "MarketTrendInfo",
    "PatternManager",
    "PatternDetector",
    "HeadAndShouldersDetector",
    "InverseHeadAndShouldersDetector",
    "DoubleTopDetector",
    "DoubleBottomDetector",
]


