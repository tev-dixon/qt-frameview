import os

os.environ.setdefault("PYTEST_QT_API", "pyqt6")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
