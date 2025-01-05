"""
Basic test suite for GitSage.
"""

from importlib import metadata


def test_version():
    """
    Verify that the package version is properly set and accessible.
    This test ensures our build configuration is working correctly.
    """
    version = metadata.version("gitsage")
    assert version == "0.8.1"
