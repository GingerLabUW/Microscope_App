#!/usr/bin/python
# -*- coding: utf-8 -*-
"""This example shows how to realize a cyclic circular motion with the wave generator."""

from time import sleep

from pipython import GCSDevice, pitools

CONTROLLERNAME = 'C-887'
STAGES = None  # set something like ('M-122.2DD', 'M-122.2DD') if your stages need CST
REFMODE = ('FRF',)  # reference first axis or hexapod

NUMPOINTS = 1000  # number of points for one sine period as integer
STARTPOS = (0.0, 0.0)  # start position of the circular motion as float for both axes
AMPLITUDE = (1.0, 1.0)  # amplitude of the circular motion as float for both axes
NUMCYLES = 10  # number of cycles for wave generator output
TABLERATE = 10  # duration of a wave table point in multiples of servo cycle times as integer


def main():
    """Connect controller, setup stages and start wave generator."""
    with GCSDevice(CONTROLLERNAME) as pidevice:
        pidevice.InterfaceSetupDlg(key='sample')
        print('connected: {}'.format(pidevice.qIDN().strip()))
        print('initialize connected stages...')
        pitools.startup(pidevice, stages=STAGES, refmode=REFMODE)
        runwavegen(pidevice)


def runwavegen(pidevice):
    """Configure two wave forms, move to start position and start the wave generators.
    @type pidevice : pipython.gcscommands.GCSCommands
    """
    assert 2 == len(pidevice.axes[:2]), 'this sample requires two connected axes'
    wavegens = (1, 2)
    wavetables = (1, 2)
    print('define sine and cosine waveforms for wave tables {}'.format(wavetables))
    pidevice.WAV_SIN_P(table=wavetables[0], firstpoint=0, numpoints=NUMPOINTS, append='X',
                       center=NUMPOINTS / 2, amplitude=AMPLITUDE[0], offset=STARTPOS[0], seglength=NUMPOINTS)
    pidevice.WAV_SIN_P(table=wavetables[1], firstpoint=NUMPOINTS / 4, numpoints=NUMPOINTS, append='X',
                       center=NUMPOINTS / 2, amplitude=AMPLITUDE[1], offset=STARTPOS[1], seglength=NUMPOINTS)
    pitools.waitonready(pidevice)
    if pidevice.HasWSL():  # you can remove this code block if your controller does not support WSL()
        print('connect wave generators {} to wave tables {}'.format(wavegens, wavetables))
        pidevice.WSL(wavegens, wavetables)
    if pidevice.HasWGC():  # you can remove this code block if your controller does not support WGC()
        print('set wave generators {} to run for {} cycles'.format(wavegens, NUMCYLES))
        pidevice.WGC(wavegens, [NUMCYLES] * len(wavegens))
    if pidevice.HasWTR():  # you can remove this code block if your controller does not support WTR()
        print('set wave table rate to {} for wave generators {}'.format(TABLERATE, wavegens))
        pidevice.WTR(wavegens, [TABLERATE] * len(wavegens), interpol=[0] * len(wavegens))
    startpos = (STARTPOS[0], STARTPOS[1] + AMPLITUDE[1] / 2.0)
    print('move axes {} to their start positions {}'.format(pidevice.axes[:2], startpos))
    pidevice.MOV(pidevice.axes[:2], startpos)
    pitools.waitontarget(pidevice, pidevice.axes[:2])
    print('start wave generators {}'.format(wavegens))
    pidevice.WGO(wavegens, mode=[1] * len(wavegens))
    while any(list(pidevice.IsGeneratorRunning(wavegens).values())):
        print '.',
        sleep(1.0)
    print('\nreset wave generators {}'.format(wavegens))
    pidevice.WGO(wavegens, mode=[0] * len(wavegens))
    print('done')


if __name__ == '__main__':
    # import logging
    # logging.basicConfig(level=logging.DEBUG)
    main()
