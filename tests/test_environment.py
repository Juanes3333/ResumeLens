import importlib

import pytest

MODULES = [
    "resumelens",
    "resumelens.core",
    "resumelens.extraction",
    "resumelens.normalization",
    "resumelens.classification",
    "resumelens.grammar",
    "resumelens.visualization",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_importable(name):
    assert importlib.import_module(name) is not None
