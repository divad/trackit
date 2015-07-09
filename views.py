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
import MySQLdb as mysql

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
	return render_template('about.html', active='help')

################################################################################
#### Suspended page

@app.route('/suspended')
def suspended():
	return render_template('suspended.html')

################################################################################
#### God audit

@app.route('/admin/audit')
@trackit.core.login_required
@trackit.core.admin_required
@trackit.core.db_required
def audit():
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `audit` ORDER BY `utime` DESC')
	log = curd.fetchall()

	for entry in log:
		entry['when'] = trackit.core.ut_to_string(entry['utime'])

	return render_template('audit.html',log=log,active='god')

################################################################################
#### God settings viewer

@app.route('/admin/settings')
@trackit.core.login_required
@trackit.core.admin_required
def settings():
	return render_template('god_settings.html', active='god')

################################################################################
#### God admin page

@app.route('/admin')
@trackit.core.login_required
@trackit.core.admin_required
def admin():
	status = trackit.core.get_system_status()
	return render_template('admin.html', active='god', status=status)
