from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import pyqtgraph as pg
import numpy as np
import time
import pickle
import os.path
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.Point import Point

class APD_StepperMotor_Control(Measurement):
    name = 'apd_steppermotor_control'

    def setup(self):
        self.ui_filename = sibling_path(__file__, "apd_steppermotor_control.ui")
        
        #Load ui file and convert it to a live QWidget of the user interface
        self.ui = load_qt_ui_file(self.ui_filename)

        self.settings.New('step_size', dtype=float, unit='um', vmin=.001)

        self.apd_steppermotor_hw = self.app.hardware['apd_steppermotor']
        
        
    def setup_figure(self):
        #connecting settings to ui
        self.apd_steppermotor_hw.settings.x_position.connect_to_widget(self.ui.x_label)
        self.apd_steppermotor_hw.settings.y_position.connect_to_widget(self.ui.y_label)
        self.settings.step_size.connect_to_widget(self.ui.step_size_spinBox)

        #setup ui signals
        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.up_pushButton.clicked.connect(self.move_up)
        self.ui.right_pushButton.clicked.connect(self.move_right)
        self.ui.down_pushButton.clicked.connect(self.move_down)
        self.ui.left_pushButton.clicked.connect(self.move_left)
                
    def move_up(self):
        if hasattr(self, 'apd_steppermotor'):
            step = self.settings["step_size"]
            self.apd_steppermotor.goto([0, step, "r"])
            self.apd_steppermotor_hw.read_position()

    def move_right(self):
        if hasattr(self, 'apd_steppermotor'):
            step = self.settings["step_size"]
            self.apd_steppermotor.goto([step, 0, "r"])
            self.apd_steppermotor_hw.read_position()

    def move_down(self):
        if hasattr(self, 'apd_steppermotor'):
            step = self.settings["step_size"]
            self.apd_steppermotor.goto([0, -step, "r"])
            self.apd_steppermotor_hw.read_position()

    def move_left(self):
        if hasattr(self, 'apd_steppermotor'):
            step = self.settings["step_size"]
            self.apd_steppermotor.goto([-step, 0, "r"])
            self.apd_steppermotor_hw.read_position()
            
    def run(self):
        self.apd_steppermotor = self.apd_steppermotor_hw.apd_steppermotor