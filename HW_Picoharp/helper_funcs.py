# -*- coding: utf-8 -*-
"""
Created on Tue Jul 13 16:48:46 2021

@author: Microscope
"""
from datetime import datetime

epoch = datetime.utcfromtimestamp(0)

def unix_time_millis(dt):
    return round((dt - epoch).total_seconds() * 1000.0)