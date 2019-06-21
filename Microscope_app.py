from ScopeFoundry import BaseMicroscopeApp

class MicroscopeApp(BaseMicroscopeApp):

    # this is the name of the microscope that ScopeFoundry uses 
    # when storing data
    name = 'microscope'
    
    # You must define a setup function that adds all the 
    #capablities of the microscope and sets default settings
    def setup(self):
    
        #Add Hardware components
        from HW_OceanOptics.OceanOptics_hardware import OceanOpticsHW
        self.add_hardware(OceanOpticsHW(self))
        from HW_PI_PiezoStage.PiezoStage_hardware import PiezoStageHW
        self.add_hardware(PiezoStageHW(self))
        from HW_Picoharp.picoharp import PicoHarpHW
        self.add_hardware(PicoHarpHW(self))

        #Add Measurement components
        from HW_OceanOptics.OceanOptics_measurement import OceanOpticsMeasure
        self.add_measurement(OceanOpticsMeasure(self))
        #from PiezoStage_measurement import PiezoStageMeasure
        #self.add_measurement(PiezoStageMeasure(self))
        from HW_PI_PiezoStage.PiezoStage_Scan import PiezoStage_Scan
        self.add_measurement(PiezoStage_Scan)
        from HW_OceanOptics.OceanOptics_Scan import OceanOptics_Scan
        self.add_measurement(OceanOptics_Scan)

        from HW_Picoharp.picoharp_countrate_measure import PicoHarpCountrateMeasure
        self.add_measurement(PicoHarpCountrateMeasure)
        from HW_Picoharp.picoharp_hist_measure import PicoHarpHistogramMeasure
        self.add_measurement(PicoHarpHistogramMeasure)
        from HW_Picoharp.picoharp_scan import PicoHarp_Scan
        self.add_measurement(PicoHarp_Scan)

        from HW_PI_PiezoStage.PiezoStage_independent_movement import PiezoStageIndependentMovement
        self.add_measurement(PiezoStageIndependentMovement)
        # show ui
        self.ui.show()
        self.ui.activateWindow()

    def on_close(self): #temp fix for properly closing the additional imageview window
        BaseMicroscopeApp.on_close(self)
        try:
            oo_scan = self.measurements["OceanOptics_Scan"]
            oo_scan.imv.close()
            oo_scan.graph_layout.close()
        except:
            pass

if __name__ == '__main__':
    import sys
    
    app = MicroscopeApp(sys.argv)
    sys.exit(app.exec_())