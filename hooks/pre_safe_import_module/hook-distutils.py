# Override PyInstaller's built-in pre-import hook for distutils
# This prevents the "already imported as ExcludedModule" error in Python 3.13+

def pre_safe_import_module(api):
    """
    Override the default distutils hook to do nothing.
    We want distutils to be completely excluded, not aliased.
    """
    # Do nothing - let distutils be excluded as specified in the spec file
    pass
