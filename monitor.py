import sqlite3
import datetime
import time
import tempsensor

dbname = '/home/pi/sensorlog.db'

# ------------------------------------------------------
def create_log_schema(db_name):
	conn = sqlite3.connect(db_name)
	conn.execute("CREATE TABLE IF NOT EXISTS Temperature([timestamp] TIMESTAMP, temp NUMERIC, sensor INTEGER);")
	conn.commit()
	conn.close()
	return

# log_data()
# ==========
# only writes to the database if the data has changed
# or we are told to "force" a write.

def log_data(sensor_list, force_logging, db_name):
	conn = sqlite3.connect(db_name)
	curs = conn.cursor()
	data_logged = False

	# write the list of temperatures passed in
	ins_sql = "INSERT INTO Temperature([timestamp], temp, sensor) VALUES(?,?,?)"
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

	for sensor in sensor_list:
		if sensor._active == False:
			continue

		print '[{0}]{1:.2f}C {2:.2f}F'.format(sensor._sensor_id, sensor.get_temperature(), sensor.get_temperature(True)),

		# only write out a temperature to the DB if we *have to*, meaning it has
		# changed or there have been no changes in a long while so we are forcing a write
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
	create_log_schema(dbname)  # if our table doesn't exist, create it

	sensor_mgr = tempsensor.SensorsMgr(dbname)

	# create our Sensor list managment classes
	sensor_mgr.initialize_sensors()

	sensors = sensor_mgr.find_sensors()

	last_sleep_time = 0.0
	time_last_logging = time.time()
	while True:
		sensor_mgr.read_sensors()	# read the temperature probes
		data_logged = log_data(sensor_mgr.get_sensor_list(),
							   (time.time() - time_last_logging) > LOGGING_THRESHOLD, dbname)
		if data_logged:
			time_last_logging = time.time()
			print " (logged)"
		else:
			print ""

		Sleep(last_sleep_time, sampling_interval_seconds)
		last_sleep_time = time.time()


if __name__ == "__main__":
	main()

