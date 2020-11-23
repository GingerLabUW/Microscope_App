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

        # setup countrate lists for T2 mode
        self.count_rate_0_array = []
        self.count_rate_1_array = []
        self.count_rate_time_array = []
    
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

        # For plotting channel 0 & 1 countrate while in T2 mode
        # setup plots
        self.channel_graph_layout = pg.GraphicsLayoutWidget()
        self.plot_count_rate_0 = self.channel_graph_layout.addPlot(
            row=0, col=0, title="Channel 0", labels={"bottom" : "Time (s)"}
            )        
        self.plot_count_rate_1 = self.channel_graph_layout.addPlot(
            row=1, col=0, title="Channel 1", labels={"bottom" : "Time (s)"}
            )
        # set log in y axis
        self.plot_count_rate_0.setLogMode(False, True)
        self.plot_count_rate_1.setLogMode(False, True)
        
                
    def run(self):
        ph_hw = self.app.hardware['picoharp']
        ph = self.picoharp = ph_hw.picoharp
        self.num_hist_chans = self.app.hardware['picoharp'].calc_num_hist_chans() #calculate # of histogram channels
        #: type: ph: PicoHarp300

        if ph.mode == "T2":
            # check every 1/10 of Tacq with limits of 10ms and 50ms
            sleep_time = min((max(0.1*ph.Tacq*1e-3, 0.010), 0.050))
            t0 = time.time()
            
            while not self.interrupt_measurement_called:
                ph.start_measure()
                while not ph.check_done_scanning():
                    if self.interrupt_measurement_called:
                        break
                    nactual_value, _ = ph.read_fifo()
                    
                    # update channel countrates and time array
                    self.count_rate_time_array.append(time.time() - t0) #append time interval in seconds to array
                    self.count_rate_0_array.append(ph.read_count_rate0()) #append new countrate data to array
                    self.count_rate_1_array.append(ph.read_count_rate1())
                    time.sleep(sleep_time)
                
                ph.stop_measure()
                nactual_value, _ = ph.read_fifo()

            save_dict = {
                "ttr_buffer" : ph.tttr_buffer[0:nactual_value]
            }
        
        elif ph.mode == "HIST":
            # check every 1/10 of Tacq with limits of 10ms and 50ms
            sleep_time = min((max(0.1*ph.Tacq*1e-3, 0.010), 0.050))
            t0 = time.time()
            
            while not self.interrupt_measurement_called:
                ph.start_histogram()
                while not ph.check_done_scanning():
                    self.set_progress( 100*(time.time() - t0)/ph_hw.settings['Tacq'] )
                    if self.interrupt_measurement_called:
                        break
                    ph.read_histogram_data()

                    # For G2 HIST mode - update channel countrates and time array
                    self.count_rate_time_array.append(time.time() - t0) #append time interval in seconds to array
                    self.count_rate_0_array.append(ph.read_count_rate0()) #append new countrate data to array
                    self.count_rate_1_array.append(ph.read_count_rate1())
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

        if ph.mode == "HIST":
            self.plotdata.setData(ph.time_array[0:self.num_hist_chans]*1e-3, ph.histogram_data[0:self.num_hist_chans]+1)

        if self.ui.plot_channels_checkBox.isChecked():
            # only update plots id countrate_time_array and count_rate arrays are of 
            # the same length
            # since, time array and count rate array are being updated within 
            # the while loop and in a different thread than plot update, there 
            # are occasionally length mismatches
            # 
            # This is a temp fix - maybe there is an elegant fix but this works 
            if len(self.count_rate_time_array) == len(self.count_rate_0_array):
                self.plot_count_rate_0.plot(
                    np.asarray(self.count_rate_time_array), np.asarray(self.count_rate_0_array),
                    pen="8ecae6"
                )
            
            if len(self.count_rate_time_array) == len(self.count_rate_1_array):
                self.plot_count_rate_1.plot(
                    np.asarray(self.count_rate_time_array), np.asarray(self.count_rate_1_array),
                    pen="8ecae6"
                )

    def save_hist_data(self):
        # TODO - Update save hist data to h5
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
