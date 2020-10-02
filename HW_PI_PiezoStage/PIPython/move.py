from pipython import GCSDevice
pi_device = GCSDevice()	# Creates a Controller instant
pi_device.ConnectUSB (serialnum='0')# Connect to the controller via USB
pi_device.SVO('1', 1)	# Turn on servo control of axis "1"
pi_device.MOV('1', 0.1)	# Command axis "1" to position 0.1mm
position = pi_device.qPOS('1')
print(position)