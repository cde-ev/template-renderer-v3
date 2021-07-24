
from typing import Dict, Callable, Any, Optional
from data import Event
from configparser import ConfigParser

# The dictionary of render targets and a decorator to add those
TARGETS: Dict[str, Callable[[Event, ConfigParser, str, str], Any]] = {}


def target_function(fun: Callable[[Event, ConfigParser, str, str], Any], name: Optional[str] = None):
    """
    Decorator to apply to a function to make it a target function
    """
    if name is None:
        name = fun.__name__
    TARGETS[name] = fun
    return fun
