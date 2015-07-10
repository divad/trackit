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


from trackit import app
import trackit.errors
from werkzeug.urls import url_encode	
from flask import Flask, g, request, redirect, session, url_for, abort, render_template, flash
from functools import wraps
import random
import base64
import os
import string
import json
import MySQLdb as mysql
import datetime
import re
import Pyro4
import ldap                   ## used in check_ldap_group, auth_user
import os.path
import redis
import requests

################################################################################

def get_system_errlog():
	## Check STATUS File for trackitd errors
	try:
		if os.path.exists(app.config['STATUS_FILE']):
			with open (app.config['STATUS_FILE'], "r") as status_file:
				return status_file.read()

	except Exception as ex:
		return "Could not load error log - " + str(ex)

def get_system_status():
	status = True
	## Check STATUS File for trackitd errors
	try:
		if os.path.exists(app.config['STATUS_FILE']):
			g.trackitd_status = False
			status = False
		else:
			g.trackitd_status = True

	except Exception as ex:
		flash("err " + str(ex),"alert-info")
		g.trackitd_status = False
		status = False

	## check trackitd is running
	try:
		trackitd = trackit.core.trackitd_connect()
		result, error_string = trackitd.ping()
		if result:
			g.trackitd_running = True
		else:
			g.trackitd_running = False
			status = False
	except Exception as ex:
		g.trackitd_running = False
		status = False	

	## check httpd is running
	try:
		req = requests.get("http://localhost",allow_redirects=False)
		g.httpd_status = True
	except Exception as ex:
		g.httpd_status = False
		status = False	

	## check mysql is running
	if g.db:
		try:
			curd = g.db.cursor(mysql.cursors.DictCursor)
			curd.execute('SELECT VERSION()')
			version = curd.fetchone()
			if version:
				g.mysql_status = True
			else:
				g.mysql_status = False
		except Exception as ex:
			g.mysql_status = False

	## check redis is running
	try:
		r = redis.StrictRedis(host='localhost')
		result = r.ping()
		if result == True:
			g.redis_status = True
		else:
			g.redis_status = False
			status = False
	except Exception as ex:
		g.redis_status = False
		status = False

	return status

def ldap_check_group(group_name):
	ldapserver = ldap.initialize(app.config['LDAP_URI'])
	results = ldapserver.search_s(app.config['LDAP_SEARCH_BASE'], ldap.SCOPE_SUBTREE,"(cn=" + group_name +")")

	for result in results:
		dn    = result[0]
		attrs = result[1]

		if not dn == None:
			if "member" in attrs:
				return True
						
	return False

def ldap_check_user_access(username):
	ldapserver = ldap.initialize(app.config['LDAP_URI'])
	results = ldapserver.search_s(app.config['LDAP_SEARCH_BASE'], ldap.SCOPE_SUBTREE,"(" + app.config['LDAP_USER_ATTRIBUTE'] + "=" + username +")")

	for result in results:
		dn    = result[0]
		attrs = result[1]

		if not dn == None:
			if "employeeID" in attrs:
				idnum = attrs['employeeID']
				session['employeeID'] = idnum[0]
				if idnum[0].startswith("1") or idnum[0].startswith("2"):
					return True
				else:
					return False
	return None

def trackitd_connect():
	proxy = Pyro4.Proxy(app.config['TRACKITD_URI'])
	proxy._pyroHmacKey = app.config['TRACKITD_KEY']
	return proxy

################################################################################

def db_connect():
	"""This function connects to the DB via parameters stored in the config file.
	"""
	## Connect to the database instance
	try:
		g.db = mysql.connect(app.config['DB_SERV'],app.config['DB_USER'],app.config['DB_PASS'],app.config['DB_NAME'])
		g.db.errorhandler = trackit.errors.db_error_handler
	except Exception as ex:
		g.db_error = str(ex)
		g.db = False

################################################################################

def db_required(f):
	"""This is a decorator function that when called ensures the view function can access the database, otherwise it shows an error.
	Usage is as such: @bargate.core.login_required
	"""
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if g.db == False:
			trackit.errors.halt("Could not connect to the database","Forge was unable to connect to the database: " + g.db_error)
		return f(*args, **kwargs)
	return decorated_function

################################################################################

def login_required(f):
	"""This is a decorator function that when called ensures the user has logged in.
	Usage is as such: @bargate.core.login_required
	"""
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if session.get('logged_in',False) is False:
			flash('You must login first','alert-danger')
			session['next_url'] = request.url
			return redirect(url_for('default'))
		return f(*args, **kwargs)
	return decorated_function

################################################################################

def admin_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if session.get('admin',False) is False:
			flash('You must be logged in as an administrator to do that!','alert-danger')
			return redirect(url_for('repo_list'))
		return f(*args, **kwargs)
	return decorated_function
	
################################################################################

@app.before_request
def before_request():
	"""This function is run before the request is handled by Flask. At present it checks
	to make sure a valid CSRF token has been supplied if a POST request is made and 
	connects to the database
	"""
	## Connect to the database
	trackit.core.db_connect()

	## Check if error status file is present
	if request.method == "GET":
		if 'STATUS_FILE' in app.config:
			if os.path.exists(app.config['STATUS_FILE']):
				g.status_error = True

	## Check CSRF key is valid
	if request.method == "POST":
		## check csrf token is valid
		token = session.get('_csrf_token')

		if not token or token != request.form.get('_csrf_token'):
			if 'username' in session:
				app.logger.warning('CSRF protection alert: %s failed to present a valid POST token',session['username'])
			else:
				app.logger.warning('CSRF protection alert: a non-logged in user failed to present a valid POST token')

			abort(403)

################################################################################

@app.teardown_request
def teardown_request(exception):
	"""This function closes the DB connection as the app stops.
	"""
	db = getattr(g, 'db', False)
	if db:
		db.close()

################################################################################

def generate_csrf_token():
	"""This function is used in __init__.py to generate a CSRF token for use
	in templates.
	"""

	if '_csrf_token' not in session:
		session['_csrf_token'] = pwgen(32)
	return session['_csrf_token']

################################################################################

def pwgen(length=16):
	"""This is very crude password generator.
	"""

	urandom = random.SystemRandom()
	alphabet = string.ascii_letters + string.digits
	return str().join(urandom.choice(alphabet) for _ in range(length))

################################################################################

def ut_to_string(ut):
	"""Converts unix time to a formatted string for human consumption
	Used by smb.py for turning fstat results into human readable dates.
	"""
	return datetime.datetime.fromtimestamp(int(ut)).strftime('%Y-%m-%d %H:%M:%S %Z')
	
################################################################################

def audit_event(username,module,event,module_id,desc):

	event = module + "." + event

	cur = g.db.cursor()
	cur.execute('''INSERT INTO `audit` 
	(`utime`, `username`, `module`, `event`, `module_id`, `desc`) 
	VALUES (UNIX_TIMESTAMP(), %s, %s, %s, %s, %s)''', (username, module, event, module_id, desc))
	
	g.db.commit()

