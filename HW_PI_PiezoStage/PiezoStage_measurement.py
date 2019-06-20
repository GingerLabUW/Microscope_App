from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
from ScopeFoundry import h5_io
from OceanOptics_hardware import OceanOpticsHW
from OceanOptics_measurement import OceanOpticsMeasure
import pyqtgraph as pg
import numpy as np
import time
import pickle
import os.path

class PiezoStageMeasure(Measurement):
	
	def setup(self):
		"""
		Runs once during App initialization.
		This is the place to load a user interface file,
		define settings, and set up data structures. 
		"""
		self.name = "oceanoptics_scan"
		
		# Define ui file to be used as a graphical interface
		# This file can be edited graphically with Qt Creator
		# sibling_path function allows python to find a file in the same folder
		# as this python module
		self.ui_filename = sibling_path(__file__, "spec_pz.ui")
		
		#Load ui file and convert it to a live QWidget of the user interface
		self.ui = load_qt_ui_file(self.ui_filename)

		# Measurement Specific Settings
		# This setting allows the option to save data to an h5 data file during a run
		# All settings are automatically added to the Microscope user interface

		self.settings.New('x_start', dtype=float, unit='um', vmin=0)
		self.settings.New('y_start', dtype=float, unit='um', vmin=0)
	
		self.settings.New('x_size', dtype=float, initial=1, unit='um', vmin=1)
		self.settings.New('y_size', dtype=float, initial=1, unit='um', vmin=1)

		self.settings.New('x_step', dtype=float, initial=1, unit='um', vmin=1)
		self.settings.New('y_step', dtype=float, initial=1, unit='um', vmin=1)
		
		# Define how often to update display during a run
		self.display_update_period = 0.1 
		
		# Convenient reference to the hardware used in the measurement
		self.spec_hw = self.app.hardware['oceanoptics']
		self.pi_device_hw = self.app.hardware['piezostage']
		
		self.spec_measure = self.app.measurements['oceanoptics_measure']

	def setup_figure(self):
		"""
		Runs once during App initialization, after setup()
		This is the place to make all graphical interface initializations,
		build plots, etc.
		"""
		
		# connect ui widgets to measurement/hardware settings or functions
		self.ui.start_scan_pushButton.clicked.connect(self.start)
		self.ui.interrupt_scan_pushButton.clicked.connect(self.interrupt)

		self.pi_device_hw.settings.x_position.connect_to_widget(self.ui.x_pos_doubleSpinBox)
		self.pi_device_hw.settings.y_position.connect_to_widget(self.ui.y_pos_doubleSpinBox)
		self.settings.x_start.connect_to_widget(self.ui.x_start_doubleSpinBox)
		self.settings.y_start.connect_to_widget(self.ui.y_start_doubleSpinBox)
		
		self.settings.x_size.connect_to_widget(self.ui.x_size_doubleSpinBox)
		self.settings.y_size.connect_to_widget(self.ui.y_size_doubleSpinBox)
		self.settings.x_step.connect_to_widget(self.ui.x_step_doubleSpinBox)
		self.settings.y_step.connect_to_widget(self.ui.y_step_doubleSpinBox)
		
		self.spec_hw.settings.intg_time.connect_to_widget(self.ui.intg_time_doubleSpinBox)
		self.spec_hw.settings.correct_dark_counts.connect_to_widget(self.ui.correct_dark_counts_checkBox)
		self.spec_measure.settings.scans_to_avg.connect_to_widget(self.ui.scans_to_avg_spinBox)


		# Set up pyqtgraph graph_layout in the UI
		self.graph_layout=pg.GraphicsLayoutWidget()
		self.ui.plot_groupBox.layout().addWidget(self.graph_layout)

		# # Create PlotItem object (a set of axes)  
		self.plot = self.graph_layout.addPlot(title="Spectrometer Live Reading")
		self.plot.setLabel('left', 'Intensity', unit='a.u.')
		self.plot.setLabel('bottom', 'Wavelength', unit='nm')
		
		# # Create PlotDataItem object ( a scatter plot on the axes )
		self.optimize_plot_line = self.plot.plot([0])

	def update_display(self):
		"""
		Displays (plots) the wavelengths on x and intensities on y as the stage moves.
		This function runs repeatedly and automatically during the measurement run.
		its update frequency is defined by self.display_update_period
		"""
		if hasattr(self, 'spec') and hasattr(self, 'pi_device') and hasattr(self, 'y'):
			self.plot.plot(self.spec.wavelengths(), self.y, pen='r', clear=True)
			pg.QtGui.QApplication.processEvents()

	def run(self):
		"""
		Runs when measurement is started. Runs in a separate thread from GUI.
		It should not update the graphical interface directly, and should only
		focus on data acquisition.

		Runs until scan is complete or measurement is interrupted.
		"""
		self.check_filename()
		
		#Directly access pi device and spectrometer.
		self.pi_device = self.pi_device_hw.pi_device
		self.spec = self.spec_hw.spec
		self.axes = self.pi_device_hw.axes

		x_start = self.settings['x_start']
		y_start = self.settings['y_start']
		
		x_scan_size = self.settings['x_size']
		y_scan_size = self.settings['y_size']
		
		x_step = self.settings['x_step']
		y_step = self.settings['y_step']
			
		#number of scans in x and y
		y_range = int(np.ceil(y_scan_size/y_step))
		x_range = int(np.ceil(x_scan_size/x_step))
		
		# Define empty array for saving intensities
		data_array = np.zeros(shape=(x_range*y_range,2048))
		
		# Move to the starting position
		self.pi_device.MOV(axes=self.axes, values=[x_start,y_start])
		self.pi_device_hw.read_from_hardware()
		

		k = 0 #track scan/'pixel' number
		for i in range(y_range):
			for j in range(x_range):
				if self.interrupt_measurement_called:
					break
				self._read_spectrometer()
				data_array[k,:] = self.y #get new intensity data
				self.pi_device.MVR(axes=self.axes[0], values=[x_step]) #continue scan...
				#self.ui.progressBar.setValue(np.floor(100*((k+1)/(x_range*y_range))))
				print(100*((k+1)/(x_range*y_range)))
				self.pi_device_hw.read_from_hardware()
				k+=1

			# TODO
			# if statement needs to be modified to keep the stage at the finish y-pos for line scans in x, and same for y
			if i == y_range-1: # this if statement is there to keep the stage at the finish position (in x) and not bring it back like we were doing during the scan 
				self.pi_device.MVR(axes=self.axes[1], values=[y_step])
				self.pi_device_hw.read_from_hardware()
			else:
				self.pi_device.MVR(axes=self.axes, values=[-x_scan_size, y_step])
				self.pi_device_hw.read_from_hardware()

			if self.interrupt_measurement_called:
				break

		save_dict = {"Wavelengths": self.spec.wavelengths(), "Intensities": data_array,
				 "Scan Parameters":{"X scan start (um)": x_start, "Y scan start (um)": y_start,
									"X scan size (um)": x_scan_size, "Y scan size (um)": y_scan_size,
									"X step size (um)": x_step, "Y step size (um)": y_step},
									"OceanOptics Parameters":{"Integration Time (ms)": self.spec_hw.settings['intg_time'],
															  "Scans Averages": self.spec_measure.settings['scans_to_avg'],
															  "Correct Dark Counts": self.spec_hw.settings['correct_dark_counts']}
				 }
	
		pickle.dump(save_dict, open(self.app.settings['save_dir']+"/"+self.app.settings['sample']+"_raw_PL_spectra_data.pkl", "wb"))

	def _read_spectrometer(self):
		'''
		Read spectrometer according to settings and update self.y (intensities array)
		'''
		if hasattr(self, 'spec'):
			intg_time_ms = self.spec_hw.settings['intg_time']
			self.spec.integration_time_micros(intg_time_ms*1e3) #seabreeze error checking
			
			scans_to_avg = self.spec_measure.settings['scans_to_avg']
			Int_array = np.zeros(shape=(2048,scans_to_avg))
			
			for i in range(scans_to_avg): #software average
				data = self.spec.spectrum(correct_dark_counts=self.spec_hw.settings['correct_dark_counts'])#acquire wavelength and intensity data from spec
				Int_array[:,i] = data[1]
				self.y = np.mean(Int_array, axis=-1)

	def check_filename(self):
		'''
		If no sample name given or duplicate sample name given, fix the problem by appending a unique number.
		'''
		samplename = self.app.settings['sample']
		filename = samplename + "_raw_PL_spectra_data.pkl"
		directory = self.app.settings['save_dir']
		if samplename == "":
			self.app.setting['sample'] = int(time.time())
		if (os.path.exists(directory+"/"+filename)):
			self.app.settings['sample'] = samplename + str(int(time.time()))