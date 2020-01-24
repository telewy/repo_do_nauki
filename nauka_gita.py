@@ -0,0 +1,118 @@
#! /usr/bin/python

# a script to pull a list of sensors from the db, read them from
# the one wire bus and store results into the db. New readings are
# archived and median values are stored into a current readings
# table. The table keeps a reading for each 15 minute interval over
# the last 4 hours.
#
# Things to fix:
# should use the scheduler to get consistent read intervals
# need to get constants via db queries
#
# you are welcome to use this at your own risk
# jerry scharf

import psycopg
import ow
import time

activepaths = []
sensors = 
lastread = 
priorread = 
lastmread = 
priormread = 
median = 

sleep_interval = 30
epoch_seconds = 450
median_hold_hours = 4

ow.init('127.0.0.1:2840')
ow.error_level(ow.error_level.fatal)
ow.error_print(ow.error_print.stderr)

conn = psycopg.connect("dbname='hcontrol' user='hcontroller'")
cur = conn.cursor()

while (1):
#    print time.asctime()
    read_count = 0
# start the simultaneaous temperature conversion on all 1-wire sensors
    ow._put('/simultaneous/temperature','1')

# get the list of sensors to read
    SQL = """SELECT id,ow_id FROM ow_sensors WHERE active = 1"""
    cur.execute(SQL)
    rows = cur.fetchall()

#loop through the rows doing reads and stores
    for row in rows:
        update = 0
        owpath = '/%s' % row[1]
        sensorid = int(row[0])

# create a sensor instance if it doesn't exist
        if (not sensors.has_key(owpath)):
            sensors[owpath] = ow.Sensor(owpath)
#           print "new sensor object for %s" % owpath

# read the sensor and store it
        try:
            dummy = sensors[owpath].temperature
        except ow.exUnknownSensor:
#            print 'unknown sensor for %s' % owpath
            continue
        temp = float(dummy)
        SQL = """INSERT INTO ow_sensor_readings (ow_sensor_id,value) VALUES (%d, %f)""" % (sensorid,temp)
        if (temp == 85):
#           print 'reading was 85'
            continue
        read_count +=1
        if (not lastread.has_key(owpath)):
            lastread[owpath] = temp
            priorread[owpath] = temp
            lastmread[owpath] = temp
            priormread[owpath] = temp
            update = 1
        elif (temp != 85 and temp != lastread[owpath] and temp != priorread[owpath]):
            update = 1
        if (update == 1):
            cur.execute(SQL)
# compute the median of the last three readings
        slist = list((temp,lastmread[owpath],priormread[owpath]))
        slist.sort
        median[owpath] = slist[1]
# compute the epoch and see if there is an existing epoch median
        epoch = int(time.time()/epoch_seconds)
        SQL = """SELECT id FROM sensor_medians WHERE epoch = %d AND ow_sensor_id = %d""" % (epoch,sensorid)
        cur.execute(SQL)
        data = cur.fetchone()
        if (data):
            SQL = """UPDATE sensor_medians SET read_at = now() WHERE id = %d""" % data[0]
            cur.execute(SQL)
            SQL = """UPDATE sensor_medians SET value = %s WHERE id = %d""" % (median[owpath],data[0])
        else:
            SQL = """INSERT INTO sensor_medians (ow_sensor_id,epoch,value,read_at) VALUES (%d,%d,%f,now())""" % (sensorid, epoch, median[owpath])
        cur.execute(SQL)

# bump the readings for the next time through
        priormread[owpath] = lastmread[owpath]
        lastmread[owpath] = temp

# save the new data for this sensor to the database
        conn.commit()

# clean up old entries from the medians table
    SQL = """DELETE FROM sensor_medians WHERE read_at < (now() - interval'%d hour')""" % median_hold_hours
    cur.execute(SQL)
    conn.commit()
    print 'sensors read = %d' % read_count

    time.sleep(sleep_interval)
    
# For those who are postgres wizardly, there is a duplicate of the readings table called ow_sensor_reading_archives.
# There is a new feature in postgres 8.2 that allows a copy from table to table with a select to identify the rows.
# This makes a program that pulls data out of the live reading and into the archive easy,
# and keeps the performance on ow_sensor_readings acceptable.    