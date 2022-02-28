#!/usr/bin/python3
#--------------------------------------------------------------
# Run k-means clustering over a data file in libsvm format using Python SKLearn
# - this script runs clustering for k = 1..8, outputs the results, and also tries
#   to infer the "best k" result for clustering
# - we use this to decide which samples of execution belong to the same phase
#
# Usage: program <input-file> [idmap-file] [flip]
#--------------------------------------------------------------

#--------------------------------------------------------------
# The input file is in "libsvm" format, described below. The idmap file, if
# given, is a JSON-formatted file that can be read in as a Python dictionary,
# the keys of which are the index values in the input file, and the values
# of which are strings that describe what the index value means. These will
# be printed in the cluster descriptions so that an understandable mapping
# can be made. If the third argument is the string "flip", then the idmap
# key-value pairs were reversed, and the whole thing is flipped (values
# become keys, and vice versa).
#
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
#--------------------------------------------------------------

# http://scikit-learn.org/stable/datasets/index.html#datasets
#The dataset generation functions and the svmlight loader share a simplistic 
#interface, returning a tuple (X, y) consisting of a n_samples * n_features 
#numpy array X and an array of length n_samples containing the targets y.

import re
import sys
import os
import argparse
import sklearn.datasets
import sklearn.cluster
import math
import json
import numpy as np

# set true for lots of debugging out (will interfere with output formats)
debug = False

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

#--------------------------------------------------------------
# Normalize a list of real numbers
# - used to show relative importance of each value in a data vector
# - assumes positive???
#--------------------------------------------------------------
def normalize(vals):
   max = -9999999.0
   for v in vals:
      if max < v:
         max = v
   for i in range(len(vals)):
      vals[i] = vals[i] / max
      
#--------------------------------------------------------------
# Load the ID Map file (function int -> name mapping, possibly backwards)
#--------------------------------------------------------------
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

#--------------------------------------------------------------
# Idea: generate ideal clustering parameters from synthetic data (above)
# and then compare numbers from real data and find best row match. Works
# kinda ok but is sensitive to std-dev of generated cluster data. If dev
# of real is lower, it selects too many clusters
#--------------------------------------------------------------
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

#--------------------------------------------------------------
# Try elbow method (compare slopes at point)
#--------------------------------------------------------------
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
      if d1 <= 0:
         continue
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

#--------------------------------------------------------------
# Find the closest interval data point to a cluster centroid
# - X is a csr_matrix and so behaves a bit weirdly
#--------------------------------------------------------------
def findClosestRealDatapoint(X,centroid):
  print("Find closest real data point------------------------")
  dim1 = X.shape[0] # num of elements (intervals) in X
  dim2 = X.shape[1] # num of attributes (functions w/ data)
  #print("X shape {0}  centroid length {1}".format(X.shape,len(centroid)))
  mindist = 99999999.0
  mindp = 0
  # loop over all datapoints to find closest
  for n in range(dim1):
     dp = X[n]
     dist = 0.0
     #print(dp)
     # loop through attributes (dimensions) and compute distance
     # - this is manhattan distance, I believe
     for i in range(dim2):
        delta = dp[(0,i)] - centroid[i]
        dist += math.sqrt(delta*delta)
     if dist < mindist:
        # new closest datapoint, so save info
        mindist = dist
        mindp = n
  #print("X shape {0}  centroid length {1}".format(X.shape,len(centroid)))
  print("Closest dp: {0} :\n{1}".format(mindp,X[mindp]))
  print("Centroid:\n{0}".format(centroid))
  print("END closest real data point------------------------")
  return True

#--------------------------------------------------------------
# counts how many datapoints are in a cluster
#--------------------------------------------------------------
def countClusterMagnitude(clusterId, labeledData):
   size = 0
   for i in labeledData:
      #if labeledData[i] == clusterId:
      if i == clusterId:
         size += 1
   return size

#--------------------------------------------------------------
# Print out info on clusters based on centroids
# - support KMeans clustering; use for multiple K choices
# - also identifies instrumentation site by finding data
#   dimension (attribute) that a cluster has significantly but
#   that is not shared by other clusters
#--------------------------------------------------------------
def printClusterCentroidInfo(centroids,sizes):
   n = 1
   for c in centroids: 
      print("Cluster {0}:".format(n-1))
      print("  size = {0}".format(sizes[n-1]))
      # skip small clusters
      if sizes[n-1] < 5: # genericise this size threshold
         n += 1
         continue
      closestReal = findClosestRealDatapoint(X,c)
      normalize(c) # is already???
      # we should do: save up all functions
      # that are not shared with other clusters, then iterate and find
      # the one with the most time, or the shallowest one
      potentialInstrFunc = []
      # iterate through data attributes of centroid (functions, for us)
      for f in range(len(c)):
         if c[f] > 0.0099: # limit to active functions
            # search if the function exist in other clusters
            # TODO: find a better way to do it
            # JEC: why is this comment between the if stmt and r=1????
            r = 1
            # JEC TODO: I have no idea the proper indent below here (w/ tabs)
            existsIn = [] #exist in other cluster list
            for c1 in centroids:
               normalize(c1)
               if r != n and c1[f] > 0.099 and sizes[r-1] > 5:
                  existsIn.append(r-1) # add the cluster number
                  #print("existsIn: {0}".format(existsIn))
               r += 1
            if len(existsIn) == 0:
               # only exists in this cluster, so a possible instr site
               existsIn.append("possible instr")
               potentialInstrFunc.append((f,c[f]))
            # JEC for 2-val func data, was m = int(f/10) but 
            # the id map file should handle this directly
            m = str(f+1) # centroid indices are off by one
            if idMap != None and m in idMap:
               print("   {0:d}: {1:.3f}  {2}  {3}".format(f, c[f],
                     idMap[m][:30],existsIn))
            elif f < len(c):
               print("   {0:d}: {1:.3f}  {2}".format(f,c[f],existsIn))
            else:
               print("unknown?? {0}".format(f))
      # if we have potential instrumentation sites, pick the one
      # with a highest data value
      if len(potentialInstrFunc) > 0:
         maxfd = potentialInstrFunc[0]
         for fd in potentialInstrFunc:
            if fd[1] > maxfd[1]:
               maxfd = fd
         fi = str(maxfd[0]+1)
         print("Instrument function: {0}".format(idMap[fi][:50]))
         print("First Instrument fc: {0}".format(
               idMap[str(potentialInstrFunc[0][0]+1)][:50]))
      # continue loop on next centroid
      n += 1

#--------------------------------------------------------------
# Do KMeans clustering and print results
#--------------------------------------------------------------
def doKMeansClustering():
   centroids = []
   cld = []
   clparms = []
   basedist = 0
   #
   # Run clustering for K=1 to K=8, save results and print metrics
   #
   print("K  metrics")
   for i in range(1,9):
      #print("dtype {0}".format(X.dtype))
      #for j in X:
      #   print j.shape,
      #print("")
      # k_means returns tuple of (?, data-cluster-id-list, total-pt-dist, ?)
      #if i==3 or i==4:
      #   c = sklearn.cluster.k_means(X,2,n_init=30)
      #else:
      print("clustering K={0}".format(i))
      c = sklearn.cluster.k_means(X,i,n_init=20)
      print("  done")
      if basedist == 0:
         basedist = c[2]
      #print i, c[1], "{0:.4f},".format(c[2]), "{0:.4f},".format(c[2]*i*i*i)
      print("{0} {1:.4f}, {2:.4f}".format(i,c[2],c[2]*i*i*i))
      centroids.append(c[0])
      cld.append(c[1])
      clparms.append(c[2]/basedist)
   #
   # Find "best" K using a couple of different methods, and print them
   bestk = findOptimalK(clparms)
   elbowk = findOptKElbow(clparms)
   print("bestK: {0}   elbowk: {1}".format(bestk, elbowk))
   # output traces of intervals and what clusters they belong in
   felbowk = open('cluster.elbowk', 'w')
   fbestk = open('cluster.bestk', 'w')
   #
   # Print the clustering of each data element vertically
   #
   #print elbowk[0]
   print("V\K:",end="")
   for i in range(1,9):
      print("{0} ".format(i), end="")
   print("")
   for j in range(0,len(cld[0])):
      print("{0:3d}:".format(j),end="")
      for i in range(0,8):
         print(cld[i][j],end="")
         # print cluster data in a seprate file
         # Print the the elbowk cluster elements vertically
         if i == (elbowk[0] - 1):
            felbowk.write("{0},{1}\n".format(j, cld[i][j]))
         # Print the the bestk cluster elements vertically
         if i == (bestk[0] - 1):
            fbestk.write("{0},{1}\n".format(j, cld[i][j]))
      print
   felbowk.close()
   fbestk.close()
   # compute sizes of clustersin best and elbow
   clSizeBest = []
   n = 0
   for c in centroids[bestk[0]-1]: 
      clSizeBest.append(countClusterMagnitude(n, cld[bestk[0]-1]))
      n += 1
   clSizeElbow = []
   n = 0
   for c in centroids[elbowk[0]-1]: 
      clSizeElbow.append(countClusterMagnitude(n, cld[elbowk[0]-1]))
      n += 1
   # Print out info based on two ideal clustering counts
   print("'Optimal' K = {0} Centroids".format(bestk[0]))
   printClusterCentroidInfo(centroids[bestk[0]-1],clSizeBest)
   if bestk[0] == elbowk[0]:
      exit()
   print("------------------------------------------------------------------")
   print("Elbow K = {0} Centroids".format(elbowk[0]))
   printClusterCentroidInfo(centroids[elbowk[0]-1],clSizeElbow)
   findSignificantFeatures(centroids[elbowk[0]-1])

#--------------------------------------------------------------
# Work in Progress: experiment with DBSCAN clustering
# -- not sure yet how to process the results
#--------------------------------------------------------------
def doDbscanClustering(fnames):
   centroids = []
   cld = []
   clparms = []
   basedist = 0
   epsilon = 0.07
   if False:
      # this was just an experiment, should remove it I guess
      c = sklearn.cluster.DBSCAN(eps=epsilon, metric='manhattan', min_samples=2).fit(X)
      print("Clusters over data vector:")
      print(c.labels_)
      #print c.n_features_in_
      print("Cluster core indices")
      print(c.core_sample_indices_)
      print("Cluster Core Components")
      print(c.components_)
   else:
      c = sklearn.cluster.dbscan(X, eps=epsilon, min_samples=2, metric='manhattan')
      print("Result len {0}".format(len(c)))
      numclusters = len(set(c[1])) - (1 if -1 in c[1] else 0)
      print("Number of clusters: {0}".format(numclusters))
      print("Clusters over data vector:")
      print(c[1])
      print("Cluster core indices")
      print(c[0])
      clusters = []
      print("Estimated centroids")
      for i in range(numclusters):
         points = np.ndarray(X[0].shape)
         csize = 0
         for l in range(len(c[1])):
            if c[1][l] == i:
               points += X[l]
               csize += 1
         if csize < 2: continue
         #points = c[1][labels==i,:]
         #print points
         #centroid = np.mean(points) 
         #print(centroid)
         points = points / csize
         #centroid = np.mean(points,axis=0)
         centroid = []
         for j in range(points.shape[1]):
            centroid.append(points[0,j])
         print("Cluster {0},{2}: {3} {1}".format(i+1,points,csize,points.shape))
         #print("   centroid: {0}".format(centroid))
         clusters.append(centroid)
      #print np.mean(X[0])
      for cluster in clusters:
         print("Cluster: ")
         for fi in range(len(cluster)):
             if cluster[fi] < 0.009: continue
             potSite = True
             for other in clusters:
                if other == cluster: continue
                if other[fi] > 0.009: potSite = False
             if potSite:
                print("  Can instrument: {0}:{1}".format(fi,
                       idMap[str(fi+1)][:40]))
      findSignificantFeatures(clusters)
   return True 

#
# Find most significant features that distinguish clusters
# from each other, give the centroids of the clusters
# 
def findSignificantFeatures(clusters):
   ci = 0
   for cluster in clusters:
      print("Cluster {0}:".format(ci))
      # use difference rather than absolute distance because we
      # want the most positive differences to stand out
      totaldiffs = []
      for i in range(len(cluster)):
         totaldiffs.append(0.0)
      for other in clusters:
         if other is cluster:
            continue
         for i in range(len(cluster)):
            totaldiffs[i] += cluster[i] - other[i];
      maxI = 0
      maxD = 0.0
      for i in range(len(cluster)):
         if totaldiffs[i] > maxD:
            maxI = i
            maxD = totaldiffs[i]
      print("  DCan instrument: {0}:{1}".format(maxI,
                       idMap[str(maxI+1)][:40]))
      ci += 1
   return True

#--------------------------------------------------------------
# Main program
#--------------------------------------------------------------
flip = False
argParser = argparse.ArgumentParser(description='Gprof data manipulator')
argParser.add_argument('svmfile', metavar='SVM-file', type=str, help='name of SVM data file')
argParser.add_argument('namefile', metavar='name-map-file', type=str, help='name of id->name mapping file')
argParser.add_argument('--debug', action='store_true', help='turn on debugging info (default off)')
argParser.add_argument('--flip', action='store_true', help='flip name map format (default: off)')
argParser.add_argument('--alg', action='store', default='kmeans', metavar='<kmeans|dbscan>', help='clustering algorithm (default: kmeans)')
args = argParser.parse_args()
debug = args.debug
algorithm = args.alg
dataFilename = args.svmfile
idmapFilename = args.namefile
flip = args.flip

#
# Load Id Map if available
idMap = None
if idmapFilename != "":
   idMap = loadIdMap(idmapFilename,flip)
   if debug:
      print(idMap)
   
#print("idmap")
#print idMap


#
# Initialize SciKit data structures
# TODO: What about data normalization?
# pp.normalize produces something  that kmeans segfaults on!
# - no idea how to fix this
# StandardScaler works but then how to interpret results?
# - hard to select instrumentation site
#
X, y = sklearn.datasets.load_svmlight_file(dataFilename)
# normalize columns (features)
#print("X RAW-------------------------------------------------"
#print X
#X = sklearn.preprocessing.normalize(X,norm="l2",axis=0)
#print("X NORM------------------------------------------------"
#scaler = sklearn.preprocessing.StandardScaler(copy=False,with_mean=False)
#scaler.fit(X)
#>>> print(scaler.transform(data))
#print("X SCALED------------------------------------------------"
#print X

#
# OBSOLETE: if K is given, do only this K
#
# if len(sys.argv) == 3:
#    i = int(sys.argv[2])
#    c = sklearn.cluster.k_means(X,i,n_init=30)
#    print i, c[1], "{0:.4f},".format(c[2]), "{0:.4f},".format(c[2]*i*i*i)
#    exit()

if debug:
   print(X)
   print(y)

if algorithm == "kmeans":
   doKMeansClustering()
elif algorithm == "dbscan":
   doDbscanClustering(0)

