#!/usr/bin/python

#
# Find the instrumantation points
# Usage: findinst.py <cluster-file> <svm-file> <svmfmap>

#
# This script will use the cluster information to prduce a list of function that is 
# recommended to instrument in the scientafic application to produce phases and 
# heartbeat information
#


import re;
import sys;
import os;
import glob;
import subprocess;
import math
import json

recordDiff = True
progFile = "none"
lastData = {}
stepData = []
funcIDMap = {}
nextFunctionID = 1
numFiles = 0


# Show progress
def progress(count, total, status=''):
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    sys.stderr.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    sys.stderr.flush()  # As suggested by Rom Ruben (see: http://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console/27871113#comment50529068_27871113)


#
# Load the ID Map file
#
def loadIdMap(filename,flip):
   idmap = {}
   f = open(filename)
   if f == None:
      return idmap
   nmap = json.load(f)
   f.close()
   if nmap == None:
      return {}
   if flip:
      # flip to make reverse map
      for n in nmap:
         idmap[nmap[n]] = n
      return idmap
   else:
      return nmap



#
# Main program
#
if len(sys.argv) != 4:
   print "Usage: {0} <cluster-file> <svm-file> <svmfmap>".format(sys.argv[0])
   exit(1)
   
cfile = open(sys.argv[1])
sfile = open(sys.argv[2])
idmapFilename = sys.argv[3]

clust = []
#
# Load the cluster
for line in cfile:
	# split the line to array of function indeces
        strs = line.split(",")
	clust.append(strs[1].rstrip())

#print max(clust)

#
# Load Id Map
idmap = None
if idmapFilename != "":
   idmap = loadIdMap(idmapFilename,True)


# functions are list of pairs per cluster (funcID, call count, count of times appeared in the cluster, where to instrument - body/loop)
functions = []
for i in range(0,int(max(clust))+1):
	functions.append([])

m = 0
for line in sfile:

        # split the line to array of function indeces
        strs = line.split(" ")
	k = 0
        tmp = []
        # Create list of pairs
        for s in strs:
                if s != "\n" and k != 0:
                        tmp.append((int(int(s.split(":")[0])/10), s.split(":")[1]))
		k += 1

	# TODO: Find the function with counts > 0 and add it to a list of list by functionID, then find the function name from the svmfmap
	# and print the cluster it belong to and if instrument the function body or the loop, (body | loop)

        # sort the list by the second pair index larger value
        tmp.sort(key=lambda x: x[1], reverse=True)

	# check if the functionID exist in one of the clusters
	L = functions[int(clust[m])]
	i=0
	exist = 0
	for d in L:
		if d[0] == tmp[0][0]:
			exist = 1
			break
		i += 1
	if exist == 0:
		# not exist add it to the cluster list
		functions[int(clust[m])].append((tmp[0][0], tmp[0][1],1))
	else:
		# exist then check how many times this function was appeared in the cluster
		count = functions[int(clust[m])][i][2]
		del functions[int(clust[m])][i]
		functions[int(clust[m])].append((tmp[0][0], tmp[0][1], count+1))

	m += 1

# Refine the functions in each cluster to select the most number of hits function
RefinedFunc = []
for i in range(0,int(max(clust))+1):
        RefinedFunc.append([])
	RefinedFunc[i].append(sorted(functions[i], key=lambda tup: tup[2], reverse=True)[0])
#	print RefinedFunc[i]
#	print sorted(functions[i], key=lambda tup: tup[2])

# If no refinment selected
#RefinedFunc = functions

print
print "Clusters\n"
for i in range(0,int(max(clust))+1):
	print "###################"
        print "Phase ", str(i) 
	print "###################"
	print "fID\t\tcalls\t\tcount\t\twhere\t\tother-clusters-exist"
	print "-----\t\t-----\t\t-----\t\t-----\t\t-----\t\t"
	#print sorted(RefinedFunc[i], key=lambda tup: tup[2])
	for f in sorted(RefinedFunc[i], key=lambda tup: tup[2], reverse=True):
		if int(f[2]) < 2:
			continue
		if f[1] == '0':
			print "{0}\t\t{1}\t\t{2}\t\tloop".format(f[0], f[1], f[2]),
		else:
			print "{0}\t\t{1}\t\t{2}\t\tbody".format(f[0], f[1], f[2]),

		print "\t\t[",
		for cl in range(0,int(max(clust))+1):
			if i == cl:
				continue
			if [m for m, v in enumerate(RefinedFunc[cl]) if v[0] == f[0]] != []:
				print cl,",",
		print "]"
		break
	print

print "\n\n--------------------------------\n Function names Per Phase\n--------------------------------\n"
# Print the function names
for i in range(0,int(max(clust))+1):
        print "###################"
        print "Phase ", str(i)
        print "###################"
	for f in sorted(RefinedFunc[i], key=lambda tup: tup[2], reverse=True):
                if int(f[2]) < 2:
                        continue
		if idmap != None and int(f[0]) in idmap:
			print "{0}: {1}".format(f[0],idmap[int(f[0])])
		break

