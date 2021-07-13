from HW_Picoharp.picoharp_scan import PicoHarp_Scan
from HW_Picoharp.picoharp_g2_measure import PicoHarpG2Measure
from HW_PI_PiezoStage.PiezoStage_Scan import PiezoStage_Scan
from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import pyqtgraph as pg
import numpy as np
import time
import pickle
import os.path
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
from pyqtgraph.Point import Point
import customplotting.mscope as cpm

class PicoHarp_G2_Scan(PicoHarp_Scan):

	name = "PicoHarp_G2_Scan"

	def setup(self):
		PicoHarp_Scan.setup(self)

		self.picoharp_hw = self.app.hardware['picoharp']
		self.pi_device_hw = self.app.hardware['piezostage']
		
	def setup_figure(self):
		PicoHarp_Scan.setup_figure(self)

	def update_estimated_scan_time(self):
		try:
			self.overhead = self.x_range * self.y_range * .055 #this number is from hist scan. update once we know more
			scan_time = self.x_range * self.y_range * self.settings["Tacq"] + self.overhead
			self.ui.estimated_scan_time_label.setText("Estimated scan time: " + "%.2f" % scan_time + "s")
		except:
			pass
			
	def update_display(self):
		PiezoStage_Scan.update_display(self)
		
	def pre_run(self):
		try:
			PiezoStage_Scan.pre_run(self) #setup scan paramters
			PicoHarpG2Measure.pre_run(self)
			self.picoharp = self.picoharp_hw.picoharp
			self.check_filename('_g2_scan.txt')
	
			dirname = self.app.settings['save_dir']        
			sample_filename = self.app.settings['sample']
			self.counts_filename = os.path.join(dirname, sample_filename + '_g2_scan.txt')
			
			scan_time = self.x_range * self.y_range * self.settings["Tacq"] #* 1e-3 #s
			self.ui.estimated_scan_time_label.setText("Estimated scan time: " + "%.2f" % scan_time + "s")
		except:
			pass

	def scan_measure(self):
		"""
		Data collection for each pixel.
		"""
		PicoHarpG2Measure.read_over_intg_time(self.settings.Tacq, self.count_rate0_spinBox, self.count_rate1_spinBox)
	
	def post_run(self):
		"""
		Export data.
		"""
		PicoHarpG2Measure.post_run(self)
