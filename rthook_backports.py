import sys
import os

# Ensure backports namespace is correctly set up
try:
    import backports
except ImportError:
    pass

# Force backports.tarfile import
try:
    import backports.tarfile
except ImportError:
    pass
