from ScopeFoundry import HardwareComponent
from .StepperMotor import StepperMotor
import serial
import sys
class StepperMotorHW(HardwareComponent):
	
	def setup(self):
		# Define your hardware settings here.
		# These settings will be displayed in the GUI and auto-saved with data files
		self.name = "steppermotor"
		self.settings.New("port", dtype=str, choices=[("", ""), ("COM1", "COM1"), ("COM2", "COM2"), ("COM3", "COM3"), ("COM4", "COM4"),
			("COM5", "COM5")], initial="COM5")
		self.settings.New("baudrate", dtype=float, initial=115200)

		self.settings.New("x_position", dtype=float, initial=0, unit="um")
		self.settings.New("y_position", dtype=float, initial=0, unit="um")

		self.settings.New("x_abs", dtype=float, initial=0, unit="um")
		self.settings.New("y_abs", dtype=float, initial=0, unit="um")
		self.add_operation("absolute_movement", self.abs_mov)
		
		self.settings.New("x_rel", dtype=float, initial=0, unit="um")
		self.settings.New("y_rel", dtype=float, initial=0, unit="um")
		self.add_operation("relative_movement", self.rel_mov)

		self.settings.New("new_port", dtype=str, choices=[("COM1", "COM1"), ("COM2", "COM2"), ("COM3", "COM3"), ("COM4", "COM4"),
			("COM5", "COM5")], initial="COM1")
		self.add_operation("set_port", self.set_port)
		self.settings.New("new_baudrate", dtype=float)
		self.add_operation("set_baudrate", self.set_baudrate)

	def connect(self):
		# Open connection to the device:
		port = self.settings["port"]
		baudrate = self.settings["baudrate"]
		sm = self.stepper_motor = StepperMotor(port, baudrate)

		#Connect settings to hardware:
		LQ = self.settings.as_dict()
		LQ["x_position"].hardware_read_func = lambda sm=sm: sm.get_position()[0]
		LQ["y_position"].hardware_read_func = lambda sm=sm: sm.get_position()[1]
		LQ["port"].hardware_read_func = lambda sm=sm: sm.get_port()
		LQ["baudrate"].hardware_read_func = lambda sm=sm: sm.get_baudrate()

		self.read_from_hardware()

	def set_port(self):
		self.stepper_motor.port = self.settings["new_port"]
		self.settings.port.read_from_hardware()

	def set_baudrate(self):
		self.stepper_motor.baudrate = self.settings["new_baudrate"]
		self.settings.baudrate.read_from_hardware()

	def abs_mov(self):
		if hasattr(self, "stepper_motor"):
			x_abs_pos = self.settings["x_abs"]
			y_abs_pos = self.settings["y_abs"]
			self.stepper_motor.goto([x_abs_pos, y_abs_pos])
			self.settings.x_position.read_from_hardware()
			self.settings.y_position.read_from_hardware()

	def rel_mov(self):
		if hasattr(self, "stepper_motor"):
			x_rel_pos = self.settings["x_rel"]
			y_rel_pos = self.settings["y_rel"]
			self.stepper_motor.goto([x_rel_pos, y_rel_pos, "r"])
			self.settings.x_position.read_from_hardware()
			self.settings.y_position.read_from_hardware()
	
	def disconnect(self):
		#Disconnect the device and remove connections from settings
		self.settings.disconnect_all_from_hardware()
		if hasattr(self, "stepper_motor"):
			self.stepper_motor.close()
			del self.stepper_motor
			self.stepper_motor = None