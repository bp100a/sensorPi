import sqlite3
import datetime
import time
import subprocess

dbname = '/home/pi/sensorlog.db'

# the index into this array becomes the "sensor id" we write
# to the database
sensors = []


# sensors = ["28-0416718527ff",
#          "28-031671cc7fff",
#          "28-0316723093ff"]

# we track the sensors via an integer value we assign to them
# in place of the 15-character serial id to reduce the size
# of the database entries.

class Sensor(object):
	_sensor_id = None
	_serial_id = None
	_active    = False
	_temperature = None
	_dirty_temp  = True

	def __init__(self, serial_id, sensor_id):
		self._sensor_id = sensor_id  # internal index to identify sensor
		self._serial_id = serial_id  # serial number of the sensor, device address
		self._active    = False

	def get_temperature(self, farenheight=False):
		if farenheight and self._temperature != None:
			return (self._temperature * 1.8 + 32.0)
		return self._temperature

	_base_temp = None
	def set_temperature(self, temperature):
		if self._temperature is None:
			self._dirty_temp = True
			self._base_temp = temperature

		# okay, to eliminate the noise we will now require a 0.2C swing
		# to consider it dirty
		if self._temperature is not None:
			delta_temp = abs(temperature - self._base_temp)
			if delta_temp > 0.2:
				self._dirty_temp = True
				self._base_temp = temperature
			else:
				self._dirty_temp = False

		self._temperature  = temperature
		return

	def get_dirty_temp(self):
		return self._dirty_temp

	def read_temperature(self):
		if self._active == False:
			return

		sensor_dev = "/sys/bus/w1/devices/{0}/w1_slave".format(self._serial_id)
		tempfile = open(sensor_dev)
		sensor_text = tempfile.read()
		tempfile.close()
		tempdata = sensor_text.split("\n")[1].split(" ")[9]
		self.set_temperature(float(tempdata[2:]) / 1000)

		return

class SensorsMgr:
	_db_name = ""  # stash our database name here
	_SensorList = []

	def get_sensor_list(self):
		return self._SensorList

	def read_sensors(self):
		for sensor in self._SensorList:
			sensor.read_temperature()
		return

	def __init__(self, db_name):
		self._db_name = db_name
		self._SensorList = []

	def create_sensor_schema(self):
		if self._db_name is None:
			return False

		conn = sqlite3.connect(self._db_name)
		conn.execute(
			"CREATE TABLE IF NOT EXISTS Sensor(sensor_id INTEGER PRIMARY KEY AUTOINCREMENT, [timestamp] TIMESTAMP DEFAULT CURRENT_TIMESTAMP, serial_id TEXT UNIQUE NOT NULL);")
		conn.commit()
		conn.close()

		return True

	# we found a new sensor, write it to the table
	def log_sensor(self, serial_id):
		if self._db_name is None:
			return False

		conn = sqlite3.connect(self._db_name)
		curs = conn.cursor()

		ins_sql = "INSERT INTO Sensor (serial_id) VALUES(?)"
		curs.execute(ins_sql, (serial_id,))
		conn.commit()

		# now read it back to get the sensor ID that was created
		sel_sql = "SELECT sensor_id from Sensor where serial_id = ?"
		curs.execute(sel_sql, (serial_id,))
		row = curs.fetchone()
		if row is None:
			return False

		conn.close()

		sensor_id = row[0]

		# we can now add this to our internal list of sensors
		sensor = Sensor(serial_id, sensor_id)
		sensor._active = True # we are adding a newly found sensor, so activate it
		self._SensorList.append(sensor)

		return True

	# read in all the sensors we know about
	def read_sensors_from_db(self):
		if self._db_name is None:
			return False

		conn = sqlite3.connect(self._db_name)
		curs = conn.cursor()
		sel_sql = "SELECT [timestamp], serial_id, sensor_id from Sensor"
		curs.execute(sel_sql)
		all_rows = curs.fetchall()
		conn.close()

		for row in all_rows:
			serial_id = row[1]
			sensor_id = row[2]
			new_sensor = Sensor(serial_id, sensor_id)
			new_sensor._active = False # not active until we see it in the wild!
			self._SensorList.append(new_sensor)

		return True

	def find_sensors(self):
		# get list of devices
		s = subprocess.check_output('ls /sys/bus/w1/devices/28-*/w1_slave', shell=True).strip()
		# we have something that looks like this:
		#	/sys/bus/w1/devices/28-0416718527ff/w1_slave
		#	/sys/bus/w1/devices/28-031671cc7fff/w1_slave
		# So we need to pull out these lines
		#

		lines = s.split('\n')  # separate the lines
		sensor_addresses = []
		for line in lines:
			sensor_addresses.append(line[20:35])

		return sensor_addresses

	def sensor_in_list(self, serial_id):
		for i in range(len(self._SensorList)):
			sensor = self._SensorList[i]
			if (serial_id == sensor._serial_id):
				return i
		return -1

	def update_sensor_list(self, active_sensors):
		if active_sensors is None:
			return False

		# active_sensors is a list of "serial identifiers"
		for active_sensor in active_sensors:
			pos = self.sensor_in_list(active_sensor)
			if pos < 0:
				self.log_sensor(active_sensor)	# new sensors are activated when written to DB
			else:
				self._SensorList[pos]._active = True # if sensor is present on bus, activate it

		return True

	def initialize_sensors(self):
		self.create_sensor_schema()  # make sure the schema is created
		self.read_sensors_from_db()  # get sensors we know about

		active_sensors = self.find_sensors()	# read sensors from device list
		if active_sensors is None:
			return False

		# okay, we have some sensors, see if any
		# aren't in our current DB list
		self.update_sensor_list(active_sensors)

		# our database should have any new sensors

		return True


# ------------------------------------------------------
def create_log_schema():
	conn = sqlite3.connect(dbname)
	conn.execute("CREATE TABLE IF NOT EXISTS Temperature([timestamp] TIMESTAMP, temp NUMERIC, sensor INTEGER);")
	conn.commit()
	return


# get_temperature()
# =================
# Read the temperature probes and return
# a list of the celsius value(s)
def get_temperature(sensor_mgr):
	temperatures = []
	sensor_mgr.read_sensors()	# read all the sensor data in

	for sensor in sensor_mgr.get_sensor_list():
		if sensor._active == False:		# ignore inactive sensors
			continue
		temp_c = sensor.get_temperature()
		temp_f = ((temp_c * 9.0) / 5.0) + 32.0
		sensor_id = sensor._sensor_id
		temperatures.insert(sensor_id+1, temp_c)
		print '[{0}]{1:.2f}C {2:.2f}F'.format(sensor_id, temp_c, temp_f),

	return temperatures


# log_data()
# ==========
# only writes to the database if the data has changed
# or we are told to "force" a write.

def log_data(sensor_list, force_logging):
	conn = sqlite3.connect(dbname)
	curs = conn.cursor()
	data_logged = False

	# write the list of temperatures passed in
	ins_sql = "INSERT INTO Temperature([timestamp], temp, sensor) VALUES(?,?,?)"
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

	for sensor in sensor_list:
		if sensor._active == False:
			continue

		print '[{0}]{1:.2f}C {2:.2f}F'.format(sensor._sensor_id, sensor.get_temperature(), sensor.get_temperature(True)),

		if sensor.get_dirty_temp() == False and force_logging == False:
			continue

		curs.execute(ins_sql, (timestamp, sensor.get_temperature(), sensor._sensor_id))
		data_logged = True

	conn.commit()
	conn.close()
	return data_logged


# Sleep()
# =======
# There's a lot of processing time in the loop
# (probably the DB connection stuff) that impacts
# the interval of sampling, this will adjust.
#
def Sleep(time_last_sleep, sleep_interval):
	# time_last_sleep is in seconds
	# sleep_interval is a float
	if (time_last_sleep == 0):
		time.sleep(sleep_interval)
		return

	current_time = time.time()
	delta_time = current_time - time_last_sleep
	new_sleep_interval = sleep_interval - delta_time
	if (new_sleep_interval < 0.0):
		time.sleep(sleep_interval)
		return

	time.sleep(new_sleep_interval)
	return


LOGGING_THRESHOLD = 10 * 60  # don't let more than 10 minutes elapse without logging

sampling_interval_seconds = 5  # every 5 seconds (our sampling interval)
create_log_schema()  # if our table doesn't exist, create it

sensor_mgr = SensorsMgr(dbname)

# create our Sensor list managment classes
sensor_mgr.initialize_sensors()

sensors = sensor_mgr.find_sensors()
previous_temperatures = None
last_sleep_time = 0.0
time_last_logging = time.time()
while True:
	sensor_mgr.read_sensors()	# read the temperature probes
	data_logged = log_data(sensor_mgr.get_sensor_list(),
						   (time.time() - time_last_logging) > LOGGING_THRESHOLD)
	if data_logged:
		time_last_logging = time.time()
		print " (logged)"
	else:
		print ""

	Sleep(last_sleep_time, sampling_interval_seconds)
	last_sleep_time = time.time()
