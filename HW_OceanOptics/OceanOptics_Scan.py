from HW_PI_PiezoStage.PiezoStage_Scan import PiezoStage_Scan
from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import pyqtgraph as pg
import numpy as np
import time
import pickle
import os.path
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.Point import Point
import customplotting.mscope as cpm

class OceanOptics_Scan(PiezoStage_Scan):

	name = "OceanOptics_Scan"

	def setup(self):
		PiezoStage_Scan.setup(self)

		self.settings.New("intg_time",dtype=int, unit='ms', initial=3, vmin=3)
		self.settings.New('correct_dark_counts', dtype=bool, initial=True)
		self.settings.New("scans_to_avg", dtype=int, initial=1, vmin=1)

	def setup_figure(self):
		PiezoStage_Scan.setup_figure(self)
		self.ui.save_array_pushButton.clicked.connect(self.save_intensities_data)
		self.ui.save_image_pushButton.clicked.connect(self.save_intensities_image)
		spec_hw = self.app.hardware['oceanoptics']
		details_groupBox = self.set_details_widget(widget = self.settings.New_UI(include=["intg_time", "correct_dark_counts", "scans_to_avg"]))
		widgets = details_groupBox.findChildren(QtGui.QWidget)
		intg_time_spinBox = widgets[1]
		correct_dark_counts_checkBox = widgets[4]
		#scans_to_avg_spinBox = widgets[6]
		spec_hw.settings.intg_time.connect_to_widget(intg_time_spinBox)
		spec_hw.settings.correct_dark_counts.connect_to_widget(correct_dark_counts_checkBox)
		
		#save data buttons
		#self.ui.save_image_pushButton.clicked.connect(self.save_intensities_image)
		self.ui.save_array_pushButton.clicked.connect(self.save_intensities_data)

		#spectrometer plot
		self.graph_layout=pg.GraphicsLayoutWidget()
		self.plot = self.graph_layout.addPlot(title="Spectrometer Live Reading")
		self.plot.setLabel('left', 'Intensity', unit='a.u.')
		self.plot.setLabel('bottom', 'Wavelength', unit='nm')        
		# # Create PlotDataItem object ( a scatter plot on the axes )
		self.optimize_plot_line = self.plot.plot([0])
		
		self.imv = pg.ImageView()
		self.imv.getView().setAspectLocked(lock=False, ratio=1)
		self.imv.getView().setMouseEnabled(x=True, y=True)
		#TODO - connect widget to settings in spectrometer 

	def update_display(self):
		PiezoStage_Scan.update_display(self)
		if hasattr(self, 'spec') and hasattr(self, 'pi_device') and hasattr(self, 'y'): #first, check if setup has happened
			if not self.interrupt_measurement_called:
				seconds_left = ((self.x_range * self.y_range) - self.pixels_scanned) * self.settings["intg_time"] * 1e-3
				self.ui.estimated_time_label.setText("Estimated time remaining: " + str(seconds_left) + "s")
			#plot wavelengths vs intensity
			self.plot.plot(self.spec.wavelengths(), self.y, pen='r', clear=True) #plot wavelength vs intensity
			self.graph_layout.show()
			self.graph_layout.window().setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False) #disable closing image view window

			sum_disp_img = self.sum_display_image_map #transpose to use for setImage, which takes 3d array (x, y, intensity)
			self.img_item.setImage(sum_disp_img)#image=sum_disp_img, autoLevels=True, autoRange=False)
			
			intensities_disp_img = self.intensities_display_image_map
			self.imv.setImage(img=intensities_disp_img, autoRange=False, autoLevels=True)
			self.imv.show()
			self.imv.window().setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False) #disable closing image view window
			
			#update progress bar
			progress = 100 * ((self.pixels_scanned+1)/np.abs(self.x_range*self.y_range))
			self.ui.progressBar.setValue(progress)
			self.set_progress(progress)
			pg.QtGui.QApplication.processEvents()


	def run(self):
		"""
		Runs when measurement is started. Runs in a separate thread from GUI.
		It should not update the graphical interface directly, and should only
		focus on data acquisition.

		Runs until scan is completed or interrupted.
		"""
		self.check_filename("_raw_PL_spectra_data.pkl")
		
		self.scan_complete = False

		self.pi_device = self.pi_device_hw.pi_device
		self.spec = self.spec_hw.spec
		self.axes = self.pi_device_hw.axes

		x_start = self.settings['x_start']
		y_start = self.settings['y_start']
		
		x_scan_size = self.settings['x_size']
		y_scan_size = self.settings['y_size']
		
		x_step = self.settings['x_step']
		y_step = self.settings['y_step']
		
		if y_scan_size == 0:
			y_scan_size = 1#self.settings['y_size'] = 1
			y_step = 1#self.settings['y_step'] = 1
		
		if x_scan_size == 0:
			x_scan_size = 1#self.settings['x_size'] = 1
			x_step = 1#self.settings['x_step'] = 1
		
		if y_step == 0:
			y_step = 1#self.settings['y_step'] = 1
			
		if x_step == 0:
			x_step = 1#self.settings['x_step'] = 1
			
		#number of scans in x and y
		self.y_range = np.abs(int(np.ceil(y_scan_size/y_step)))
		self.x_range = np.abs(int(np.ceil(x_scan_size/x_step)))
		
		# Define empty array for saving intensities
		data_array = np.zeros(shape=(self.x_range*self.y_range,2048))

		# Define empty array for image map
		#self.sum_display_image_map = np.zeros((y_range, x_range), dtype=float)

		#Store spectrum for each pixel
		self.sum_display_image_map = np.zeros((self.x_range, self.y_range), dtype=float)
		self.intensities_display_image_map = np.zeros((2048, self.x_range, self.y_range), dtype=float)
		
		# Move to the starting position
		self.pi_device.MOV(axes=self.axes, values=[x_start,y_start])
		self.pi_device_hw.read_from_hardware()
		

		self.pixels_scanned = 0 #keep track of scan/'pixel' number
		if (self.ui.scan_comboBox.currentText() == 'XY'): #todo - add to settings sidebar once this is tested
			for i in range(self.y_range):
				for j in range(self.x_range):
					if self.interrupt_measurement_called:
						break
					self._read_spectrometer()
					data_array[self.pixels_scanned,:] = self.y

					#make sure the right indices of image arrays are updated
					index_x = j
					index_y = i
					if x_step < 0:
						index_x = self.x_range - j - 1
					if y_step < 0:
						index_y = self.y_range - i - 1

					self.sum_display_image_map[index_x, index_y] = self.y.sum()
					self.intensities_display_image_map[:, index_x, index_y] = self.y#intensities_sum
					self.pi_device.MVR(axes=self.axes[0], values=[x_step])
					self.pi_device_hw.read_from_hardware()
					self.pixels_scanned+=1
				# TODO
				# if statement needs to be modified to keep the stage at the finish y-pos for line scans in x, and same for y
				if i == self.y_range-1: # this if statement is there to keep the stage at the finish position (in x) and not bring it back like we were doing during the scan 
					self.pi_device.MVR(axes=self.axes[1], values=[y_step])
					self.pi_device_hw.read_from_hardware()
				else:                
					self.pi_device.MVR(axes=self.axes[1], values=[y_step])
					self.pi_device.MOV(axes=self.axes[0], values=[x_start])
					self.pi_device_hw.read_from_hardware()
				if self.interrupt_measurement_called:
					break
		elif (self.ui.scan_comboBox.currentText() == 'YX'):
			for i in range(self.x_range):
				for j in range(self.y_range):
					if self.interrupt_measurement_called:
						break
					self._read_spectrometer()
					data_array[self.pixels_scanned,:] = self.y

					#make sure the right indices of image arrays are updated
					index_x = i
					index_y = j
					if x_step < 0:
						index_x = self.x_range - i - 1
					if y_step < 0:
						index_y = self.y_range - j - 1

					self.sum_display_image_map[index_x, index_y] = self.y.sum()
					self.intensities_display_image_map[:, index_x, index_y] = self.y#intensities_sum
					self.pi_device.MVR(axes=self.axes[1], values=[y_step])
					self.pi_device_hw.read_from_hardware()
					self.pixels_scanned+=1
				# TODO
				# if statement needs to be modified to keep the stage at the finish y-pos for line scans in x, and same for y
				if j == self.x_range-1: # this if statement is there to keep the stage at the finish position (in x) and not bring it back like we were doing during the scan 
					self.pi_device.MVR(axes=self.axes[0], values=[x_step])
					self.pi_device_hw.read_from_hardware()
				else:                
					self.pi_device.MVR(axes=self.axes[0], values=[x_step])
					self.pi_device.MOV(axes=self.axes[1], values=[y_start])
					self.pi_device_hw.read_from_hardware()
				if self.interrupt_measurement_called:
					break

		self.ui.estimated_time_label.setText("Estimated time remaining: 0s")
		self.scan_complete = True;
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
				data = self.spec.spectrum(correct_dark_counts=self.spec_hw.settings['correct_dark_counts'])#acquire wavelengths and intensities from spec
				Int_array[:,i] = data[1]
				self.y = np.mean(Int_array, axis=-1)

	def save_intensities_data(self):
		PiezoStage_Scan.save_intensities_data(self.sum_display_image_map, 'oo')

	def save_intensities_image(self):
		PiezoStage_Scan.save_intensities_image(self.sum_display_image_map, 'oo')