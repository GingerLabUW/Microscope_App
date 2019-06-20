from ScopeFoundry import BaseMicroscopeApp

class OceanOpticsApp(BaseMicroscopeApp):

    # this is the name of the microscope that ScopeFoundry uses 
    # when storing data
    name = 'microscope'
    
    # You must define a setup function that adds all the 
    #capablities of the microscope and sets default settings
    def setup(self):
    
        #Add Hardware components
        from OceanOptics_hardware import OceanOpticsHW
        self.add_hardware(OceanOpticsHW(self))
        from PiezoStage_hardware import PiezoStageHW
        self.add_hardware(PiezoStageHW(self))

        #Add Measurement components
        from OceanOptics_measurement import OceanOpticsMeasure
        self.add_measurement(OceanOpticsMeasure(self))
        #from PiezoStage_measurement import PiezoStageMeasure
        #self.add_measurement(PiezoStageMeasure(self))
        from PiezoStage_measurement_liveImage import PiezoStageMeasureLive
        self.add_measurement(PiezoStageMeasureLive)
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
    
    app = OceanOpticsApp(sys.argv)
    sys.exit(app.exec_())