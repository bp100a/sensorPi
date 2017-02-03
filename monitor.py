import sqlite3
import datetime
import time
import tempsensor

dbname = '/home/pi/sensorlog.db'

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

def main():
	LOGGING_THRESHOLD = 10 * 60  # don't let more than 10 minutes elapse without logging

	sampling_interval_seconds = 5  # every 5 seconds (our sampling interval)
	create_log_schema()  # if our table doesn't exist, create it

	sensor_mgr = tempsensor.SensorsMgr(dbname)

	# create our Sensor list managment classes
	sensor_mgr.initialize_sensors()

	sensors = sensor_mgr.find_sensors()
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


if __name__ == "__main__":
	main()

