#!/bin/bash

# Usage: script <exec-file> <regexp>

# Please change to your path
IncProf_PATH="/data/phases_work//IncProf/MohammedVersion/"
if [ "$#" -lt 1 ]
then
    echo "Illegal number of parameters!!!"
    echo "Usage: DiscoverInst <exec-file> [gmon-regexp]"
    exit
fi
rm *.dat	
rm gmon.*
rm svmfmap.txt
rm instPoints.out
id=$(ls gmon-0.* | cut -d "." -f2 | sort | head -n 1)
# sed -n '2p')
gmon_regexp="gmon-*.$id"

# If the regexp was given by the user
if [ "$#" -eq 3 ]
then
        gmon_regexp=$2
fi

# Generate the SVM file which is used as an input for Kmeans clustering

#echo "### Generate SVM file"
#python ${IncProf_PATH}/gensvm.py $1 "$gmon_regexp" rank.svm > gmon.svm
# Generate data file with functions time difference and function
# call count and rank file for each function
echo "### Generate Data file and rank file"
python ${IncProf_PATH}/sampleSetReduction.py $1 "$gmon_regexp" > gmon.data
echo "### Generate SVM file"
python ${IncProf_PATH}/gensvm.py $1 "$gmon_regexp" rank.svm > gmon.svm

# print the best instrumentation points for elbowk
echo "### find phases and inst points"
python ${IncProf_PATH}/algorithm2.py gmon.data svmfmap.txt rank.svm gmon.svm $2 $3> instPoints.out

