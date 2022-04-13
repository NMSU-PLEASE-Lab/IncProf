
#!/bin/bash
#
# Usage: RunAllScripts.sh <exec-file> <regexp> <elbow|silhoutte>
#
# this script should not need any setting of a path, it figures
# it out on its own
# OLD: USE an external setting of INCPROF_PATH preferably, so that you
# do not need to change this script
#
#if [ -z ${INCPROF_PATH+x} ]
#then
#    INCPROF_PATH="/home/jcook/ws/please-lab-github/IncProf/MohammedVersion"
#fi
INCPROF_PATH=$(dirname $(readlink -f $0))
echo "Using IncProf path ${INCPROF_PATH}"

if [ "$#" -lt 1 ]
then
    echo "Illegal number of parameters!!!"
    echo "Usage: RunAllScripts.sh <exec-file> <elbow|silhouette>"
    exit
fi
# Remove previous generated files
rm -f *.dat	
rm -f gmon.* gmon*new
rm -f svmfmap.txt
rm -f instPoints.out
# Get process id from gmon file names
#rank0
procid=$(ls gmon-0.* | cut -d "." -f2 | sort | head -n 1)
#rank1
#procid=$(ls gmon-0.* | cut -d "." -f2 | sort | sed -n '2p')
# Formulate gmon filename regex 
gmon_regexp="gmon-*.$procid"

# If the regexp was given by the user, use it
# JEC: Doesn't work because of hardcoded args on algorithm2.py
# TODO: Fix the algorithm2 invocation to use other variables names
if [ "$#" -eq 3 ]
then
    gmon_regexp=$2
fi

# Generate the SVM file which is used as an input for Kmeans clustering
# Generate data file with functions time difference and function
# call count and rank file for each function
echo "### Generate SVM, data, and rank files"
python ${INCPROF_PATH}/sampleSetReduction.py $1 "$gmon_regexp"

# print the best instrumentation points
echo "### Find phases and inst points"
python ${INCPROF_PATH}/algorithm2.py gmon.data svmfmap.txt rank.svm gmon.svm $2 $3 

