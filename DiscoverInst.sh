#!/bin/bash

# Usage: DiscoverInst <exec-file> <regexp>

if [ $# -lt 1 ]
then
    echo "Illegal number of parameters!!!"
    echo "Usage: DiscoverInst <exec-file> [gmon-regexp]"
    exit
fi

rm gmon.*
rm result.*
rm svmfmap.txt
rm cluster.*
rm elb_distance.csv

id=$(ls gmon-0.* | cut -d "." -f2 | sort | head -n 1)
gmon_regexp="gmon-*.$id"

# If the regexp was given by the user
if [ $# -eq 2 ]
then
	gmon_regexp=$2
fi

# Generate the SVM file with functions time difference and function
# call count percentage
echo "### Generate SVM file"
python /home/oaaziz/Source/IncProf/gensvm.py $1 "$gmon_regexp" > gmon.svm
# Generate data file with functions time difference and function
# call count
echo "### Generate Data file"
python /home/oaaziz/Source/IncProf/gendata.py $1 "$gmon_regexp" > gmon.data

# Use the data file to get the most used functions without recording the function call count
echo "### Find most used functions by time"
python /home/oaaziz/Source/IncProf/findmostused.py gmon.data 0 > gmon.small.svm
# Use the data file to get the most used functions with recording the function call count
echo "### Find most used functions by time and count"
python /home/oaaziz/Source/IncProf/findmostused.py gmon.data 1 > gmon.count.svm

#
# cluster using full gmon 
#
echo "### Cluster the full gmon"
python /home/oaaziz/Source/IncProf/cluster.py gmon.svm svmfmap.txt flip > cluster.out
# print the best instrumentation points for bestk
#echo "### Find inst points for full gmon cluster (bestk)"
#python /home/oaaziz/Source/IncProf/findinstr.py cluster.bestk gmon.count.svm svmfmap.txt > result.bestk
# print the best instrumentation points for elbowk
echo "### find inst points for full gmon cluster (elbowk)"
python /home/oaaziz/Source/IncProf/findinstr.py elb_distance.csv gmon.count.svm svmfmap.txt > result.elbowk

#
# cluster using small gmon
#
echo "### Cluster the small gmon"
python /home/oaaziz/Source/IncProf/cluster.py gmon.small.svm svmfmap.txt flip > cluster.small.out
# print the best instrumentation points for bestk
#echo "### Find inst points for full gmon cluster (bestk)"
#python /home/oaaziz/Source/IncProf/findinstr.py cluster.bestk gmon.count.svm svmfmap.txt > result.bestk
# print the best instrumentation points for elbowk
echo "### find inst points for small gmon cluster (elbowk)"
python /home/oaaziz/Source/IncProf/findinstr.py elb_distance.csv gmon.count.svm svmfmap.txt > result.small.elbowk
