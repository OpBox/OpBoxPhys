from numpy import arange, zeros, ndarray, NaN, isnan, append, delete
from PyDAQmx.DAQmxFunctions import DAQError
from PyQt4.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt4.QtGui import (QHBoxLayout,
                         QWidget,
                         )
from pyqtgraph import GraphicsLayoutWidget

from ..rw import DAQmxReader


class Worker(QObject):
    """Subprocess that acquires data from NI, writes them to EDF and sends the
    data back to Traces to plot them.
    """
    dataReady = pyqtSignal(ndarray, float)

    def __init__(self, args):
        super().__init__()
        self.args = args

    @pyqtSlot()
    def start_task(self):
        self.reader = DAQmxReader(self.args, self.dataReady.emit)
        self.reader.StartTask()


class Figure(GraphicsLayoutWidget):
    """Widget with the plots of the recordings.

    Parameters
    ----------
    n_chan : int
        number of channels
    x_axis : ndarray
        values to plot on the x-axis (assuming they never change).
    """
    def __init__(self, n_chan, x_axis):
        super().__init__()
        self.plot = []
        self.n_chan = n_chan
        self.x_axis = x_axis

        for i in range(self.n_chan):
            self.plot.append(self.addPlot().plot())
            self.plot.append(self.addPlot().plot())
            self.plot[-1].opts['fftMode'] = True
            self.nextRow()

    def update(self, data):
        """Update the data in the plots.

        Parameters
        ----------
        data : ndarray
            nChan x nSampls matrix to plot
        """
        for i in range(self.n_chan):
            self.plot[i * 2].setData(x=self.x_axis, y=data[i, :])
            if not isnan(data[i, :]).any():
                self.plot[i * 2 + 1].setData(x=self.x_axis, y=data[i, :])


class Traces(QWidget):
    """Main widget with the traces.

    Parameters
    ----------
    args : argparse.Namespace
        arguments specified by the user
    """
    def __init__(self, args):
        super().__init__()
        self.args = args

        self.figure = Figure(args.n_chan,
                             arange(0, args.window_size, 1 / args.s_freq))

        layout = QHBoxLayout()
        layout.addWidget(self.figure, 5)
        self.setLayout(layout)

        self.data = zeros((args.n_chan, int(args.window_size * args.s_freq)))
        self.data.fill(NaN)
        self.idx = 0

    def start(self):
        """Start acquisition by starting a new thread.
        """
        thread = QThread()
        self.thread = thread
        obj = Worker(self.args)
        self.obj = obj
        obj.dataReady.connect(self.plot_data)
        obj.moveToThread(thread)

        thread.started.connect(obj.start_task)
        thread.start()
        thread.quit()  # why does it go here?

    def stop(self):
        """End acquisition and close edf file if still open.
        """
        try:
            self.obj.reader.StopTask()
        except DAQError:
            pass
        else:
            if self.obj.reader.edf is not None:
                self.obj.reader.edf.close()
            self.obj.reader.ClearTask()

    def plot_data(self, data):
        """Update the data matrix with the recordings and plot it

        Parameters
        ----------
        data : ndarray
            matrix with the incoming recordings
        """
        self.data = append(self.data, data, axis=1)
        self.data = delete(self.data, range(data.shape[1]), axis=1)

        # TODO: take into account not integer mod
        # ? buffer_size = data.shape[1] ?
        # self.data[:, self.idx:(self.idx + buffer_size)] = data
        # self.idx = (self.idx + buffer_size) % int(wndw_size * self.args.s_freq)

        self.figure.update(self.data)
