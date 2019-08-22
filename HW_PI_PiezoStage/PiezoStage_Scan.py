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

class PiezoStage_Scan(Measurement):
    name = "PiezoStage_Scan"

    
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
        self.ui_filename = sibling_path(__file__, "stage_scan.ui")
        
        #Load ui file and convert it to a live QWidget of the user interface
        self.ui = load_qt_ui_file(self.ui_filename)

        # Measurement Specific Settings
        # This setting allows the option to save data to an h5 data file during a run
        # All settings are automatically added to the Microscope user interface
        self.settings.New("scan_direction", dtype=str, choices=[('XY', 'XY'), ('YX', 'YX')], initial='XY')

        self.settings.New('x_start', dtype=float, unit='um', vmin=0)
        self.settings.New('y_start', dtype=float, unit='um', vmin=0)
    
        self.settings.New('x_size', dtype=float, initial=1, unit='um', vmin=0)
        self.settings.New('y_size', dtype=float, initial=1, unit='um', vmin=0)

        self.settings.New('x_step', dtype=float, initial=1, unit='um', vmin=-99, vmax=99)#vmin=.001)
        self.settings.New('y_step', dtype=float, initial=1, unit='um', vmin=-99, vmax=99)#vmin=.001)

        self.settings.New('x_clicked', dtype=float, initial=0, unit='um', vmin=0, vmax=100, ro=True)
        self.settings.New('y_clicked', dtype=float, initial=0, unit='um', vmin=0, vmax=100, ro=True)

        self.settings.New('lock_position', dtype=bool, initial=False)
        self.settings.New('save_positions', dtype=bool, initial=False)

        self.update_ranges()
        
        # Define how often to update display during a run
        self.display_update_period = .3
        
        # Convenient reference to the hardware used in the measurement
        self.pi_device_hw = self.app.hardware['piezostage']

        self.scan_complete = False

        self.selected_positions = np.zeros((1000, 2))
        self.selected_count = 0 #number of points selected

    def setup_figure(self):
        """
        Runs once during App initialization, after setup()
        This is the place to make all graphical interface initializations,
        build plots, etc.
        """
        
        # connect settings to ui
        self.pi_device_hw.settings.x_position.connect_to_widget(self.ui.x_pos_doubleSpinBox)
        self.pi_device_hw.settings.y_position.connect_to_widget(self.ui.y_pos_doubleSpinBox)
        self.settings.scan_direction.connect_to_widget(self.ui.scan_comboBox)
        self.settings.x_start.connect_to_widget(self.ui.x_start_doubleSpinBox)
        self.settings.y_start.connect_to_widget(self.ui.y_start_doubleSpinBox)    
        self.settings.x_size.connect_to_widget(self.ui.x_size_doubleSpinBox)
        self.settings.y_size.connect_to_widget(self.ui.y_size_doubleSpinBox)
        self.settings.x_step.connect_to_widget(self.ui.x_step_doubleSpinBox)
        self.settings.y_step.connect_to_widget(self.ui.y_step_doubleSpinBox)
        self.settings.x_clicked.connect_to_widget(self.ui.x_clicked_doubleSpinBox)
        self.settings.y_clicked.connect_to_widget(self.ui.y_clicked_doubleSpinBox)
        self.settings.lock_position.connect_to_widget(self.ui.lock_position_checkBox)
        self.settings.save_positions.connect_to_widget(self.ui.save_positions_checkBox)
        self.settings.progress.connect_to_widget(self.ui.progressBar)

        #stage ui base
        self.stage_layout=pg.GraphicsLayoutWidget()
        self.ui.stage_groupBox.layout().addWidget(self.stage_layout)
        self.stage_plot = self.stage_layout.addPlot(title="Stage view")
        self.stage_plot.setXRange(0, 100)
        self.stage_plot.setYRange(0, 100)
        self.stage_plot.setLimits(xMin=0, xMax=100, yMin=0, yMax=100) 

        #region of interest - allows user to select scan area
        self.scan_roi = pg.ROI([0,0],[25, 25], movable=True)
        self.handle1 = self.scan_roi.addScaleHandle([1, 1], [0, 0])
        self.handle2 = self.scan_roi.addScaleHandle([0, 0], [1, 1])        
        self.scan_roi.sigRegionChangeFinished.connect(self.mouse_update_scan_roi)
        self.scan_roi.sigRegionChangeFinished.connect(self.update_ranges)
        self.stage_plot.addItem(self.scan_roi)

        #setup ui signals
        self.ui.start_scan_pushButton.clicked.connect(self.start)
        self.ui.interrupt_scan_pushButton.clicked.connect(self.interrupt)
        self.ui.move_to_selected_pushButton.clicked.connect(self.move_to_selected)
        self.ui.export_positions_pushButton.clicked.connect(self.export_positions)

        self.ui.x_start_doubleSpinBox.valueChanged.connect(self.update_roi_start)
        self.ui.y_start_doubleSpinBox.valueChanged.connect(self.update_roi_start)
        self.ui.x_size_doubleSpinBox.valueChanged.connect(self.update_roi_size)
        self.ui.y_size_doubleSpinBox.valueChanged.connect(self.update_roi_size)
        self.ui.x_step_doubleSpinBox.valueChanged.connect(self.update_roi_start)
        self.ui.y_step_doubleSpinBox.valueChanged.connect(self.update_roi_start)

        self.ui.x_size_doubleSpinBox.valueChanged.connect(self.update_ranges)
        self.ui.y_size_doubleSpinBox.valueChanged.connect(self.update_ranges)
        self.ui.x_step_doubleSpinBox.valueChanged.connect(self.update_ranges)
        self.ui.y_step_doubleSpinBox.valueChanged.connect(self.update_ranges)

        #histogram for image
        self.hist_lut = pg.HistogramLUTItem()
        self.stage_layout.addItem(self.hist_lut)

        #image on stage plot, will show intensity sums
        self.img_item = pg.ImageItem()
        self.stage_plot.addItem(self.img_item)
        blank = np.zeros((3,3))
        self.img_item.setImage(image=blank) #placeholder image
        
        self.hist_lut.setImageItem(self.img_item) #setup histogram

        #arrow showing stage location
        self.current_stage_pos_arrow = pg.ArrowItem()
        self.current_stage_pos_arrow.setZValue(100)
        self.stage_plot.addItem(self.current_stage_pos_arrow)
        self.pi_device_hw.settings.x_position.updated_value.connect(self.update_arrow_pos, QtCore.Qt.UniqueConnection)
        self.pi_device_hw.settings.y_position.updated_value.connect(self.update_arrow_pos, QtCore.Qt.UniqueConnection)

        #Define crosshairs that will show up after scan, event handling.
        self.vLine = pg.InfiniteLine(angle=90, movable=False, pen='r')
        self.hLine = pg.InfiniteLine(angle=0, movable=False, pen='r')
        self.stage_plot.scene().sigMouseClicked.connect(self.ch_click)

    def ch_click(self, event):
        '''
        Handle crosshair clicking, which toggles movement on and off.
        '''
        pos = event.scenePos()
        if not self.settings['lock_position'] and self.stage_plot.sceneBoundingRect().contains(pos):
            mousePoint = self.stage_plot.vb.mapSceneToView(pos)
            self.vLine.setPos(mousePoint.x())
            self.hLine.setPos(mousePoint.y())
            self.settings['x_clicked'] = mousePoint.x()
            self.settings['y_clicked'] = mousePoint.y()
            if self.settings['save_positions']:
                self.selected_positions[self.selected_count, 0] = mousePoint.x()
                self.selected_positions[self.selected_count, 1] = mousePoint.y()
                self.selected_count += 1

    def export_positions(self):
        """ Export selected positions into txt. """
        self.check_filename("_selected_positions.txt")
        trimmed = self.selected_positions[~np.all(self.selected_positions == 0, axis=1)] #get rid of empty rows
        np.savetxt(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + "_selected_positions.txt", trimmed, fmt='%f')

    def move_to_selected(self):
        """Move stage to position selected by crosshairs."""
        if self.scan_complete and hasattr(self, 'pi_device'):
            x = self.settings['x_clicked']
            y = self.settings['y_clicked']
            self.pi_device.MOV(axes=self.axes, values=[x, y])
            self.pi_device_hw.read_from_hardware()

    def mouse_update_scan_roi(self):
        """Update settings and spinboxes to reflect region of interest."""
        x0,y0 =  self.scan_roi.pos()
        w, h =  self.scan_roi.size()
        if self.settings['x_step'] > 0: 
            self.settings['x_start'] = x0
        else: 
            self.settings['x_start'] = x0 + w

        if self.settings['y_step'] > 0:
            self.settings['y_start'] = y0
        else:
            self.settings['y_start'] = y0 + h 

        self.settings['x_size'] = w
        self.settings['y_size'] = h

    def update_roi_start(self):
        """Update region of interest start position according to spinboxes"""
        x_roi = self.settings['x_start'] #default start values that work with positive x and y steps
        y_roi = self.settings['y_start']
        if self.settings['x_step'] < 0:
            x_roi = self.settings['x_start'] - self.settings['x_size']
        if self.settings['y_step'] < 0:
            y_roi = self.settings['y_start'] - self.settings['y_size']
        self.scan_roi.setPos(x_roi, y_roi)

    def update_roi_size(self):
        ''' Update region of interest size according to spinboxes '''
        self.scan_roi.setSize((self.settings['x_size'], self.settings['y_size']))

    def update_ranges(self):
        """ 
        Update # of pixels calculation (x_range and y_range) when spinboxes change
        This is important in getting estimated scan time before scan starts.
        """
        self.x_scan_size = self.settings['x_size']
        self.y_scan_size = self.settings['y_size']
        
        self.x_step = self.settings['x_step']
        self.y_step = self.settings['y_step']

        if self.y_scan_size == 0:
            self.y_scan_size = 1
            self.y_step = 1
        
        if self.x_scan_size == 0:
            self.x_scan_size = 1
            self.x_step = 1
        
        if self.y_step == 0:
            self.y_step = 1
            
        if self.x_step == 0:
            self.x_step = 1

        self.x_range = np.abs(int(np.ceil(self.x_scan_size/self.x_step)))
        self.y_range = np.abs(int(np.ceil(self.y_scan_size/self.y_step)))
        self.update_estimated_scan_time()

    def update_estimated_scan_time(self):
        """implemented in hard-specific scan programs"""
        pass

    def update_arrow_pos(self):
        '''
        Update arrow position on image to stage position
        '''
        x = self.pi_device_hw.settings['x_position']
        y = self.pi_device_hw.settings['y_position']
        self.current_stage_pos_arrow.setPos(x,y)

    def pre_run(self):
        """
        Define devices, scan parameters, and move stage to start.
        """
        self.pi_device = self.pi_device_hw.pi_device
        self.axes = self.pi_device_hw.axes

        #disable roi and spinboxes during scan
        self.scan_roi.removeHandle(self.handle1)
        self.scan_roi.removeHandle(self.handle2)
        self.scan_roi.translatable = False
        for lqname in "scan_direction x_start y_start x_size y_size x_step y_step".split():
            self.settings.as_dict()[lqname].change_readonly(True)

        self.x_start = self.settings['x_start']
        self.y_start = self.settings['y_start']

        self.pi_device.MOV(axes=self.axes, values=[self.x_start, self.y_start])
        self.pi_device_hw.read_from_hardware()

    def update_display(self):
        """
        Displays (plots) the numpy array self.buffer. 
        This function runs repeatedly and automatically during the measurement run.
        its update frequency is defined by self.display_update_period
        """
        self.pi_device_hw.read_from_hardware()
        roi_pos = self.scan_roi.pos()
        self.img_item_rect = QtCore.QRectF(roi_pos[0], roi_pos[1], self.settings['x_size'], self.settings['y_size'])
        self.img_item.setRect(self.img_item_rect)

        if self.scan_complete:
            self.ui.estimated_time_label.setText("Estimated time remaining: 0s")
            self.ui.progressBar.setValue(100)
            self.set_progress(100)
            self.stage_plot.addItem(self.hLine)
            self.stage_plot.addItem(self.vLine)

            x, y = self.scan_roi.pos()
            middle_x = x + self.settings['x_size']/2
            middle_y = y + self.settings['y_size']/2
            self.hLine.setPos(middle_y)
            self.vLine.setPos(middle_x)

    def run(self):
        self.scan_complete = False
        self.pixels_scanned = 0 #keep track of scan/'pixel' number
        if (self.settings['scan_direction'] == 'XY'): #xy scan
            for i in range(self.y_range):
                for j in range(self.x_range):
                    t0 = time.time()
                    if self.interrupt_measurement_called:
                        break
                    #make sure the right indices of image arrays are updated
                    self.index_x = j
                    self.index_y = i
                    if self.x_step < 0:
                        self.index_x = self.x_range - j - 1
                    if self.y_step < 0:
                        self.index_y = self.y_range - i - 1
                    t1 = time.time()
                    self.scan_measure() #defined in hardware-specific scans
                    if self.pi_device_hw.settings["debug_mode"]:
                        print("Scan measure time: " + str(time.time() - t1))
                    self.pi_device.MVR(axes=self.axes[0], values=[self.x_step])
                    self.pixels_scanned+=1

                    if self.pi_device_hw.settings["debug_mode"]:
                        print("Pixel scan time: " + str(time.time() - t0) )
                # TODO
                # if statement needs to be modified to keep the stage at the finish y-pos for line scans in x, and same for y
                if i == self.y_range-1: # this if statement is there to keep the stage at the finish position (in x) and not bring it back like we were doing during the scan 
                    self.pi_device.MVR(axes=self.axes[1], values=[self.y_step])
                else:                
                    self.pi_device.MVR(axes=self.axes[1], values=[self.y_step])
                    self.pi_device.MOV(axes=self.axes[0], values=[self.x_start])
                if self.interrupt_measurement_called:
                    break
        elif (self.settings['scan_direction'] == 'YX'): #yx scan
            t2 = time.time()
            for i in range(self.x_range):
                for j in range(self.y_range):
                    t0 = time.time()
                    if self.interrupt_measurement_called:
                        break

                    #make sure the right indices of image arrays are updated
                    self.index_x = i
                    self.index_y = j
                    if self.x_step < 0:
                        self.index_x = self.x_range - i - 1
                    if self.y_step < 0:
                        self.index_y = self.y_range - j - 1

                    t1 = time.time()
                    self.scan_measure()
                    if self.pi_device_hw.settings["debug_mode"]:
                        print("Scan measure time: " + str(time.time()-t1))

                    self.pi_device.MVR(axes=self.axes[1], values=[self.y_step])
                    self.pixels_scanned+=1

                    if self.pi_device_hw.settings["debug_mode"]:
                        print("Pixel scan time: " + str(time.time() - t0))
                # TODO
                # if statement needs to be modified to keep the stage at the finish y-pos for line scans in x, and same for y
                if i == self.x_range-1: # this if statement is there to keep the stage at the finish position (in x) and not bring it back like we were doing during the scan 
                    self.pi_device.MVR(axes=self.axes[0], values=[self.x_step])
                else:                
                    self.pi_device.MVR(axes=self.axes[0], values=[self.x_step])
                    self.pi_device.MOV(axes=self.axes[1], values=[self.y_start])
                if self.interrupt_measurement_called:
                    break
            if self.pi_device_hw.settings["debug_mode"]:
                print("Total scan time: " + str(time.time() - t2))
        self.scan_complete = True
        
    def post_run(self):
        """Re-enable roi and spinboxes. """
        self.handle1 = self.scan_roi.addScaleHandle([1, 1], [0, 0])
        self.handle2 = self.scan_roi.addScaleHandle([0, 0], [1, 1])
        self.scan_roi.translatable = True
        for lqname in "scan_direction x_start y_start x_size y_size x_step y_step".split():
            self.settings.as_dict()[lqname].change_readonly(False)
        if self.pi_device_hw.settings["debug_mode"]:
            print("Scan complete.")
            
    def scan_measure(self):
        """
        Not defined in this class. This is defined in hardware-specific scans that inherit this class.
        """
        pass

    def check_filename(self, append):
        """
        If no sample name given or duplicate sample name given, fix the problem by appending a unique number.
        append - string to add to sample name (including file extension)
        """
        samplename = self.app.settings['sample']
        filename = samplename + append
        directory = self.app.settings['save_dir']
        if samplename == "":
            self.app.settings['sample'] = int(time.time())
        if (os.path.exists(directory+"/"+filename)):
            self.app.settings['sample'] = samplename + str(int(time.time()))
    
    def set_details_widget(self, widget = None, ui_filename=None):
        """ Helper function for setting up ui elements for settings. """
        #print('LOADING DETAIL UI')
        if ui_filename is not None:
            details_ui = load_qt_ui_file(ui_filename)
        if widget is not None:
            details_ui = widget
        if hasattr(self, 'details_ui'):
            if self.details_ui is not None:
                self.details_ui.deleteLater()
                self.ui.details_groupBox.layout().removeWidget(self.details_ui)
                #self.details_ui.hide()
                del self.details_ui
        self.details_ui = details_ui
        #return replace_widget_in_layout(self.ui.details_groupBox,details_ui)
        self.ui.details_groupBox.layout().addWidget(self.details_ui)
        return self.details_ui

    def save_intensities_data(self, intensities_array, hw_name):
        """
        intensities_array - array of intensities to save
        hw_name - string that describes intensities source (ie. oo for oceanoptics, ph for picoharp) 
        """
        append = '_' + hw_name + '_intensity_sums.txt' #string to append to sample name
        self.check_filename(append)
        transposed = np.transpose(intensities_array)
        np.savetxt(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append, transposed, fmt='%f')

        if self.pi_device_hw.settings["debug_mode"]:
            print("Intensities array saved.")

    def save_intensities_image(self, intensities_array, hw_name):
        """
        intensities_array - array of intensities to save as image
        hw_name - string that describes intensities source (ie. oo for oceanoptics, ph for picoharp) 
        """
        append = '_' + hw_name + '_intensity_sums.png'
        cpm.plot_confocal(intensities_array, stepsize=np.abs(self.settings['x_step']))
        self.check_filename(append)
        cpm.plt.savefig(self.app.settings['save_dir'] + '/' + self.app.settings['sample'] + append, bbox_inches='tight', dpi=300)
        if self.pi_device_hw.settings["debug_mode"]:
            print("Intensities image saved.")