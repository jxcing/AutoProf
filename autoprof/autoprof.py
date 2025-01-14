#!/usr/bin/python3

import os
import sys
os.environ['AUTOPROF'] = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.environ['AUTOPROF'])
from Pipeline import Isophote_Pipeline

if __name__ == '__main__':
    assert len(sys.argv) >= 2
    
    config_file = sys.argv[1]

    try:
        if '.log' == sys.argv[2][-4:]:
            logfile = sys.argv[2]
        else:
            logfile = None
    except:
        logfile = None

    PIPELINE = Isophote_Pipeline(loggername = logfile)
    
    PIPELINE.Process_ConfigFile(config_file)
