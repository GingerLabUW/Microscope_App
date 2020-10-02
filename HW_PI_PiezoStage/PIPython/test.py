from pipython import GCSDevice
gcs = GCSDevice('E-727')
gcs.InterfaceSetupDlg()
print(gcs.qIDN())
gcs.CloseConnection()