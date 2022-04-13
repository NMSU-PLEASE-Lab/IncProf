#!/usr/bin/python3


#
# Usage: gensvm.py <executable> <#samples> > <svm-format-filename>

#
# This script invokes gprof on each sample data file (a gmon.out file)
# and then processes all of the gprof output files to generate a
# sample dataset in SVM format. It expects the gmon files to be named
# "gmon-%d.out", where %d runs from 0 to #samples-1. It generates all
# corresponding gprof-%d.out files, using the -b option on gprof

# LIBSVM format
# https://stats.stackexchange.com/questions/61328/libsvm-data-format
#    The format of training and testing data file is:
#    <label> <index1>:<value1> <index2>:<value2> ...
#    ...
#    Each line contains an instance and is ended by a '\n' character. 
#    For classification, <label> is an integer indicating the class label 
#    (multi-class is supported). For regression, <label> is the target 
#    value which can be any real number. For one-class SVM, it's not used 
#    so can be any number. The pair <index>:<value> gives a feature 
#    (attribute) value: <index> is an integer starting from 1 and <value> 
#    is a real number. The only exception is the precomputed kernel, where 
#    <index> starts from 0; see the section of precomputed kernels. 
#    Indices must be in ASCENDING order. Labels in the testing file are 
#    only used to calculate accuracy or errors. If they are unknown, just 
#    fill the first column with any numbers.
# 
# It also generates the data file (gmon.data), which holds the required data 
# for the analysis such as calls and self time.

#
# Problem: gprof outputs can change the index number of functions from one
# file to another, so we cannot use the index table as a reliable mapping from
# functions to indexes --> must create our own (done).
#

import re
import sys
import os
import glob
import subprocess
progFile = "none"
stepData = []
funcIDMap = {}
nextFunctionID = 1
numFiles = 0
rank = {}


# Show progress
def progress(count, total, status=''):
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    sys.stderr.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    sys.stderr.flush()  # As suggested by Rom Ruben (see: http://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console/27871113#comment50529068_27871113)

#-------------------------------------------end of progress-------------------------------------#


#
# Generate gprof file for one sample, and record its data
#
def generate_svm(filename):
    global nextFunctionID
    # create gmon file if it's not created
    if not(os.path.isfile(filename+".new")):
        os.system("gprof -b {0} {1} > {1}.new".format(progFile,filename))
    inf = open("{0}.new".format(filename), 'r')
    # create a list of each file, where each list contains the list of all functions 
    # appeared in the Flat profile of the gmon file
    fdata = []
    inTable = False
    # read the lines of the gmon file
    # use the Flat profile for current analysis
    for line in inf:
        if line.find("Flat profile") >= 0:
            inTable = True
        if line.find("Call graph") >= 0:
            inTable = False
        if inTable == True:
            # change function match from \w to non-newline because 
            # of C++ class/template names (:,<>,spaces,...)
            # match the line with an RE, where the line has no blank column
            v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
            short = 0
            # if the line has blank values, match it with another RE
            if v == None:
                v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
                short = 1
            # for all lines, with or without blank values, get the function % time, cumulative sec, and 
            # self sec
            if v != None:
                percTime = float(v.group(1)) # % time
                cumTime = float(v.group(2)) # cumulative seconds
                selfTime = float(v.group(3)) # self seconds
                # if the line has no blanks, get the values of calls and self ms/call 
                if short == 0:
                    selfCallTime = float(v.group(5)) # self ms/call, added to skip functions with 0 value
                    calls = int(v.group(4)) # calls
                    # 6 is total ms/call
                    # add the function name to funcIDMap dictionary if not added (fname: funID)
                    if not (v.group(7) in funcIDMap):
                        funcIDMap[v.group(7)] = nextFunctionID
                        nextFunctionID += 1
                    funcID = funcIDMap[v.group(7)]
                else:
                    # if calls and self ms/call are blank, make them 0
                    calls = 0
                    selfCallTime = 0  

                    if not (v.group(4) in funcIDMap):
                        funcIDMap[v.group(4)] = nextFunctionID
                        nextFunctionID += 1
                    funcID = funcIDMap[v.group(4)]
                # create a list of each function in the file
                # each list holds funID, % time, cumulative sec, self sec, calls, and self ms/call
                # add the created list to fdata list
                fdata.append([funcID, percTime, cumTime, selfTime, calls, selfCallTime])
    inf.close()
    # Put all function data together in one list for the sample step
    # - must iterate through fdata (function data) and then add required data to
    # - the step list. Select the required data from the fdata and add it to stepData.
    steps = []
    for f in fdata:
        if f == None:
            continue
        step = []
        step.append(f[0])   # function id
        step.append(f[2])   # self time
        step.append(f[3])   # num calls
        step.append(f[4])   # self ms/call
        steps.append(step)
   
    stepData.append(steps)
   
#-------------------------------------------end of generate_svm-------------------------------------#


#
# Output aggregate sample data in libsvm format
# It outputs two files (gmon.svm and gmon.data) in the libsvm format
# where a line in each file represents the data of active functions in each interval
# To get the value of each interval, compute the difference between 2 executive gmon files
#
def output_data():
    # create a list to hold the previous step data
    pstep = []
   
    intervals =  []
    # read stepData where each step represents data of one profiling file
    for i,step in enumerate(stepData):
        # while each function has a unique id, sort the current and previous steps based on the
        # function ids to do difference between corresponding functions
        step.sort(key=lambda x: int(x[0]))
        pstep.sort(key=lambda x: x[0])
        # extend the previous step to make it's size same as the current step 
        pstep.extend([[0,0,0,0]]* (len(step) - len(pstep)))
        # create an interval to hold the difference data between current and previous step
        interval = []
        # iterate over the functions of each step and compute the difference with the 
        # correspending function from the previous step
        for j, func in enumerate(step):
            if abs(func[2]-pstep[j][2]) > 0.00:
                # compute the rank of each function
                # rank: # of intervals a function was active in 
                if func[0] not in rank:
                    rank[func[0]]=1
                else:
                    rank[func[0]] +=1
                # each interval holds lists of all active functions in the interval
                interval.append([func[0],round(func[2]-pstep[j][2],4),func[3]-pstep[j][3]])
      
        # if an interval is empty (time difference of all functions is zero)
        if not interval:
            continue
        # make the current profiling file as previous to do difference between next and current
        pstep = step
        # list of all intervals
        intervals.append(interval)
  
    index = 0
    # create gmon.data file and add the required data in libsvm format (interval funcID:stime:calls)
    datafile = open("gmon.data", "w")
    for i, inter in enumerate(intervals):
        datafile.write("{0} ".format(index))
        for func in inter:
            datafile.write("{0}:{1}:{2} ".format(func[0],func[1],func[2]))
        datafile.write("\n")
        index += 1
    # create gmon.svm file and add the required data in libsvm format (interval funcID:stime)
    index = 0
    svmfile = open("gmon.svm", "w")
    for i, inter in enumerate(intervals):
        svmfile.write(str(index))
        for func in inter:
            svmfile.write(" {0}:{1}".format(func[0],func[1]))
        svmfile.write("\n")
        index += 1

#---------------------------------------end of output_data--------------------------------#

# print the function names along with their id's in svmfmap file
def output_functions_names():
    i = 1
    outf = open("svmfmap.txt","w")
    outf.write("{")
    for f in sorted(funcIDMap):
        outf.write('"{0}":{1}'.format(f,funcIDMap[f]))
        outf.write("\n")
        if i < len(funcIDMap):
            outf.write(",")
        i += 1
    outf.write("}")
    outf.close()

#-------------------------------end of output_functions_names-----------------------------#

# print function Ids with the rank of each function, it will be used in algorithm2
# to descover instrumentation sites
def output_functions_rank():
    outfile = open("rank.svm","w")
    outfile.write("FID:Rank\n")
    for funID, funRank in rank.items():
        outfile.write("{0}:{1}\n".format(funID, funRank))
    outfile.close()

#--------------------------------end of output_functions_rank-------------------------#


#
# Main program
#
if len(sys.argv) != 3:
    print("Usage: {0} <exec-binary-filename> <filenames-regexp>".format(sys.argv[0]))
    exit(1)
# get the program executable file to generate gmon files
progFile = sys.argv[1]
filename_regexp = sys.argv[2]


i = 0
# get a list of file names that match the regexp
listOfFiles = glob.glob(filename_regexp)
# total number of files
noOfFiles = len(listOfFiles)
# get the process id from the file name (i.e., gmon-328.1441 -> 1441 )
# all file names in the list of file names have the same process id (regexp)
# so, here we chose the last file in the list
proc_num = listOfFiles[noOfFiles-1].split(".")[1]
# get the start of the file name (i.e., gmon-328.1441 -> gmon)
pref_filename = listOfFiles[noOfFiles-1].split("-")[0]
# iterate over the list of file names in assending order to generate
# gmon file and find all active functions in the files
for entry in listOfFiles:
    fname = pref_filename+"-"+str(i)+"."+str(proc_num)
    generate_svm(fname)
    i = i + 1

output_data()
output_functions_names()
output_functions_rank()

