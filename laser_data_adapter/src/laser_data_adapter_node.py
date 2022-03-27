#! /usr/bin/env python
#Ubuntu 16.04, ROS Kinetic, python 2.7
import rospy
import rosbag
from sensor_msgs.msg import LaserScan
import os
from math import pi
from tf2_msgs.msg import TFMessage 
from geometry_msgs.msg import TransformStamped
import tf

###ROS LaserScan message format###
# std_msgs/Header header
  # uint32 seq  --------numerar del 1 al 1695
  # time stamp ------------unix epoch timestamp, 18 digitos sec los primeros 10, nsecs los ultimos 8
        #sec:
        #nsecs:
  # string frame_id -----------name of the TF 'laser_link', tomar launch file o hacer funcion?
# float32 angle_min---------- 2.094395102
# float32 angle_max---------- -2.094395102
# float32 angle_increment-------??   pi/num_scans 0.00460644
# float32 time_increment----------0.0
# float32 scan_time--------0.0
# float32 range_min-------0.06 segun datasheet
# float32 range_max ---- 4m segun datasheet
# float32[] ranges ------valores de la 4a fila hasta el cambio de linea
# float32[] intensities--vacio

#2. Managae files in folder !!!!!! update to get this paths from launchfile
path_laser_logs= "/home/fer/Desktop/catkin_ws/src/ROS_AMCL_Hybrid_Localization/laser_data_adapter/data/alma/1_hokuyo_processed/"
file_laser_tstamps="/home/fer/Desktop/catkin_ws/src/ROS_AMCL_Hybrid_Localization/laser_data_adapter/data/alma/1_hokuyo_processed.txt"
file_odom="/home/fer/Desktop/catkin_ws/src/ROS_AMCL_Hybrid_Localization/laser_data_adapter/data/alma/log_estimated_path.txt"

#3. Get all txt files names in a list
filenames = [ ]
for file in os.listdir(path_laser_logs):
    if file.endswith( '.txt'): 
        filenames.append(file) #append in list all text files located in the given path_laser_logs
        
num_files = len(filenames)
print 'There are', num_files, 'laser txt files in the folder path_laser_logs'
filenames.sort(key=lambda f: int(filter(str.isdigit, f))) #order files names in natural ascending order

#4. Function to populate ROS LaserMsg format with relevant data
def fill_laser_msg(laser_values, num_txt_file, num_readings, t):  
    laser_msg = LaserScan()
    laser_msg.header.seq = num_txt_file
    laser_msg.header.stamp = t
    laser_msg.header.frame_id = '/laser' #transform frame name
    laser_msg.angle_min = -120.0 / 180.0 * pi #120 is min/max range, taken from the datasheet
    laser_msg.angle_max = 120.0 / 180.0 * pi
    laser_msg.angle_increment = pi / num_readings
    laser_msg.time_increment = 0.1/ 360.0
    laser_msg.scan_time = 0.1 #taken from hokuyo laser datasheet
    laser_msg.range_min = 0.06 # taken from hokuyo laser datasheet
    laser_msg.range_max = 4.0 # taken from hokuyo laser datasheet
    laser_msg.ranges = laser_values
    return laser_msg
    
 #5. Function to create TF data for laser frame
def laser_tf_msg(seq, t):
    trans = TransformStamped()
    trans.header.seq = seq
    trans.header.stamp = t
    trans.header.frame_id = '/base_link'
    trans.child_frame_id = '/laser'
    trans.transform.translation.x = 0.205 #laser position in m, taken from dataset paper
    trans.transform.translation.y = 0.0
    trans.transform.translation.z = 0.31
    q = tf.transformations.quaternion_from_euler(0,0,0)
    trans.transform.rotation.x = q[0]
    trans.transform.rotation.y = q[1]
    trans.transform.rotation.z = q[2]
    trans.transform.rotation.w = q[3]
    msg = TFMessage()
    msg.transforms.append(trans)
    return msg
    
#6. Logic to put timestamp data in list format and transform from TTimeStamp format to unix epoch
with open(file_laser_tstamps,'r') as tstamps_file:
    tstamp_file= tstamps_file.readlines()
    #print "The num of lines in the tstamp file is", len(tstamp_file) #first four lines are not relevant just header data
    tstamp_lines = tstamp_file[4:len(tstamp_file)]
    tstamp = []
    for line in tstamp_lines:
        breaking_lines = line.split()
        tstamp.append(breaking_lines[8]) #tstamp data in 8th row
    for item in range(0,len(tstamp)):
        mrpt_tstamp = int(tstamp[item]) #MRPT TTimeStamp format must be converted to ROS compatible timestamps
        ros_secs = (mrpt_tstamp/10000000) - (11644473600) #formulas taken from: http://docs.ros.org/en/jade/api/mrpt_bridge/html/time_8h_source.html#l00027
        ros_nsecs =  (mrpt_tstamp % 10000000) * 100
        tstamp[item]=rospy.Time(ros_secs,ros_nsecs)#turning the timestamp values to timestamp object
        
        
#7. Lo mismo que el paso 6 pero para crear lista con datos de estimated path x,y,theta
with open(file_odom,'r') as odom_file:
    odom_file = odom_file.readlines()
    x = []
    for line in odom_file:
        breaking_lines = line.split()
        x.append(float(breaking_lines[1])) #data in 2nd row and convert str to float
    y = []
    for line in odom_file:
        breaking_lines = line.split()
        y.append(float(breaking_lines[2])) #data in 3 row
    theta = []
    for line in odom_file:
        breaking_lines = line.split()
        theta.append(float(breaking_lines[3])) #data in 4th row


#8.  Open bag file to write data in it 
scenario = "alma" #!!!!! get this data from launch file
bag = rosbag.Bag('laser_data_'+scenario+'.bag', 'w')

#9. Extract  laser data from multiple text files (one text file for each scan with multiple laser readings )
for file in range(num_files):
    with open (path_laser_logs+filenames[file], 'r') as myfile:
        data = myfile.readlines()
        range_values = data[10]
        range_values_list= range_values.split()
        map_r_values = map(float, range_values_list)
        range_values = list(map_r_values)
        num_scans = len(range_values)
        print "There are ", num_scans, "scanner readings in txt file", file
        laser_msg = fill_laser_msg(range_values,file,num_scans, tstamp[file])  #call function to fill laser data
        tf_data = laser_tf_msg(file,tstamp[file])#call function to generate TF laser data
    bag.write("/tf", tf_data, tstamp[file])
    bag.write("/scan", laser_msg, tstamp[file])


bag.close() #export rosbag file to /home/user/.ros 