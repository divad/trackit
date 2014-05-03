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
import trackit.core
import trackit.errors
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
import kerberos
import pwd
import grp
import MySQLdb as mysql

################################################################################
#### HOME PAGE

@app.route('/')
def default():
	if 'username' in session:
		return redirect(url_for('about'))
	else:
		next = request.args.get('next',default=None)
		return render_template('default.html', next=next)

################################################################################
#### ABOUT 

@app.route('/about')
@trackit.core.login_required
def about():
	return render_template('about.html', active='about')

################################################################################
#### LOGIN

@app.route('/login', methods=['GET','POST'])
def login():

	if request.method == 'GET':
		return redirect(url_for('default'))
	else:

		try:
			## Check password with kerberos
			kerberos.checkPassword(request.form['username'], request.form['password'], app.config['KRB5_SERVICE'], app.config['KRB5_DOMAIN'])
		except kerberos.BasicAuthError as e:
			flash('Incorrect username and/or password','alert-danger')
			return redirect(url_for('default'))
		except kerberos.KrbError as e:
			flash('Kerberos Error: ' + e.__str__(),'alert-danger')
			return redirect(url_for('default'))
		except kerberos.GSSError as e:
			flash('GSS Error: ' + e.__str__(),'alert-danger')
			return redirect(url_for('default'))
		except Exception as e:
			trackit.errors.fatal(e)

		## Ensure user is in trackit management group
		#group = grp.getgrnam(app.config['ACCESS_GROUP'])
		#if not request.form['username'] in group.gr_mem:
		#	flash('You must be a member of the Linux group ' + app.config['ACCESS_GROUP'] + ' to use this service','alert-danger')
		#	return redirect(url_for('default'))

		## Set logged in (if we got this far)
		session['logged_in'] = True
		session['username'] = request.form['username']

		## Check if the user selected "Log me out when I close the browser"
		permanent = request.form.get('sec',default="")

		## Set session as permanent or not
		if permanent == 'sec':
			session.permanent = True
		else:
			session.permanent = False

		## Log a successful login
		app.logger.info('User "' + session['username'] + '" logged in from "' + request.remote_addr + '" using ' + request.user_agent.string)

		## determine if "next" variable is set (the URL to be sent to)
		next = request.form.get('next',default=None)

		if next == None:
			return redirect(url_for('about'))
		else:
			return redirect(next)

################################################################################
#### LOGOUT

@app.route('/logout')
@trackit.core.login_required
def logout():
	app.logger.info('User "' + session['username'] + '" logged out from "' + request.remote_addr + '" using ' + request.user_agent.string)

	session.pop('logged_in', None)
	session.pop('username', None)

	flash('You have been logged out. Goodbye.','alert-success')

	return redirect(url_for('default'))
