from ScopeFoundry import HardwareComponent
import serial

class StepperMotorHW(HardwareComponent):
	
	def setup(self):
		# Define your hardware settings here.
		# These settings will be displayed in the GUI and auto-saved with data files
		self.name = 'steppermotor'
		self.settings.New('port', dtype=str, choices=[("", ""), ("COM1", "COM1"), ("COM2", "COM2"), ("COM3", "COM3"), ("COM4", "COM4"),
			("COM5", "COM5")], initial="")
		self.settings.New('baudrate', dtype=float, initial=115200)

	def connect(self):
		# Open connection to the device:
		port = self.settings['port']
		baudrate = self.settings['baudrate']
		self.stepper_motor = serial.Serial(port=port, baudrate=baudrate, stopbits=serial.STOPBITS_TWO, write_timeout=2., dsrdtr=True)

		#Connect settings to hardware:
		LQ = self.settings.as_dict()
		LQ["baudrate"].hardware_read_func = self.getBaudrate
		LQ["baudrate"].hardware_set_func = self.setBaudrate

		LQ["port"].hardware_read_func = self.getPort
		LQ["port"].hardware_set_func = self.setPort
	
		#Take an initial sample of the data.
		self.read_from_hardware()
		
	def getBaudrate(self):
		return self.stepper_motor.baudrate

	def setBaudrate(self):
		if hasattr(self, "stepper_motor"):
			self.stepper_motor.baudrate = self.settings["baudrate"]
			self.read_from_hardware()

	def getPort(self):
		return self.stepper_motor.port

	def setPort(self):
		try:
			self.stepper_motor.port = self.settings["port"]
			self.read_from_hardware()
		except:
			pass

	def disconnect(self):
		#Disconnect the device and remove connections from settings
		self.settings.disconnect_all_from_hardware()
		if hasattr(self, 'stepper_motor'):
			self.stepper_motor.close()
			del self.stepper_motor
			self.stepper_motor = None