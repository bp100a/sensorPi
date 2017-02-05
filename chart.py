#!/usr/bin/python

import sqlite3
import sys
import cgi
import cgitb
import tempsensor

dbname = "/home/pi/sensorlog.db"

def printHTTPheader():
	print "Content-type: text/html\n\n"

def printHTMLHead(title, table, fahrenheit = False):
	print "<head>"
	print "	<title>"
	print title
	print "	</title>"

	print_graph_script(table, fahrenheit)
	print "</head>"
	return



def get_data(interval_hours):
	conn = sqlite3.connect(dbname)
	curs = conn.cursor()

	if interval_hours == None:
		curs.execute("select sensor, [timestamp], [temp] from Temperature ORDER BY [timestamp]")
	else:
		curs.execute("select sensor, [timestamp], [temp] from Temperature where [timestamp] > datetime('now', '-%s hours') ORDER BY [timestamp]" % interval_hours)

	rows = curs.fetchall()
	conn.close()
	return rows

def create_table_all(rows, fahrenheit = False):
	if rows == None:
		return None

	# first see how many sensors logged data
	sensors = []
	output_temps = []
	for row in rows:
		if row[0] not in sensors:
			sensors.append(row[0])
			output_temps.append(row[2])

	# the number of sensors is len(sensors)

	sensor_mgr = tempsensor.SensorsMgr(dbname)
	sensor_mgr.read_sensors_from_db()	# get the list of sensors from the db!

	# Now let's create our composite data table
	current_timestamp = rows[0][1]
	IsFirstRow = True

	# create our header dynamically based on # of sensors found
	chart_table = "['Time'"
	for i in range(len(sensors)):
		sensor = sensor_mgr.get_sensor_by_index(sensors[i])
		serial_id = sensor.get_serial_id()
		chart_table += ",'T[{0}]'".format(serial_id[3:])

	chart_table += "],\n"

	for row in rows:
		idx = sensors.index(row[0])
		temp = float(row[2])
		if fahrenheit == True:
			temp = temp *1.8 + 32.0

		if row[1] == current_timestamp:
			output_temps[idx] = temp   # update temperature from sensor if available
		else: # output info we have accumulated a row's worth of data
			rowstr = "['{0}'".format(current_timestamp)
			for i in range(len(sensors)):
				rowstr += ", {0}".format(output_temps[i])

			rowstr += "]" 
			current_timestamp = row[1]
			output_temps[idx] = temp

			if IsFirstRow == True:
				chart_table += rowstr
				IsFirstRow = False
			else:
				chart_table += ",\n" + rowstr
		
	return chart_table


def print_graph_script(table, fahrenheight = False):

	# create google chart snippet
	chart_code = """
	<script type="text/javascript" src="https://www.google.com/jsapi"></script>
	<script type="text/javascript">
	google.load("visualization", "1", {packages:["corechart"]});
	google.setOnLoadCallback(drawChart);
	function drawChart() {
		var data = google.visualization.arrayToDataTable([%s]);

		var options = { title: 'Temperature(%s)',
                                curveType: 'function',
                                legend:{position: 'bottom',
                                        textStyle:{fontSize: '11'}
                                }
                      };
		var chart = new google.visualization.LineChart(document.getElementById('chart_div'));
		chart.draw(data, options);

		}
		</script>"""

	temp_scale = '\xB0C'
	if fahrenheight == True:
		temp_scale = '\xB0F'

	print chart_code % (table, temp_scale)

	return	

def show_graph():
	print"<h2>Temperature Chart</h2>"
	print '<div id ="chart_div" style="width: 1200px; height: 600px;"></div>'
	return

def show_button(fahrenheit):
	print "<form action=\"chart.py\" method=\"post\">"
	if fahrenheit == True:
		print "<input OnChange='this.form.submit();' type=\"radio\" name=\"temperature\" value=\"celsius\">\xB0Celsius<br>"
		print "<input OnChange='this.form.submit();' type=\"radio\" name=\"temperature\" value=\"fahrenheit\" checked=\"checked\">\xB0Fahrenheit<br>"
	else:
		print "<input OnChange='this.form.submit();' type=\"radio\" name=\"temperature\" value=\"celsius\" checked=\"checked\">\xB0Celsius<br>"
		print "<input OnChange='this.form.submit();' type=\"radio\" name=\"temperature\" value=\"fahrenheit\">\xB0Fahrenheit<br>"

	print "</form>"
	return

def show_stats():
	conn=sqlite3.conn(dbname)
	curs=conn.cursor()

	curs.execute("SELECT [timestamp], max(temp) FROM Temperature")
	rowmax = curs.fetchone()
	rowstrmax = "{0}&nbsp&nbsp{1}C".format(str(rowmax[0]), str(rowmax[1]) )

	print "<hr>"
	print "<h2>Maximum Temperature</h2>"
	print rowstrmax
	print "<hr>"

	conn.close()
	return

def main():
	cgitb.enable()

	form = cgi.FieldStorage()
	fahrenheit = False	# display in celsius
	if form != None:
		value = form.getvalue('temperature')
		if value == 'fahrenheit':
			fahrenheit = True

	records = get_data(None)

	printHTTPheader()

	if len(records) != 0:
		table = create_table_all(records, fahrenheit)
	else:
		print "No data found!"
		return

	# start printing the page
	print "<html>"
	printHTMLHead("Raspberry Pi Temperature logger", table, fahrenheit)

	print "<body>"
	print "<h1>Raspberry Pi Temperature Logger</h1>"
	print "<hr>"
	show_graph()
	show_button(fahrenheit)

	print "</body>"
	print "</html>"
	sys.stdout.flush()

if __name__ == "__main__":
	main()
