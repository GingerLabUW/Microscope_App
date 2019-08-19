import serial
import sys

class APD_StepperMotor(serial.Serial):
	def __init__(self, port, baudrate):
		serial.Serial.__init__(self, port=port, baudrate=baudrate, stopbits=serial.STOPBITS_TWO, write_timeout=2., dsrdtr=True)

	def readAndPrintBuffer(self):
		print('\n' + self.readBuffer() + '\n')
		

	def readBuffer(self):
		c=self.read().decode();
		thisStr='';
		while c is not '$':
			thisStr += c
			c=self.read().decode()
		return thisStr

	def set_port(self, new_port):
		self.port = new_port

	def get_port(self):
		return self.port

	def set_baudrate(self, new_baudrate):
		self.baudrate = new_baudrate

	def get_baudrate(self):
		return self.baudrate

	def get_position(self):
		self.write(b"p")
		position = self.readBuffer().split(",")
		try:
			position = [int(num) for num in position] #convert string to int
		except:
			pass
		return position

	def goto(self, input_array):
		#Check input arguments
		if len(input_array)<3:
			motionType="a"
		else:
			motionType=input_array[2]

		#Build string to send to controller
		strToSend="g" + motionType
		for arg in input_array[0:2]:
			thisNumber=int(round(float(arg)*1000))
			strToSend += str(thisNumber) + ","

		strToSend=strToSend[:-1] + "$"

		#Send string to OpenStage (initiates motion automatically)
		self.write(strToSend.encode()) #encode() converts string to bytes

		#Now block and wait for terminator
		while self.read().decode() is not "$":
			0