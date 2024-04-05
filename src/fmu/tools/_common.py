"""
This private module is used for some common functions and testing
"""

import os
import sys
from functools import wraps


class _QCCommon(object):
    """
    Common functions, like print_info()
    """

    def __init__(self):
        self._verbosity = 0  # verbosity level

    @property
    def verbosity(self):
        return self._verbosity

    @verbosity.setter
    def verbosity(self, level):
        if level in ("info", 1):
            self._verbosity = 1
        elif level in ("debug", 2):
            self._verbosity = 2

    def print_info(self, string):
        """Do print based on verbosity level >= 1"""
        if self._verbosity > 0:
            print("INFO  >>", string)

    def print_debug(self, string):
        """Do debug print based on verbosity level >= 2"""
        if self._verbosity > 1:
            print("DEBUG >>", string)

    @staticmethod
    def give_warn(string):
        """Give warning to user"""
        print("WARN  >>", string)

    @staticmethod
    def force_stop(string):
        """Give stop message to STDERR and stop process"""
        mode = sys.stderr
        print()
        print("!" * 70, file=mode)
        print("STOP! >>", string, file=mode)
        print("!" * 70, file=mode)
        print()

        sys.exit(string)


def preserve_cwd(func):
    """Decorator to return to orginal CWD, applied in testing"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        original_cwd = os.getcwd()
        try:
            return func(*args, **kwargs)
        finally:
            os.chdir(original_cwd)

    return wrapper
