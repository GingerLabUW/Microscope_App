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

class PicoHarp_Scan(PiezoStage_Scan):

    name = "PicoHarp_Scan"

    def setup(self):
        PiezoStage_Scan.setup(self)

        self.picoharp_hw = self.app.hardware['picoharp']
        self.pi_device_hw = self.app.hardware['piezostage']

        self.settings.New("Tacq", unit="s", dtype=float, vmin=1e-3, vmax=100*60*60, initial=1) #removed si=True to keep units from auto-changing
        self.settings.New("Resolution", dtype=int, choices=[("4 ps", 4), ("8 ps", 8), ("16 ps", 16), ("32 ps", 32), ("64 ps", 64), ("128 ps", 128), ("256 ps", 256), ("512 ps", 512)], initial=4)
        self.settings.New("count_rate0", dtype=int, ro=True, vmin=0, vmax=100e6)
        self.settings.New("count_rate1", dtype=int, ro=True, vmin=0, vmax=100e6)

    def setup_figure(self):
        PiezoStage_Scan.setup_figure(self)

        #setup ui for picoharp specific settings
        details_groupBox = self.set_details_widget(widget = self.settings.New_UI(include=["Tacq", "Resolution", "count_rate0", "count_rate1"]))
        widgets = details_groupBox.findChildren(QtGui.QWidget)
        tacq_spinBox = widgets[1]
        resolution_comboBox = widgets[4]
        self.count_rate0_spinBox = widgets[6]
        self.count_rate1_spinBox = widgets[9]
        #connect settings to ui
        self.picoharp_hw.settings.Tacq.connect_to_widget(tacq_spinBox)
        self.picoharp_hw.settings.Resolution.connect_to_widget(resolution_comboBox)
        self.picoharp_hw.settings.count_rate0.connect_to_widget(self.count_rate0_spinBox)
        self.picoharp_hw.settings.count_rate1.connect_to_widget(self.count_rate1_spinBox)

        tacq_spinBox.valueChanged.connect(self.update_estimated_scan_time)
        self.update_estimated_scan_time()

        #save data buttons
        self.ui.save_image_pushButton.clicked.connect(self.save_intensities_image)
        self.ui.save_array_pushButton.clicked.connect(self.save_intensities_data)
    
        #setup imageview
        self.imv = pg.ImageView()
        self.imv.getView().setAspectLocked(lock=False, ratio=1)
        self.imv.getView().setMouseEnabled(x=True, y=True)
        self.imv.getView().invertY(False)
        roi_plot = self.imv.getRoiPlot().getPlotItem()
        roi_plot.getAxis("bottom").setLabel(text="Time (ns)")

    def update_estimated_scan_time(self):
        try:
            self.overhead = self.x_range * self.y_range * .055 #determined by running scans and timing
            scan_time = self.x_range * self.y_range * self.settings["Tacq"] + self.overhead
            self.ui.estimated_scan_time_label.setText("Estimated scan time: " + "%.2f" % scan_time + "s")
        except:
            pass
            
    def update_display(self):
        PiezoStage_Scan.update_display(self)
        if hasattr(self, 'sum_intensities_image_map'):
            self.picoharp_hw.read_from_hardware()
            if not self.interrupt_measurement_called:
                seconds_left = ((self.x_range * self.y_range) - self.pixels_scanned) * self.settings["Tacq"] + self.overhead
                self.ui.estimated_time_label.setText("Estimated time remaining: " + "%.2f" % seconds_left + "s")
            self.img_item.setImage(self.sum_intensities_image_map) #update stage image

            #update imageview
            self.times = self.time_data[:, 0, 0]*1e-3
            self.imv.setImage(img=self.hist_data, autoRange=False, autoLevels=True, xvals=self.times)
            self.imv.show()
            self.imv.window().setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False) #disable closing image view window

            #update progress bar
            progress = 100 * ((self.pixels_scanned+1)/np.abs(self.x_range*self.y_range))
            self.ui.progressBar.setValue(progress)
            self.set_progress(progress)
            pg.QtGui.QApplication.processEvents()

    def pre_run(self):
        try:
            PiezoStage_Scan.pre_run(self) #setup scan paramters
            self.picoharp = self.picoharp_hw.picoharp
            self.check_filename("_raw_PL_hist_data.pkl")
            self.num_hist_chans = self.app.hardware['picoharp'].calc_num_hist_chans()
    
            dirname = self.app.settings['save_dir']        
            self.check_filename('_histdata.dat')
            sample_filename = self.app.settings['sample']
            self.hist_filename = os.path.join(dirname, sample_filename + '_histdata.dat')
            self.check_filename('_timedata.dat')
            self.time_filename = os.path.join(dirname,  sample_filename + '_timedata.dat')
            
            hist_len = self.num_hist_chans
    
            #Use memmaps to use less memory and store data into disk
            self.hist_data= np.memmap(self.hist_filename,dtype='float32',mode='w+',shape=(hist_len, self.x_range, self.y_range))
            self.time_data= np.memmap(self.time_filename,dtype='float32',mode='w+',shape=(hist_len, self.x_range, self.y_range))
    
            #Store histogram sums for each pixel
            self.sum_intensities_image_map = np.zeros((self.x_range, self.y_range), dtype=float)
    
            scan_time = self.x_range * self.y_range * self.settings["Tacq"] #* 1e-3 #s
            self.ui.estimated_scan_time_label.setText("Estimated scan time: " + "%.2f" % scan_time + "s")
        except:
            pass

    def scan_measure(self):
        """
        Data collection for each pixel.
        """
        #t0 = time.time()
        data = self.measure_hist()
        #print(str(time.time()-t0), " measure_hist")
        #t1 = time.time()
        self.time_data[:, self.index_x, self.index_y], self.hist_data[:, self.index_x, self.index_y] = data
        self.sum_intensities_image_map[self.index_x, self.index_y] = sum(data[1])
#        self.time_data.flush()
#        self.hist_data.flush()
        #print(str(time.time()-t1), " rest of scan_measure")

    def post_run(self):
        """
        Export data.
        """
        PiezoStage_Scan.post_run(self)
        save_dict = {"Histogram data": self.hist_data, "Time data": self.time_data,
                 "Scan Parameters":{"X scan start (um)": self.x_start, "Y scan start (um)": self.y_start,
                                    "X scan size (um)": self.x_scan_size, "Y scan size (um)": self.y_scan_size,
                                    "X step size (um)": self.x_step, "Y step size (um)": self.y_step},
                                    "PicoHarp Parameters":{"Acquisition Time (s)": self.settings['Tacq'],
                                                              "Resolution (ps)": self.settings['Resolution']} }

        pickle.dump(save_dict, open(self.app.settings['save_dir']+"/"+self.app.settings['sample']+"_raw_PL_hist_data.pkl", "wb"))

    def measure_hist(self):
        """ Read from picoharp """
        ph = self.picoharp_hw.picoharp           
        ph.start_histogram()
        while not ph.check_done_scanning():
            if self.interrupt_measurement_called:
                break
            ph.read_histogram_data()
            time.sleep(0.001)
    
        ph.stop_histogram()
        ph.read_histogram_data()
        return ph.time_array[0:self.num_hist_chans], ph.histogram_data[0:self.num_hist_chans]

    def save_intensities_data(self):
        transposed = np.transpose(self.sum_intensities_image_map) #transpose so data visually makes sense
        PiezoStage_Scan.save_intensities_data(self, transposed, 'ph')

    def save_intensities_image(self):
        PiezoStage_Scan.save_intensities_image(self, self.sum_intensities_image_map, 'ph')
