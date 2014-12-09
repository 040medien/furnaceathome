#! /usr/bin/env python
import bluetooth
import subprocess
import re
import time
import string
import pywapi
import httplib
import ast
import socket
import ConfigParser
import io
from datetime import datetime, date
from time import mktime
from urllib import urlencode
from urllib2 import Request, urlopen, URLError, HTTPError
from ssl import SSLError
from socket import error as SocketError

class Config:
    """Holds basic settings as well as current state"""
    
    def __init__(self):
        c = ConfigParser.RawConfigParser()
        c.read('.furnace.cfg')
        
        self.bluetooth_addr = c.get('relay', 'bluetooth_addr')
        self.bluetooth_port = c.getint('relay', 'bluetooth_port')
        self.relay_channels = c.getint('relay', 'channels')
        self.primary_furnace = c.getint('relay', 'primary_furnace')
        self.base_url = c.get('url', 'base_url')
        self.secret = c.get('url', 'secret')
        self.zip_code = c.get('house', 'zip_code')
        self.room = c.get('house', 'room')
        self.home_status = ''
        self.mode = ''
        self.last_time_home=0
        self.indoor_temp_target=0
        self.indoor_temp_target_dict={}
        self.default_temp_day=c.getint('default_temp', 'day')
        self.default_temp_night=c.getint('default_temp', 'night')
        self.default_temp_away=c.getint('default_temp', 'away')
        
        presence_devices=c.items('devices')
        presence_devices_wifi=[]
        for device in presence_devices:
            presence_devices_wifi.append(dict(owner=device[0], ip_address=device[1], timestamp=0))
        self.presence_devices_wifi = presence_devices_wifi

    def write(self):
        c = ConfigParser.RawConfigParser()
        c.write('.furnace.cfg')

def ping(ip_address):
    """Determines if a certain IP address is currently used on our network
    (to determine device presence)."""
    try:
        ping = subprocess.Popen(["nmap", "-sP", ip_address], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, error = ping.communicate()
        received = 0
        if out:
            try:
                received=int(re.findall(r"(\d+) host up", out)[0])
            except:
                print "no data for packets received"
        else:
            print 'No ping'
    except subprocess.CalledProcessError:
        print "Couldn't get a ping"
    return received

def getTarget(config, indoor_temp):
    """Defines the target temperature and current operating mode (target temp,
    day default, night default)."""
    now = datetime.now()
    home_status = config.home_status
    indoor_temp_target_dict = config.indoor_temp_target_dict
    print "%s:%s" % (string.zfill(now.hour,2), string.zfill(now.minute,2))
    utimestamp=mktime(datetime.now().utctimetuple())
    default_temp_day = config.default_temp_day
    default_temp_night = config.default_temp_night
    default_temp_away = config.default_temp_away
    default_temp_mode = ''
    config.mode = ''
    try:
        default_temp = indoor_temp_target_dict['default_temperature']
        default_temp_mode = indoor_temp_target_dict['default_temperature_mode']
        target_timestamp = indoor_temp_target_dict['date'] + indoor_temp_target_dict['start_minutes'] * 60
        target_end_timestamp = indoor_temp_target_dict['date'] + indoor_temp_target_dict['start_minutes'] * 60 + indoor_temp_target_dict['held_minutes'] * 60
        if target_end_timestamp > utimestamp:
            time_to_target = int(round((target_timestamp - utimestamp) / 60))
            time_to_end = int(round((target_end_timestamp - utimestamp) / 60))
            if target_timestamp > utimestamp:
                print "we've got a target coming up in %s minutes" % time_to_target
            # we need about 2 minutes per degree Celsius
            if time_to_target <= 0 or time_to_target * 2 <= indoor_temp_target_dict['temperature'] - indoor_temp:
                config.indoor_temp_target = indoor_temp_target_dict['temperature']
                config.mode = 'timer'
                print "setting target to %s degrees Celsius for %s more minutes" % (indoor_temp_target_dict['temperature'], time_to_end)
    except KeyError:
        print "no target set"
    if config.mode != 'timer':
        # TODO: make the time periods configurable in the interface
        if datetime.today().isoweekday() <= 5:
          # Week day
          if home_status=='away':
              config.mode='away'
              if config.mode == default_temp_mode and default_temp != default_temp_away:
                  config.indoor_temp_target = default_temp
                  print "When mode is %s it should be %s degrees Celsius" % (config.mode, default_temp)
                  config.default_temp_away = default_temp
              else:
                  config.indoor_temp_target=default_temp_away
          elif (0 <= now.hour < 7) and home_status=='home':
              config.mode='night'
              if config.mode == default_temp_mode and default_temp != default_temp_night:
                  config.indoor_temp_target = default_temp
                  print "When mode is %s it should be %s degrees Celsius" % (config.mode, default_temp)
                  config.default_temp_night = default_temp
              else:
                  config.indoor_temp_target = default_temp_night
          elif 7 <= now.hour and home_status=='home':
              config.mode='day'
              if config.mode == default_temp_mode and default_temp != default_temp_day:
                  config.indoor_temp_target = default_temp
                  print "When mode is %s it should be %s degrees Celsius" % (config.mode, default_temp)
                  config.default_temp_day = default_temp
              else:
                  config.indoor_temp_target = default_temp_day
        else:
          # Weekend
          if home_status=='away':
              config.mode='away'
              if config.mode == default_temp_mode and default_temp != default_temp_away:
                  config.indoor_temp_target = default_temp
                  print "When mode is %s it should be %s degrees Celsius" % (config.mode, default_temp)
                  config.default_temp_away = default_temp
              else:
                  config.indoor_temp_target=default_temp_away
          elif (0 <= now.hour < 8) and home_status=='home':
              config.mode='night'
              if config.mode == default_temp_mode and default_temp != default_temp_night:
                  config.indoor_temp_target = default_temp
                  print "When mode is %s it should be %s degrees Celsius" % (config.mode, default_temp)
                  config.default_temp_night = default_temp
              else:
                  config.indoor_temp_target = default_temp_night
          elif 8 <= now.hour and home_status=='home':
              config.mode='day'
              if config.mode == default_temp_mode and default_temp != default_temp_day:
                  config.indoor_temp_target = default_temp
                  print "When mode is %s it should be %s degrees Celsius" % (config.mode, default_temp)
                  config.default_temp_day = default_temp
              else:
                  config.indoor_temp_target = default_temp_day
        config.write
    return config

def checkPresence(config):
    """Pings all configured devices to determine who's at home"""
    no_of_users_at_home=0
    last_time_home=config.last_time_home
    now = mktime(datetime.now().utctimetuple())
    for device in config.presence_devices_wifi:
        if device['timestamp'] >= now - 600:
            print "Assuming %s is still at home" % device['owner']
            no_of_users_at_home+=1
    if no_of_users_at_home == 0:
        for device in config.presence_devices_wifi:
            if ping(device['ip_address']) > 0:
                print "%s seems to be at home" % device['owner']
                device['timestamp']=now
                last_time_home=now
                no_of_users_at_home+=1
        if no_of_users_at_home > 0:
            home_status='home'
        else:
            home_status='away'
    else:
        home_status='home'
    return last_time_home, home_status, config.presence_devices_wifi

def btConnection(config, sendchar = 'n', close_after = True):
    """Creates a bluetooth connection to the relay, sends a command and returns
    the result"""
    print("opening Bluetooth connection")
    i = 1
    timed_out = False
    while True:
        try:
            furnace_socket=bluetooth.BluetoothSocket( bluetooth.RFCOMM )
            if furnace_socket.getpeername()[0] != config.bluetooth_addr:
                furnace_socket.connect((config.bluetooth_addr, config.bluetooth_port))
                furnace_socket.settimeout(10)
                print "Bluetooth connected"
            furnace_socket.send(sendchar+'[')
            response_byte = furnace_socket.recv(1)
            break
        except bluetooth.btcommon.BluetoothError as error:
            print(".")
            print error
            time.sleep(1)
            i += 1
            if i >= 30 and sendchar != '':
                timed_out = True
                break
    if close_after:
        print("closing Bluetooth connection")
        furnace_socket.close()
    if not timed_out:
        response_bin = bin(ord(response_byte))[2:].zfill(config.relay_channels)
        response_bit_list = map(int, list(response_bin))
        response_bit_list.reverse()
        return response_bit_list
    else:
        return False

def turnOnFurnace(config, furnace_state, furnace_no):
    """turns on a furnace using the bluetooth relay"""
    channels = config.relay_channels
    if furnace_no <= channels:
        relaychar = chr(101+furnace_no)
    elif furnace_no == channels + 1:
        relaychar = 'd'
    else:
        print("Error: no such furnace!")
        #raise
    furnace_state = btConnection(config, relaychar, close_after=False)
    if furnace_state:
        if furnace_state[furnace_no]:
            print("furnace %s turned on") % furnace_no
        elif sum(furnace_state) == channels:
            print("all furnaces turned on")
        else:
            print("Error: furnace has not been turned on!")
            #raise
    else:
        print("Error: furnace has not been turned on!")
        #raise
    return furnace_state

def turnOffFurnace(config, furnace_state, furnace_no):
    """turns off a furnace using the bluetooth relay"""
    channels = config.relay_channels
    if furnace_no <= channels:
        relaychar = chr(111+furnace_no)
    elif furnace_no == channels + 1:
        relaychar = 'n'
    else:
        print("Error: no such furnace!")
        #raise
    furnace_state = btConnection(config, relaychar, close_after=True)
    if furnace_state[furnace_no]:
        print("Error: furnace has not been turned off!")
        #raise
    elif sum(furnace_state) == 0:
        print("all furnaces turned off")
    else:
        print("furnace %s turned off") % furnace_no
    return furnace_state

def checkOutdoorTemp(zip_code):
    """Gets outdoor temperature for our ZIP code from Yahoo!"""
    try:
        yahoo_com_result = pywapi.get_weather_from_yahoo( zip_code, units = 'metric' )
        outdoor_temperature = int(yahoo_com_result['condition']['temp'])
    except (KeyError, AttributeError, httplib.BadStatusLine):
        outdoor_temperature = 0
    return outdoor_temperature

def checkIndoorTemp():
    """Gets indoor temperature from USB thermometer using command line tool"""
    # repeat forever - temper is very flaky
    while True:
        try:
            indoor_temp = float(subprocess.Popen("/usr/local/bin/temper", stdout=subprocess.PIPE).communicate()[0])
            break
        except ValueError:
            print "Oops! Did not get a temperature. Trying again..."
    return indoor_temp

def transmit(config, outdoor_temp, indoor_temp):
    """Transmits the current state to the server for reporting and gets targets
    set in the web GUI (if any exist)"""

    furnace_state=config.furnace_state
    primary_furnace=config.primary_furnace
    indoor_temp_target_dict={}

    # round up or down to half degrees C
    rounded_indoor_temp = round(indoor_temp*10/5)/2
    print "It is %s degrees Celsius - target is %s (outdoors it's %s degrees Celsius)" % (rounded_indoor_temp, config.indoor_temp_target, outdoor_temp)

    values = { 't' : indoor_temp,
               'g' : config.indoor_temp_target,
               'h' : config.home_status,
               'f' : furnace_state[primary_furnace],
               'r' : config.room,
               's' : config.secret,
               'o' : outdoor_temp,
               'm' : config.mode }
    try:
        data = urlencode(values)
        req = Request(config.base_url, data)
        response = urlopen(req)
        indoor_temp_target_dict = ast.literal_eval(response.read())
    except HTTPError as e:
        print 'The server couldn\'t fulfill the request.'
        print 'Error code: ', e.code
    except URLError as e:
        print 'We failed to reach a server.'
        print 'Reason: ', e.reason
    except SSLError as e:
        print 'We had an SSL error.'
    except SocketError as e:
        print 'Socket error'
    if rounded_indoor_temp < config.indoor_temp_target and furnace_state[ primary_furnace ] == 0:
        print "it is too cold"
        furnace_state = turnOnFurnace(config, furnace_state, primary_furnace)
    elif rounded_indoor_temp >= config.indoor_temp_target and furnace_state[ primary_furnace ] == 1:
        print "it is warm enough"
        furnace_state = turnOffFurnace(config, furnace_state, primary_furnace)
    elif rounded_indoor_temp < config.indoor_temp_target and furnace_state[ primary_furnace ] == 1:
        print "heating up"
    elif rounded_indoor_temp >= config.indoor_temp_target and furnace_state[ primary_furnace ] == 0:    
        print "letting it cool down"
    else:
        print "weird state"
    return furnace_state, indoor_temp_target_dict

def loop():
    """Main part of the client that repeats every 60 seconds""" 
    config = Config()
    config.furnace_state = btConnection(config, 'n', close_after=False)
    while True:
        beforetime = mktime(datetime.now().utctimetuple())
        config.last_time_home, config.home_status, config.presence_devices_wifi = checkPresence(config)
        outdoor_temp=checkOutdoorTemp(config.zip_code)
        indoor_temp=checkIndoorTemp()
        config = getTarget(config, indoor_temp)
        config.furnace_state, config.indoor_temp_target_dict=transmit(config, outdoor_temp, indoor_temp)
        aftertime = mktime(datetime.now().utctimetuple())
        if aftertime - beforetime >= 60:
            sleeptime = 0
        else:
            sleeptime = 60 - (aftertime - beforetime)
        time.sleep(sleeptime)  # Delay the rest of 1 minute (60 seconds)

loop()