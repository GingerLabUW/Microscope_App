from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
from ScopeFoundry import h5_io
import pyqtgraph as pg
from PyQt5 import *
import numpy as np
import time
import seabreeze.spectrometers as sb
import os.path

class OceanOpticsMeasure(Measurement):
	
	# this is the name of the measurement that ScopeFoundry uses 
	# when displaying your measurement and saving data related to it    
	
	
	def setup(self):
		"""
		Runs once during App initialization.
		This is the place to load a user interface file,
		define settings, and set up data structures. 
		"""
		
		# Define ui file to be used as a graphical interface
		# This file can be edited graphically with Qt Creator
		# sibling_path function allows python to find a file in the same folder
		# as this python module
		self.name = "oceanoptics_measure"
		self.ui_filename = sibling_path(__file__, "spec_plot.ui")
		
		#Load ui file and convert it to a live QWidget of the user interface
		self.ui = load_qt_ui_file(self.ui_filename)

		# Measurement Specific Settings
		# This setting allows the option to save data to an h5 data file during a run
		# All settings are automatically added to the Microscope user interface
		self.settings.New('save_every_spec', dtype=bool, initial=False)
		self.settings.New('scans_to_avg', dtype=int, initial=1, vmin=1)

		# Define how often to update display during a run
		self.display_update_period = 0.1 
		
		# Create empty numpy array to serve as a buffer for the acquired data
		self.buffer = np.zeros(120, dtype=float)

		self.save_array = np.zeros(shape=(2048,2))
		self.point_counter = 0
		
		# Convenient reference to the hardware used in the measurement
		self.spec_hw = self.app.hardware['oceanoptics']


	def setup_figure(self):
		"""
		Runs once during App initialization, after setup()
		This is the place to make all graphical interface initializations,
		build plots, etc.
		"""
		
		# connect ui widgets to measurement/hardware settings or functions
		self.ui.start_pushButton.clicked.connect(self.start)
		self.ui.interrupt_pushButton.clicked.connect(self.interrupt)
		self.ui.saveSingle_pushButton.clicked.connect(self.save_single_spec)
		
		self.settings.save_every_spec.connect_to_widget(self.ui.save_every_spec_checkBox)
		self.settings.scans_to_avg.connect_to_widget(self.ui.scans_to_avg_spinBox)
		self.spec_hw.settings.correct_dark_counts.connect_to_widget(self.ui.correct_dark_counts_checkBox)
		self.spec_hw.settings.intg_time.connect_to_widget(self.ui.intg_time_spinBox)

		# Set up pyqtgraph graph_layout in the UI
		self.graph_layout=pg.GraphicsLayoutWidget()
		self.ui.plot_groupBox.layout().addWidget(self.graph_layout)

		# # Create PlotItem object (a set of axes)  
		self.plot = self.graph_layout.addPlot(title="Spectrometer Readout Plot")
		self.plot.setLabel('left', 'Intensity', unit='a.u.')
		self.plot.setLabel('bottom', 'Wavelength', unit='nm')
		
		# # Create PlotDataItem object ( a scatter plot on the axes )
		self.optimize_plot_line = self.plot.plot([0])

	def update_display(self):
		"""
        Displays (plots) the wavelengths on x and intensities on y.
        This function runs repeatedly and automatically during the measurement run.
        its update frequency is defined by self.display_update_period
        """
		if hasattr(self, 'spec'):
			self.plot.plot(self.spec.wavelengths(), self.y, pen='r', clear=True)
			pg.QtGui.QApplication.processEvents()

	def run(self):
		"""
		Runs when measurement is started. Runs in a separate thread from GUI.
		It should not update the graphical interface directly, and should only
		focus on data acquisition.

		Runs until measurement is interrupted. Data is continuously saved if checkbox checked.
		"""
		self.check_filename()
		self.spec = self.spec_hw.spec
		while not self.interrupt_measurement_called:
			self._read_spectrometer()
			self.save_array[:,1] = self.y
			if self.ui.save_every_spec_checkBox.isChecked(): #while interrupt not called, inside, have an if for if interrupt is called 
				self.save_array[:,0] = self.spec.wavelengths()
				np.savetxt(self.app.settings['save_dir']+"/"+self.app.settings['sample']+str(self.point_counter)+".txt", self.save_array, fmt = '%.5f', header = 'Wavelength (nm), Intensity (counts)', delimiter = ' ')
				self.point_counter += 1
			if self.interrupt_measurement_called:
				break


	def save_single_spec(self):
		'''
		When button is pushed, save wavelength vs intensity data at that moment.
		'''
		save_array = np.zeros(shape=(2048,2))
		save_array[:,1] = self.y
		save_array[:,0] = self.spec.wavelengths()
		self.check_filename()
		np.savetxt(self.app.settings['save_dir']+"/"+self.app.settings['sample']+".txt", save_array, fmt = '%.5f', 
				   header = 'Wavelength (nm), Intensity (counts)', delimiter = ' ')

	def _read_spectrometer(self):
		'''
		Read spectrometer according to settings and update self.y (intensities array)
		'''
		if hasattr(self, 'spec'):
			intg_time_ms = self.spec_hw.settings['intg_time']
			self.spec.integration_time_micros(intg_time_ms*1e3) #seabreeze error checking
			
			scans_to_avg = self.settings['scans_to_avg']
			Int_array = np.zeros(shape=(2048,scans_to_avg))
			
			for i in range(scans_to_avg): #software average
				data = self.spec.spectrum(correct_dark_counts=self.spec_hw.settings['correct_dark_counts']) #data as wavelengths, intensities array   
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
			self.app.settings['sample'] = int(time.time())
		if (os.path.exists(directory+"/"+filename)):
			self.app.settings['sample'] = samplename + str(int(time.time()))