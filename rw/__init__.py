"""rename rw (read/write) from io because of a conflict in python2 with numpy
libraries.
"""
from .daqmx import DAQmxReader
from .edf import ExportEdf