import pathlib
import pytest


@pytest.fixture
def project_root() -> pathlib.Path:
    return pathlib.Path("/Users/karthik/projects/ticket-to-prompt")
