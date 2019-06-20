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

        #Add Measurement components
        from HW_OceanOptics.OceanOptics_measurement import OceanOpticsMeasure
        self.add_measurement(OceanOpticsMeasure(self))
        #from PiezoStage_measurement import PiezoStageMeasure
        #self.add_measurement(PiezoStageMeasure(self))
        from HW_PI_PiezoStage.PiezoStage_measurement_liveImage import PiezoStageMeasureLive
        self.add_measurement(PiezoStageMeasureLive)
        from HW_PI_PiezoStage.OceanOptics_Scan import OceanOptics_Scan
        self.add_measurement(OceanOptics_Scan)
        # show ui
        self.ui.show()
        self.ui.activateWindow()

    def on_close(self): #temp fix for properly closing the additional imageview window
        BaseMicroscopeApp.on_close(self)
        try:
            liveupdate = self.measurements["oceanoptics_scan_liveupdate"]
            liveupdate.imv.close()
        except:
            pass

if __name__ == '__main__':
    import sys
    
    app = MicroscopeApp(sys.argv)
    sys.exit(app.exec_())