# Microscope_App
Application for controlling Ginger lab inverted confocal microscope.

## Installing dependencies from command-line
First, create a new conda environment
```bash
conda create -n "microscope-app" python=3.7 -y
conda activate microscope-app
pip install -r requirements.txt
pip install "HW_PI_PiezoStage/PIPython/"
```

## Run instructions from command line
In the newly created conda environment with all the dependencies
```bash
python Microscope_app.py
```
