'''
Created on Apr 1, 2014

@author: esbarnard
'''
from __future__ import absolute_import, print_function
from ScopeFoundry import HardwareComponent
import numpy as np

try:
    from HW_Picoharp.pypicoharp.pypicoharp import PicoHarp300
except Exception as err:
    print("could not load modules for PicoHarp: {}".format(err))

class PicoHarpHW(HardwareComponent):

    def setup(self):
        self.name = "picoharp"
        
        self.count_rate0 = self.settings.New("count_rate0", dtype=int, ro=True, vmin=0, vmax=100e6)
        self.count_rate1 = self.settings.New("count_rate1", dtype=int, ro=True, vmin=0, vmax=100e6)
        self.mode = self.settings.New("Mode", dtype=str, choices=[("HIST","HIST"),("T2","T2"),("T3","T3")], initial='HIST')


        self.settings.New("Tacq", dtype=float, unit="s", si=True, vmin=1e-3, vmax=100*60*60)
        self.settings.New("Binning", dtype=int, choices=[(str(x), x) for x in range(0,8)]) ##binning/range
        #self.settings.New("Resolution", dtype=int, unit="ps", si=False)
        self.settings.New("Resolution", dtype=int, choices=[("4 ps", 4), ("8 ps", 8), ("16 ps", 16), ("32 ps", 32), ("64 ps", 64), ("128 ps", 128), ("256 ps", 256), ("512 ps", 512)], initial=4)
        self.settings.New("SyncDivider", dtype=int, choices=[("1",1),("2",2),("4",4),("8",8)])
        self.settings.New("SyncOffset", dtype=int, vmin=-99999, vmax=99999, si=False)
        
        self.settings.New("CFDLevel0", dtype=int, unit="mV", vmin=0, vmax=800, si=False)
        self.settings.New("CFDZeroCross0", dtype=int,  unit="mV", vmin=0, vmax=20, si=False)
        self.settings.New("CFDLevel1", dtype=int, unit="mV", vmin=0, vmax=800, si=False)
        self.settings.New("CFDZeroCross1", dtype=int, unit="mV", vmin=0, vmax=20, si=False)

        self.settings.New("stop_on_overflow", dtype=bool)
        
        self.histogram_channels = self.settings.New("histogram_channels", dtype=int, ro=False, vmin=0, vmax=2**16, initial=2**16, si=False)

    def connect(self):
        if self.settings['debug_mode']: self.log.info( "Connecting to PicoHarp" )
        
        # Open connection to hardware
        
        self.log.debug(str(self.settings['Mode']))
        
        PH = self.picoharp = PicoHarp300(devnum=0, mode = self.mode.val, debug=self.settings['debug_mode'])

        # connect logged quantities
        
        LQ = self.settings.as_dict()
        
        LQ["count_rate0"].hardware_read_func = PH.read_count_rate0
        LQ["count_rate1"].hardware_read_func = PH.read_count_rate1
        
        LQ["Binning"].updated_value.connect(lambda x, LQ=LQ: LQ["Resolution"].read_from_hardware() ) ##
        
        
        LQ["Tacq"].hardware_set_func         = PH.set_Tacq_seconds
        LQ["Tacq"].hardware_read_func        = PH.get_Tacq_seconds
        
        LQ["Binning"].hardware_set_func      = PH.write_Binning ##
        LQ["Binning"].hardware_read_func     = lambda PH=PH: PH.Binning ##

        #LQ["Resolution"].hardware_set_func = PH.set_Resolution ###
        LQ["Resolution"].hardware_read_func     = PH.read_Resolution
        
        LQ["SyncDivider"].hardware_set_func  = PH.write_SyncDivider
        LQ["SyncDivider"].hardware_read_func = lambda PH=PH: PH.SyncDivider
        
        LQ["SyncOffset"].hardware_set_func   = PH.write_SyncOffset
        LQ["SyncOffset"].hardware_read_func = lambda PH=PH: PH.SyncOffset
        
        LQ["CFDLevel0"].hardware_set_func    = PH.write_CFDLevel0
        LQ["CFDLevel0"].hardware_read_func = lambda PH=PH: PH.CFDLevel[0]
        
        LQ["CFDZeroCross0"].hardware_set_func  = PH.write_CFDZeroCross0
        LQ["CFDZeroCross0"].hardware_read_func = lambda PH=PH: PH.CFDZeroCross[0]
        
        LQ["CFDLevel1"].hardware_set_func    = PH.write_CFDLevel1
        LQ["CFDLevel1"].hardware_read_func   = lambda PH=PH: PH.CFDLevel[1]
        
        LQ["CFDZeroCross1"].hardware_set_func  = PH.write_CFDZeroCross1
        LQ["CFDZeroCross1"].hardware_read_func = lambda PH=PH: PH.CFDZeroCross[1]

        LQ["stop_on_overflow"].hardware_set_func = PH.write_stop_overflow
        LQ["stop_on_overflow"].update_value(True)
        
        
        #connect logged quantities to other gui widgets
        
        
        # initial settings
        self.picoharp.setup_experiment() # sets all the defaults
        
        # read initial information
        self.read_from_hardware()
        
        
        
        if self.settings['debug_mode']: self.log.debug( "Done Connecting to PicoHarp" )
        
        
    def disconnect(self):
        
        for lq in self.settings.as_list():
            lq.hardware_read_func = None
            lq.hardware_set_func = None


        if hasattr(self, 'picoharp'):
            #disconnect hardware
            self.picoharp.close()
            
            #clean up hardware object
            del self.picoharp

    def calc_num_hist_chans(self):
        cr0 = self.settings.count_rate0.read_from_hardware()
        rep_period_s = 1.0/cr0
        time_bin_resolution = self.settings['Resolution']*1e-12
        return int(np.ceil(rep_period_s/time_bin_resolution))