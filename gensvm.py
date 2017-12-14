#!/usr/bin/python

#
# Generate SVM format lines from gprof profile data
# Usage: gensvm.py <executable> <#samples> > <svm-format-filename>

#
# This script invokes gprof on each sample data file (a gmon.out file)
# and then processes all of the gprof output files to generate a
# sample dataset in SVM format. It expects the gmon files to be named
# "gmon-%d.out", where %d runs from 0 to #samples-1. It generates all
# corresponding gprof-%d.out files, using the --brief option on gprof

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
# Problem: gprof outputs can change the index number of functions from one
# file to another, so we cannot use the index table as a reliable mapping from
# functions to indexes --> must create our own (done).
#

import re;
import sys;
import os;

recordDiff = True
progFile = "none"
lastData = {}
stepData = []
funcIDMap = {}
nextFunctionID = 1

#
# Generate gprof file for one sample, and record its data
#
def gensvm(fileNum):
   global nextFunctionID
   os.system("gprof -b {0} gmon-{1}.out > gprof-{1}.out".format(progFile,fileNum))
   inf = open("gprof-{0}.out".format(fileNum))
   inTable = False
   fdata = []
   #funcIDMap = {}
   #
   # Not useful to look for index table, see above
   #
   #for line in inf:
   #   #print line
   #   if line.find("Index by function name") >= 0:
   #      inTable = True
   #      #print "In function index table"
   #   if inTable == True:
   #      pi = re.finditer("\s*\[(\d+)\] (\w*)", line)  #
   #      for v in pi:
   #         #print v.group(1), v.group(2)
   #         funcIDMap[v.group(2)] = int(v.group(1))
   #inf.seek(0,0)
   inTable = False
   for line in inf:
      #print line
      if line.find("Flat profile") >= 0:
         inTable = True
         #print "In flat profile table"
      if line.find("Call graph") >= 0:
         inTable = False
         #print "Out of flat profile table"
      if inTable == True:
         #print line
         # change function match from \w to non-newline because 
         # of C++ class/template names (:,<>,spaces,...)
         v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
         if v != None:
            #print v.group(1), v.group(2), v.group(3), v.group(4), 
            #print v.group(5), v.group(6), funcIDMap[v.group(7)]
            fpct = float(v.group(1))
            fttime = float(v.group(2))
            fstime = float(v.group(3))
            fcalls = int(v.group(4))
            # 5 and 6 are self ms/call and tot ms/call
            if not (v.group(7) in funcIDMap):
               funcIDMap[v.group(7)] = nextFunctionID
               nextFunctionID += 1
            fid = funcIDMap[v.group(7)]
            while len(fdata) <= fid:
               fdata.append(None)
            fdata[fid] = (fpct, fttime, fstime, fcalls)
   #print fileNum,
   # Put all function data together in one list for the sample step
   # - must iterate through fdata (function data) and then add it to
   # - the step list; we are using indices f*10 through f*10+9 for 
   # - multiple data items per function 
   step = []
   for i,v in enumerate(fdata):
      if v == None:
         continue
      #print v
      #print "{0}:{1} {2}:{3}".format(i*10,v[0]/10.0,i*10+1,v[1]),
      while len(step) <= i*10+5:
         step.append(0)
      #step[i*10] = v[0]/10.0
      step[i*10+1] = v[2]   # self time
      step[i*10+2] = v[3]   # num calls
   while len(stepData) <= fileNum:
      stepData.append(None)
   stepData[fileNum] = step
   #print ""

#
# Output aggregate sample data in libsvm format
#
def outputData(totSteps):
   pstep = [0]*1000;
   for i,step in enumerate(stepData):
      print i,
      for k in range(10,len(step),10):
         #print "{0}:{1} {2}:{3}".format(k,step[k],k+1,step[k+1]),
         # added skip if close to zero since getting many 0s on minixyce
         if abs(step[k+1]-pstep[k+1]) > 0.001:
             print "{0}:{1}".format(k+1,round(step[k+1]-pstep[k+1],3)),
         # num calls is processed using fraction of total, to keep < 1
         dc = (step[k+2]-pstep[k+2]) / float(step[k+2])
         if dc > 0.1:
             print "{0}:{1}".format(k+2,round(dc/10,4)),
      print ""
      pstep = step
      pstep.extend([0]*1000)
      
      
# print function name mapping
def outputFuncNames():
   outf = open("svmfmap.txt","w")
   for f in sorted(funcIDMap):
      #print funcIDMap[f], f
      outf.write("{0}:{1}\n".format(funcIDMap[f],f))
   outf.close()

#
# Main program
#
if len(sys.argv) != 3:
   print "Usage: {0} <exec-binary-filename> <max-sample-#>".format(sys.argv[0])
   exit(1)
   
progFile = sys.argv[1]
numFiles = int(sys.argv[2])

for i in range(0,numFiles+1):
   gensvm(i)
outputData(numFiles)
outputFuncNames()
