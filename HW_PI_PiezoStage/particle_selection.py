from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import pyqtgraph as pg
import numpy as np
import time
import pickle
import os.path
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
from pyqtgraph.Point import Point

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
		self.selected_positions = []
		self.origin_x = 0 
		self.origin_y = 0

		###self.pi_device_hw = self.app.hardware['piezostage']

	def setup_figure(self):
		
		self.settings.Magnification.connect_to_widget(self.ui.magnification_comboBox)
		self.settings.W1.connect_to_widget(self.ui.w1_spinBox)
		self.settings.H1.connect_to_widget(self.ui.h1_spinBox)
		self.settings.W2.connect_to_widget(self.ui.w2_spinBox)
		self.settings.H2.connect_to_widget(self.ui.h2_spinBox)
		self.settings.dW.connect_to_widget(self.ui.dw_label)
		self.settings.dH.connect_to_widget(self.ui.dh_label)
		self.settings.dX.connect_to_widget(self.ui.dx_label)
		self.settings.dY.connect_to_widget(self.ui.dy_label)

		self.ui.load_image_pushButton.clicked.connect(self.load_image)
		self.ui.export_pushButton.clicked.connect(self.export_points)
		self.ui.move_stage_pushButton.clicked.connect(self.move_stage)
		self.ui.move_stage_pushButton.clicked.connect(self.start)

		self.image_layout=pg.GraphicsLayoutWidget()
		self.ui.image_groupBox.layout().addWidget(self.image_layout)
		self.image_plot = self.image_layout.addPlot(title="")
		self.image_plot.setAspectLocked(lock=True, ratio=1)

		self.image = pg.ImageItem()
		self.image_plot.addItem(self.image)
		self.image.setPos(0, 0)

		self.arrow1 = pg.ArrowItem()
		self.arrow1.setPos(0,0)
		self.image_plot.addItem(self.arrow1)

		self.arrow2 = pg.ArrowItem()
		self.arrow2.setPos(0,0)
		self.arrow2.setStyle(brush='r')
		self.image_plot.addItem(self.arrow2)

		self.arrow_last_pos = pg.ArrowItem()
		self.arrow_last_pos.setPos(0,0)
		self.image_plot.addItem(self.arrow_last_pos)

		#make sure values update when a new point is selected
		self.settings.W1.updated_value.connect(self.update_positions)
		self.settings.H1.updated_value.connect(self.update_positions)
		self.settings.W2.updated_value.connect(self.update_positions)
		self.settings.H2.updated_value.connect(self.update_positions)
		self.settings.Magnification.updated_value.connect(self.update_positions)

		self.image_plot.scene().sigMouseClicked.connect(self.image_click)
		self.ui.tabWidget.currentChanged.connect(self.switch_arrows)

	def update_positions(self):
		#placeholder values for scaling_factor
		self.scaling_factor = self.calc_scaling_factor()

		self.settings['dW'] = self.settings['W2'] - self.settings['W1']
		self.settings['dH'] = self.settings['H2'] - self.settings['H1']
		self.settings['dX'] = self.settings['dW'] * self.scaling_factor
		self.settings['dY'] = self.settings['dH'] * self.scaling_factor
		self.arrow1.setPos(self.settings['W1'], self.settings['H1'])
		self.arrow2.setPos(self.settings['W2'], self.settings['H2'])

	def calc_scaling_factor(self):
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
				self.point_counter += 1
				if self.ui.first_point_checkBox.isChecked(): #if checked, set first point as origin
					if self.point_counter == 1:
						self.origin_x = mousePoint.x()
						self.origin_y = mousePoint.y()
						self.ui.textBrowser.append("Using (" + str(round(mousePoint.x(),3)) + ", " + str(round(mousePoint.y(),3)) + ") as origin." )
				x_point = mousePoint.x() - self.origin_x
				y_point = mousePoint.y() - self.origin_y
				self.selected_positions.append([x_point, y_point]) #add point to exportable list
				text = "Point #" + str(self.point_counter) + " at (" + str(round(x_point, 3)) + ", " + str(round(y_point, 3)) + ")"
				self.ui.textBrowser.append(text)


	def load_image(self):
		"""
		Prompts the user to select a text file containing image data.
		"""
		try:
			file = QtWidgets.QFileDialog.getOpenFileName(self.ui, 'Open file', os.getcwd())#"*.txt")
			self.image_array = np.genfromtxt(file[0], dtype=None, encoding=None)
			try:
				self.image.setImage(image=self.image_array)
				width = self.image_array.shape[0]
				height = self.image_array.shape[1]
				self.image_plot.setXRange(0, width)
				self.image_plot.setYRange(0, height)
				self.image_plot.setLimits(xMin=0, xMax=width, yMin=0, yMax=height)
				self.image.setRect(0, 0, width, height)
			except:
				print("")
		except Exception as err:
			print(format(err))

	def move_stage(self):
		# if hasattr(self, 'pi_device'):
		# 	self.pi_device.MVR(axes=self.axes, values=[self.settings['dX'], self.settings['dY']])
		pass

	def export_points(self):
		self.check_filename("_selected_particle_positions.txt")
		np.savetxt(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + "_selected_particle_positions.txt", np.asarray(self.selected_positions), fmt='%f')

	def check_filename(self, append):
		'''
		If no sample name given or duplicate sample name given, fix the problem by appending a unique number.
		append - string to add to sample name (including file extension)
		'''
		samplename = self.app.settings['sample']
		filename = samplename + append
		directory = self.app.settings['save_dir']
		if samplename == "":
			self.app.settings['sample'] = int(time.time())
		if (os.path.exists(directory+"/"+filename)):
			self.app.settings['sample'] = samplename + str(int(time.time()))

	def run(self):
		###self.pi_device = self.pi_device_hw.pi_device
		###self.axes = self.pi_device_hw.axes[0:2]
		pass