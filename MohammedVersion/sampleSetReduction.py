#!/usr/bin/python


#
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
import glob;
import subprocess;
recordDiff = True
progFile = "none"
lastData = {}
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


#
# Generate gprof file for one sample, and record its data
#
def gensvm(filename, fileNum):
   global nextFunctionID
   global numFiles
   if not(os.path.isfile(filename+".new")):
      os.system("gprof -b {0} {1} > {1}.new".format(progFile,filename))
   inf = open("{0}.new".format(filename))
   inTable = False
   fdata = []
   inTable = False
   for line in inf:
      if line.find("Flat profile") >= 0:
         inTable = True
      if line.find("Call graph") >= 0:
         inTable = False
      if inTable == True:
         # change function match from \w to non-newline because 
         # of C++ class/template names (:,<>,spaces,...)
         v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
         short = 0
         if v == None:
            v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
            short = 1

         if v != None:
            fpct = float(v.group(1))
            fttime = float(v.group(2))
            fstime = float(v.group(3))
            if short == 0:
               fcalls = int(v.group(4))
               # 5 and 6 are self ms/call and tot ms/call
               if not (v.group(7) in funcIDMap):
                  funcIDMap[v.group(7)] = nextFunctionID
                  nextFunctionID += 1
               fid = funcIDMap[v.group(7)]
            else:
               # to skip functions with blank # of calls, make fcalls = -1
               fcalls = 0
               if not (v.group(4) in funcIDMap):
                  funcIDMap[v.group(4)] = nextFunctionID
                  nextFunctionID += 1
               fid = funcIDMap[v.group(4)]

            while len(fdata) <= fid:
               fdata.append(None)
            fdata[fid] = (fpct, fttime, fstime, fcalls)
   # Put all function data together in one list for the sample step
   # - must iterate through fdata (function data) and then add it to
   # - the step list; we are using indices f*10 through f*10+9 for 
   # - multiple data items per function 
   step = []
   for i,v in enumerate(fdata):
      if v == None:
         continue
      while len(step) <= i*10+5:
         step.append(0)
      step[i*10+1] = v[2]   # self time
      step[i*10+2] = v[3]   # num calls

   while len(stepData) <= fileNum:
      stepData.append(None)

   stepData[fileNum] = step

#
# Output aggregate sample data in libsvm format
#
def outputData(totSteps):
   pstep = [0]*10000;
   step_num = 0
   mylist = []
   intervals =  []
   for i,step in enumerate(stepData):
      if (not step):
         continue
      check = 0
      # Check if the line is empty
      for k in range(10,len(step),10):
         # added skip if close to zero since getting many 0s on minixyce
         if abs(step[k+1]-pstep[k+1]) > 0:#0.001:
            mylist = [];
            check = 1 
         # num calls is processed using fraction of total, to keep < 1
      if (check == 0 and not mylist):
         continue
      if (check == 0):
         #print step_num,
         for x in mylist:
            m = 10
            #intervals.append([x+1,0,0])
            #print "{0}:{1}:{2}".format(x+1,0,0),
         
         #print ""
         #step_num = step_num + 1
         continue
      interval = []
      #print step_num,
      for k in range(10,len(step),10):
         # added skip if close to zero since getting many 0s on minixyce
         c = 0
         if abs(step[k+1]-pstep[k+1]) > 0.001:
            if (k+1) not in rank:
               rank[k+1]=1
            else:
               rank[k+1] +=1
            #########
            # NOTE: This will not create a regular SVM file
            #########
            if step[k+2] == -1 or pstep[k+2] == -1:
               continue
            else:
               #print "{0}:{1}:{2}".format(k+1,round(step[k+1]-pstep[k+1],3),step[k+2]-pstep[k+2]), # Function index and the time diff and count
               interval.append([k+1,round(step[k+1]-pstep[k+1],3),step[k+2]-pstep[k+2]])
               mylist.append(k)
         # num calls is processed using fraction of total, to keep < 1

      #print ""
      pstep = step
      pstep.extend([0]*10000)
      step_num = step_num + 1
      intervals.append(interval)
  
   count = 0
   index = 0
   for i, inter in enumerate(intervals):
      if not inter:
         count +=1
         continue
      print index,
      for func in inter:
         print "{0}:{1}:{2}".format(func[0],func[1],func[2]),
      print ""
      index += 1
  #print "hi"
  #print intervals
      
def outputFuncNames():
   i = 1
   outf = open("svmfmap.txt","w")
   outf.write("[")
   for f in sorted(funcIDMap):
      outf.write('"{0}":{1}'.format(f,funcIDMap[f]))
      outf.write("\n")

      if i < len(funcIDMap):
         outf.write(",")
      i += 1
   outf.write("}")
   outf.close()

def outputFunctionRank():
   outfile = open("rank.svm","w")
   outfile.write("FID:Rank\n")
   for fnid, rk in rank.items():
      outfile.write("{0}:{1}\n".format(fnid, rk))
   outfile.close()
#
# Main program
#
if len(sys.argv) != 3:
   print "Usage: {0} <exec-binary-filename> <filenames-regexp>".format(sys.argv[0])
   exit(1)
   
progFile = sys.argv[1]
#numFiles = int(sys.argv[2])
filename_regexp = sys.argv[2]


i = 0
listOfFiles = glob.glob(filename_regexp)

total = len(listOfFiles)
proc_num = listOfFiles[total-1].split(".")[1]
pref_filename = listOfFiles[total-1].split("-")[0]
for entry in listOfFiles:
   fname = pref_filename+"-"+str(i)+"."+str(proc_num)
   gensvm(fname, i)
   i = i + 1

numFiles = i
outputData(numFiles)
outputFuncNames()
outputFunctionRank()

