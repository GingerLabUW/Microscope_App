from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import numpy as np
import time
import pyqtgraph as pg
import os

# TODO h5 save

class PicoHarpCountrateMeasure(Measurement):    
    name = "picoharp_countrate_measure"
    
    hardware_requirements = ['picoharp']
    
    def setup(self):
        self.display_update_period = 0.1 #seconds

        S = self.settings
#         self.stored_histogram_channels = self.add_logged_quantity(
#                                       "stored_histogram_channels", 
#                                      dtype=int, vmin=1, vmax=2**16, initial=2**16)
#         self.stored_histogram_channels.connect_bidir_to_widget(
#                                            self.gui.ui.trpl_live_stored_channels_doubleSpinBox)
        
        S.New('continuous', dtype=bool, initial=False)
        
        # UI 
        self.ui_filename = sibling_path(__file__,"picoharp_countrate_measure.ui")
        self.ui = load_qt_ui_file(self.ui_filename)
        self.ui.setWindowTitle(self.name)

        self.elapsed_time = 0
        self.count_array = [] #array storing countrate data
        self.time_array = [] #array storing time points
        
    def setup_figure(self):
#         self.fig = self.gui.add_figure("picoharp_live", self.gui.ui.picoharp_plot_widget)
#                     
#         self.ax = self.fig.add_subplot(111)
#         self.plotline, = self.ax.semilogy([0,20], [1,65535])
#         self.ax.set_ylim(1e-1,1e5)
#         self.ax.set_xlabel("Time (ns)")
#         self.ax.set_ylabel("Counts")
        
        S = self.settings
        
        # hardware
        ph_hw = self.picoharp_hw = self.app.hardware['picoharp']

        #connect events/settings to ui
        S.progress.connect_bidir_to_widget(self.ui.progressBar)
        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.interrupt_pushButton.clicked.connect(self.interrupt)
        S.continuous.connect_to_widget(self.ui.continuous_checkBox)
        ph_hw.settings.Tacq.connect_bidir_to_widget(self.ui.picoharp_tacq_doubleSpinBox)
        ph_hw.settings.count_rate0.connect_to_widget(self.ui.ch0_label)
        ph_hw.settings.count_rate1.connect_to_widget(self.ui.ch1_label)
        self.ui.save_data_pushButton.clicked.connect(self.save_countrates)
        self.ui.clear_plot_pushButton.clicked.connect(self.clear_plot)
        self.graph_layout = pg.GraphicsLayoutWidget()    
    
        self.plot = self.graph_layout.addPlot()
        self.plot.setLogMode(False, True)
        
        self.ui.plot_groupBox.layout().addWidget(self.graph_layout)
        
    def run(self):
        ph_hw = self.app.hardware['picoharp']
        ph = self.picoharp = ph_hw.picoharp
        #: type: ph: PicoHarp300
        
        #FIXME
        #self.plotline.set_xdata(ph.time_array*1e-3)
#        if not self.settings['continuous']:
#            self.plot.setXRange(0, ph_hw.settings['Tacq'])
#            self.plot.setLimits(xMin=0, xMax=ph_hw.settings['Tacq'])
#            
#        else:
#            self.plot.enableAutoRange()
            #self.plot.setRange(disableAutoRange=False)
            #self.plot.setXLimits(xMin=0, xMax=None)

        sleep_time = self.display_update_period
        
        t0 = time.time()
        
        while not self.interrupt_measurement_called or (self.settings['continuous'] and self.elapsed_time < ph_hw.settings['Tacq']):
            ph.start_histogram()
            while not ph.check_done_scanning():
                self.set_progress( 100*(time.time() - t0)/ph_hw.settings['Tacq'] )
                if not self.settings['continuous']: #if not continuous measure, stop at interrupt or acquisition time has elapsed
                    if self.interrupt_measurement_called or self.elapsed_time > ph_hw.settings['Tacq']:
                        break
                else: 
                    if self.interrupt_measurement_called:
                        break   
                self.count_array.append(ph.read_count_rate1()) #append new countrate data to array
                self.time_array.append(self.elapsed_time) #append time interval to array
                self.elapsed_time += self.display_update_period
                
                time.sleep(sleep_time)
    
            ph.stop_histogram()
            ph.read_histogram_data()

        self.elasped_time = 0
        
        save_dict = {
                     'time_histogram': ph.histogram_data,
                     'time_array': ph.time_array
                    }               

        for lqname,lq in self.app.settings.as_dict().items():
            save_dict[lqname] = lq.val
        
        for hc in self.app.hardware.values():
            for lqname,lq in hc.settings.as_dict().items():
                save_dict[hc.name + "_" + lqname] = lq.val
        
        for lqname,lq in self.settings.as_dict().items():
            save_dict[self.name +"_"+ lqname] = lq.val
        
        if not self.settings['continuous']:
            self.elapsed_time = 0
            self.time_array = []
            self.count_array = []
        self.interrupt()
                               
    def update_display(self):
        ph = self.picoharp
        self.picoharp_hw.read_from_hardware()
        self.plot.plot(np.asarray(self.time_array), np.asarray(self.count_array), pen='r')

    def save_countrates(self):
        cr_data = np.zeros((len(self.time_array), 2))
        cr_data[:,0] = self.time_array #set first column with time data
        cr_data[:,1] = self.count_array #set second column with countrate data
        append = '_countrate_data.txt' #string to append to sample name
        self.check_filename(append)
        np.savetxt(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append, cr_data, fmt='%f')

    def clear_plot(self):
        self.plot.clear()
        self.set_progress(0)
        self.elapsed_time = 0
        self.time_array = []
        self.count_array = []

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