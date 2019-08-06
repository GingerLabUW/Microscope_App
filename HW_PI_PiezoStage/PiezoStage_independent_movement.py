from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
from ScopeFoundry import h5_io
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import sys
from pathlib import Path
import numpy as np
import time
import pickle
import os.path

class PiezoStageIndependentMovement(Measurement):
	def setup(self):
		self.name = 'piezo_independent_movement'
		self.ui_filename = sibling_path(__file__, "independent_movement.ui")
		
		self.settings.New("sleep_time", dtype=float, unit="s", vmin=0)

		#Load ui file and convert it to a live QWidget of the user interface
		self.ui = load_qt_ui_file(self.ui_filename)
		self.pi_device_hw = self.app.hardware['piezostage']

	def setup_figure(self):
		#connect settings to ui
		self.settings.sleep_time.connect_to_widget(self.ui.sleep_time_spinBox)
		self.pi_device_hw.settings.x_position.connect_to_widget(self.ui.x_position_label)
		self.pi_device_hw.settings.y_position.connect_to_widget(self.ui.y_position_label)

		#setup ui signals
		self.ui.import_pushButton.clicked.connect(self.array_from_file)
		self.ui.start_pushButton.clicked.connect(self.start)
		self.ui.interrupt_pushButton.clicked.connect(self.interrupt)
	
	def array_from_file(self):
		'''
		Prompts the user to select a text file containing the list of positions.
		'''
		try:
			fname = QtWidgets.QFileDialog.getOpenFileName(self.ui, 'Open file', os.getcwd(),"*.txt")
			try:
				self.position_array = np.genfromtxt(fname[0], dtype=None, encoding=None) #convert file contents into np array
				self.ui.textBrowser.append("Successfully imported from " + str(fname[0]))
			except:
				self.ui.textBrowser.append("Error: File containing position array is not formatted correctly.")
		except Exception as err:
			self.ui.textBrowser.append(format(err))

	def run(self):
		"""
		Move to each point specified in file, pausing for the set sleep time.
		"""
		if not hasattr(self, "position_array"):
			self.ui.textBrowser.append("Must import text file before running.")
		else:
			self.pi_device = self.pi_device_hw.pi_device
			self.axes = self.pi_device.axes[0:2]
			num_points = self.position_array.shape[0] #get number of rows = number of points
			for i in range(num_points):
				if self.interrupt_measurement_called:
					break
				abs_mov = self.position_array[i] #get next point for stage to move to
				self.pi_device.MOV(axes=self.axes, values=[abs_mov[0], abs_mov[1]])
				self.pi_device_hw.read_from_hardware()
				self.ui.textBrowser.append("Point #" + str(i+1) + " complete.")
				time.sleep(self.settings['sleep_time'])