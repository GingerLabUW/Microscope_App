#!/usr/bin/python
# -*- coding: utf-8 -*-
"""This example shows how to connect three controllers on a daisy chain."""

from pipython import GCSDevice


# C-863 controller with device ID 3, this is the master device
# E-861 controller with device ID 7
# C-867 controller with device ID 1

def main():
    """Connect three controllers on a daisy chain."""
    with GCSDevice('C-863.11') as c863:
        c863.OpenRS232DaisyChain(comport=1, baudrate=115200)
        # c863.OpenUSBDaisyChain(description='1234567890')
        # c863.OpenTCPIPDaisyChain(ipaddress='192.168.178.42')
        daisychainid = c863.dcid
        c863.ConnectDaisyChainDevice(3, daisychainid)
        with GCSDevice('E-861') as e861:
            e861.ConnectDaisyChainDevice(7, daisychainid)
            with GCSDevice('C-867') as c867:
                c867.ConnectDaisyChainDevice(1, daisychainid)
                print('\n{}:\n{}'.format(c863.GetInterfaceDescription(), c863.qIDN()))
                print('\n{}:\n{}'.format(e861.GetInterfaceDescription(), e861.qIDN()))
                print('\n{}:\n{}'.format(c867.GetInterfaceDescription(), c867.qIDN()))


if __name__ == '__main__':
    # import logging
    # logging.basicConfig(level=logging.DEBUG)
    main()
