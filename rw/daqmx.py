# On Dell Optiplex Physiology computer as of 1/29/2015:
# Dev1=PCIe-6323: AI: 0-7, 16-23. DI: Port0/0:31
# Dev2=PCI-6225: AI: 0-7, 16-23, 32-39, 48-55, 64-71. DI: Port0/0:7

from numpy import zeros

# package to control NI
from ctypes import byref, c_char_p, c_float, create_string_buffer
from PyDAQmx.DAQmxConstants import (DAQmx_Val_Diff,
                                    DAQmx_Val_Volts,
                                    DAQmx_Val_Rising,
                                    DAQmx_Val_ContSamps,
                                    DAQmx_Val_Acquired_Into_Buffer,
                                    DAQmx_Val_GroupByChannel,
                                    DAQmx_Val_Auto,
                                    DAQmx_Val_ChanPerLine,
                                    )
from PyDAQmx.DAQmxTypes import *
from PyDAQmx.Task import Task

from .edf import ExportEdf


# quick workaround for args to pass to EDF
class Args():
    edf = r'C:\Users\cashlab\Documents\data'
    nchan = 96
    minval = -1
    maxval = 1
    s_freq = 1000

args = Args()


class DAQmxReader(Task):
    """Class to interact with NI devices.
	"""
    def __init__(self):
        super().__init__()

        nameToAssignToChannel  = ''.encode('utf-8')  # use default names
        s_freq = 1000.
        self.buffer_size = int(s_freq * 0.1)
        self.timeout = 10.
        minval = -1.
        maxval = 1.

        # Master Analog task is the parent task. Digital/Slave tasks are children
        self.MasterDTask = Task()
        self.SlaveATask = Task()
        self.SlaveDTask = Task()

        # Master Analog Inputs
        self.CreateAIVoltageChan(b'Dev1/ai0:7, Dev1/ai16:23', nameToAssignToChannel,
                                 DAQmx_Val_Diff, minval, maxval,
                                 DAQmx_Val_Volts, None)
        # Master Digital Inputs
        self.MasterDTask.CreateDIChan(b'Dev1/port0/line0:31', nameToAssignToChannel, DAQmx_Val_ChanPerLine)


        # Slave Analog Inputs
        self.SlaveATask.CreateAIVoltageChan(b'Dev2/ai0:7, Dev2/ai16:23, Dev2/ai32:39, Dev2/ai48:55, Dev2/ai64:71', nameToAssignToChannel,
                                            DAQmx_Val_Diff, minval, maxval,
                                            DAQmx_Val_Volts, None)
        # Slave Digital Inputs
        self.SlaveDTask.CreateDIChan(b'Dev2/port0/line0:7', nameToAssignToChannel, DAQmx_Val_ChanPerLine)

        # Set Master analog sample clock
        self.CfgSampClkTiming(b'', s_freq, DAQmx_Val_Rising,
                              DAQmx_Val_ContSamps, self.buffer_size)
		# Synchronize Master Digital clock to Master Analog sample clock
        master_analog_sample_clock = b'/Dev1/ai/SampleClock'
        self.MasterDTask.CfgSampClkTiming(master_analog_sample_clock, s_freq, DAQmx_Val_Rising,
                                          DAQmx_Val_ContSamps, self.buffer_size)
		# Digital devices need to be started first, and slave before master for analog
        self.MasterDTask.StartTask()

		# Set Slave analog sample clock
        self.SlaveATask.CfgSampClkTiming(b'', s_freq, DAQmx_Val_Rising,
                                         DAQmx_Val_ContSamps, self.buffer_size)

		# Synchronize Slave Digital clock to Slave Analog sample clock
        slave_analog_sample_clock = b'/Dev2/ai/SampleClock'
        self.SlaveDTask.CfgSampClkTiming(slave_analog_sample_clock, s_freq, DAQmx_Val_Rising,
                                          DAQmx_Val_ContSamps, self.buffer_size)

		# Route Master analog clock to Slave devices
        self.SlaveATask.SetRefClkSrc(master_analog_sample_clock)
        # Get/Set reference clock rates: Master -> Slave devices
        clkRate = float64()
        self.GetRefClkRate(byref(clkRate))
        self.SlaveATask.SetRefClkRate(clkRate)

        self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Acquired_Into_Buffer,
                                            self.buffer_size, 0)
        self.AutoRegisterDoneEvent(0)

		# Digital devices need to be started first, and slave before master for analog
        self.SlaveDTask.StartTask()
        self.SlaveATask.StartTask()

        self.edf = None
        if args.edf is not None:
            self.edf = ExportEdf()
            self.edf.open(args)

    def EveryNCallback(self):
        """Read the recording once buffer on the device is ready.
        """
        read = int32()
        master_a_nchan = 16
        slave_a_nchan = 40
        master_d_nchan = 32
        slave_d_nchan = 8

        # Data arrays for analog data must be Float 64, which is apparently the python default
        master_adata = zeros(self.buffer_size * master_a_nchan)
        self.ReadAnalogF64(DAQmx_Val_Auto, self.timeout,
                           DAQmx_Val_GroupByChannel, master_adata,
                           self.buffer_size * master_a_nchan, byref(read), None)

        slave_adata = zeros(self.buffer_size * slave_a_nchan)
        self.SlaveATask.ReadAnalogF64(DAQmx_Val_Auto, self.timeout,
                                      DAQmx_Val_GroupByChannel, slave_adata,
                                      self.buffer_size * slave_a_nchan, byref(read), None)

        # Data arrays for Digital data must be unisigned int32
        master_ddata = zeros(self.buffer_size * master_d_nchan, dtype=uInt32)
        slave_ddata = zeros(self.buffer_size * slave_d_nchan, dtype=uInt32)

        self.MasterDTask.ReadDigitalU32(DAQmx_Val_Auto, self.timeout,
                            DAQmx_Val_GroupByChannel, master_ddata,
                            self.buffer_size * master_d_nchan, byref(read), None)
        self.SlaveDTask.ReadDigitalU32(DAQmx_Val_Auto, self.timeout,
                            DAQmx_Val_GroupByChannel, slave_ddata,
                            self.buffer_size * slave_d_nchan, byref(read), None)

        master_adata = master_adata.reshape((master_a_nchan, self.buffer_size))
        slave_adata = slave_adata.reshape((slave_a_nchan, self.buffer_size))
        master_ddata = master_ddata.reshape((master_d_nchan, self.buffer_size))
        slave_ddata = slave_ddata.reshape((slave_d_nchan, self.buffer_size))

        print('MA: ' + str(master_adata[0, 0]) + ' SA: ' + str(slave_adata[0, 0]))
        print('MD: ' + str(master_ddata[0, 0]) + ' SD: ' + str(slave_ddata[0, 0]))

        if self.edf is not None:
            self.edf.write(vstack((master_adata, master_ddata,
                                   slave_adata, slave_ddata)))

        return 0 # The function should return an integer

    def DoneCallback(self, status):
        """Close the recordings, although I'm not sure when this is called.

        Probably raise error if recordings are interrupted
        """
        self.SlaveDTask.StopTask()
        self.SlaveDTask.ClearTask()
        self.SlaveATask.StopTask()
        self.SlaveATask.ClearTask()
        self.MasterDTask.StopTask()
        self.MasterDTask.ClearTask()

        if self.edf is not None:
            self.edf.close()
        return 0


reader = DAQmxReader()
reader.StartTask()
input('Acquiring samples continuously. Press Enter to interrupt\n')
reader.StopTask()
reader.ClearTask()
