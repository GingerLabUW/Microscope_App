from HW_PI_PiezoStage.PiezoStage_measurement_liveImage import PiezoStageMeasureLive

class OceanOptics_Scan(PiezoStageMeasureLive):

    name = "OceanOptics_Scan"

    def setup(self):
        PiezoStageMeasureLive.setup(self)

        self.settings.New("intg_time",dtype=int, unit='ms', initial=3, vmin=3)
        self.settings.New('correct_dark_counts', dtype=bool, initial=True)
        self.settings.New("scans_to_avg", dtype=int, initial=1, vmin=1)

    def setup_figure(self):
        PiezoStageMeasureLive.setup_figure(self)

        self.set_details_widget(widget = self.settings.New_UI(include=["intg_time", "correct_dark_counts", "scans_to_avg"]))