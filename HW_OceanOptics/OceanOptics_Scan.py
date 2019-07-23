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
#		self.ui.save_array_pushButton.clicked.connect(self.save_intensities_data)
#		self.ui.save_image_pushButton.clicked.connect(self.save_intensities_image)

		spec_hw = self.app.hardware['oceanoptics']
		details_groupBox = self.set_details_widget(widget = self.settings.New_UI(include=["intg_time", "correct_dark_counts", "scans_to_avg"]))
		widgets = details_groupBox.findChildren(QtGui.QWidget)
		intg_time_spinBox = widgets[1]
		correct_dark_counts_checkBox = widgets[4]
		#scans_to_avg_spinBox = widgets[6]
		spec_hw.settings.intg_time.connect_to_widget(intg_time_spinBox)
		spec_hw.settings.correct_dark_counts.connect_to_widget(correct_dark_counts_checkBox)

		intg_time_spinBox.valueChanged.connect(self.update_estimated_scan_time)
		
		#save data buttons
		self.ui.save_image_pushButton.clicked.connect(self.save_intensities_image)
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
		self.imv.getView().invertY(False)
		roi_plot = self.imv.getRoiPlot().getPlotItem()
		roi_plot.getAxis("bottom").setLabel(text="Wavelength (nm)")

	def update_estimated_scan_time(self):
		scan_time = self.x_range * self.y_range * self.settings["intg_time"] * 1e-3 #s
		self.ui.estimated_scan_time_label.setText("Estimated scan time: " + "%.2f" % scan_time + "s")

	def update_display(self):
		PiezoStage_Scan.update_display(self)
		if hasattr(self, 'spec') and hasattr(self, 'pi_device') and hasattr(self, 'y'): #first, check if setup has happened
			if not self.interrupt_measurement_called:
				seconds_left = ((self.x_range * self.y_range) - self.pixels_scanned) * self.settings["intg_time"] * 1e-3
				self.ui.estimated_time_label.setText("Estimated time remaining: " + "%.2f" % seconds_left + "s")
			#plot wavelengths vs intensity
			self.plot.plot(self.spec.wavelengths(), self.y, pen='r', clear=True) #plot wavelength vs intensity
			self.graph_layout.show()
			self.graph_layout.window().setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False) #disable closing image view window

			self.img_item.setImage(self.sum_intensities_image_map)#image=sum_disp_img, autoLevels=True, autoRange=False)
			
			self.imv.setImage(img=self.spectrum_image_map, autoRange=False, autoLevels=True, xvals=self.spec.wavelengths()) #adjust roi plot x axis
			self.imv.show()
			self.imv.window().setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False) #disable closing image view window
			
			#update progress bar
			progress = 100 * ((self.pixels_scanned+1)/np.abs(self.x_range*self.y_range))
			self.ui.progressBar.setValue(progress)
			self.set_progress(progress)
			pg.QtGui.QApplication.processEvents()

	def pre_run(self):
		PiezoStage_Scan.pre_run(self) #setup scan parameters
		self.spec = self.spec_hw.spec
		self.check_filename("_raw_PL_spectra_data.pkl")
		
		# Define empty array for saving intensities
		self.data_array = np.zeros(shape=(self.x_range*self.y_range,2048))

		# Define empty array for image map
		self.sum_intensities_image_map = np.zeros((self.x_range, self.y_range), dtype=float) #store sum of intensities for each pixel
		self.spectrum_image_map = np.zeros((2048, self.x_range, self.y_range), dtype=float) #Store spectrum for each pixel
		scan_time = self.x_range * self.y_range * self.settings["intg_time"] * 1e-3 #s
		self.ui.estimated_scan_time_label.setText("Estimated scan time: " + "%.2f" % scan_time + "s")
		
	def scan_measure(self):
		"""
		Data collection for each pixel.
		"""
		self._read_spectrometer()
		self.data_array[self.pixels_scanned,:] = self.y
		self.sum_intensities_image_map[self.index_x, self.index_y] = self.y.sum()
		self.spectrum_image_map[:, self.index_x, self.index_y] = self.y
	
	def post_run(self):
		"""
		Export data.
		"""
		PiezoStage_Scan.post_run(self)
		save_dict = {"Wavelengths": self.spec.wavelengths(), "Intensities": self.data_array,
				 "Scan Parameters":{"X scan start (um)": self.x_start, "Y scan start (um)": self.y_start,
									"X scan size (um)": self.x_scan_size, "Y scan size (um)": self.y_scan_size,
									"X step size (um)": self.x_step, "Y step size (um)": self.y_step},
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
		transposed = np.transpose(self.sum_intensities_image_map)
		PiezoStage_Scan.save_intensities_data(self, transposed, 'oo')

	def save_intensities_image(self):
		PiezoStage_Scan.save_intensities_image(self, self.sum_intensities_image_map, 'oo')