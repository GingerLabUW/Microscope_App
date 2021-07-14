from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import numpy as np
import pyqtgraph as pg
import os
import time
from datetime import datetime
from HW_Picoharp import helper_funcs

epoch = datetime.utcfromtimestamp(0)

class PicoHarpG2Measure(Measurement):
    name = "picoharp_g2_measure"

    hardware_requirements = ["picoharp"]

    def setup(self):
        self.display_update_period = 0.1 #seconds

        # settings
        self.settings.New("update_period", unit="ms", dtype=int, vmin=1, vmax=100*60*60, initial=1)

        # UI 
        self.ui_filename = sibling_path(__file__,"picoharp_g2_measure.ui")
        self.ui = load_qt_ui_file(self.ui_filename)
        self.ui.setWindowTitle(self.name)

        self.count_rate_0_array = []
        self.count_rate_1_array = []
        self.time_array = []
    
    def setup_figure(self):
        ph_hw = self.picoharp_hw = self.app.hardware['picoharp']

        # conect ui buttons to functions
        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.interrupt_pushButton.clicked.connect(self.interrupt)
        self.ui.save_data_pushButton.clicked.connect(self.save_countrates)
        self.ui.clear_plot_pushButton.clicked.connect(self.clear_plot)

        # connect picoharp settings to widgets in the current measurement panel
        self.settings.update_period.connect_to_widget(self.ui.update_time_doubleSpinBox)
        ph_hw.settings.count_rate0.connect_to_widget(self.ui.ch0_label)
        ph_hw.settings.count_rate1.connect_to_widget(self.ui.ch1_label)
        
        # setup plots
        self.graph_layout = pg.GraphicsLayoutWidget()
        self.plot_count_rate_0 = self.graph_layout.addPlot(
            row=0, col=0, title="Channel 0", labels={"bottom" : "Time (s)"}
            )        
        self.plot_count_rate_1 = self.graph_layout.addPlot(
            row=1, col=0, title="Channel 1", labels={"bottom" : "Time (s)"}
            )

        # set log in y axis
        self.plot_count_rate_0.setLogMode(False, True)
        self.plot_count_rate_1.setLogMode(False, True)

        self.ui.plot_groupBox.layout().addWidget(self.graph_layout)
    
#
#    def unix_time_millis(self, dt):
#        return round((dt - epoch).total_seconds() * 1000.0)
    
    def pre_run(self):
        self.time_array = []
        self.count_rate_0_array = []
        self.count_rate_1_array = []
        self.ph = self.picoharp_hw.picoharp
        self.t0 = time.time()
        
    def run(self):
        intg_time = self.settings["update_period"] #in ms       
        while not self.interrupt_measurement_called:
            self.read_over_intg_time(intg_time, self.ui.ch0_label, self.ui.ch1_label)


            #time.sleep(sleep_time) # TODO double check this in practice

        # save app and hardware settings
        # for lqname,lq in self.app.settings.as_dict().items():
        #     save_dict[lqname] = lq.val
        
        # for hc in self.app.hardware.values():
        #     for lqname,lq in hc.settings.as_dict().items():
        #         save_dict[hc.name + "_" + lqname] = lq.val
        
        # for lqname,lq in self.settings.as_dict().items():
        #     save_dict[self.name +"_"+ lqname] = lq.val    
    def read_over_intg_time(self, intg_time, count0_field, count1_field):

        start_time_ms = helper_funcs.unix_time_millis(datetime.now())
        current_time_ms = start_time_ms
        counts_0 = []
        counts_1 = []
        while current_time_ms - start_time_ms < intg_time:
            counts_0.append(self.ph.read_count_rate0())
            counts_1.append(self.ph.read_count_rate1())
            current_time_ms = helper_funcs.unix_time_millis(datetime.now())
        total_counts_0 = np.sum(counts_0)
        total_counts_1 = np.sum(counts_1)
        try: #if label
            count0_field.setText(f"{total_counts_0}")
            count1_field.setText(f"{total_counts_1}")
        except: #if spinbox
            count0_field.setValue(total_counts_0)
            count1_field.setValue(total_counts_1)
        self.count_rate_0_array.append(total_counts_0)
        self.count_rate_1_array.append(total_counts_1)
        self.time_array.append(time.time() - self.t0) #append time interval in seconds to array
        
    def post_run(self):
        self.save_array = np.array([self.time_array, self.count_rate_0_array, self.count_rate_1_array]).T
        
        # set all coutrate and time arrays to defaults 
        self.time_array = []
        self.count_rate_0_array = []
        self.count_rate_1_array = []
        self.interrupt()
                                    
    def update_display(self):
        # only update plots id time_array and count_rate arrays are of 
        # the same length
        # since, time array and count rate array are being updated within 
        # the while loop and in a different thread than plot update, there 
        # are occasionally length mismatches
        # 
        # This is a temp fix - maybe there is an elegant fix but this works 
        if len(self.time_array) == len(self.count_rate_0_array):
            self.plot_count_rate_0.plot(
                np.asarray(self.time_array), np.asarray(self.count_rate_0_array),
                pen="8ecae6"
            )
        
        if len(self.time_array) == len(self.count_rate_1_array):
            self.plot_count_rate_1.plot(
                np.asarray(self.time_array), np.asarray(self.count_rate_1_array),
                pen="8ecae6"
            )

    def save_countrates(self):
        append = '_countrate_data.txt' #string to append to sample name
        self.check_filename(append)
        np.savetxt(
            self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append,
            self.save_array,
            fmt='%f',
            header="Time (s), Countrate 0, Countrate 1"
        )

    def clear_plot(self):
        self.plot_count_rate_0.clear()
        self.plot_count_rate_1.clear()
        self.time_array = []
        self.count_rate_0_array = []
        self.count_rate_1_array = []
    
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
