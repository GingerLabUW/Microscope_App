import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets#, QColorDialog
import numpy as np
import pickle
import sys
import seabreeze.spectrometers as sb
from pipython import GCSDevice
import time
from ScopeFoundry import HardwareComponent

class PiezoStageHW(HardwareComponent):
    
    ## Define name of this hardware plug-in

    
    def setup(self):
        # Define your hardware settings here.
        # These settings will be displayed in the GUI and auto-saved with data files
        self.name = 'piezostage'
        self.settings.New('x_position', dtype=float, unit='um')
        self.settings.New('y_position', dtype=float, unit='um')

        self.settings.New('x_abs', dtype=float, initial=0, unit='um', vmin=0, vmax=100)
        self.settings.New('y_abs', dtype=float, initial=0, unit='um', vmin=0, vmax=100)
        
        self.settings.New('x_rel', dtype=float, initial=0, unit='um')
        self.settings.New('y_rel', dtype=float, initial=0, unit='um')

        self.add_operation('center_stage', self.center_piezo)
        self.add_operation('absolute_movement', self.abs_mov)
        self.add_operation('relative_movement', self.rel_mov)

    def connect(self):
        # Open connection to the device:
        self.pi_device = GCSDevice("E-710")	# Creates a Controller instant
        self.pi_device.ConnectNIgpib(board=0,device=4) # Connect to GPIB board

        self.axes = self.pi_device.axes[0:2] # selecting x and y axis of the stage
        self.pi_device.INI()
        self.pi_device.REF(axes=self.axes)
        self.pi_device.SVO(axes=self.axes, values=[True,True])	# Turn on servo control for both axes
        
        #Connect settings to hardware:
        LQ = self.settings.as_dict()
        LQ["x_position"].hardware_read_func = self.getX
        LQ["y_position"].hardware_read_func = self.getY

        LQ["x_position"].hardware_set_func = self.abs_mov
        LQ["y_position"].hardware_set_func = self.abs_mov
        
        LQ["x_position"].hardware_set_func = self.rel_mov
        LQ["y_position"].hardware_set_func = self.rel_mov
		
        #Take an initial sample of the data.
        self.read_from_hardware()
        
    def disconnect(self):
        #Disconnect the device and remove connections from settings
        self.settings.disconnect_all_from_hardware()
        if hasattr(self, 'pi_device'):
            self.pi_device.close()
            del self.pi_device
            self.pi_device = None

    def center_piezo(self):
        if hasattr(self, 'pi_device'):
            self.pi_device.MOV(axes=self.axes, values=[50,50])
            self.read_from_hardware()

    def abs_mov(self):
        if hasattr(self, 'pi_device'):
            x_abs_pos = self.settings['x_abs']
            y_abs_pos = self.settings['y_abs']
            self.pi_device.MOV(axes=self.axes, values=[x_abs_pos,y_abs_pos])
            self.read_from_hardware()
        
    def rel_mov(self):
        if hasattr(self, 'pi_device'):
            x_rel_pos = self.settings['x_rel']
            y_rel_pos = self.settings['y_rel']
            self.pi_device.MVR(axes=self.axes, values=[x_rel_pos,y_rel_pos])
            self.read_from_hardware()

    def getX(self):
        return self.pi_device.qPOS(axes=self.axes)['1']

    def getY(self):
        return self.pi_device.qPOS(axes=self.axes)['2']