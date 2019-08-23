# Microscope_App
Confocal Microscope App

## Requirements
- Python 3.6.8
- scopefoundry
- numpy
- pyqt
- qtpy
- h5py
- pyqtgraph
- pillow
- pyserial
- customplotting
- python seabreeze
- pipython (contact manufacturer to get software)

## Includes
* OceanOptics Spectrum Measurement
    * Plot spectrometer readout over specified integration time
    * Save single spectrum
    * Continuously save spectrum
* OceanOptics PI Piezo Stage Scan
    * Piezo Stage raster scan taking OceanOptics spectrum at each point
    * XY or YX scans
    * Reverse scans
    * Live update of intensity sums
    * Live spectrometer readout
    * Click and export absolute positions
    * Move Piezo Stage to a clicked point
    * Export intensities image
    * Export intensities array
    * Automatically saves scan data in .pkl file
* PicoHarp Countrate Measurement
    * Measure PicoHarp countrate continuously or over specified integration time
    * Export countrate data
* PicoHarp Histogram Measurement
    * Measure PicoHarp histogram continuously or over specified integration time
    * Export histogram data
* PicoHarp PI Piezo Stage Scan
    * Piezo Stage raster scan taking PicoHarp histogram at each point
    * XY or YX scans
    * Reverse scans
    * Live update of intensity sums
    * Live histogram reading
    * Click and export absolute positions
    * Move Piezo Stage to a clicked point
    * Export intensities image
    * Export intensities array
    * Automatically saves data in .pkl file
* PI Piezo Stage Independent Movement
    * Load file containing absolute positions, produced by stage scan selections or manually formatted
    * Move Piezo Stage to each successive point, pausing for the specified sleep time
* PI Piezo Stage Control
    * Simple interface for relative stage movements up, down, left, and right
    * Specify step size for relative movement
* Particle Selection
    * Load camera image and select magnification
    * Assuming stage is centered on the starting point:
        * Select start point and second point, and move stage to second point
        * Click particles on image and export relative positions
* Particle Spectra Measurement
    * Load relative positions of particles from Particle selection
    * Take a spectrum at each particle
    * Automatically saves each spectrum
* Stepper Motor Control
    * Simple interface for relative stepper motor movements up, down, left, and right
    * Specify step size for relative movement
* PicoHarp Avalanche Photodiode Scan
    * APD raster scan taking PicoHarp histogram at each point
    * XY or YX scans
    * Reverse scans
    * Live update of intensity sums
    * Live histogram reading
    * Export intensities image
    * Export intensities array
    * Automatically saves data in .pkl file
    
## Screenshots
### OceanOptics Spectrum Measurement
![OceanOptics Spectrum Measurement](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_oo_measure.png)
### OceanOptics PI Piezo Stage Scan
![OceanOptics PI Piezo Stage Scan](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_pi_oo_scan.png)
### PicoHarp Countrate Measurement
![PicoHarp Countrate Measurement](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_ph_countrate.png)
### PicoHarp Histogram Measurement
![PicoHarp Histogram Measurement](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_ph_hist.png)
### PicoHarp PI Piezo Stage Scan
![PicoHarp PI Piezo Stage Scan](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_pi_ph_scan.png)
### PI Piezo Stage Independent Movement
![PI Piezo Stage Independent Movement](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_pi_movement.png)
### PI Piezo Stage Control
![PI Piezo Stage Control](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_pi_control.png)
### Particle Selection
![Particle Selection](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_particle_selection1.png)
(https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscpoe_App_particle_selection2.png)
### Particle Spectra Measurement
![Particle Spectra Measurement](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_particle_spectra.png)
### Stepper Motor Control
![Stepper Motor Control](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_sm_control.png)
### PicoHarp Avalanche Photodiode Scan
![PicoHarp Avalanche Photodiode Scan](https://github.com/SarthakJariwala/Microscope_App/blob/stepper_motor/Screenshots/Microscope_App_apd_ph_scan.png)

## Installing dependencies from command-line
```
conda install numpy pyqt qtpy h5py pyqtgraph
conda install -c poehlmann python-seabreeze
pip install git+git://github.com/ScopeFoundry/ScopeFoundry.git
pip install pillow pyserial customplotting==0.1.4.dev0
```

## Run instructions
After setup, you can run the application by double-clicking Microscope_app.py.
You can also run it from command-line:
```
python Microscope_app.py
```
