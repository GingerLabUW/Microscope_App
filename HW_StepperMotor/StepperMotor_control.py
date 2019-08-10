from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import pyqtgraph as pg
import numpy as np
import time
import pickle
import os.path
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.Point import Point

class StepperMotorControl(Measurement):
    name = 'steppermotor_control'

    def setup(self):
        self.ui_filename = sibling_path(__file__, "steppermotor_control.ui")
        
        #Load ui file and convert it to a live QWidget of the user interface
        self.ui = load_qt_ui_file(self.ui_filename)

        self.settings.New('step_size', dtype=float, unit='um', vmin=.001)

        self.stepper_motor_hw = self.app.hardware['stepper_motor']
        
        
    def setup_figure(self):
        #connecting settings to ui
        self.stepper_motor_hw.settings.x_position.connect_to_widget(self.ui.x_label)
        self.stepper_motor_hw.settings.y_position.connect_to_widget(self.ui.y_label)
        self.settings.step_size.connect_to_widget(self.ui.step_size_spinBox)

        #setup ui signals
        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.up_pushButton.clicked.connect(self.move_up)
        self.ui.right_pushButton.clicked.connect(self.move_right)
        self.ui.down_pushButton.clicked.connect(self.move_down)
        self.ui.left_pushButton.clicked.connect(self.move_left)
                
    def move_up(self):
        if hasattr(self, 'stepper_motor'):
            step = self.settings["step_size"]
            self.stepper_motor.goto([0, step, "r"])
            self.stepper_motor_hw.read_position()

    def move_right(self):
        if hasattr(self, 'stepper_motor'):
            step = self.settings["step_size"]
            self.stepper_motor.goto([step, 0, "r"])
            self.stepper_motor_hw.read_position()

    def move_down(self):
        if hasattr(self, 'stepper_motor'):
            step = self.settings["step_size"]
            self.stepper_motor.goto([0, -step, "r"])
            self.stepper_motor_hw.read_position()

    def move_left(self):
        if hasattr(self, 'stepper_motor'):
            step = self.settings["step_size"]
            self.stepper_motor.goto([-step, 0, "r"])
            self.stepper_motor_hw.read_position()
            
    def run(self):
        self.stepper_motor = self.stepper_motor_hw.stepper_motor