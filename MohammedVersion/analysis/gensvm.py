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
import glob;
import subprocess;
recordDiff = True
progFile = "none"
lastData = {}
stepData = []
funcIDMap = {}
nextFunctionID = 1
numFiles = 0
functions = [[]]


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
   #try:
   #   print "1"
   if not(os.path.isfile(filename+".new")):
       os.system("gprof -b {0} {1} > {1}.new".format(progFile,filename))
   inf = open("{0}.new".format(filename))
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
         # change function match from \w to non-newline because 
         # of C++ class/template names (:,<>,spaces,...)
         v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
         #print "line = ", line
         #print "v = ", v
         # short is 1 if the line have missing last 3 values
         short = 0
         if v == None:
            v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
            short = 1

         if v != None:
            fpct = float(v.group(1))
            fttime = float(v.group(2))
            fstime = float(v.group(3))
            if short == 0:
               sms_call = float(v.group(5)) # self ms/call, added to skip functions with 0 value
               fcalls = int(v.group(4))
               # 5 and 6 are self ms/call and tot ms/call
               if not (v.group(7) in funcIDMap):
                  funcIDMap[v.group(7)] = nextFunctionID
                  #print "hi", v.group(5), v.group(6), funcIDMap[v.group(7)], v.group(7)
                  nextFunctionID += 1
               fid = funcIDMap[v.group(7)]
            else:
               # to skip functions with blank # of calls, make fcalls = -1
               fcalls = 0
               sms_call = 0  # if it's blank, make it 0
               if not (v.group(4) in funcIDMap):
                  funcIDMap[v.group(4)] = nextFunctionID
                  nextFunctionID += 1
               fid = funcIDMap[v.group(4)]

            while len(fdata) <= fid:
               fdata.append(None)
            fdata[fid] = (fpct, fttime, fstime, fcalls, sms_call)
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
      step[i*10+3] = v[4]   # self ms/call

   while len(stepData) <= fileNum:
      stepData.append(None)

   stepData[fileNum] = step

#--------------------------------- end gensvm() function-------------------------------#

#
# Find the rank of each function from the rank file, it is used to do clustering using ranks of functions instead of time
#
def findRank(rfile):
   rank = {}
   j = 0
   for l in rfile:
      strs = l.split(":")
      if j != 0:
         rank[int(strs[0])] = int(strs[1].rstrip())
      j+=1
   return(rank)

#------------------------------------------end of findRank-------------------------------#


#
# Output aggregate sample data in libsvm format
#
def outputData(totSteps, rank):
   csvfile = open("data.csv", "w")
   newgmonfile = open("newGmon.data", "w")
   pstep = [0]*10000;
   step_num = 0
   f = 0
   intervals = []
   mylist = [];
   skippedInterPer = 0.0
   for i,step in enumerate(stepData):
      if (not step):
         continue

      check = 0
      # Check if the line is empty
      for k in range(10,len(step),10):
         # added skip if close to zero since getting many 0s on minixyce
         if abs(step[k+1]-pstep[k+1]) > 0:#0.001:
            #print "diff=", abs(step[k+1]-pstep[k+1])
            mylist = [];
            check = 1 
         # num calls is processed using fraction of total, to keep < 1
         #if ((step[k+2]-pstep[k+2]) / float(step[k+2]) > 0.1):
             #check = 1
      if (check == 0 and not mylist):
         continue
      if (check == 0):
         for x in mylist:
            functions[f].append(x/10)
         functions.append([])
         step_num = step_num + 1
         continue
      sortedbyTime = []
      newgmonfile.write(str(step_num))
      newgmonfile.write(" ")
      interval = []
      for k in range(10,len(step),10):
         # added skip if close to zero since getting many 0s on minixyce
         c = 0
         if abs(step[k+1]-pstep[k+1]) > 0.001: # or abs(step[k+2]-pstep[k+2]):
            c = 1
            #if step[k+3] < 0.001 or pstep[k+3] < 0.001:
            #  continue
            # skip if # of calls is blank 
            if step[k+2] == -1 or pstep[k+2] == -1:
               continue
            else:
               # get the function id and difference in time between two successive profiling files
               # this will be used as input data for clustering

               interval.append([k+1,step[k+1]-pstep[k+1]]) 
               #interval.append([k+1,1])

               # Use the rank in the gmon.data file for experiemrents
               #interval.append([k+1,rank[k+1]])#(step[k+1]-pstep[k+1])])
               functions[f].append(k/10)
               mylist.append(k)
               function = [k+1,round(step[k+1]-pstep[k+1],3),step[k+2]-pstep[k+2],rank[k+1]]#round(step[k+1]-pstep[k+1],3),step[k+2]-pstep[k+2]]
               sortedbyTime.append(function)
               sortedfun = sorted(sortedbyTime,key= lambda x:(x[2],-x[3]), reverse = False)

      pstep = step
      pstep.extend([0]*10000)
      step_num = step_num + 1
      f+=1
      functions.append([])
      intervals.append(interval)

   count = 0
   index = 0
   for i, inter in enumerate(intervals):
      if not inter:
         count +=1
         continue
      print index,
      for func in inter:
         print "{0}:{1}".format(func[0],func[1]),
      print ""
      index +=1
   skippedInterPer = (count/(len(intervals)*1.0))
   skippedfile = open("skippedInter.csv", "w")
   skippedfile.write("The % of skipped intervals is ")
   skippedfile.write(str(skippedInterPer))
   skippedfile.write("\n")

#---------------------------------end of outputData---------------------------------#

# print function name mapping
def outputFuncNames():
   i = 1
   outf = open("svmfmap.txt","w")
   outf.write("{")
   for f in sorted(funcIDMap):
      #print funcIDMap[f], f
      #outf.write("{0}:{1}\n".format(funcIDMap[f],f))
      outf.write('"{0}":{1}\n'.format(f,funcIDMap[f]))
      if i < len(funcIDMap):
         outf.write(",")
      i += 1
   outf.write("}")
   outf.close()

#
# Main program
#
if len(sys.argv) != 4:
   print "Usage: {0} <exec-binary-filename> <filenames-regexp>".format(sys.argv[0])
   exit(1)
   
progFile = sys.argv[1]
#numFiles = int(sys.argv[2])
filename_regexp = sys.argv[2]
#print "start"
rfile = open(sys.argv[3])
rank = findRank(rfile)
i = 0
listOfFiles = glob.glob(filename_regexp)
total = len(listOfFiles)
proc_num = listOfFiles[total-1].split(".")[1]
pref_filename = listOfFiles[total-1].split("-")[0]
#exit(0)
for entry in listOfFiles:  
   fname = pref_filename+"-"+str(i)+"."+str(proc_num)
   #print (fname)
   gensvm(fname, i)
   i = i + 1
   #progress(i, total+2, status='Extract Gproph files')
   #print (entry)

numFiles = i
functionss =  funcIDMap.values()
#sortedfunctionss = functionss.sort()
functionss.sort()
sortedfuncIDMap = sorted(funcIDMap.items(),key = lambda x: x[1])
#print sortedfuncIDMap
#print sortedfuncIDMap[0]
#print sorted(sortedfuncIDMap, key=lambda x: x[1])
outputData(numFiles, rank)
outputFuncNames()
# To print a csv file containig all functions in each interval (0 = absent, 1 = present)
# for experiements
csvfile = open("data.csv", "w")
csvfile.write("ID,")
for fn in functionss:
   csvfile.write(str(fn))
   if fn ==functionss[-1]:
      csvfile.write("\n")
   else:
      csvfile.write(",")
for h,inter in enumerate(functions):
   if inter != functions[-1]:
      csvfile.write(str(h))
      csvfile.write(",")
      for fun in functionss:
         if fun in inter:
            csvfile.write("1")
         else:
            csvfile.write("0")
         if fun == functionss[-1]:
            csvfile.write("\n")
         else:
            csvfile.write(",")
#progress(total, total, status='Write the SVM file')

