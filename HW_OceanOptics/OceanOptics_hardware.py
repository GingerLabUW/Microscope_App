from ScopeFoundry import HardwareComponent
import seabreeze.spectrometers as sb

class OceanOpticsHW(HardwareComponent):
    
    def setup(self):
        # Define your hardware settings here.
        # These settings will be displayed in the GUI and auto-saved with data files
        self.name = 'oceanoptics'
        self.settings.New('intg_time', dtype=int, unit='ms', initial=3, vmin=3)
        self.settings.New('correct_dark_counts', dtype=bool, initial=True)

    def connect(self):
        # Open connection to the device:
        devices = sb.list_devices()
        self.spec = sb.Spectrometer(devices[0])

        #Connect settings to hardware:
        self.settings.intg_time.connect_to_hardware(
            self.spec.integration_time_micros(self.settings['intg_time']*1000))
    
        #Take an initial sample of the data.
        self.read_from_hardware()
        
    def disconnect(self):
        #Disconnect the device and remove connections from settings
        self.settings.disconnect_all_from_hardware()
        if hasattr(self, 'spec'):
            self.spec.close()
            del self.spec
            self.spec = None