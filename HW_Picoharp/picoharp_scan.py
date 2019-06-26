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

class PicoHarp_Scan(PiezoStage_Scan):

    name = "PicoHarp_Scan"

    def setup(self):
        PiezoStage_Scan.setup(self)

        self.picoharp_hw = self.app.hardware['picoharp']
        self.pi_device_hw = self.app.hardware['piezostage']

        self.settings.New("Tacq", dtype=float, unit="s", si=True, vmin=1e-3, vmax=100*60*60)
        self.settings.New("Resolution", dtype=int, choices=[("4 ps", 4), ("8 ps", 8), ("16 ps", 16), ("32 ps", 32), ("64 ps", 64), ("128 ps", 128), ("256 ps", 256), ("512 ps", 512)], initial=4)
        self.settings.New("count_rate0", dtype=int, ro=True, vmin=0, vmax=100e6)
        self.settings.New("count_rate1", dtype=int, ro=True, vmin=0, vmax=100e6)

    def setup_figure(self):
        PiezoStage_Scan.setup_figure(self)
        self.ui.save_array_pushButton.clicked.connect(self.save_intensities_data)
        self.ui.save_image_pushButton.clicked.connect(self.save_intensities_image)
        details_groupBox = self.set_details_widget(widget = self.settings.New_UI(include=["Tacq", "Resolution", "count_rate0", "count_rate1"]))
        widgets = details_groupBox.findChildren(QtGui.QWidget)        
        tacq_spinBox = widgets[1]
        resolution_comboBox = widgets[4]
        count_rate0_spinBox = widgets[6]
        count_rate1_spinBox = widgets[9]
        self.picoharp_hw.settings.Tacq.connect_to_widget(tacq_spinBox)
        self.picoharp_hw.settings.Resolution.connect_to_widget(resolution_comboBox)
        self.picoharp_hw.settings.count_rate0.connect_to_widget(count_rate0_spinBox)
        self.picoharp_hw.settings.count_rate1.connect_to_widget(count_rate1_spinBox)

        #save data buttons
        #self.ui.save_image_pushButton.clicked.connect(self.save_intensities_image)
        self.ui.save_array_pushButton.clicked.connect(self.save_intensities_data)
    
        self.imv = pg.ImageView()
        self.imv.getView().setAspectLocked(lock=False, ratio=1)
        self.imv.getView().setMouseEnabled(x=True, y=True)

    def update_display(self):
        PiezoStage_Scan.update_display(self)
        if hasattr(self, 'picoharp') and hasattr(self, 'pi_device') and hasattr(self, 'sum_display_image_map'):
            if not self.interrupt_measurement_called:
                seconds_left = ((self.x_range * self.y_range) - self.pixels_scanned) * self.settings["Tacq"]
                self.ui.estimated_time_label.setText("Estimated time remaining: " + str(seconds_left) + "s")
            sum_disp_img = self.sum_display_image_map
            self.img_item.setImage(sum_disp_img)
            self.imv.setImage(img=self.hist_data, autoRange=False, autoLevels=True)
            self.imv.show()
            self.imv.window().setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False) #disable closing image view window

            progress = 100 * ((self.pixels_scanned+1)/np.abs(self.x_range*self.y_range))
            self.ui.progressBar.setValue(progress)
            self.set_progress(progress)
            pg.QtGui.QApplication.processEvents()

    def pre_run(self):
            """
            numpy memmaps do not play well when being overwritten if they aren't closed.
            However, any call to the memmap after it has closed will crash the Python program.
            Since the run() function runs on a thread that constantly calls update_display() which
            calls the memmaps to plot the data, then the program will crash if the garbage collection
            is done in the main run thread.

            Therefore, before the program runs and the update_display() function is called, we should
            check whether the memmaps exist. If they do, we need to close them, delete them and then remove
            the temporary filename on disk associated to the memmap.

            """
            # if hasattr(self,'time_data'): ###
            #     self.time_data._mmap.close()
            #     self.hist_data._mmap.close()
            #     delattr(self,'time_data')
            #     delattr(self,'hist_data')
            #     os.remove(self.time_filename)
            #     os.remove(self.hist_filename)
            ## set all logged quantities read only
            #for lqname in "xdim ydim map_size".split():
            #    self.settings.as_dict()[lqname].change_readonly(True)
            #compute relevant scan parameters and move the APT motors to the start point of the scan
            #self.compute_scan_params()
            self.num_hist_chans = self.app.hardware['picoharp'].calc_num_hist_chans()
            #self.ui.time_remaining_disp.setText(self.calc_time_left())
            #self.move_to_start()
    
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

        # XX, YY = np.meshgrid(np.arange(0,  x_scan_size, x_step),np.arange(0, y_scan_size, y_step))
  #       YY = YY+y_start
  #       XX = XX+x_start

        dirname = self.app.settings['save_dir']
        sample_filename = self.app.settings['sample']
        self.check_filename('histdata.dat')
        self.hist_filename = os.path.join(dirname, sample_filename + 'histdata.dat')
        self.check_filename('timedata.dat')
        self.time_filename = os.path.join(dirname,  sample_filename + 'timedata.dat')
        
        hist_len = self.num_hist_chans

        #Use memmaps to use less memory and store data into disk
        self.hist_data= np.memmap(self.hist_filename,dtype='float32',mode='w+',shape=(hist_len, self.x_range, self.y_range))#len(XX[0,:]),len(YY[:,0])))
        self.time_data= np.memmap(self.time_filename,dtype='float32',mode='w+',shape=(hist_len, self.x_range, self.y_range))#len(XX[0,:]),len(YY[:,0]))) ###TODO: memmap throwing errors

        #self.hist_data = np.zeros(shape=(hist_len, self.x_range, self.y_range)) ###use array instead of memmap for now
        #self.time_data = np.zeros(shape=(hist_len, self.x_range, self.y_range))
        #Store histogram sums for each pixel
        self.sum_display_image_map = np.zeros((self.x_range, self.y_range), dtype=float)
        
        # Move to the starting position
        self.pi_device.MOV(axes=self.axes, values=[x_start,y_start])
        self.pi_device_hw.read_from_hardware()

        self.pixels_scanned = 0 #keep track of scan/'pixel' number
        for i in range(self.y_range):
            for j in range(self.x_range):
                if self.interrupt_measurement_called:
                    break

                #make sure the right indices of image arrays are updated
                index_x = j
                index_y = i
                if x_step < 0:
                    index_x = self.x_range - j - 1
                if y_step < 0:
                    index_y = self.y_range - i - 1

                data = self.measure_hist()
                self.time_data[:,index_x, index_y], self.hist_data[:, index_x, index_y] = data            
                self.sum_display_image_map[index_x, index_y] = sum(data[1])
                ####self.time_data.flush()
                ###self.hist_data.flush()
                
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

        self.ui.estimated_time_label.setText("Estimated time remaining: 0s")
        self.scan_complete = True
        #np.savez_compressed(data_filename,bins=self.time_data,hist=self.hist_data)

    def measure_hist(self):
        ph = self.picoharp_hw.picoharp
        
        # print(ph.Tacq)                
        ph.start_histogram()
        while not ph.check_done_scanning():
            if self.interrupt_measurement_called:
                break
            ph.read_histogram_data()
            self.picoharp_hw.settings.count_rate0.read_from_hardware()
            self.picoharp_hw.settings.count_rate1.read_from_hardware()
            time.sleep(0.001)
    
        ph.stop_histogram()
        ph.read_histogram_data()
        return ph.time_array[0:self.num_hist_chans], ph.histogram_data[0:self.num_hist_chans]

    def save_intensities_data(self):
        PiezoStage_Scan.save_intensities_data(self.sum_display_image_map, 'ph')

    def save_intensities_image(self):
        PiezoStage_Scan.save_intensities_image(self.sum_display_image_map, 'ph')