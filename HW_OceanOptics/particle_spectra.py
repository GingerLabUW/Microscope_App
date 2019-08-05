from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
from ScopeFoundry import h5_io
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
#from OceanOptics_Measurement import _read_spectrometer, check_filename
from .OceanOptics_measurement import OceanOpticsMeasure
import pyqtgraph as pg
import sys
from pathlib import Path
import numpy as np
import time
import pickle
import os.path

class ParticleSpectra(Measurement):

    def setup(self):
        self.name = 'particle_spectra'
        self.ui_filename = sibling_path(__file__, "particle_spectra.ui")
        
        self.settings.New("intg_time", dtype=int, unit="ms", initial=3, vmin=3)
        self.settings.New("correct_dark_counts", dtype=bool, initial=True)
        self.settings.New("scans_to_avg", dtype=int, initial=1, vmin=1)

        #Load ui file and convert it to a live QWidget of the user interface
        self.ui = load_qt_ui_file(self.ui_filename)

        self.pi_device_hw = self.app.hardware['piezostage']
        self.spec_hw = self.app.hardware['oceanoptics']
        
    def setup_figure(self):
        #set up ui signals
        self.pi_device_hw.settings.x_position.connect_to_widget(self.ui.x_position_label)
        self.pi_device_hw.settings.y_position.connect_to_widget(self.ui.y_position_label)
        self.settings.intg_time.connect_to_widget(self.ui.intg_time_spinBox)
        self.spec_hw.settings.intg_time.connect_to_widget(self.ui.intg_time_spinBox)
        self.settings.correct_dark_counts.connect_to_widget(self.ui.correct_dark_counts_checkBox)
        self.spec_hw.settings.correct_dark_counts.connect_to_widget(self.ui.correct_dark_counts_checkBox)
        self.settings.scans_to_avg.connect_to_widget(self.ui.scans_to_avg_spinBox)
        self.ui.import_pushButton.clicked.connect(self.array_from_file)
        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.interrupt_pushButton.clicked.connect(self.interrupt)
        
        # Set up pyqtgraph graph_layout in the UI
        self.graph_layout=pg.GraphicsLayoutWidget()
        self.ui.plot_groupBox.layout().addWidget(self.graph_layout)

        # # Create PlotItem object (a set of axes)  
        self.plot = self.graph_layout.addPlot(title="Spectrometer Readout Plot")
        self.plot.setLabel('left', 'Intensity', unit='a.u.')
        self.plot.setLabel('bottom', 'Wavelength', unit='nm')
        
        # # Create PlotDataItem object ( a scatter plot on the axes )
        self.optimize_plot_line = self.plot.plot([0])
    
    def array_from_file(self):
        '''
        Prompts the user to select a text file containing the list of relative movements.
        '''
        try:
            fname = QtWidgets.QFileDialog.getOpenFileName(self.ui, 'Open file', os.getcwd(),"*.txt")
            try:
                self.movements_array = np.genfromtxt(fname[0], dtype=None, encoding=None) #convert file contents into np array
                self.ui.textBrowser.append("Successfully imported from " + str(fname[0]))
            except:
                self.ui.textBrowser.append("Error: File containing position array is not formatted correctly.")
        except Exception as err:
            self.ui.textBrowser.append(format(err))
            
    def update_display(self):
        """
        Displays (plots) the wavelengths on x and intensities on y.
        This function runs repeatedly and automatically during the measurement run.
        its update frequency is defined by self.display_update_period
        """
        if hasattr(self, 'spec'):
            self.plot.plot(self.spec.wavelengths(), self.y, pen='r', clear=True)
            pg.QtGui.QApplication.processEvents()

    def run(self):
        """
        Iterates through list of relative movements in given file, taking a spectrometer reading at each point. 
        """
        if not hasattr(self, "movements_array"):
            self.ui.textBrowser.append("Must import text file before running.")
        else:
            self.pi_device = self.pi_device_hw.pi_device
            self.spec = self.spec_hw.spec
            self.axes = self.pi_device.axes[0:2]
            num_points = self.movements_array.shape[0] #get number of rows = number of points
            
            OceanOpticsMeasure.check_filename(self, "_particle_position1.txt") #make sure filename doesn't already exist
            
            #first spectrometer reading before stage movements
            OceanOpticsMeasure._read_spectrometer(self)
            save_array = np.zeros(shape=(2048, 2))
            save_array[:,0] = self.spec.wavelengths()
            save_array[:,1] = self.y                   
            np.savetxt(self.app.settings['save_dir']+"/"+self.app.settings['sample']+ "_particle_position1.txt", save_array, fmt = '%.5f',
                header = 'Wavelength (nm), Intensity (counts)', delimiter = ' ')
        
            for i in range(num_points):
                if self.interrupt_measurement_called:
                    break
                rel_mov = self.movements_array[i]
                self.pi_device.MVR(axes=self.axes, values=[rel_mov[0], rel_mov[1]]) #move stage
                
                #read spectrometer at each point
                OceanOpticsMeasure._read_spectrometer(self)
                save_array = np.zeros(shape=(2048, 2))
                save_array[:,0] = self.spec.wavelengths()
                save_array[:,1] = self.y                   
                np.savetxt(self.app.settings['save_dir']+"/"+self.app.settings['sample']+ "_particle_position" + str(i+2) + ".txt", save_array, fmt = '%.5f',
                    header = 'Wavelength (nm), Intensity (counts)', delimiter = ' ') #save the reading at each position in txt file
                
                self.pi_device_hw.read_from_hardware()
                self.ui.textBrowser.append("Movement #" + str(i+1) + " complete.")