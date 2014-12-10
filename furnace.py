#!/usr/bin/env python
import os
import uuid
import cgi
import hashlib
import webapp2 as webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util
from google.appengine.ext import db
from google.appengine.api import users
import datetime
from calendar import timegm
import time

class SettingsEntry(db.Model):
    valid_users_entry = db.ListProperty(str,indexed=False,default=None)
    secret_hash_entry = db.StringProperty()

class TemperatureEntry(db.Model):
    date = db.DateTimeProperty(auto_now_add=True)
    room = db.StringProperty()
    temperature = db.FloatProperty()
    target = db.FloatProperty()
    furnacestate = db.IntegerProperty()
    mode = db.StringProperty()
    outside = db.FloatProperty()
    other = db.FloatProperty()

class DailyTemperatureEntry(db.Model):
    date = db.IntegerProperty()
    temp_entry = db.TextProperty()
    target_entry = db.TextProperty()
    furnace_entry = db.TextProperty()
    room_entry = db.TextProperty()
    mode_entry = db.TextProperty()
    outside_entry = db.TextProperty()

class TargetEntry(db.Model):
    date = db.IntegerProperty()
    target_temperature_entry = db.IntegerProperty()
    target_start_minutes_entry = db.IntegerProperty()
    target_held_minutes_entry = db.IntegerProperty()
    target_executed = db.BooleanProperty()
    default_temperature_entry = db.IntegerProperty()
    default_temperature_mode_entry = db.TextProperty()

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.redirect('http://www.google.com/')

class Temperature(webapp.RequestHandler):
    def post(self):
        secret_hash = db.GqlQuery(
              "SELECT * FROM SettingsEntry LIMIT 1")[0].secret_hash_entry
        temp = str(float(cgi.escape(self.request.get('t'))))
        target = str(float(cgi.escape(self.request.get('g'))))
        furnace = str(cgi.escape(self.request.get('f')))
        room = str(cgi.escape(self.request.get('r')))
        home = str(cgi.escape(self.request.get('h')))
        outside = str(float(cgi.escape(self.request.get('o'))))
        mode = str(cgi.escape(self.request.get('m')))
        strS = str(cgi.escape(self.request.get('s')))
        # secret added since I don't want just anyone to pollute my furnace data
        if hashlib.sha512(strS).hexdigest() == secret_hash:
            rightNow = int(time.time())
            dayAgo = rightNow-86400
            recent_record = DailyTemperatureEntry.gql(
                    "WHERE date > :1 ORDER BY date DESC", dayAgo)
            rightNow = str(rightNow)
            if recent_record.count()!=0: # update entry
                dayObj = recent_record[0]
                dayObj.temp_entry = dayObj.temp_entry + \
                                    '['+rightNow+','+temp+'],'
                dayObj.target_entry = dayObj.target_entry + \
                                    '['+rightNow+','+target+'],'
                dayObj.furnace_entry = dayObj.furnace_entry + \
                                    '['+rightNow+','+furnace+'],'
                dayObj.room_entry = dayObj.room_entry + \
                                    '['+rightNow+','+room+'],'
                dayObj.mode_entry = dayObj.mode_entry + \
                                    '['+rightNow+','+mode+'],'
                dayObj.outside_entry = dayObj.outside_entry + \
                                    '['+rightNow+','+outside+'],'
                dayObj.put()
            else: # create entry
                newEntry = DailyTemperatureEntry(
                      date = int(time.time()),
                      temp_entry = '['+rightNow+','+temp+'],',
                      target_entry = '['+rightNow+','+target+'],',
                      furnace_entry = '['+rightNow+','+furnace+'],',
                      room_entry = '['+rightNow+','+room+'],',
                      mode_entry = '['+rightNow+','+mode+'],',
                      outside_entry = '['+rightNow+','+outside+'],'
                )
                newEntry.put()
            self.response.headers.add_header("X-Raspberry-Pi-Data", temp +','+ \
                                                        target +','+ furnace + \
                                                        ','+ room +','+ mode + \
                                                        ','+ outside)
            the_target = db.GqlQuery(
                  "SELECT * FROM TargetEntry ORDER BY date DESC LIMIT 1")
            template_values = {
                'target' : the_target
            }
            path = os.path.join(os.path.dirname(__file__), 'target.html')
            self.response.write(template.render(path, template_values))
        else:
            self.error(500)

class Submit(webapp.RequestHandler):
    def post(self):
      user = users.get_current_user()
      valid_users = db.GqlQuery(
            "SELECT * FROM SettingsEntry LIMIT 1")[0].valid_users_entry
      if user and user.nickname() in valid_users and \
                self.request.get('target_temperature'):
        self.response.write('<html><head><meta http-equiv="refresh" ' + \
           'content="5; url=https://furnaceathome.appspot.com/t"></head><body>')
        target_temperature = \
            int(cgi.escape(self.request.get('target_temperature')))
        target_start_minutes = \
            int(cgi.escape(self.request.get('target_start_minutes')))
        target_held_minutes = \
            int(cgi.escape(self.request.get('target_held_minutes')))
        errors = 0
        if 0 <= target_temperature <= 22:
            self.response.write( \
              'will set target to %s &deg;C</br>' % target_temperature)
        else:
            self.response.write( \
              'invalid temperature: %s</br></body></html>' % target_temperature)
            errors+=1
        if errors == 0 and 0 <= target_start_minutes <= 120:
            self.response.write( \
              'to be reached in %s minutes</br>' % target_start_minutes)
        else:
            self.response.write( \
              'invalid time span: %s</br></body></html>' % target_start_minutes)
            errors+=1
        if errors == 0 and 5 <= target_held_minutes <= 120:
            self.response.write('for %s minutes' % target_held_minutes)
        else:
            self.response.write( \
              'invalid duration: %s</br></body></html>' % target_held_minutes)
            errors+=1
        if errors == 0:
            self.response.write('</body></html>')
            recent_record = TargetEntry.gql("WHERE date > 0 ORDER BY date DESC")
            if recent_record.count()!=0: #update entry
                targetObj = recent_record[0]
                targetObj.date = timegm(datetime.datetime.now().utctimetuple())
                targetObj.target_temperature_entry = target_temperature
                targetObj.target_start_minutes_entry = target_start_minutes
                targetObj.target_held_minutes_entry = target_held_minutes
                targetObj.target_executed = False
                targetObj.put()
            else: #create entry
                newEntry = TargetEntry(
                    date = int(time.time()),
                    target_temperature_entry = target_temperature,
                    target_start_minutes_entry = target_start_minutes,
                    target_held_minutes_entry = target_held_minutes,
                    target_executed = False
                )
                newEntry.put()
                self.response.headers.add_header("X-Raspberry-Pi-Data",
                      target_temperature + ',' + target_start_minutes + \
                      ',' + target_held_minutes)
      elif user and user.nickname() in valid_users and \
                                    self.request.get('default_temp'):
          default_temperature=int(cgi.escape(self.request.get('default_temp')))
          default_temperature_mode = \
                str(cgi.escape(self.request.get('default_temp_mode')))
          recent_record = TargetEntry.gql("WHERE date > 0 ORDER BY date DESC")
          if recent_record.count()!=0: #update entry
              targetObj = recent_record[0]
              targetObj.default_temperature_entry = default_temperature
              targetObj.default_temperature_mode_entry = default_temperature_mode
              targetObj.put()
          else: #create entry
              newEntry = TargetEntry(
                  default_temperature_entry = default_temperature,
                  default_temperature_mode_entry = default_temperature_mode
              )
              newEntry.put()
              self.response.headers.add_header("X-Raspberry-Pi-Data", ': ',
                     default_temperature +','+ default_temperature_mode)



class ShowTemperature(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        valid_users = db.GqlQuery( \
               "SELECT * FROM SettingsEntry LIMIT 1")[0].valid_users_entry
        if user and user.nickname() in valid_users:
            the_temperature = db.GqlQuery( \
               "SELECT * FROM DailyTemperatureEntry ORDER BY date DESC LIMIT 1")

            template_values = {
                'temperature' : the_temperature,
                'user'        : user.nickname(),
                'logout_url'  : users.create_logout_url('/')
            }

            path = os.path.join(os.path.dirname(__file__), 'temperature.html')
            self.response.out.write(template.render(path, template_values))
        else:
            greeting = ('<a href="%s">Sign in or register</a>.' %
                        users.create_login_url('/t'))
            self.response.out.write('<html><body>%s</body></html>' % greeting)

app = webapp.WSGIApplication([('/', MainHandler),
                              ('/temperature', Temperature),
                              ('/submit', Submit),
                              ('/t', ShowTemperature)
                             ])
