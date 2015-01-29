# On Dell Optiplex Physiology computer as of 1/29/2015:
# Dev1=PCIe-6323: AI 0-7, 16-23. DI: Port0/0:31
# Dev2=PCI-6225: AI 0-7, 16-23, 32-39, 48-55, 64-71. DI: Port0/0:7

from __future__ import division  # py2

from numpy import zeros

# package to control NI
from ctypes import byref  # also in PyDAQmx
from PyDAQmx.DAQmxConstants import (DAQmx_Val_Diff,
                                    DAQmx_Val_Volts,
                                    DAQmx_Val_Rising,
                                    DAQmx_Val_ContSamps,
                                    DAQmx_Val_Acquired_Into_Buffer,
                                    DAQmx_Val_GroupByChannel,
                                    DAQmx_Val_Auto,
                                    DAQmx_Val_ChanPerLine,
                                    )
from PyDAQmx.DAQmxTypes import int32
from PyDAQmx.Task import Task

from .edf import ExportEdf


class DAQmxReader(Task):
    """Class to interact with NI devices.

    Parameters
    ----------
    args : argparse.Namespace
        arguments specified by the user
    funct : function
        function to be called when the recording is being read.
    """
    def __init__(self, args, funct):
        super(DAQmxReader, self).__init__()  # py2

        # this line is also in the EDF input
        physicalChannel = (args.dev + '/ai' + args.analoginput).encode('utf-8')
        nameToAssignToChannel  = ''.encode('utf-8')  # use default names
        s_freq = float(args.s_freq)
        self.buffer_size = int(s_freq * args.buffer_size)
        self.timeout = args.timeout
        self.n_chan = args.n_chan
        self.funct = funct

        # self.CreateAIVoltageChan(physicalChannel, nameToAssignToChannel,
                                 # DAQmx_Val_Diff, args.minval, args.maxval,
                                 # DAQmx_Val_Volts, None)
        self.CreateAIVoltageChan(b'Dev1/ai0:7, Dev1/ai16:23', nameToAssignToChannel,
                                 DAQmx_Val_Diff, args.minval, args.maxval,
                                 DAQmx_Val_Volts, None)
        # self.CreateAIVoltageChan(b'Dev2/ai0:7, Dev2/ai16:23, Dev2/ai32:39, Dev2/ai48:55, Dev2/ai64:71', nameToAssignToChannel,
                                 # DAQmx_Val_Diff, args.minval, args.maxval,
                                 # DAQmx_Val_Volts, None)
        self.CreateDIChan(b'Dev1/port0/line0:31', nameToAssignToChannel, DAQmx_Val_ChanPerLine) 
        # self.CreateDIChan(b'Dev2/port0/line0:7', nameToAssignToChannel, DAQmx_Val_ChanPerLine)
        self.CfgSampClkTiming(b'', s_freq, DAQmx_Val_Rising,
                              DAQmx_Val_ContSamps, self.buffer_size)
        self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Acquired_Into_Buffer,
                                            self.buffer_size, 0)
        self.AutoRegisterDoneEvent(0)

        self.edf = None
        if args.edf is not None:
            self.edf = ExportEdf()
            self.edf.open(args)

    def EveryNCallback(self):
        """Read the recording once buffer on the device is ready.
        """
        read = int32()
        data = zeros(self.buffer_size * self.n_chan)
        self.ReadAnalogF64(DAQmx_Val_Auto, self.timeout,
                           DAQmx_Val_GroupByChannel, data,
                           self.buffer_size * self.n_chan, byref(read), None)
        self.ReadDigitalU32(DAQmx_Val_Auto, self.timeout,
                            DAQmx_Val_GroupByChannel, data,
                            self.buffer_size * self.n_chan, byref(read), None)

        data = data.reshape((self.n_chan, self.buffer_size))
        if self.edf is not None:
            self.edf.write(data)
        self.funct(data, self.buffer_size)
        return 0 # The function should return an integer

    def DoneCallback(self, status):
        """Close the recordings, although I'm not sure when this is called.

        Probably raise error if recordings are interrupted
        """
        if self.edf is not None:
            self.edf.close()
        return 0
