#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

__author__ = "Kyle Gordon"
__copyright__ = "Copyright (C) Kyle Gordon"

import os
import logging
import signal
import socket
import time
import serial
import sys

import mosquitto
import ConfigParser

# Read the config file
config = ConfigParser.RawConfigParser()
config.read("/etc/mqtt-rfm12b/mqtt-rfm12b.cfg")

# Use ConfigParser to pick out the settings
DEBUG = config.getboolean("global", "debug")
LOGFILE = config.get("global", "logfile")
MQTT_HOST = config.get("global", "mqtt_host")
MQTT_PORT = config.getint("global", "mqtt_port")
MQTT_SUBTOPIC = config.get("global", "MQTT_SUBTOPIC")
MQTT_TOPIC = "/raw/" + socket.getfqdn() + MQTT_SUBTOPIC

client_id = "rfm12b_%d" % os.getpid()
mqttc = mosquitto.Mosquitto(client_id)

LOGFORMAT = '%(asctime)-15s %(message)s'

if DEBUG:
    logging.basicConfig(filename=LOGFILE, level=logging.DEBUG, format=LOGFORMAT)
else:
    logging.basicConfig(filename=LOGFILE, level=logging.INFO, format=LOGFORMAT)

logging.info('Starting mqtt-rfm12b')
logging.info('INFO MODE')
logging.debug('DEBUG MODE')

def cleanup(signum, frame):
     """
     Signal handler to ensure we disconnect cleanly 
     in the event of a SIGTERM or SIGINT.
     """
     logging.info("Disconnecting from broker")
     # FIXME - This status topis too far up the hierarchy.
     mqttc.publish("/status/" + socket.getfqdn() + MQTT_SUBTOPIC, "Offline")
     mqttc.disconnect()
     logging.info("Exiting on signal %d", signum)
     sys.exit(signum)

def connect():
    """
    Connect to the broker, define the callbacks, and subscribe
    """
    result = mqttc.connect(MQTT_HOST, MQTT_PORT, 60, True)
    if result != 0:
        logging.info("Connection failed with error code %s. Retrying", result)
        time.sleep(10)
        connect()

    #define the callbacks
    mqttc.on_message = on_message
    mqttc.on_connect = on_connect
    mqttc.on_disconnect = on_disconnect

    mqttc.subscribe(MQTT_TOPIC, 2)

def open_serial(port,speed):
    """
    Open the serial port
    """
    global ser
    ser = serial.Serial('/dev/ttyUSB0', 57600)

def on_connect(obj, result_code):
     """
     Handle connections (or failures) to the broker.
     """
     ## These return codes are defined at http://mosquitto.org/documentation/python/

     if result_code == 0:
        logging.info("Connected to broker")
        mqttc.publish("/status/" + socket.getfqdn() + MQTT_SUBTOPIC, "Online")
     else:
        if result_code == 1:
            logging.warning("Unacceptable protocol version")
        elif result_code == 2:
            logging.warning("Identifier rejected")
        elif result_code == 3:
            logging.warning("Server unavailable")
        elif result_code == 4:
            logging.warning("Bad username or password")
        elif result_code == 5:
            logging.warning("Not authorised")
        else:
            logging.warning("Something went wrong")
            logging.warning("Return code was %s", result_code)
        cleanup()

def on_disconnect(result_code):
     """
     Handle disconnections from the broker
     """
     if result_code == 0:
        logging.info("Clean disconnection")
     else:
        logging.info("Unexpected disconnection! Reconnecting in 5 seconds")
        logging.debug("Result code: %s", result_code)
        time.sleep(5)
        connect()
        main_loop()

def on_message(msg):
    """
    What to do once we receive a message
    """
    logging.debug("Received: " + msg.topic)
    if msg.topic == "/status" and msg.payload == "status?":
        mqttc.publish("/status/" + socket.getfqdn(), "Online")

def main_loop():
    """
    The main loop in which we stay connected to the broker
    """
    while mqttc.loop() == 0:
        msg = ser.readline()
        items = msg.split()
        try:
            logging.debug("items list is %s", items)
            if (items[0] == "OK"):
                logging.debug("Received a list of " + str(len(items)) + " items from node " + str(items[1]) + ". Checksum " + str(items[len(items)-1]))
                logging.debug(items)
                for pair in range(2,len(items),2):
                    pairone = int(items[pair]) + (int(items[pair+1]) * 256)
                    if (pairone > 32768):
                        pairone = -65536 + pairone
                    pairone = pairone / 100.000
                    mqttc.publish(MQTT_TOPIC + str(pair/2), str(pairone))
        except IndexError:
            logging.info("Caught a null line. Nothing to worry about")

# Use the signal module to handle signals
signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

# Connect to the broker, open the serial port, and enter the main loop
open_serial("/dev/ttyUSB0", 57600)
connect()
main_loop()
