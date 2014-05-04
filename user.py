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

		## mark the user as an admin if they are in the admins group
		group = grp.getgrnam(app.config['ADMIN_GROUP'])
		if session['username'] in group.gr_mem:
			session['admin'] = True
		else:
			session['admin'] = False

		## determine if "next" variable is set (the URL to be sent to)
		if 'next_url' in session:
			if session['next_url'] != None:
				return redirect(session['next_url'])

		return redirect(url_for('about'))

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
