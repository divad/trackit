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
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
import traceback

def debug_error(msg):
	return output_error("Debug Message",msg,"Debug")

def output_error(title,message,errstr):
	return render_template('error.html',error=errstr,title=title, message=message), 200

def halt(title,message):
	"""Call this when you want to halt processing the request and you want trackit to stop
	executing further. This function will abort with a 500 HTTP error and will
	display the message and title passed to it.
	"""
	g.fault_title = title
	g.fault_message = message
	abort(500)

#### Generic fatal error
def fatal(ex):
	"""Call this when a fatal exception has occured and you want trackit to stop
	executing further. This function will abort with a 500 HTTP error and will
	display a message about the 'ex' exception passed to it.
	"""
	g.fault_message = "An unexpected error occured. The error was of type " + str(type(ex)) + " and the message was: " + ex.__str__()
	abort(500)

#### Database error
def db_error_handler(connection, cursor=None, errorclass=None,errorvalue=None):
	g.fault_title = "Database Error"
	g.fault_message = "A fault occured whilst communicating with the database: " + str(errorclass)
	abort(500)

################################################################################
#### Flask error handlers - captures "abort" calls from within flask and our code

@app.errorhandler(500)
def error500(error):
	"""Handles abort(500) calls in code.
	"""
	if not hasattr(g, 'fault_message'):
			g.fault_message = "An unexpected error occured. The error was of type " + str(type(error)) + " and the message was: " + error.__str__()
	if not hasattr(g, 'fault_title'):
		g.fault_title = "Sorry, something went wrong!"


	if 'username' in session:
		usr = session['username']
	else:
		usr = 'Not logged in'

	## send a log aobut this as flask doesn't seem to catch it?
	app.logger.error("""trackit 500 handler called.

Title:                %s
Message:              %s
HTTP Path:            %s
HTTP Method:          %s
Client IP Address:    %s
User Agent:           %s
User Platform:        %s
User Browser:         %s
User Browser Version: %s
Username:             %s

""" % (
			g.fault_title,
			g.fault_message,
			request.path,
			request.method,
			request.remote_addr,
			request.user_agent.string,
			request.user_agent.platform,
			request.user_agent.browser,
			request.user_agent.version,
			usr,
			
		))

	debug = traceback.format_exc()
	return render_template('error.html',error=error,title=g.fault_title,message=g.fault_message,debug=debug), 500

@app.errorhandler(400)
def error400(error):
	"""Handles abort(400) calls in code.
	"""
	debug = traceback.format_exc()
	return render_template('error.html',error=error,title="Bad Request",message='Your request was invalid, please try again.',debug=debug), 400

@app.errorhandler(403)
def error403(error):
	"""Handles abort(403) calls in code.
	"""
	return render_template('error.html',error=error,title="Permission Denied",message='You do not have permission to access this resource.'), 403

@app.errorhandler(404)
def error404(error):
	"""Handles abort(404) calls in code.
	"""
	return render_template('error.html',error=error,title="Not found",message="Sorry, I couldn't find what you were after."), 404

@app.errorhandler(405)
def error405(error):
	"""Handles abort(405) calls in code.
	"""
	return render_template('error.html',error=error,title="Not allowed",message="Method not allowed. This usually happens when your browser sent a POST rather than a GET, or vice versa"), 405
