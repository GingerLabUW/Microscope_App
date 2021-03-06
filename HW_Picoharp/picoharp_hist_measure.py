from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import numpy as np
import time
import pyqtgraph as pg
import os

# TODO h5 save

class PicoHarpHistogramMeasure(Measurement):    
    name = "picoharp_histogram"
    
    hardware_requirements = ['picoharp']
    
    def setup(self):
        self.display_update_period = 0.1 #seconds

        S = self.settings
        S.New('continuous', dtype=bool, initial=False)

        # UI 
        self.ui_filename = sibling_path(__file__,"picoharp_hist_measure.ui")
        self.ui = load_qt_ui_file(self.ui_filename)
        self.ui.setWindowTitle(self.name)
    
    def setup_figure(self):
        S = self.settings
        # hardware
        ph_hw = self.picoharp_hw = self.app.hardware['picoharp']

        #connect events
        S.progress.connect_bidir_to_widget(self.ui.progressBar)
        S.continuous.connect_to_widget(self.ui.continuous_checkBox)
        ph_hw.settings.Tacq.connect_bidir_to_widget(self.ui.picoharp_tacq_doubleSpinBox)
        #ph.settings.histogram_channels.connect_bidir_to_widget(self.ui.histogram_channels_doubleSpinBox)
        ph_hw.settings.count_rate0.connect_to_widget(self.ui.ch0_label)
        ph_hw.settings.count_rate1.connect_to_widget(self.ui.ch1_label)
        ph_hw.settings.Resolution.connect_to_widget(self.ui.resolution_comboBox)

        #setup ui signals
        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.interrupt_pushButton.clicked.connect(self.interrupt)
        self.ui.save_data_pushButton.clicked.connect(self.save_hist_data)

        self.graph_layout = pg.GraphicsLayoutWidget()    
        
        self.plot = self.graph_layout.addPlot()
        self.plotdata = self.plot.plot(pen='r')
        self.plot.setLogMode(False, True)
        
        self.ui.plot_groupBox.layout().addWidget(self.graph_layout)
        
                
    def run(self):
        ph_hw = self.app.hardware['picoharp']
        ph = self.picoharp = ph_hw.picoharp
        self.num_hist_chans = self.app.hardware['picoharp'].calc_num_hist_chans() #calculate # of histogram channels
        #: type: ph: PicoHarp300
        
        #FIXME
        #self.plotline.set_xdata(ph.time_array*1e-3)
        sleep_time = min((max(0.1*ph.Tacq*1e-3, 0.010), 0.100)) # check every 1/10 of Tacq with limits of 10ms and 100ms
        
        t0 = time.time()
        
        while not self.interrupt_measurement_called:
            ph.start_histogram()
            while not ph.check_done_scanning():
                self.set_progress( 100*(time.time() - t0)/ph_hw.settings['Tacq'] )
                if self.interrupt_measurement_called:
                    break
                ph.read_histogram_data()
                time.sleep(sleep_time)
    
            ph.stop_histogram()
            ph.read_histogram_data()
        
            if not self.settings['continuous']:
                break
        
        save_dict = {
                     'time_histogram': ph.histogram_data[0:self.num_hist_chans],
                     'time_array': ph.time_array[0:self.num_hist_chans],
                    }               

        for lqname,lq in self.app.settings.as_dict().items():
            save_dict[lqname] = lq.val
        
        for hc in self.app.hardware.values():
            for lqname,lq in hc.settings.as_dict().items():
                save_dict[hc.name + "_" + lqname] = lq.val
        
        for lqname,lq in self.settings.as_dict().items():
            save_dict[self.name +"_"+ lqname] = lq.val
                               
    def update_display(self):
        ph = self.picoharp
        self.picoharp_hw.read_from_hardware()
#        self.plotdata.setData(ph.time_array*1e-3, ph.histogram_data+1)
        self.plotdata.setData(ph.time_array[0:self.num_hist_chans]*1e-3, ph.histogram_data[0:self.num_hist_chans]+1)
        #self.fig.canvas.draw()

    def save_hist_data(self):
        ph = self.picoharp
        hist_data = np.zeros((ph.time_array[0:self.num_hist_chans].shape[0], 2)) #check what the shape of this array should be when testing
        hist_data[:,0] = ph.time_array[0:self.num_hist_chans] #set first column with time data
        hist_data[:,1] = ph.histogram_data[0:self.num_hist_chans] #set second column with histogram data
        append = '_histogram_data.txt' #string to append to sample name
        self.check_filename(append)
        np.savetxt(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append, hist_data, fmt='%f')

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
