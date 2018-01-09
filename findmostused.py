#!/usr/bin/python

#
# Find the most used functions and create a new svm file according to some percent
# Usage: findmostused.py <svm-format-filename> <percent> > <svm-format-filename>

#
# This script eliminate the least used functions in a gmon svm file
# and produce a smaller list of functions. This new file can be used in the cluster
#

import re;
import sys;
import os;
import glob;
import subprocess;
funcIDlist = [0] * 10000
funcTimelist = [0.0] * 10000

# Show progress
def progress(count, total, status=''):
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    sys.stderr.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    sys.stderr.flush()  # As suggested by Rom Ruben (see: http://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console/27871113#comment50529068_27871113)


#
# Main program
#
if len(sys.argv) != 3:
   print "Usage: {0} <svm-format-filename> <limit>".format(sys.argv[0])
   exit(1)
   
svmFile = sys.argv[1]
keep_lim = int(sys.argv[2])

f = open("{0}".format(svmFile))

nlines = 0
# read the file and get the sunction counts
for line in f:
	strs = line.split(" ")
	#print (strs)
	i = 0
	for s in strs:
		if s != "\n" and i != 0:
			funcID = int(s.split(":")[0])
			funcIDlist[funcID] += 1
		i += 1
     	nlines += 1

# find the percentage for each function
m = 0
for fid in funcIDlist:
	if fid != 0:
		funcIDlist[m] = float(funcIDlist[m]) / nlines * 100
	m += 1


# find the maximum function calls
#highlist = []
#for m in range(0,keep_lim):
#	highest = max(funcIDlist)
#	ind = [i for i, j in enumerate(funcIDlist) if j == highest][0]
#	#print ind
#	funcIDlist[ind] = 0
#	highlist.append(ind)

# Find the highst percentage compared to the user percentage input 
i = 0
highlist = []
for m in funcIDlist:
#	print m,
	if float(m) >= float(keep_lim):
		highlist.append(i)
	i += 1


f = open("{0}".format(svmFile))
# generate the new svm file
i = 1
for line in f:
	found = 0
	print "{0}".format(i),
	for fid in highlist:
		t = " "+str(fid)+":"
		if t in line:
			found = 1
			print str(fid)+":1",

	# if no function appeared in the line, then print the fist one
	if found == 0:
		print str(line.split(" ")[1].split(":")[0])+":1",

	print ""
	i += 1


# sort the functionIDs by percentage - ignored for now
B = sorted(funcIDlist,key=float,reverse=True)
sortfuncID = []
for v in B:
	if v > 0:
		sortfuncID.append(funcIDlist.index(v)) 

#print sortfuncID







