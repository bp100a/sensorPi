import sqlite3
import subprocess


# we track the sensors via an integer value we assign to them
# in place of the 15-character serial id to reduce the size
# of the database entries.

class Sensor(object):
	_sensor_id = None
	_serial_id = None
	_active    = False
	_temperature = None
	_dirty_temp  = True
	_base_temp   = None

	def __init__(self, serial_id, sensor_id):
		self._sensor_id = sensor_id  # internal index to identify sensor
		self._serial_id = serial_id  # serial number of the sensor, device address
		self._active    = False
		self._base_temp = None

	def get_temperature(self, farenheight=False):
		if farenheight and self._temperature != None:
			return (self._temperature * 1.8 + 32.0)
		return self._temperature

	def set_temperature(self, temperature):
		if self._active == False:
			return

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

	def get_serial_id(self):
		return self._serial_id

	def get_ensor_id(self):
		return self._sensor_id


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

	def get_sensor_by_index(self, idx):
		for sensor in self._SensorList:
			if sensor._sensor_id == idx:
				return sensor

		return None

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

