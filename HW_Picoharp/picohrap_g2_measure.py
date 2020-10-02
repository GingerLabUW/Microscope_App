from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import numpy as np
import pyqtgraph as pg
import os

class PicoHarpG2Measure(Measurement):
    name = "picoharp_g2_measure"

    hardware_requirements = ["picoharp"]

    def setup(self):
        self.display_update_period = 0.1 #seconds

        # UI 
        # self.ui_filename = sibling_path(__file__,"picoharp_countrate_measure.ui")
        # self.ui = load_qt_ui_file(self.ui_filename)
        # self.ui.setWindowTitle(self.name)

        self.count_rate_0_array = []
        self.count_rate_1_array = []
        self.time_array = []
    
    def setup_figure(self):
        ph_hw = self.picoharp_hw = self.app.hardware['picoharp']

        # connect picoharp settings to widgets in the current measurement panel
        # ph_hw.settings.Tacq.connect_bidir_to_widget(self.ui.picoharp_tacq_doubleSpinBox)
        # ph_hw.settings.count_rate0.connect_to_widget(self.ui.ch0_label)
        # ph_hw.settings.count_rate1.connect_to_widget(self.ui.ch1_label)
        
        # setup plots
        self.graph_layout = pg.GraphicsLayoutWidget()
        self.plot_count_rate_0 = self.graph_layout.addPlot()        
        self.plot_count_rate_1 = self.graph_layout.addPlot()

        # set log in y axis
        self.plot_count_rate_0.setLogMode(False, True)
        self.plot_count_rate_1.setLogMode(False, True)

        # self.ui.plot_groupBox.layout().addWidget(self.graph_layout)
    
    def run(self):
        ph_hw = self.app.hardware['picoharp']
        ph = self.picoharp = ph_hw.picoharp
        
        sleep_time = self.display_update_period
        
        t0 = time.time()
        
        while not self.interrupt_measurement_called:
            self.time_array.append(time.time() - t0) #append time interval in seconds to array
            self.count_rate_0_array.append(ph.read_count_rate0()) #append new countrate data to array
            self.count_rate_1_array.append(ph.read_count_rate1())

            time.sleep(sleep_time) # TODO double check this in practice

        # save app and hardware settings
        # for lqname,lq in self.app.settings.as_dict().items():
        #     save_dict[lqname] = lq.val
        
        # for hc in self.app.hardware.values():
        #     for lqname,lq in hc.settings.as_dict().items():
        #         save_dict[hc.name + "_" + lqname] = lq.val
        
        # for lqname,lq in self.settings.as_dict().items():
        #     save_dict[self.name +"_"+ lqname] = lq.val
        
        # set all coutrate and time arrays to defaults 
        self.time_array = []
        self.count_rate_0_array = []
        self.count_rate_1_array = []
        self.interrupt()
                               
    def update_display(self):
        self.plot_count_rate_0.plot(
            np.asarray(self.time_array), np.asarray(self.count_rate_0_array), pen='r'
        )
        self.plot_count_rate_1.plot(
            np.asarray(self.time_array), np.asarray(self.count_rate_1_array), pen='r'
        )

    # def save_countrates(self):
    #     cr_data = np.zeros((len(self.time_array), 2))
    #     cr_data[:,0] = self.time_array #set first column with time data
    #     cr_data[:,1] = self.count_array #set second column with countrate data
    #     append = '_countrate_data.txt' #string to append to sample name
    #     self.check_filename(append)
    #     np.savetxt(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append, cr_data, fmt='%f')

    # def clear_plot(self):
    #     self.plot.clear()
    #     self.elapsed_time = 0
    #     self.time_array = []
    #     self.count_array = []
