from pipython import GCSDevice
with GCSDevice() as pidevice:
	pidevice.ConnectUSB(serialnum='0')
	print('connected: {}'.format(pidevice.qIDN().strip()))