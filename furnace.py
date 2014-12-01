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

valid_users = ['https://www.google.com/accounts/o8/id?id=AItOawn07UaCDuXgTDdKlMJVR1oOzqLtaExkn2A', 'https://www.google.com/accounts/o8/id?id=AItOawk3kRjZB2x5IGTfzRLfXP2_QDdCJfXmm6o']
    
class TemperatureEntry(db.Model):
    date = db.DateTimeProperty(auto_now_add=True)
    room = db.StringProperty()
    temperature = db.FloatProperty()
    target = db.FloatProperty()
    furnacestate = db.IntegerProperty()
    homestate = db.StringProperty()
    outside = db.FloatProperty()
    state = db.TextProperty()
    other = db.FloatProperty()

class DailyTemperatureEntry(db.Model):
    date = db.IntegerProperty()
    temp_entry = db.TextProperty()
    target_entry = db.TextProperty()
    furnace_entry = db.TextProperty()
    room_entry = db.TextProperty()
    home_entry = db.TextProperty()
    outside_entry = db.TextProperty()
    state_entry = db.TextProperty()

class TargetEntry(db.Model):
    date = db.IntegerProperty()
    target_temperature_entry = db.IntegerProperty()
    target_start_minutes_entry = db.IntegerProperty()
    target_held_minutes_entry = db.IntegerProperty()
    target_executed = db.BooleanProperty()
    when_home_temperature_entry = db.IntegerProperty()
    when_away_temperature_entry = db.IntegerProperty()
    when_night_temperature_entry = db.IntegerProperty()
    when_night_away_temperature_entry = db.IntegerProperty()
    when_timer_temperature_entry = db.IntegerProperty()

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.redirect('http://www.google.com/')

class Temperature(webapp.RequestHandler):
    def get(self):
        secretHash = 'd6317c18a9854602486bd6dc2a4e6a1e8a2fd' + \
            '03fec1bba13a26775406caeb8922ce75884d6dadb3a86e' + \
            '959b22850aa8d19bd13e04fc4458183dfd3916d012853'
        temp = str(float(cgi.escape(self.request.get('t'))))
        target = str(float(cgi.escape(self.request.get('g'))))
        furnace = str(cgi.escape(self.request.get('f')))
        room = str(cgi.escape(self.request.get('r')))
        home = str(cgi.escape(self.request.get('h')))
        outside = str(float(cgi.escape(self.request.get('o'))))
        state = str(cgi.escape(self.request.get('h')))
        strS = str(cgi.escape(self.request.get('s')))
        # secret added since I don't want just anyone to pollute my furnace data!
        if hashlib.sha512(strS).hexdigest() == secretHash:
		        rightNow = int(time.time())
		        dayAgo = rightNow-86400
		        recent_record = DailyTemperatureEntry.gql("WHERE date > :1 ORDER BY date DESC",dayAgo)
		        rightNow = str(rightNow)
		        if recent_record.count()!=0: # update entry
		            dayObj = recent_record[0]
		            dayObj.temp_entry = dayObj.temp_entry + '['+rightNow+','+temp+'],'
		            dayObj.target_entry = dayObj.target_entry + '['+rightNow+','+target+'],'
		            dayObj.furnace_entry = dayObj.furnace_entry + '['+rightNow+','+furnace+'],'
		            dayObj.room_entry = dayObj.room_entry + '['+rightNow+','+room+'],'
		            dayObj.home_entry = dayObj.home_entry + '['+rightNow+',"'+home+'"],'
		            dayObj.outside_entry = dayObj.outside_entry + '['+rightNow+','+outside+'],'
                  dayObj.state_entry = dayObj.state_entry + '['+rightNow+',"'+state+'"],'
		            dayObj.put()	
		        else: # create entry
		            newEntry = DailyTemperatureEntry(
			              date = int(time.time()),
			              temp_entry = '['+rightNow+','+temp+'],',
			              target_entry = '['+rightNow+','+target+'],',
			              furnace_entry = '['+rightNow+','+furnace+'],',
			              room_entry = '['+rightNow+','+room+'],',
			              home_entry = '['+rightNow+',"'+home+'"],',
                       state_entry = '['+rightNow+',"'+state+'"],',     
			              outside_entry = '['+rightNow+','+outside+'],'
		            )	
		            newEntry.put()        	
		        self.response.headers.add_header("X-Raspberry-Pi-Data", temp +','+ \
		                                                     target +','+ furnace + \
		                                                     ','+ room +','+ home + \
                                                         ','+ outside, ','+ state)
		        the_target = db.GqlQuery("SELECT * FROM TargetEntry ORDER BY date DESC LIMIT 1")
		        template_values = {
		            'target' : the_target
		        }
		        path = os.path.join(os.path.dirname(__file__), 'target.html')
		        self.response.write(template.render(path, template_values))
        else:
		        self.error(500)

class Submit(webapp.RequestHandler):
    def get(self):
      user = users.get_current_user()
      if user and user.nickname() in valid_users and self.request.get('target_temperature'):
        self.response.write('<html><head><meta http-equiv="refresh" content="5; url=https://furnaceathome.appspot.com/t"></head><body>')
        target_temperature=int(cgi.escape(self.request.get('target_temperature')))
        target_start_minutes=int(cgi.escape(self.request.get('target_start_minutes')))
        target_held_minutes=int(cgi.escape(self.request.get('target_held_minutes')))
        errors = 0
        if 0 <= target_temperature <= 20:
            self.response.write('will set target to %s &deg;C</br>' % target_temperature)
        else:
            self.response.write('invalid temperature: %s</br></body></html>' % target_temperature)
            errors+=1
        if errors == 0 and 0 <= target_start_minutes <= 120:
            self.response.write('to be reached in %s minutes</br>' % target_start_minutes)
        else:
            self.response.write('invalid time span: %s</br></body></html>' % target_start_minutes)
            errors+=1
        if errors == 0 and 5 <= target_held_minutes <= 120:
            self.response.write('for %s minutes' % target_held_minutes)
        else:
            self.response.write('invalid duration: %s</br></body></html>' % target_held_minutes)
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
                self.response.headers.add_header("X-Raspberry-Pi-Data", target_temperature +','+ \
                                                         target_start_minutes +','+ target_held_minutes)
      elif self.request.get('when_home_temp'):
        when_home_temperature=int(cgi.escape(self.request.get('when_home_temp')))
        recent_record = TargetEntry.gql("WHERE date > 0 ORDER BY date DESC")
        if recent_record.count()!=0: #update entry
                targetObj = recent_record[0]
                targetObj.when_home_temperature_entry = when_home_temperature
                targetObj.put()
        else: #create entry
                newEntry = TargetEntry(
                    when_home_temperature_entry = when_home_temperature
                )    
                newEntry.put()        	
                self.response.headers.add_header("X-Raspberry-Pi-Data", ': ', when_home_temperature, ', ', state)



class ShowTemperature(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user and user.nickname() in valid_users:
            the_temperature = db.GqlQuery(
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
