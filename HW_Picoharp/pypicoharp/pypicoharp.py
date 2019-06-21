from __future__ import print_function, absolute_import
import ctypes
from ctypes import create_string_buffer, c_int, c_double, byref
import time
import numpy
import platform
import os
import logging

logger = logging.getLogger(__name__)
#
if platform.architecture()[0] == '64bit':
    #phlib = ctypes.WinDLL("phlib64.dll")
    phlib = ctypes.WinDLL(os.path.join(os.path.dirname(__file__), "phlib64.dll"))

else:
    phlib = ctypes.WinDLL(os.path.join(os.path.dirname(__file__), "phlib.dll"))
#    
#phlib = ctypes.WinDLL(os.path.join(os.path.dirname(__file__), "phlib64.dll"))
# updated for phlib v3.0 2014-04-02
# updated to work in T2, T3 modes 2015-06-26

class PicoHarp300(object):

    MODE_HIST = 0
    MODE_T2   = 2
    MODE_T3   = 3

    HISTCHAN  = 65536
    TTREADMAX = 131072  # 128K event records

    FLAG_FIFOFULL  = 0x0003  # T-modes
    FLAG_OVERFLOW  = 0x0040  # Histomode
    FLAG_SYSERROR  = 0x0100  # Hardware problem


    def __init__(self, devnum=0, mode='HIST', debug=False):

        self.debug = debug

        self.mode = mode
        assert mode in ('HIST', 'T2','T3')

        self.devnum = devnum
        self.Countrate    = [None,None]
        self.CFDLevel     = [None,None]
        self.CFDZeroCross = [None, None]

        self.histogram_data = numpy.zeros(self.HISTCHAN, dtype=numpy.uint32) #unsigned int counts[HISTCHAN];
        self.time_array = numpy.arange(self.HISTCHAN, dtype=float)

        self.tttr_buffer = numpy.zeros(self.TTREADMAX, dtype=numpy.uint32) # unsigned int buffer[TTREADMAX];

        self._err_buffer = create_string_buffer(40)
        
        lib_version = create_string_buffer(8)
        self.handle_err(phlib.PH_GetLibraryVersion(lib_version))
        self.lib_version = lib_version.value
#        if self.debug: logger.debug("PHLib Version: '%s'" % self.lib_version)
#        assert self.lib_version == b"3.0"
        
        hw_serial = create_string_buffer(8)
        self.handle_err(phlib.PH_OpenDevice(self.devnum, hw_serial)) 
        self.hw_serial = hw_serial.value
        if self.debug: logger.debug( "Device %i Found, serial %s" % (self.devnum, self.hw_serial) )
        
        if self.debug:  logger.debug( "Initializing PicoHarp device..." )

        if self.mode == 'HIST':
            if self.debug: "HIST mode"
            self.handle_err(phlib.PH_Initialize(self.devnum, self.MODE_HIST))
        elif self.mode == 'T2':
            if self.debug: "T2 mode"
            self.handle_err(phlib.PH_Initialize(self.devnum, self.MODE_T2))
        elif self.mode == 'T3':
            if self.debug: "T2 mode"
            self.handle_err(phlib.PH_Initialize(self.devnum, self.MODE_T3))

        hw_model   = create_string_buffer(16)
        hw_partnum = create_string_buffer(8)
        hw_version = create_string_buffer(8)
        self.handle_err(phlib.PH_GetHardwareVersion(
                                self.devnum,hw_model, hw_version))
        self.hw_model   = hw_model.value
        self.hw_partnum = hw_partnum.value
        self.hw_version = hw_version.value
        if self.debug: 
            logger.debug( "Found Model %s PartNum %s Version %s" % (self.hw_model, self.hw_partnum, self.hw_version) )
        
        if self.debug: logger.debug( "PicoHarp Calibrating..." )
        self.handle_err( phlib.PH_Calibrate(self.devnum) )
            
        # automatically stops acquiring a histogram when a bin is filled to 2**16
        self.handle_err(phlib.PH_SetStopOverflow(self.devnum,1,65535)) 
    
    def handle_err(self, retcode):
        if retcode < 0:
            phlib.PH_GetErrorString(self._err_buffer, retcode)
            self.err_message = self._err_buffer.value
            raise IOError(self.err_message)
        return retcode

    def setup_experiment(self,
            Tacq=1000, #Measurement time in millisec, you can change this
            Binning=0, SyncOffset=0, 
            SyncDivider = 8, 
            CFDZeroCross0=10, CFDLevel0=100, 
            CFDZeroCross1=10, CFDLevel1=100):

        self.Tacq = self.set_Tacq(Tacq)
        
        #self.write_Binning(Binning)
        self.write_SyncOffset(SyncOffset)
        self.write_SyncDivider(SyncDivider)
        self.write_InputCFD(0, CFDLevel0, CFDZeroCross0)
        self.write_InputCFD(1, CFDLevel1, CFDZeroCross1)

        self.read_count_rates()
        if self.debug: logger.debug( "Resolution=%1dps Countrate0=%1d/s Countrate1=%1d/s" % (self.Resolution, self.Countrate0, self.Countrate1) )

    def set_Tacq(self, Tacq):
        "Set Acquisition time in milliseconds"
        self.Tacq = int(Tacq)
        return self.Tacq
    
    def set_Tacq_seconds(self, t_sec):
        "Set Acquisition time in seconds"
        return self.set_Tacq(t_sec*1000) / 1000.
    
    def get_Tacq_seconds(self):
        return self.Tacq * 1.0e-3

    def write_SyncDivider(self, SyncDivider):
        self.SyncDivider = int(SyncDivider)
        if self.debug: logger.debug( "write_SyncDivider " + str(self.SyncDivider) )
        self.handle_err(phlib.PH_SetSyncDiv(self.devnum, self.SyncDivider))
        #Note: after Init or SetSyncDiv you must allow 100 ms for valid new count rate readings
        time.sleep(0.11)
    
    def write_InputCFD(self, chan, level, zerocross):
        self.CFDLevel[chan] = int(level)
        self.CFDZeroCross[chan] = int(zerocross)
        if self.debug: logger.debug( "write_InputCFD {} {} {}".format( chan, level, zerocross))
        #self.handle_err(phlib.PH_SetInputCFD(self.devnum, chan, int(level), int(zerocross)))
        self.handle_err(phlib.PH_SetCFDZeroCross(self.devnum, chan, int(zerocross)))
    def write_CFDLevel0(self, level):
        self.write_InputCFD(0, level, self.CFDZeroCross[0])
        
    def write_CFDLevel1(self, level):
        self.write_InputCFD(1, level, self.CFDZeroCross[1])

    def write_CFDZeroCross0(self, zerocross):
        self.write_InputCFD(0, self.CFDLevel[0], zerocross)
    
    def write_CFDZeroCross1(self, zerocross):
        self.write_InputCFD(1, self.CFDLevel[1], zerocross)
        
#    def write_Binning(self, Binning):
#        self.Binning = int(Binning)
#        self.handle_err(phlib.PH_SetBinning(self.devnum, self.Binning))
#        self.read_Resolution()
#        self.time_array = numpy.arange(self.HISTCHAN, dtype=float)*self.Resolution
        
    def read_Resolution(self):
#        r = c_double(0)
#        self.handle_err(phlib.PH_GetResolution(self.devnum))#, byref(r)))
#        self.Resolution = r.value
#        return self.Resolution
        self.time_array = numpy.arange(self.HISTCHAN, dtype=float)*phlib.PH_GetResolution(self.devnum)
        return phlib.PH_GetResolution(self.devnum)
	
    def write_SyncOffset(self, SyncOffset):
        """
        :param SyncOffset: time offset in picoseconds
        :type SyncOffset: int
        """     
        self.SyncOffset = int(SyncOffset)
        self.handle_err(phlib.PH_SetOffset(self.devnum, self.SyncOffset))

    def read_count_rate(self, chan):
#        cr = c_int(-1)
#        self.handle_err(phlib.PH_GetCountRate(self.devnum, chan))#, byref(cr)))
#        self.Countrate[chan] = cr.value
        return phlib.PH_GetCountRate(self.devnum, chan)
    
    def read_count_rate0(self):
        self.Countrate0 = self.read_count_rate(0)
        return self.Countrate0
    
    def read_count_rate1(self):
        self.Countrate1 = self.read_count_rate(1)
        return self.Countrate1

    def read_count_rates(self):
        self.read_count_rate0()
        self.read_count_rate1()
        return self.Countrate0, self.Countrate1
        
    def start_histogram(self, Tacq=None):
        if self.debug: logger.debug( "Starting Histogram" )

        self.handle_err(phlib.PH_ClearHistMem(self.devnum, 0))
        # always use Block 0 if not Routing
        self.start_measure(Tacq)

    def start_measure(self, Tacq=None):
#        self.time_array = numpy.arange(self.HISTCHAN, dtype=float)*self.Resolution
        if self.debug: logger.debug( "PH Starting Measure" )
        # set a new acquisition time if given
        if Tacq:
            self.set_Tacq(Tacq)
        self.handle_err(phlib.PH_StartMeas(self.devnum, self.Tacq))

    def check_done_scanning(self):
#        status = c_int()
#        self.handle_err(phlib.PH_CTCStatus(self.devnum))#, byref(status)))
        if phlib.PH_CTCStatus(self.devnum) == 0: # not done
            return False
        else: # scanning done
            return True
            
    def stop_histogram(self):
        if self.debug: logger.debug( "Stop Histogram" )
        return self.stop_measure()

    def stop_measure(self):
        if self.debug: logger.debug( "PH Stop Measure" )
        self.handle_err(phlib.PH_StopMeas(self.devnum))
        
    def read_histogram_data(self):
        if self.debug: logger.debug( "Read Histogram Data" )
        phlib.PH_GetBlock.argtypes = (ctypes.c_int, ctypes.c_void_p, ctypes.c_int)
        self.handle_err(phlib.PH_GetBlock(self.devnum, self.histogram_data.ctypes.data, ctypes.c_int(0) )) # grab block 0
        return self.histogram_data

    def read_fifo(self, max_count=TTREADMAX):
        nactual = c_int()
        #blocksz = TTREADMAX; // in steps of 512
        assert max_count % 512 == 0
        self.handle_err(phlib.PH_ReadFiFo(self.devnum, self.tttr_buffer.ctypes.data, max_count, byref(nactual)))
        return nactual.value, self.tttr_buffer
    
    def write_stop_overflow(self, stop_on_overflow=True, stopcount=65535):
        """
        This setting determines if a measurement run will stop if any channel 
        reaches the maximum set by stopcount. If stop_ofl is 0
        the measurement will continue but counts above 65,535 in any bin will be clipped.
        """
        
        if stop_on_overflow:
            overflow_int = 1
        else:
            overflow_int = 0
        
        self.handle_err(phlib.PH_SetStopOverflow(self.devnum, overflow_int, stopcount))
        
    def read_elapsed_meas_time(self):
        elapsed_time = ctypes.c_double()
        self.handle_err(phlib.PH_GetElapsedMeasTime(self.devnum, byref(elapsed_time)))
    
        self.elapsed_time = elapsed_time.value
        return self.elapsed_time
    
    def close(self):
        return self.handle_err(phlib.PH_CloseDevice(self.devnum))
    

if __name__ == '__main__':
    
    #import pylab as pl
    import matplotlib.pyplot as plt
    
    ## HIST mode test
    ph = PicoHarp300(debug=True, mode='HIST')
    ph.setup_experiment()#Range, Offset, Tacq, SyncDivider, CFDZeroCross0, CFDLevel0, CFDZeroCross1, CFDLevel1)
    ph.start_histogram(Tacq=2300)
    t0 = time.time()
    while not ph.check_done_scanning():
        print("acquiring {} sec".format( time.time() - t0 ))
        time.sleep(0.1)
    ph.stop_histogram()
    ph.read_histogram_data()
    
    plt.figure(1)
    plt.plot(ph.histogram_data)
    plt.show()

    ## T3 mode test
    ph = PicoHarp300(debug=True, mode='T3')
    ph.setup_experiment()
    ph.start_measure(Tacq=1000)
    t0 = time.time()
    while not ph.check_done_scanning():
        print("acquiring {} sec".format( time.time() - t0 ))
        nactual, buffer = ph.read_fifo()
        print(nactual)
        time.sleep(0.1)
    ph.stop_measure()

