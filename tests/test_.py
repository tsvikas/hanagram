import importlib.metadata

import hanagram


def test_version() -> None:
    assert importlib.metadata.version("hanagram") == hanagram.__version__
