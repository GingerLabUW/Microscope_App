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

class PicoHarp_Scan(PiezoStage_Scan):

	name = "PicoHarp_Scan"

	def setup(self):
		PiezoStage_Scan.setup(self)

		self.picoharp_hw = self.app.hardware['picoharp']
		self.pi_device_hw = self.app.hardware['piezostage']
		#figure out which settings

	def setup_figure(self):
		#TODO : add picoharp specific settings
		PiezoStage_Scan.setup_figure(self)
		#details_groupBox = self.set_details_widget(widget = self.settings.New_UI(include=["intg_time", "correct_dark_counts", "scans_to_avg"]))
		#widgets = details_groupBox.findChildren(QtGui.QWidget)		

		#image display container, will show sp
		self.imv = pg.ImageView()
		self.imv.getView().setAspectLocked(lock=False, ratio=1)
		self.imv.getView().setMouseEnabled(x=True, y=True)

	def update_display(self):
		PiezoStage_Scan.update_display(self)
		if hasattr(self, 'picoharp') and hasattr(self, 'pi_device'):
			sum_disp_img = self.sum_display_image_map
			self.img_item.setImage(sum_disp_img)
			
			histogram_disp_img = self.histogram_display_image_map
			self.imv.setImage(img=histogram_disp_img, autoRange=False, autoLevels=True)
			self.imv.show()
			self.imv.window().setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False) #disable closing image view window
			pg.QtGui.QApplication.processEvents()


	def run(self):
		"""
		Runs when measurement is started. Runs in a separate thread from GUI.
		It should not update the graphical interface directly, and should only
		focus on data acquisition.

		Runs until scan is completed or interrupted.
		"""
		#self.check_filename("_raw_PL_spectra_data.pkl")
		
		self.scan_complete = False

		self.pi_device = self.pi_device_hw.pi_device
		self.picoharp = self.picoharp_hw.picoharp
		self.axes = self.pi_device_hw.axes

		###self.sleep_time = min((max(0.1*ph.Tacq*1e-3, 0.010), 0.100))

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
		self.histogram_display_image_map = np.zeros((2048, self.x_range, self.y_range), dtype=float)
		
		# Move to the starting position
		self.pi_device.MOV(axes=self.axes, values=[x_start,y_start])
		self.pi_device_hw.read_from_hardware()
		

		k = 0 #keep track of scan/'pixel' number
		for i in range(self.y_range):
			for j in range(self.x_range):
				if self.interrupt_measurement_called:
					break
				histogram = self.read_picoharp_histogram()

				#make sure the right indices of image arrays are updated
				index_x = j
				index_y = i
				if x_step < 0:
					index_x = self.x_range - j - 1
				if y_step < 0:
					index_y = self.y_range - i - 1

				self.sum_display_image_map[index_x, index_y] = histogram.sum()
				self.histogram_display_image_map[:, index_x, index_y] = histogram #intensities_sum
				self.pi_device.MVR(axes=self.axes[0], values=[x_step])
				#self.ui.progressBar.setValue(np.floor(100*((k+1)/(x_range*y_range))))
				#print(100*((k+1)/np.abs((self.x_range*self.y_range))))
				self.ui.progressBar.setValue( 100 * ((k+1)/np.abs(self.x_range*self.y_range)) )
				self.pi_device_hw.read_from_hardware()
				k+=1
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

		self.scan_complete = True;
		#TODO : figure out saving data
		# save_dict = {"Wavelengths": self.spec.wavelengths(), "Intensities": data_array,
		# 		 "Scan Parameters":{"X scan start (um)": x_start, "Y scan start (um)": y_start,
		# 							"X scan size (um)": x_scan_size, "Y scan size (um)": y_scan_size,
		# 							"X step size (um)": x_step, "Y step size (um)": y_step},
		# 							"OceanOptics Parameters":{"Integration Time (ms)": self.spec_hw.settings['intg_time'],
		# 													  "Scans Averages": self.spec_measure.settings['scans_to_avg'],
		# 													  "Correct Dark Counts": self.spec_hw.settings['correct_dark_counts']}
		# 		 }

		# pickle.dump(save_dict, open(self.app.settings['save_dir']+"/"+self.app.settings['sample']+"_raw_PL_spectra_data.pkl", "wb"))

	def read_picoharp_histogram(self):
		self.picoharp.start_histogram()

		while not self.picoharp.check_done_scanning():
			if self.picoharp_hw.settings['Tacq'] > 200:
				self.picoharp.read_histogram_data()
			time.sleep(.005)###self.sleep_time)  #TODO : figure out sleep time
		self.picoharp.stop_histogram()
		#ta = time.time()
		self.picoharp.read_histogram_data()

		return self.picoharp.histogram_data