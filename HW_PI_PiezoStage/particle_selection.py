from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import pyqtgraph as pg
from PIL import Image
import numpy as np
import time
import pickle
import os.path
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
from pyqtgraph.Point import Point
from .PiezoStage_Scan import PiezoStage_Scan

class ParticleSelection(Measurement):
	name = 'particleselection'

	def setup(self):
		self.ui_filename = sibling_path(__file__, "particle_selection.ui")
		
		#Load ui file and convert it to a live QWidget of the user interface
		self.ui = load_qt_ui_file(self.ui_filename)

		self.settings.New('Magnification', dtype=float, choices=[("50x", 50),("75x", 75),("100x", 100), ("150x", 150)], initial=75)
		self.settings.New('W1', dtype=float)
		self.settings.New('H1', dtype=float)
		self.settings.New('W2', dtype=float)
		self.settings.New('H2', dtype=float)
		self.settings.New('dW', dtype=float, ro=True)
		self.settings.New('dH', dtype=float, ro=True)
		self.settings.New('dX', dtype=float, ro=True)
		self.settings.New('dY', dtype=float, ro=True)

		self.PIXEL_SIZE = 7.4

		self.scaling_factor = self.calc_scaling_factor() #initial scaling factor

		#for selecting multiple points
		self.point_counter = 0
		self.relative_movements = []
		self.x_origin = 0 
		self.y_origin = 0

		self.pi_device_hw = self.app.hardware['piezostage']

	def setup_figure(self):
		#connect settings to ui
		self.settings.Magnification.connect_to_widget(self.ui.magnification_comboBox)
		self.settings.W1.connect_to_widget(self.ui.w1_spinBox)
		self.settings.H1.connect_to_widget(self.ui.h1_spinBox)
		self.settings.W2.connect_to_widget(self.ui.w2_spinBox)
		self.settings.H2.connect_to_widget(self.ui.h2_spinBox)
		self.settings.dW.connect_to_widget(self.ui.dw_label)
		self.settings.dH.connect_to_widget(self.ui.dh_label)
		self.settings.dX.connect_to_widget(self.ui.dx_label)
		self.settings.dY.connect_to_widget(self.ui.dy_label)

		#setup ui signals
		self.ui.load_image_pushButton.clicked.connect(self.load_image)
		self.ui.export_pushButton.clicked.connect(self.export_relative_movements)
		self.ui.clear_pushButton.clicked.connect(self.clear_selections)
		self.ui.move_stage_pushButton.clicked.connect(self.start)

		#plot where selected image will be displayed
		self.image_layout=pg.GraphicsLayoutWidget()
		self.ui.image_groupBox.layout().addWidget(self.image_layout)
		self.image_plot = self.image_layout.addPlot(title="")
		self.image_plot.setAspectLocked(lock=True, ratio=1)

		#image item
		self.image = pg.ImageItem()
		self.image_plot.addItem(self.image)
		self.image.setPos(0, 0)

		#arrow showing location of first selected point
		self.arrow1 = pg.ArrowItem()
		self.arrow1.setPos(0,0)
		self.image_plot.addItem(self.arrow1)

		#arrow showing location of second selected point
		self.arrow2 = pg.ArrowItem()
		self.arrow2.setPos(0,0)
		self.arrow2.setStyle(brush='r')
		self.image_plot.addItem(self.arrow2)

		#when selecting multiple points, arrow showing location of last selected point
		self.arrow_last_pos = pg.ArrowItem()
		self.arrow_last_pos.setPos(0,0)
		self.image_plot.addItem(self.arrow_last_pos)

		#make sure values update when a new point is selected
		self.settings.W1.updated_value.connect(self.update_positions)
		self.settings.H1.updated_value.connect(self.update_positions)
		self.settings.W2.updated_value.connect(self.update_positions)
		self.settings.H2.updated_value.connect(self.update_positions)
		self.settings.Magnification.updated_value.connect(self.update_positions)

		self.image_plot.scene().sigMouseClicked.connect(self.image_click) #setup plot click signal
		self.ui.tabWidget.currentChanged.connect(self.switch_arrows) #setup tab switch signal

	def update_positions(self):
		"""
		Keep scaling factor, arrows, and x/y positions updated 
		"""
		self.scaling_factor = self.calc_scaling_factor()

		self.settings['dW'] = self.settings['W2'] - self.settings['W1']
		self.settings['dH'] = (self.settings['H2'] - self.settings['H1']) * -1 #invert sign of dH since image has been flipped vertically
		self.settings['dX'] = self.settings['dW'] * self.scaling_factor
		self.settings['dY'] = self.settings['dH'] * self.scaling_factor
		self.arrow1.setPos(self.settings['W1'], self.settings['H1'])
		self.arrow2.setPos(self.settings['W2'], self.settings['H2'])

	def calc_scaling_factor(self):
		"""
		Calculate scaling factor
		"""
		return self.PIXEL_SIZE/self.settings['Magnification']

	def switch_arrows(self):
		"""
		Update arrows to match the current tab's functionality.
		"""
		if self.ui.tabWidget.currentIndex() == 0:
			self.arrow1.show()
			self.arrow2.show()
			self.arrow_last_pos.hide()
		elif self.ui.tabWidget.currentIndex() == 1:
			self.arrow_last_pos.show()
			self.arrow1.hide()
			self.arrow2.hide()

	def image_click(self, event):
		"""
		Handle image clicking
		"""
		pos = event.scenePos()
		mousePoint = self.image_plot.vb.mapSceneToView(pos)

		if self.image_plot.sceneBoundingRect().contains(pos) and self.ui.select_point_checkBox.isChecked():

			if self.ui.tabWidget.currentIndex() == 0: #if on "2 points" tab
				if  self.ui.point1_radioButton.isChecked():
					self.settings['W1'] = mousePoint.x()
					self.settings['H1'] = mousePoint.y()
				elif self.ui.point2_radioButton.isChecked():
					self.settings['W2'] = mousePoint.x()
					self.settings['H2'] = mousePoint.y()
			
			elif self.ui.tabWidget.currentIndex() == 1: #if on "particle selection" tab
				self.arrow_last_pos.setPos(mousePoint)
				
				if self.point_counter == 0: #if first point
					self.prev_point = mousePoint
					text = "Starting point selected."

					#store initial stage position and first point for later bounds-checking 
					self.pi_x_start = self.pi_device_hw.settings['x_position']
					self.pi_y_start = self.pi_device_hw.settings['y_position']
					self.x_origin = mousePoint.x()
					self.y_origin = mousePoint.y()
					self.point_counter += 1
				else: #if second point or more
					x_point_check = (mousePoint.x() - self.x_origin) * self.scaling_factor + self.pi_x_start #get projected stage position
					y_point_check = (mousePoint.y() - self.y_origin) * self.scaling_factor + self.pi_y_start
					if x_point_check < 0 or x_point_check > 100 or y_point_check < 0 or y_point_check > 100: #stage bounds checking
						text = self.ui.textBrowser.append("This point is out of stage bounds.")
					else: # if not out of stage bounds, carry on with point selection
						self.point_counter += 1
						x_difference = (mousePoint.x() - self.prev_point.x()) * self.scaling_factor #get difference between current and previous points
						y_difference = (mousePoint.y() - self.prev_point.y()) * self.scaling_factor
						self.relative_movements.append([x_difference, y_difference])
						text = "Relative movement #" + str(self.point_counter - 1) + " of (" + str(round(x_difference,3)) + ", " + str(round(y_difference,3)) + ")"
						self.prev_point = mousePoint #save this point for the next calculation

				self.ui.textBrowser.append(text)

	def load_image(self):
		"""
		Prompts the user to select a text file containing image data.
		"""
		try:
			file = QtWidgets.QFileDialog.getOpenFileName(self.ui, 'Open file', os.getcwd())#"*.txt")
			#self.image_array = np.genfromtxt(file[0], dtype=None, encoding=None)
			image = Image.open(file[0])
			image = image.rotate(-90, expand=True) #rotate since pyqtgraph's setImage is column-major
			image_array = np.asarray(image)
			try:
				self.image.setImage(image=image_array)
				width = image_array.shape[0]
				height = image_array.shape[1]

				#set limits for zooming/panning
				self.image_plot.setXRange(0, width)
				self.image_plot.setYRange(0, height)
				self.image_plot.setLimits(xMin=0, xMax=width, yMin=0, yMax=height)
			except:
				pass
		except Exception as err:
			print(format(err))
			
	def export_relative_movements(self):
		PiezoStage_Scan.check_filename(self, "_selected_relative_movements.txt") #make sure filename doesn't already exist
		np.savetxt(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + "_selected_relative_movements.txt", np.asarray(self.relative_movements), fmt='%f')

	def clear_selections(self):
		"""
		Reset multiple point selection.
		"""
		self.point_counter = 0
		self.relative_movements = []
		self.x_origin = 0 
		self.y_origin = 0
		self.ui.textBrowser.append("Selections cleared.")

	def run(self):
		"""
		Move stage from first selected point to the second point, assuming piezo stage is already at first point.
		"""
		self.pi_device = self.pi_device_hw.pi_device
		self.axes = self.pi_device_hw.axes[0:2]
		self.pi_device.MVR(axes=self.axes, values=[self.settings['dX'], self.settings['dY']])
		self.pi_device_hw.read_from_hardware()