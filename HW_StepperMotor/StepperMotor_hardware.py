from ScopeFoundry import HardwareComponent
import serial

class StepperMotorHW(HardwareComponent):
	
	def setup(self):
		# Define your hardware settings here.
		# These settings will be displayed in the GUI and auto-saved with data files
		self.name = 'steppermotor'
		self.settings.New('port', dtype=str, choices=[("COM1", "COM1"), ("COM2", "COM2"), ("COM3", "COM3"), ("COM4", "COM4"),
			("COM5", "COM5")], initial="COM5")
		self.settings.New('baudrate', dtype=float, initial=115200)
		# self.settings.New('x_position', dtype=float, unit='um')
		# self.settings.New('y_position', dtype=float, unit='um')
		#self.settings.New('intg_time', dtype=int, unit='ms', initial=3, vmin=3)
		#self.settings.New('correct_dark_counts', dtype=bool, initial=True)

	def connect(self):
		# Open connection to the device:
		port = self.settings['port']
		baudrate = self.settings['baudrate']
		self.stepper_motor = serial.Serial(port=port, baudrate=baudrate, stopbits=serial.STOPBITS_TWO, write_timeout=2., dsrdtr=True)

		##TODO
		#Connect settings to hardware:


	
		#Take an initial sample of the data.
		self.read_from_hardware()
		
	def disconnect(self):
		#Disconnect the device and remove connections from settings
		#self.settings.disconnect_all_from_hardware()
		if hasattr(self, 'stepper_motor'):
			self.stepper_motor.close()
			del self.stepper_motor
			self.stepper_motor = None