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

class APD_StepperMotor_Scan(Measurement):
    name = "apd_steppermotor_scan"
    
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
        self.ui_filename = sibling_path(__file__, "apd_stage_scan.ui")
        
        #Load ui file and convert it to a live QWidget of the user interface
        self.ui = load_qt_ui_file(self.ui_filename)

        # Measurement Specific Settings
        # This setting allows the option to save data to an h5 data file during a run
        # All settings are automatically added to the Microscope user interface
        self.settings.New("scan_direction", dtype=str, choices=[('XY', 'XY'), ('YX', 'YX')], initial='XY')
        self.settings.New('magnification', dtype=float, vmin=1, vmax=1000, initial=1)
    
        self.settings.New('x_size', dtype=float, initial=1, unit='um', vmin=0)
        self.settings.New('y_size', dtype=float, initial=1, unit='um', vmin=0)

        self.settings.New('x_step', dtype=float, initial=1, unit='um', vmin=-99, vmax=1000)#vmin=.001)
        self.settings.New('y_step', dtype=float, initial=1, unit='um', vmin=-99, vmax=1000)#vmin=.001)

        self.update_ranges()
        
        # Define how often to update display during a run
        self.display_update_period = .3
        
        # Convenient reference to the hardware used in the measurement
        self.apd_steppermotor_hw = self.app.hardware['apd_steppermotor']
        
        self.scan_complete = False

    def setup_figure(self):
        """
        Runs once during App initialization, after setup()
        This is the place to make all graphical interface initializations,
        build plots, etc.
        """
        
        # connect settings to ui
        self.apd_steppermotor_hw.settings.x_position.connect_to_widget(self.ui.x_pos_doubleSpinBox)
        self.apd_steppermotor_hw.settings.y_position.connect_to_widget(self.ui.y_pos_doubleSpinBox)
        self.settings.scan_direction.connect_to_widget(self.ui.scan_comboBox)
        self.settings.magnification.connect_to_widget(self.ui.magnification_spinBox)
        self.settings.x_size.connect_to_widget(self.ui.x_size_doubleSpinBox)
        self.settings.y_size.connect_to_widget(self.ui.y_size_doubleSpinBox)
        self.settings.x_step.connect_to_widget(self.ui.x_step_doubleSpinBox)
        self.settings.y_step.connect_to_widget(self.ui.y_step_doubleSpinBox)
        self.settings.progress.connect_to_widget(self.ui.progressBar)

        #stage ui base
        self.stage_layout=pg.GraphicsLayoutWidget()
        self.ui.stage_groupBox.layout().addWidget(self.stage_layout)
        self.stage_plot = self.stage_layout.addPlot(title="Stage view")
        self.stage_plot.setXRange(0, 100000) # todo - figure out actual stage range
        self.stage_plot.setYRange(0, 100000)
        self.stage_plot.setLimits(xMin=0, xMax=1000000, yMin=0, yMax=100000) 

        #region of interest - allows user to select scan area
        self.scan_roi = pg.ROI([0,0],[25, 25], movable=False)
        self.handle1 = self.scan_roi.addScaleHandle([1, 1], [0, 0])
        self.handle2 = self.scan_roi.addScaleHandle([0, 0], [1, 1])        
        self.scan_roi.sigRegionChangeFinished.connect(self.mouse_update_scan_roi)
        self.scan_roi.sigRegionChangeFinished.connect(self.update_ranges)
        self.stage_plot.addItem(self.scan_roi)

        #setup ui signals
        self.ui.start_scan_pushButton.clicked.connect(self.start)
        self.ui.interrupt_scan_pushButton.clicked.connect(self.interrupt)

        self.ui.x_size_doubleSpinBox.valueChanged.connect(self.update_roi_size)
        self.ui.y_size_doubleSpinBox.valueChanged.connect(self.update_roi_size)
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
        self.apd_steppermotor_hw.settings.x_position.updated_value.connect(self.update_arrow_pos, QtCore.Qt.UniqueConnection)
        self.apd_steppermotor_hw.settings.y_position.updated_value.connect(self.update_arrow_pos, QtCore.Qt.UniqueConnection)

    def mouse_update_scan_roi(self):
        """Update settings and spinboxes to reflect region of interest."""
        w, h =  self.scan_roi.size()
        self.settings['x_size'] = w
        self.settings['y_size'] = h

    def update_roi_size(self):
        ''' Update region of interest size according to spinboxes '''
        self.scan_roi.setSize((self.settings['x_size'], self.settings['y_size']))

    def update_ranges(self):
        """ 
        Update # of pixels calculation (x_range and y_range) when spinboxes change
        This is important in getting estimated scan time before scan starts.
        """
        self.x_scan_size = self.settings['x_size'] * self.settings['magnification']
        self.y_scan_size = self.settings['y_size'] * self.settings['magnification']
        
        self.x_step = self.settings['x_step'] * self.settings['magnification']
        self.y_step = self.settings['y_step'] * self.settings['magnification']

        if self.y_scan_size == 0:
            self.y_scan_size = self.settings['magnification']
            self.y_step = self.settings['magnification']
        
        if self.x_scan_size == 0:
            self.x_scan_size = self.settings['magnification']
            self.x_step = self.settings['magnification']
        
        if self.y_step == 0:
            self.y_step = self.settings['magnification']
            
        if self.x_step == 0:
            self.x_step = self.settings['magnification']

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
        x = self.apd_steppermotor_hw.settings['x_position']
        y = self.apd_steppermotor_hw.settings['y_position']
        self.current_stage_pos_arrow.setPos(x,y)

    def pre_run(self):
        """
        Define devices, scan parameters, and move stage to start.
        """
        self.apd_steppermotor = self.apd_steppermotor_hw.apd_steppermotor

        #disable roi and spinboxes during scan
        self.scan_roi.removeHandle(self.handle1)
        self.scan_roi.removeHandle(self.handle2)
        for lqname in "scan_direction x_size y_size x_step y_step".split():
            self.settings.as_dict()[lqname].change_readonly(True)

        self.apd_steppermotor_hw.read_position()

        #store motor center position for post-run
        self.x_center = self.apd_steppermotor_hw.settings['x_position']
        self.y_center = self.apd_steppermotor_hw.settings['y_position']

        #determine relative movements to move stage to correct start position
        x_rel = -self.x_scan_size / 2
        y_rel = -self.y_scan_size / 2
        if self.x_step < 0:
            x_rel = x_rel * -1
        if self.y_step < 0:
            y_rel = y_rel * -1

        self.apd_steppermotor.goto([x_rel, y_rel, "r"])

    def update_display(self):
        """
        Displays (plots) the numpy array self.buffer. 
        This function runs repeatedly and automatically during the measurement run.
        its update frequency is defined by self.display_update_period
        """
        self.apd_steppermotor_hw.read_position()
        roi_pos = self.scan_roi.pos()
        self.img_item_rect = QtCore.QRectF(roi_pos[0], roi_pos[1], self.settings['x_size'], self.settings['y_size'])
        self.img_item.setRect(self.img_item_rect)

        if self.scan_complete:
            self.ui.estimated_time_label.setText("Estimated time remaining: 0s")
            self.ui.progressBar.setValue(100)
            self.set_progress(100)

    def run(self):
        self.scan_complete = False
        self.pixels_scanned = 0 #keep track of scan/'pixel' number
        if (self.settings['scan_direction'] == 'XY'): #xy scan
            for i in range(self.y_range):
                for j in range(self.x_range):
                    if self.interrupt_measurement_called:
                        break
                    #make sure the right indices of image arrays are updated
                    self.index_x = j
                    self.index_y = i
                    if self.x_step < 0:
                        self.index_x = self.x_range - j - 1
                    if self.y_step < 0:
                        self.index_y = self.y_range - i - 1
                    self.scan_measure() #defined in hardware-specific scans
                    self.apd_steppermotor.goto([self.x_step, 0, "r"])
                    #self.pi_device.MVR(axes=self.axes[0], values=[self.x_step])
                    self.pixels_scanned+=1
                # TODO
                # if statement needs to be modified to keep the stage at the finish y-pos for line scans in x, and same for y
                if i == self.y_range-1: # this if statement is there to keep the stage at the finish position (in x) and not bring it back like we were doing during the scan 
                    #self.pi_device.MVR(axes=self.axes[1], values=[self.y_step])
                    self.apd_steppermotor.goto([0, self.y_step, "r"])
                else:                
                    #self.pi_device.MVR(axes=self.axes[1], values=[self.y_step])
                    #self.pi_device.MOV(axes=self.axes[0], values=[self.x_start])
                    self.apd_steppermotor.goto([-self.x_scan_size, self.y_step, "r"])
                if self.interrupt_measurement_called:
                    break
        elif (self.settings['scan_direction'] == 'YX'): #yx scan
            for i in range(self.x_range):
                for j in range(self.y_range):
                    if self.interrupt_measurement_called:
                        break

                    #make sure the right indices of image arrays are updated
                    self.index_x = i
                    self.index_y = j
                    if self.x_step < 0:
                        self.index_x = self.x_range - i - 1
                    if self.y_step < 0:
                        self.index_y = self.y_range - j - 1
                    self.scan_measure()
                    #self.pi_device.MVR(axes=self.axes[1], values=[self.y_step])
                    self.apd_steppermotor.goto([0, self.y_step, "r"])
                    self.pixels_scanned+=1
                # TODO
                # if statement needs to be modified to keep the stage at the finish y-pos for line scans in x, and same for y
                if i == self.x_range-1: # this if statement is there to keep the stage at the finish position (in x) and not bring it back like we were doing during the scan 
                    #self.pi_device.MVR(axes=self.axes[0], values=[self.x_step])
                    self.apd_steppermotor.goto([self.x_step, 0, "r"])
                else:                
                    #self.pi_device.MVR(axes=self.axes[0], values=[self.x_step])
                    #self.pi_device.MOV(axes=self.axes[1], values=[self.y_start])
                    self.apd_steppermotor.goto([self.x_step, -self.y_scan_size, "r"])
                if self.interrupt_measurement_called:
                    break
        self.scan_complete = True
        
    def post_run(self):
        """Re-enable roi and spinboxes. """
        self.handle1 = self.scan_roi.addScaleHandle([1, 1], [0, 0])
        self.handle2 = self.scan_roi.addScaleHandle([0, 0], [1, 1])
        for lqname in "scan_direction x_size y_size x_step y_step".split():
            self.settings.as_dict()[lqname].change_readonly(False)
        self.apd_steppermotor.goto([self.x_center, self.y_center]) #reset stepper motor position
            
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

    def save_intensities_image(self, intensities_array, hw_name):
        """
        intensities_array - array of intensities to save as image
        hw_name - string that describes intensities source (ie. oo for oceanoptics, ph for picoharp) 
        """
        append = '_' + hw_name + '_intensity_sums.png'
        cpm.plot_confocal(intensities_array, stepsize=np.abs(self.settings['x_step']))
        self.check_filename(append)
        cpm.plt.savefig(self.app.settings['save_dir'] + '/' + self.app.settings['sample'] + append, bbox_inches='tight', dpi=300)