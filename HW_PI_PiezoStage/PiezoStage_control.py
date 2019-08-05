from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import pyqtgraph as pg
import numpy as np
import time
import pickle
import os.path
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.Point import Point

class PiezoStageControl(Measurement):
    name = 'piezostage_control'

    def setup(self):
        self.ui_filename = sibling_path(__file__, "stage_control.ui")
        
        #Load ui file and convert it to a live QWidget of the user interface
        self.ui = load_qt_ui_file(self.ui_filename)

        self.settings.New('step_size', dtype=float, unit='um', vmin=.001)

        self.pi_device_hw = self.app.hardware['piezostage']
        
        
    def setup_figure(self):
        #connecting settings to ui
        self.pi_device_hw.settings.x_position.connect_to_widget(self.ui.x_label)
        self.pi_device_hw.settings.y_position.connect_to_widget(self.ui.y_label)
        self.settings.step_size.connect_to_widget(self.ui.step_size_spinBox)

        #setup ui signals
        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.up_pushButton.clicked.connect(self.move_up)
        self.ui.right_pushButton.clicked.connect(self.move_right)
        self.ui.down_pushButton.clicked.connect(self.move_down)
        self.ui.left_pushButton.clicked.connect(self.move_left)

        #plot showing stage area
        self.stage_layout=pg.GraphicsLayoutWidget()
        self.ui.stage_groupBox.layout().addWidget(self.stage_layout)
        self.stage_plot = self.stage_layout.addPlot(title="Stage view")
        self.stage_plot.setXRange(0, 100)
        self.stage_plot.setYRange(0, 100)
        self.stage_plot.setLimits(xMin=0, xMax=100, yMin=0, yMax=100) 

        #arrow indicating stage position
        self.current_stage_pos_arrow = pg.ArrowItem()
        self.current_stage_pos_arrow.setZValue(100)
        self.current_stage_pos_arrow.setPos(0, 0)#self.pi_device_hw.settings['x_position'], self.pi_device_hw.settings['y_position'])
        self.stage_plot.addItem(self.current_stage_pos_arrow)
                
    def move_up(self):
        if hasattr(self, 'pi_device') and hasattr(self, 'axes'):
            self.pi_device.MVR(axes=self.axes[1], values=[self.settings['step_size']])
            self.pi_device_hw.read_from_hardware()
            self.current_stage_pos_arrow.setPos(self.pi_device_hw.settings['x_position'], self.pi_device_hw.settings['y_position'])

    def move_right(self):
        if hasattr(self, 'pi_device') and hasattr(self, 'axes'):
            self.pi_device.MVR(axes=self.axes[0], values=[self.settings['step_size']])
            self.pi_device_hw.read_from_hardware()
            self.current_stage_pos_arrow.setPos(self.pi_device_hw.settings['x_position'], self.pi_device_hw.settings['y_position'])

    def move_down(self):
        if hasattr(self, 'pi_device') and hasattr(self, 'axes'):
            self.pi_device.MVR(axes=self.axes[1], values=[-self.settings['step_size']])
            self.pi_device_hw.read_from_hardware()
            self.current_stage_pos_arrow.setPos(self.pi_device_hw.settings['x_position'], self.pi_device_hw.settings['y_position'])

    def move_left(self):
        if hasattr(self, 'pi_device') and hasattr(self, 'axes'):
            self.pi_device.MVR(axes=self.axes[0], values=[-self.settings['step_size']])
            self.pi_device_hw.read_from_hardware()
            self.current_stage_pos_arrow.setPos(self.pi_device_hw.settings['x_position'], self.pi_device_hw.settings['y_position'])

#    def update_display(self):
#        x_pos = self.pi_device_hw.settings['x_position']
#        y_pos = self.pi_device_hw.settings['y_position']
#        self.current_stage_pos_arrow.setPos(x_pos, y_pos)
    
    def run(self):
        self.pi_device = self.pi_device_hw.pi_device
        self.axes = self.pi_device.axes