#!/usr/bin/python
#
# This file is part of trackit.
#
# trackit is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# trackit is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with trackit.  If not, see <http://www.gnu.org/licenses/>.

import imp
import syslog
import hashlib
import redis

TRACKIT_CONFIG_FILE = '/data/trackit/trackit.conf'

def load_config():
	d = imp.new_module('config')
	d.__file__ = TRACKIT_CONFIG_FILE
	try:
		with open(TRACKIT_CONFIG_FILE) as config_file:
			exec(compile(config_file.read(), TRACKIT_CONFIG_FILE, 'exec'), d.__dict__)
	except IOError as e:
		print 'Unable to load configuration file (%s)' % e.strerror
		sys.exit(1)
	config = {}
	for key in dir(d):
		if key.isupper():
			config[key] = getattr(d, key)
			
	return config

def check_password(environ, username, password):
	enc_password = hashlib.sha512(password).hexdigest()

	## We use REDIS password caching for both to reduce having to hit
	## kerberos (AD) (dog slow!) or MySQL (which has a cache, but redis is in memory)

	try:
		r = redis.StrictRedis(host='localhost', port=6379, db=0)
		use_redis = True
	except Exception as ex:
		syslog.openlog("trackit-auth",syslog.LOG_PID)
		syslog.syslog('ERROR could not connect to REDIS: ' + str(ex))	
		use_redis = False

	if use_redis:
		try:		
			cached_password = r.get('user' + ':' + username + ':cached_password')
			cached_alt_password  = r.get('user' + ':' + username + ':cached_alt_password')

			## Check the cache for the main password
			if not cached_password == None:
				## redis cache exists
				if cached_password == enc_password:
					return True

			## Try the alt password cache instead
			if not cached_alt_password == None:
				if cached_alt_password == enc_password:
					return True
				else:
					return False
			

		except Exception as ex:
			syslog.openlog("trackit-auth",syslog.LOG_PID)
			syslog.syslog('check_password redis get call failed! - ' + str(ex))

	## If we got here then redis didnt' have a password cache for this user
	config = load_config()

	try:
		import kerberos
		kerberos.checkPassword(username, password, config['KRB5_SERVICE'], config['KRB5_DOMAIN'])
		result = True
		
	except Exception:
		result = False

	if result:
		if use_redis:
			try:
				encrypted_password = hashlib.sha512(password).hexdigest()
				r.setex('user' + ':' + username + ':cached_password', 300, encrypted_password)
			except Exception as ex:
				syslog.openlog("trackit-auth",syslog.LOG_PID)
				syslog.syslog('check_password redis set call failed! - ' + str(ex))

		return True
	else:
		import MySQLdb as mysql
		db = mysql.connect(config['DB_SERV'],config['DB_USER'],config['DB_PASS'],config['DB_NAME'])
		curd = db.cursor(mysql.cursors.DictCursor)
	
		curd.execute('SELECT * FROM `alt_passwords` WHERE `username` = %s',(username))
		user = curd.fetchone()

		if user == None:
			return False
		else:
			if password == user['password']:

				if use_redis:
					try:
						encrypted_password = hashlib.sha512(password).hexdigest()
						r.setex('user' + ':' + username + ':cached_alt_password', 300, encrypted_password)
					except Exception as ex:
						syslog.openlog("trackit-auth",syslog.LOG_PID)
						syslog.syslog('check_password redis set call failed! - ' + str(ex))

				return True

	return False
