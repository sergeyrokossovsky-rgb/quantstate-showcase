"""Event-driven permission windows and session-aware deadlines (generic building blocks)."""
from .window import PermissionWindow, WindowState, next_deadline

__all__ = ["PermissionWindow", "WindowState", "next_deadline"]
