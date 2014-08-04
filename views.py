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

################################################################################
#### HOME PAGE

@app.route('/')
def default():
	if 'username' in session:
		return redirect(url_for('repo_list'))
	else:
		next = request.args.get('next',default=None)
		return render_template('default.html', next=next)

################################################################################
#### ABOUT 

@app.route('/about')
@trackit.core.login_required
def about():
	return render_template('about.html', active='about')
