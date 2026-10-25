import os

import pytest
from PyQt6.QtWidgets import QApplication

from gerald.home.typography import ensure_fonts

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def qapplication():
    application = QApplication.instance() or QApplication([])
    ensure_fonts()
    application.setQuitOnLastWindowClosed(False)
    return application
