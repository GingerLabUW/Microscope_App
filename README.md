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
- serial
- customplotting
- python seabreeze
- pipython (contact manufacturer to get software)

## Installing dependencies from command-line
```
conda install numpy pyqt qtpy h5py pyqtgraph
conda install -c poehlmann python-seabreeze
pip install git+git://github.com/ScopeFoundry/ScopeFoundry.git
pip install pillow serial customplotting==0.1.4.dev0
```

## Run instructions
After setup, you can run the application by double-clicking Microscope_app.py.
You can also run it from command-line:
```
python Microscope_app.py
```
