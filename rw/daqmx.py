# On Dell Optiplex Physiology computer as of 1/29/2015:
# Dev1=PCIe-6323: AI: 0-7, 16-23. DI: Port0/0:31
# Dev2=PCI-6225: AI: 0-7, 16-23, 32-39, 48-55, 64-71. DI: Port0/0:7

from numpy import zeros

# package to control NI
from ctypes import byref, create_string_buffer
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

# from edf import ExportEdf

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

        ''' Define Tasks: 
        Master Analog task is already defined as the parent task (self)
        Digital/Slave tasks are children (self.___)
        '''
        self.MasterDTask = Task()
        self.SlaveATask = Task()
        self.SlaveDTask = Task()

        ''' Define inputs channels for Master & Slave devices: Analog & Digital channel types
        '''
        # Master Analog Inputs
        self.CreateAIVoltageChan(b'Dev1/ai0:7, Dev1/ai16:23', 
                                 nameToAssignToChannel, DAQmx_Val_Diff, minval, maxval, DAQmx_Val_Volts, None)
        self.nchan = 16
		
        # Master Digital Inputs
        self.MasterDTask.CreateDIChan(b'Dev1/port0/line0:31', 
                                      nameToAssignToChannel, DAQmx_Val_ChanPerLine)
        self.MasterDTask.nchan = 32

        # Slave Analog Inputs
        self.SlaveATask.CreateAIVoltageChan(b'Dev2/ai0:7, Dev2/ai16:23, Dev2/ai32:39, Dev2/ai48:55, Dev2/ai64:71', 
                                            nameToAssignToChannel, DAQmx_Val_Diff, minval, maxval, DAQmx_Val_Volts, None)
        self.SlaveATask.nchan = 40
        
        # Slave Digital Inputs
        self.SlaveDTask.CreateDIChan(b'Dev2/port0/line0:7', 
                                     nameToAssignToChannel, DAQmx_Val_ChanPerLine)
        self.SlaveDTask.nchan = 8
		
        
        
        ''' Set Clocks for each task: Master/Slave & Analog/Digital
        '''
        # Set Master analog sample clock
        self.CfgSampClkTiming(b'', s_freq, DAQmx_Val_Rising, DAQmx_Val_ContSamps, self.buffer_size)
        master_analog_sample_clock = b'/Dev1/ai/SampleClock' # By definition (revealed in ANSI C example: ContAI-ReadDigChan.c
		# Set Master Digital sample clock to be Master Analog sample clock
        self.MasterDTask.CfgSampClkTiming(master_analog_sample_clock, s_freq, DAQmx_Val_Rising, DAQmx_Val_ContSamps, self.buffer_size)

        # Synchronize Slave device by setting clocks to master_analog_sample_clock
        self.SlaveATask.CfgSampClkTiming(master_analog_sample_clock, s_freq, DAQmx_Val_Rising, DAQmx_Val_ContSamps, self.buffer_size)
        self.SlaveDTask.CfgSampClkTiming(master_analog_sample_clock, s_freq, DAQmx_Val_Rising, DAQmx_Val_ContSamps, self.buffer_size)
        
		# Register an event to automatically occur every N samples
        self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Acquired_Into_Buffer, self.buffer_size, 0)
        self.AutoRegisterDoneEvent(0) # Registers a callback function to receive an event when a task stops due to an error or when a finite acquisition task or finite generation task completes execution. A Done event does not occur when a task is stopped explicitly, such as by calling DAQmxStopTask.

		# Start non-master devices first: Digital devices need to be started first, and slave before master
        self.SlaveDTask.StartTask()
        self.SlaveATask.StartTask()
        self.MasterDTask.StartTask()

        
        # self.edf = None
        # if args.edf is not None:
            # self.edf = ExportEdf()
            # self.edf.open(args)

            
            
    def EveryNCallback(self):
        # Read the recording once buffer on the device is ready.
        read = int32()
        # master_a_nchan = 16
        # slave_a_nchan = 40
        # master_d_nchan = 32
        # slave_d_nchan = 8

        # Data arrays for analog data must be Float 64, which is apparently the python default
        master_adata = zeros(self.buffer_size * self.nchan)
        self.ReadAnalogF64(DAQmx_Val_Auto, self.timeout,
                           DAQmx_Val_GroupByChannel, master_adata,
                           self.buffer_size * self.nchan, byref(read), None)

        slave_adata = zeros(self.buffer_size * self.SlaveATask.nchan)
        self.SlaveATask.ReadAnalogF64(DAQmx_Val_Auto, self.timeout,
                                      DAQmx_Val_GroupByChannel, slave_adata,
                                      self.buffer_size * self.SlaveATask.nchan, byref(read), None)

        # Data arrays for Digital data must be unisigned int32
        master_ddata = zeros(self.buffer_size * self.MasterDTask.nchan, dtype=uInt32)
        slave_ddata = zeros(self.buffer_size * self.SlaveDTask.nchan, dtype=uInt32)

        self.MasterDTask.ReadDigitalU32(DAQmx_Val_Auto, self.timeout,
                            DAQmx_Val_GroupByChannel, master_ddata,
                            self.buffer_size * self.MasterDTask.nchan, byref(read), None)
        self.SlaveDTask.ReadDigitalU32(DAQmx_Val_Auto, self.timeout,
                            DAQmx_Val_GroupByChannel, slave_ddata,
                            self.buffer_size * self.SlaveDTask.nchan, byref(read), None)
        
        # Reshape data into 2D matrix (not necessarily necessary, but simplifies indexing)
        master_adata = master_adata.reshape(self.nchan, self.buffer_size)
        slave_adata = slave_adata.reshape(self.SlaveATask.nchan, self.buffer_size)
        master_ddata = master_ddata.reshape(self.MasterDTask.nchan, self.buffer_size)
        slave_ddata = slave_ddata.reshape(self.SlaveDTask.nchan, self.buffer_size)

        # print('MA: ' + str(master_adata[0, 0]) + ' SA: ' + str(slave_adata[0, 0]))
        # print('MD: ' + str(master_ddata[0, 0]) + ' SD: ' + str(slave_ddata[0, 0]))
        for i in range(0,50):
            print('MA: %.3f' %master_adata[0, i] + ' SA: %.3f' %slave_adata[0, i] + ' MD: ' + str(master_ddata[0, i]) + ' SD: ' + str(slave_ddata[0, i]))

        # if self.edf is not None:
            # self.edf.write(vstack((master_adata, master_ddata,
                                   # slave_adata, slave_ddata)))

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

        # if self.edf is not None:
            # self.edf.close()
        # return 0


reader = DAQmxReader()
reader.StartTask()
input('Acquiring samples continuously. Press Enter to interrupt\n')
reader.StopTask()
reader.ClearTask()
