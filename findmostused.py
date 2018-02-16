#!/usr/bin/python

#
# Find the most used functions and create a new svm file according to some percent
# Usage: findmostused.py <svm-format-filename> <0/1/2>  > <svm-format-filename>
# 0 time only / 1 count only / 2 both


#
# This script eliminate the least used functions in a gmon svm file
# and produce a smaller list of functions. This new file can be used in the cluster
#

import re;
import sys;
import os;
import glob;
import subprocess;
funcIDCountlist = [0] * 10000
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
   print "Usage: {0} <svm-format-filename> <0/1/2>".format(sys.argv[0])
   exit(1)
   
svmFile = sys.argv[1]
# with count is 1 and without count is 0
with_count = int(sys.argv[2])

f = open("{0}".format(svmFile))

nlines = 0
# read the file and get the functions count
for line in f:
	strs = line.split(" ")
	#print (strs)
	i = 0
	for s in strs:
		if s != "\n" and i != 0:
			funcID = int(s.split(":")[0])
			funcIDCountlist[funcID] += 1
		i += 1
     	nlines += 1

# find the percentage for each function
m = 0
for fid in funcIDCountlist:
	if fid != 0:
		funcIDCountlist[m] = float(funcIDCountlist[m]) / nlines * 100
	m += 1

f.close()


# sort the functionIDs by percentage
B = sorted(funcIDCountlist,key=float,reverse=True)
sortfuncID = []
for v in B:
        if v > 0:
                sortfuncID.append(funcIDCountlist.index(v))
                funcIDCountlist[funcIDCountlist.index(v)] = 0

	
f = open("{0}".format(svmFile))
step = 1
for line in f:
	found = 0
	print "{0}".format(step-1),

	# Here keep only functions that have counts and
        # keep the most used function
        # The solution is to mark every function with the highst used one

        # split the line to array of function indeces
        strs = line.split(" ")
	k=0
	tmp = []
	# Create list of triples
        for s in strs:
		if s != "\n" and k != 0:
			tmp.append((int(s.split(":")[0]), s.split(":")[1], int(s.split(":")[2])))
		k += 1

	# sort the list by the third item smaller value
	tmp.sort(key=lambda x: x[2])

#	print tmp

	refine_list=[] # tuple (function number, value - time or counts)
	k=1 # k sets the number of function we should add if they have calls counts
	# For each triple get the write the function with lowest number of calls more than zero
	for t in tmp:
		if int(t[2]) > 0:
			found = 1
			#print str(t[0])+":"+str(t[1]),
			if with_count == 0 or with_count == 2:
				refine_list.append((int(t[0]),str(t[1])))
			if with_count == 1 or with_count == 2:
				refine_list.append((int(t[0])+1,str(t[2])))
			if k == 1: # set here!!
				break
			k += 1

	# split the line to array of function indeces
	strs = line.split(" ")
        #print (strs)
        k = 0
	tmp = []
        for s in strs:
       	        if s != "\n" and k != 0:
               	        tmp.append(int(s.split(":")[0]))
                k += 1
	# sort the line array by the sorted function IDs
	Z = sorted(tmp, key=lambda x: sortfuncID.index(x))
	# write the most used function in that line
	#print str(Z[0])+":1",

	# search the refine list to eliminate duplicates

        i = 0
        exist = 0
#	print "\n old refine_list = ", refine_list
        for d in refine_list:
                if d[0] == Z[0] or d[0] == (Z[0]+1):
                        exist = 1
                        break
                i += 1
        if exist == 0:
		if with_count == 0 or with_count == 2:
			refine_list.append((int(Z[0]),1))
       		else:
                	if with_count == 1 or with_count == 2:
                        	refine_list.append((int(Z[0])+1,0))

 #       print "new refine_list = ", refine_list, "\n"

#	if [i for i, v in enumerate(refine_list) if v[0] == int(Z[0])] == []:
#		if with_count == 0 or with_count == 2:
#			refine_list.append((int(Z[0]),1))
#		if with_count == 1 or with_count == 2:
#	                refine_list.append((int(Z[0])+1,0))

	# Sort and save
	refine_list.sort(key=lambda x: x[0])

	for t in refine_list:
		print str(t[0])+":"+str(t[1]),

	print ""
#	print "-------------"
	step += 1



