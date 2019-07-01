import ctypes
from ctypes import create_string_buffer, c_int, c_char, c_char_p, c_byte, c_ubyte, c_short, c_double, cdll, pointer, byref, c_uint32
import time
import numpy

hhlib = ctypes.WinDLL("hhlib.dll")

print hhlib


class HydraHarp400(object):

    MODE_HIST = 0
    HISTCHAN  = 65536

    def __init__(self, devnum=0, refsource='internal', debug=False):
        self.debug = debug
        self.devnum = int(devnum)
        self.lib_version = create_string_buffer(8)
        hhlib.HH_GetLibraryVersion(self.lib_version);
        if self.debug: print "HHLib Version: '%s'" % self.lib_version.value #% str(self.lib_version.raw).strip()
        self.lib_version = self.lib_version.value
        
        self.hw_serial = create_string_buffer(8)
        retcode = hhlib.HH_OpenDevice(self.devnum, self.hw_serial) 
        if(retcode==0):
            self.hw_serial = self.hw_serial.value
            if self.debug: print "Device %i Found, serial %s" % (self.devnum, self.hw_serial)
        else:
            print "failed to find device %i" % self.devnum
            error_string = create_string_buffer(40)
            hhlib.HH_GetErrorString(error_string, retcode)
            print "print Error: %s" % error_string.value
        
        
        self.refsource = refsource.lower()
        if   self.refsource == 'internal': self.refsource_i = 0
        elif self.refsource == 'external': self.refsource_i = 1
        else: print "Unknown refsource %s" % self.refsource
        
        if self.debug:  print "Initializing the device..."
        
        retcode = hhlib.HH_Initialize(self.devnum, self.MODE_HIST, self.refsource_i)
        if retcode < 0:
            print "HH init error %i. Aborted." % retcode

        self.hw_model   = create_string_buffer(16)
        self.hw_partno  = create_string_buffer(8)
        retcode = hhlib.HH_GetHardwareInfo(self.devnum,self.hw_model,self.hw_partno); #/*this is only for information*/
        if retcode < 0:
            print "HH_GetHardwareInfo error %d. Aborted." % retcode
        else:
            self.hw_model   = self.hw_model.value
            self.hw_partno  = self.hw_partno.value
            print "Found Model %s Part No %s" % (self.hw_model, self.hw_partno)
        
        self.num_input_channels = c_int()
        retcode = hhlib.HH_GetNumOfInputChannels(self.devnum, byref(self.num_input_channels))
        if retcode < 0:
            print "HH_GetNumOfInputChannels error %d." % retcode
        else:
            self.num_input_channels = self.num_input_channels.value
            print "Device has %i input channels" % self.num_input_channels
        
        
        self.hist_data_channel = [None]*self.num_input_channels
        
        if self.debug: print "Calibrating..."
        retcode = hhlib.HH_Calibrate(self.devnum);
        if retcode < 0:
            print "HH_Calibrate error %i" % retcode

    def setup_experiment(self,
            Binning = 0,
            #Range=0, 
            Offset=0, 
            Tacq=1000, #Measurement time in millisec, you can change this
            SyncDivider = 8,
            SyncChannelOffset = 0,
            SyncCFDZeroCross = 10, SyncCFDLevel = 100, 
            InputCFDZeroCross = 10, InputCFDLevel = 100):

        self.Tacq = int(Tacq)

        self.SyncDivider = int(SyncDivider)
        retcode = hhlib.HH_SetSyncDiv(self.devnum, self.SyncDivider)
        if retcode < 0: print "HH_SetSyncDiv error %i" % retcode
        
        self.SyncCFDLevel = int(SyncCFDLevel)
        self.SyncCFDZeroCross = int(SyncCFDZeroCross)

        retcode = hhlib.HH_SetSyncCFD(self.devnum, self.SyncCFDLevel, self.SyncCFDZeroCross)
        if retcode < 0: print "HH_SetSyncCFD error %i" % retcode

        self.SyncChannelOffset = int(SyncChannelOffset)
        retcode = hhlib.HH_SetSyncChannelOffset(self.devnum, self.SyncChannelOffset)
        if retcode < 0: print "HH_SetSyncChannelOffset error %i" % retcode

        self.InputCFDLevel = int(InputCFDLevel)
        self.InputCFDZeroCross = int(InputCFDZeroCross) 
        for chan_num in range(self.num_input_channels):
            retcode = hhlib.HH_SetInputCFD(self.devnum, chan_num, self.InputCFDLevel, self.InputCFDZeroCross)
            if retcode < 0: print "HH_SetInputCFD error %i" % retcode
            retcode = hhlib.HH_SetInputChannelOffset(self.devnum, chan_num, 0)
            if retcode < 0: print "HH_SetInputChannelOffset error %i" % retcode

        MAXLENCODE = 6
        self.HistLen = c_int()
        retcode = hhlib.HH_SetHistoLen(self.devnum, MAXLENCODE, byref(self.HistLen))
        self.HistLen = self.HistLen.value
        if retcode < 0: print "HH_SetHIstoLen error %i" % retcode

        
        self.Binning = int(Binning)
        retcode = hhlib.HH_SetBinning(self.devnum, self.Binning)
        if retcode < 0: print "HH_SetBinning Error %i" % retcode
        
        self.Offset = int(Offset)
        retcode = hhlib.HH_SetOffset(self.devnum, self.Offset)
        if retcode < 0: print "HH_SetOffset error %i" % retcode
        
        self.Resolution = c_int()
        retcode = hhlib.HH_GetResolution(self.devnum, byref(self.Resolution))
        if retcode <0: print "HH_GetResolution error %i" % retcode
        
        #Note: after Init or SetSyncDiv you must allow >400 ms for valid new count rate readings
        time.sleep(0.4)
        
        self.read_count_rates()
            
        # TODO HH_GetWarnings

        #if self.debug: print "Resolution=%1dps Countrate0=%1d/s Countrate1=%1d/s" % (self.Resolution, self.Countrate0, self.Countrate1)

        retcode = hhlib.HH_SetStopOverflow(self.devnum,0,65535)
        
        
    def read_count_rates(self):
        sr = c_int()
        cr = c_int()
        retcode = hhlib.HH_GetSyncRate(self.devnum, byref(sr))
        self.Syncrate = sr.value
        self.Countrate = numpy.zeros(self.num_input_channels, dtype=int)
        for chan_num in range(self.num_input_channels):
            retcode = hhlib.HH_GetCountRate(self.devnum, chan_num, byref(cr))
            self.Countrate[chan_num] = cr.value
            
        return self.Syncrate, self.Countrate
        
    def start_histogram(self, Tacq=None):
        if self.debug: print "Starting Histogram"
        retcode = hhlib.HH_ClearHistMem(self.devnum)
        if retcode < 0 : "HH_ClearHistMem error %i" % retcode
        
        # set a new acquisition time if given
        if Tacq:
            self.Tacq = int(Tacq)
            
        retcode = hhlib.HH_StartMeas(self.devnum, self.Tacq)
        if retcode < 0: "HH_StartMeas error %i" % retcode
        
        return
    
    def check_done_scanning(self):
        status = c_int()
        retcode = hhlib.HH_CTCStatus(self.devnum, byref(status))
        if status.value == 0: # not done
            return False
        else: # scanning done
            return True
            
    def stop_histogram(self):
        if self.debug: print "Stop Histogram"
        retcode = hhlib.HH_StopMeas(self.devnum)
        if retcode < 0: "HH_StopMeas error %i" % retcode
        
    def read_histogram_data(self, channel=0, clear_after=True):
        channel = int(channel)
        if self.debug: print "Read Histogram Data for channel %i" % channel
        
        #unsigned int counts[HISTCHAN];
        #self.hist_data = numpy.zeros(self.HISTCHAN, dtype=numpy.uint32)
        #retcode = phlib.PH_GetBlock(self.devnum, self.hist_data.ctypes.data, 0) # grab block 0
        
        self.hist_data_channel[channel] = numpy.zeros(self.HistLen, dtype=numpy.uint32)
        retcode = hhlib.HH_GetHistogram(self.devnum, 
                                        self.hist_data_channel[channel].ctypes.data_as(ctypes.POINTER(c_uint32)), 
                                        channel,
                                        int(clear_after))
        
        if retcode < 0: "HH_GetHistogram error %i" % retcode

        return self.hist_data_channel[channel]


if __name__ == '__main__':
    
    import pylab as pl
    
    hh = HydraHarp400(debug=True)
    print hh.read_count_rates()
    hh.setup_experiment()#Range, Offset, Tacq, SyncDivider, CFDZeroCross0, CFDLevel0, CFDZeroCross1, CFDLevel1)
    hh.start_histogram(Tacq=2300)
    t0 = time.time()
    while not hh.check_done_scanning():
        print "acquiring", time.time() - t0, "sec"
        time.sleep(0.1)
    hh.stop_histogram()
    hh.read_histogram_data(channel=0)
    print hh.read_count_rates()
    
    pl.figure(1)
    pl.plot(hh.hist_data_channel[0])
    pl.show()