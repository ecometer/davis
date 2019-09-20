#!/usr/bin/python3
# ----------------------------------------------------------------------
#  Copyright (c) 1995-2018, Ecometer s.n.c.
#  Author: Paolo Saudin.
#
#  Desc : get data from davis meteo station and store it to file
#  File : get_davis_filedata.py
#
#  Date : 2018-05-31
# ----------------------------------------------------------------------
# https://pythonhosted.org/pyserial/index.html
# http://www.tutorialspoint.com/python/index.htm
# https://github.com/banksjh/WeatherLinkPy/blob/master/WeatherLinkPy/WeatherLink.py
# https://github.com/beamerblvd/weatherlink-python
# pip install pyserial

"""
    main template script
"""
# imports
# ----------------------------------------------------------------------
import os
import sys
import platform
import logging
import logging.handlers
import struct
import re
import time
import serial
import datetime
import shutil
"""
pip3 install serial
"""
ser = None

def create_log(logging_level):
    """Create log manager"""
    # path
    logpath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'log')
    if not os.path.exists(logpath):
        os.makedirs(logpath)
    # script name
    file_name = os.path.basename(sys.argv[0])
    # log name
    logdatafile = os.path.join(logpath, file_name + '.log')

    # logging custom level
    logging.addLevelName(logging.VERBOSE, 'VERBOSE')
    logging.getLogger('').setLevel(logging.INFO)
    logging.Logger.verbose = lambda inst, msg, *args, **kwargs: inst.log(logging.VERBOSE, msg, *args, **kwargs)
    logging.verbose = lambda msg, *args, **kwargs: logging.log(logging.VERBOSE, msg, *args, **kwargs)

    # formatter
    formatter = logging.Formatter('%(asctime)s-%(levelname)s: %(message)s')

    # rotation -  max 100 MB
    handler = logging.handlers.RotatingFileHandler(logdatafile, maxBytes=10*1024*1024, backupCount=100)
    handler.setFormatter(formatter)
    logging.getLogger('').addHandler(handler)

    # console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # formatter
    formatter_console = logging.Formatter('%(asctime)s-%(levelname)s: %(message)s')
    #formatter_console = logging.Formatter('%(message)s')
    console.setFormatter(formatter_console)
    logging.getLogger('').addHandler(console)

    # set custom level
    logging.getLogger('').setLevel(logging_level)
    console.setLevel(logging_level)

    # https://docs.python.org/3.4/library/logging.handlers.html?highlight=backupcount
    # CRITICAL 50
    # ERROR    40
    # WARNING  30
    # INFO     20
    # DEBUG    10
    # VERBOSE   5
    # NOTSET    0

def clear_screen():
    """Clear screen"""
    if os.name == "posix":
        # Unix/Linux/MacOS/BSD/etc
        os.system('clear')
    elif os.name in ("nt", "dos", "ce"):
        # DOS/Windows
        os.system('CLS')

def serial_open(cnf):
    global ser
    try:
        if ser is not None:
            if ser.isOpen():
                return True

        logging.debug("Opening serial port")
        #logging.debug(cnf)
        ser = serial.Serial(
            port     = cnf['port'],
            baudrate = cnf['baudrate'],
            parity   = cnf['parity'],
            stopbits = cnf['stopbits'],
            bytesize = cnf['bytesize'],
            timeout  = cnf['timeout']
        )
        # log info
        logging.debug("Serial port %s" % (ser.portstr))
        return ser.isOpen()

    except Exception as e:
        logging.debug("An exception was encountered in serial_open(): %s" % str(e))
        return False

def serial_close():
    global ser
    if ser.isOpen():
        ser.close()
    logging.debug("Serial closed")

def davis_wakeup():
    global ser
    logging.debug("Function probe_davis_wakeup()")
    try:
        # get group values
        for _ in range(3):
            command = "\n"
            ser.write(command.encode())
            ser.flush()

            # timeout 1 seconds from now
            timeout = time.time() + 1
            response = ''
            regexpr = "\n"
            while True:
                buffer_data = ser.read()
                # data check
                if buffer_data:
                    response = response + buffer_data.decode()

                    # analyse data
                    matches = re.match(regexpr, response)
                    if matches:
                        logging.verbose("Response RX[%s]" % str(response))
                        return True

                # timeout check
                if time.time() > timeout:
                    logging.warning("Serial timeout")
                    break

            time.sleep(0.5)

        logging.warning("Serial does not respond")
        return False

    except Exception as e:
        logging.critical("An exception was encountered in probe_davis_wakeup(): %s" % str(e))
        return False

def davis_getdata():
    global ser

    # chars
    LF   = "\n"

    # flush input buffer, discarding all its contents
    logging.debug("Flush serial input")
    ser.flushInput()
    # flush output buffer, aborting current output
    # and discard all that is in buffer
    logging.debug("Flush serial output")
    ser.flushOutput()

    # get recron number 0038
    command = 'LOOP 1' + LF
    logging.debug("Sending serial command TX: %s" % str(command))
    ser.write(command.encode())
    ser.flush()
    time.sleep(1.5)

    logging.debug("Reading data ...")
    # timeout
    timeout = time.time() + 3
    while True:
        #buffer_data = ser.read(1024)
        raw_data = bytearray(ser.read(200))
        # # data check
        # if buffer_data:
        #     response = response + buffer_data.decode()
        #     #response = response + buffer_data.decode('latin1')
        #     #logging.debug("Response: %s" % str(response))

        if len(raw_data) == 100:
            return raw_data
            break

        # timeout check
        if time.time() > timeout:
            logging.debug ("Timeout!")
            return None
            break

        time.sleep(0.1)

    return None

def getdata(cnf):
    # serial port
    if serial_open(cnf):

        if davis_wakeup():
            raw_data = davis_getdata()
            if raw_data != None:
                #logging.debug(raw_data)
                if len(raw_data) == 100:

                    # c = struct.unpack('c', raw_data[0:1])[0]
                    # print(c)

                    # type = struct.unpack('B', raw_data[4:5])[0]
                    # print(type)

                    pressure = struct.unpack('H', raw_data[8:10])[0] / 1000
                    pressure = pressure * 33.864
                    pressure = round(pressure, 2)
                    logging.debug("getting pressure: %s" % pressure)

                    temperature = struct.unpack('H', raw_data[13:15])[0] / 10
                    temperature = (temperature - 32) * 5/9
                    temperature = round(temperature, 2)
                    logging.debug("getting temperature: %s" % temperature)

                    windspeed = struct.unpack('B', raw_data[15:16])[0]
                    windspeed = windspeed / 2.237
                    windspeed = round(windspeed, 2)
                    logging.debug("getting windspeed: %s" % windspeed)

                    winddir = struct.unpack('H', raw_data[17:19])[0]
                    winddir = round(winddir, 2)
                    logging.debug("getting winddir: %s" % winddir)

                    humidity = struct.unpack('B', raw_data[34:35])[0]
                    humidity = round(humidity, 2)
                    logging.debug("getting humidity: %s" % humidity)

                    rain = struct.unpack('H', raw_data[47:49])[0] / 100
                    rain = rain * 25.4
                    rain = round(rain, 2)
                    logging.debug("getting rain: %s" % rain)

                    # build daily filename
                    now = datetime.datetime.now()
                    # application path
                    app_path = os.path.dirname(os.path.realpath(__file__))
                    data_path = os.path.join(app_path, "data")
                    data_path = os.path.join(data_path, now.strftime('%Y%m%d'))
                    if not os.path.exists(data_path):
                        os.mkdir(data_path)
                    archiveFileName = os.path.join(data_path, "davis_"+now.strftime('%Y%m%d-%H%M%S')+".dat")

                    # store to file
                    logging.debug("Saving data to file")
                    with open(archiveFileName, 'a') as temp:
                        temp.write(str(temperature).replace(".", ",") + ";")
                        temp.write(str(humidity).replace(".", ",") + ";")
                        temp.write(str(pressure).replace(".", ",") + ";")
                        temp.write(str(windspeed).replace(".", ",") + ";")
                        temp.write(str(winddir).replace(".", ",") + ";")
                        temp.write(str(rain).replace(".", ","))

                    # copy to OPAS pipe path
                    logging.debug("Copiing to OPAS path")
                    pipePath = "C:/OPAS/pipe"
                    pipeFileName = os.path.join(pipePath, "vantage2pro.csv")
                    try:
                        shutil.copy(archiveFileName, pipeFileName)
                    except (IOError, Exception) as ex:
                        logging.critical("An exception was encountered: %s", str(ex))

                else:
                    logging.warning("Raw data lenght incorrect: %s" % len(raw_data))

            else:
                logging.warning("Raw data not valid")
                time.sleep(5)
        else:
            logging.warning("Instrumento not connected")
            time.sleep(30)
    else:
        logging.warning("Serial NOT Ok")
        time.sleep(30)

def main():
    """Main function"""
    try:
        # Clear
        clear_screen()

        # Logging VERBOSE | DEBUG
        logging.VERBOSE = 5
        create_log(logging.VERBOSE)

        # Start
        now = datetime.datetime.now()
        logging.info("Program start @ %s on %s", now.strftime("%Y-%m-%d %H:%M:%S"), platform.system())

        # Get the connection handler
        cnf = {
            'port'     : 'COM9',
            'baudrate' : 19200, # 9600 19200
            'timeout'  : 0,
            'parity'   : serial.PARITY_NONE,
            'stopbits' : serial.STOPBITS_ONE,
            'bytesize' : serial.EIGHTBITS,
            'timeout'  : 0 # non-blocking mode (return immediately on read)
        }

        while True:
            getdata(cnf)
            time.sleep(5)

    except (IOError, Exception) as ex:
        logging.critical("An exception was encountered: %s", str(ex))


if __name__ == '__main__':
    main()
