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
import ldap                   ## used in check_ldap_group

################################################################################

def ldap_check_group(group_name):
	ldapserver = ldap.initialize('ldaps://nlbldap.soton.ac.uk')
	results = ldapserver.search_s("dc=soton,dc=ac,dc=uk", ldap.SCOPE_SUBTREE,"(cn=" + group_name +")")

	for result in results:
		dn    = result[0]
		attrs = result[1]

		if not dn == None:
			if "member" in attrs:
				return True
						
	return False

def trackitd_connect():
	proxy = Pyro4.Proxy(app.config['TRACKITD_URI'])
	proxy._pyroHmacKey = app.config['TRACKITD_KEY']
	return proxy

################################################################################

def db_connect():
	"""This function connects to the DB via parameters stored in the config file.
	"""
	## Connect to the database instance
	g.db = mysql.connect(app.config['DB_SERV'],app.config['DB_USER'],app.config['DB_PASS'],app.config['DB_NAME'])
	g.db.errorhandler = trackit.errors.db_error_handler

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

@app.before_request
def before_request():
	"""This function is run before the request is handled by Flask. At present it checks
	to make sure a valid CSRF token has been supplied if a POST request is made and 
	connects to the database
	"""
	## Connect to the database
	trackit.core.db_connect()

	## Check CSRF key is valid
	if request.method == "POST":
		## check csrf token is valid
		token = session.get('_csrf_token')


#		try:
#			if '_csrf_token' in session:
#				app.logger.info('CSRF token in session is: ' + token)
#			else:
#				app.logger.info('No token in session')

#			if '_csrf_token' in request.form:
#				app.logger.info('CSRF token presented is: ' + request.form.get('_csrf_token'))
#			else:
#				app.logger.info('No CSRF token in form')

#		except Exception as e:
#			app.logger.error(str(e))

		if not token or token != request.form.get('_csrf_token'):
			if 'username' in session:
				app.logger.warning('CSRF protection alert: %s failed to present a valid POST token',session['username'])
			else:
				app.logger.warning('CSRF protection alert: a non-logged in user failed to present a valid POST token')

			### the user cannot have accidentally triggered this (?)
			### so just throw a 403.
			abort(403)

################################################################################

@app.teardown_request
def teardown_request(exception):
	"""This function closes the DB connection as the app stops.
	"""
	db = getattr(g, 'db', None)
	if db is not None:
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
	
