#!/usr/bin/python
#
# Run k-means clustering over a data file in libsvm format using Python SKLearn
# - this script runs clustering for k = 1..8, outputs the results, and also tries
#   to infer the "best k" result for clustering
# - we use this to decide which samples of execution belong to the same phase
#
# Usage: program <input-file>

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

# http://scikit-learn.org/stable/datasets/index.html#datasets
#The dataset generation functions and the svmlight loader share a simplistic 
#interface, returning a tuple (X, y) consisting of a n_samples * n_features 
#numpy array X and an array of length n_samples containing the targets y.

import re;
import sys;
import os;
import sklearn.datasets;
import sklearn.cluster;
import math;

# Idea for selecting best K: compare to "gold standard" params
# generated from synthetic data
#1 [ 1.000, 0.677, 0.462, 0.363, 0.306, 0.253, 0.223, 0.201, ]
#2 [ 1.000, 0.367, 0.295, 0.238, 0.192, 0.163, 0.144, 0.128, ]
#3 [ 1.000, 0.334, 0.179, 0.154, 0.134, 0.115, 0.099, 0.087, ]
#4 [ 1.000, 0.284, 0.166, 0.105, 0.093, 0.084, 0.075, 0.067, ]
#5 [ 1.000, 0.281, 0.145, 0.099, 0.068, 0.062, 0.057, 0.052, ]
#6 [ 1.000, 0.265, 0.128, 0.088, 0.065, 0.047, 0.044, 0.041, ]
#7 [ 1.000, 0.266, 0.128, 0.081, 0.059, 0.046, 0.035, 0.033, ]
#8 [ 1.000, 0.259, 0.124, 0.074, 0.054, 0.043, 0.034, 0.027, ]
optClusterParams = [ \
( 1.000, 0.677, 0.462, 0.363, 0.306, 0.253, 0.223, 0.201 ), \
( 1.000, 0.367, 0.295, 0.238, 0.192, 0.163, 0.144, 0.128 ), \
( 1.000, 0.334, 0.179, 0.154, 0.134, 0.115, 0.099, 0.087 ), \
( 1.000, 0.284, 0.166, 0.105, 0.093, 0.084, 0.075, 0.067 ), \
( 1.000, 0.281, 0.145, 0.099, 0.068, 0.062, 0.057, 0.052 ), \
( 1.000, 0.265, 0.128, 0.088, 0.065, 0.047, 0.044, 0.041 ), \
( 1.000, 0.266, 0.128, 0.081, 0.059, 0.046, 0.035, 0.033 ), \
( 1.000, 0.259, 0.124, 0.074, 0.054, 0.043, 0.034, 0.027 ) ]

#
# Idea: generate ideal clustering parameters from synthetic data (above)
# and then compare numbers from real data and find best row match. Works
# kinda ok but is sensitive to std-dev of generated cluster data. If dev
# of real is lower, it selects too many clusters
#
def findOptimalK (clParams):
   dist = []
   for i in range(0,8):
      # compute distance between optimal and actual
      d = 0.0
      for j in range(0,8):
         d += abs(clParams[j] - optClusterParams[i][j])
      dist.append(d)
   # find min dist and return index+1 of it -- this is optimal K
   mind = 999
   mink = 0
   amind = 999
   amink = 0
   for i in range(0,8):
      if dist[i] < mind*0.95:  # % threshold to decide better
         mind = dist[i]
         mink = i+1
      if dist[i] < amind*0.99:
         amind = dist[i]
         amink = i+1
   # return two different selections for 2 tholds
   return (mink, round(mind,3), amink, round(amind,3))

#
# Try elbow method (compare slopes at point)
#
def findOptKElbow(clParams):
   maxd = 0
   maxk = 0
   amaxd = 0
   amaxk = 0
   for i in range(1,7): # need free ends at both ends
      d1 = abs(clParams[i-1]-clParams[i])
      d2 = abs(clParams[i]-clParams[i+1])
      # ad hoc metric for finding elbow: diff of differences
      # scaled by lower (and probably bigger) one, then times
      # loglog of the # of clusters (1-log seemed too much)
      dd = ((d1 - d2) / d1) * math.log(math.log(i+1)+1)
      # try only accepting new if greater than 20% improvement
      if dd > maxd*1.2:
         maxd = dd
         maxk = i+1
      if dd > amaxd*1.1:
         amaxd = dd
         amaxk = i+1
   # return two selections based on thresholds
   return (maxk, round(maxd,3), amaxk, round(amaxd,3))


#
# Main program
#
if len(sys.argv) != 2 and len(sys.argv) != 3:
   print "Usage: {0} <libsvm-format-data-file> [K]".format(sys.argv[0])
   exit(1)
   
inFile = sys.argv[1]

X, y = sklearn.datasets.load_svmlight_file(inFile)

#
# if K is given, do only this K
#
if len(sys.argv) == 3:
   i = int(sys.argv[2])
   c = sklearn.cluster.k_means(X,i,n_init=30)
   print i, c[1], "{0:.4f},".format(c[2]), "{0:.4f},".format(c[2]*i*i*i)
   exit()

#print X
#print y
cld = []
clparms = []
basedist = 0
print "K  metrics"
for i in range(1,9):
   #print "dtype", X.dtype
   #for j in X:
   #   print j.shape,
   #print ""
   # k_means returns tuple of (?, data-cluster-id-list, total-pt-dist, ?)
   #if i==3 or i==4:
   #   c = sklearn.cluster.k_means(X,2,n_init=30)
   #else:
   c = sklearn.cluster.k_means(X,i,n_init=30)
   if basedist == 0:
      basedist = c[2]
   #print i, c[1], "{0:.4f},".format(c[2]), "{0:.4f},".format(c[2]*i*i*i)
   print i, "{0:.4f},".format(c[2]), "{0:.4f},".format(c[2]*i*i*i)
   cld.append(c[1])
   clparms.append(c[2]/basedist)
print "bestK:", findOptimalK(clparms), "elbK:", findOptKElbow(clparms)

print "V\K:",
for i in range(1,9):
   print i,
print ""
for j in range(0,len(cld[0])):
   print "{0:3d}:".format(j),
   for i in range(0,8):
      print cld[i][j],
   print
   

