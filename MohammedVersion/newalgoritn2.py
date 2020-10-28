#!/usr/bin/python



#
# Find the instrumantation points
# Usage: algorithm2.py <data-file> <svmfmap> <rank-file> <svm-file>

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
import sklearn.datasets
from sklearn.cluster import KMeans
from sklearn.preprocessing import MaxAbsScaler
from scipy.spatial.distance import cdist
from sklearn.decomposition import PCA

from sklearn.preprocessing import scale

import numpy as np
from sklearn.metrics import silhouette_score
import csv
#import pandas as pd
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

# Laod the rank of each function from rank file.
def findRank(rfile):
   rank = {}
   j = 0
   for l in rfile:
      strs = l.split(":")
      if j != 0:
	 rank[int(strs[0])+1] = int(strs[1].rstrip())
      j+=1
   return(rank)  
# Find the optimal k of KMeans using elbow method 
def findOptKElbow(clParams):
   maxd = 0
   maxk = 0
   amaxd = 0
   amaxk = 0
   for i in range(1,6): # need free ends at both ends
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
   return (maxk, round(maxd,3), amaxk, round(amaxd,3))
# Find optimal k using silhouette coefficient
def findOptKSillho(sillhouet):
   k = 0
   for i, sill in enumerate(sillhouet):
      if sill == max(sillhouet):
	 k = i+2
   return(k)

def runKmenas(X, cluster_range):
   centroids = []
   cld = []
   clparms = []
   basedist = 0
   clustdist = []
   interias = []
   distortions = []
   silhout = []
   labelss = []
   #
   # Run clustering for K=1 to K=8, save results 
   #
   #k = range(2,9)
   for i in cluster_range:
      # kmeans is an object of KMeans class, bellow KMeans is the constructor.
      kmeans = KMeans(n_clusters=i,n_init=30)
      #Compute k-means clustering

      kmeans.fit(X)
      label = kmeans.labels_
      labelss.append(label)
      #distortions.append(sum(np.min(cdist(X, kmeans.cluster_centers_,'euclidean'),axis=1)) / X.shape[0]) 
      
#      distortions.append(np.average(np.min(cdist(X, kmeans.cluster_centers_, 'euclidean'), axis=1)))
      pdist = []
      # Transform X to a cluster-distance space.
      alldist = kmeans.transform(X)
      clustdist.append(alldist)
      #Coordinates of cluster centers
      centroid = kmeans.cluster_centers_
      centroids.append(centroid)
      #Predict the closest cluster each sample in X belongs to.
      labels = kmeans.predict(X)
      label = kmeans.labels_
      silhout.append(silhouette_score(X,label,metric='euclidean'))
     # distortions.append(np.sum(np.min(cdist(X, kmeans.cluster_centers_, 'euclidean'),axis=1)) / X.shape[0])
      # Sum of squared distances of samples to their closest cluster center.
      interia = kmeans.inertia_
      # The silhouette_score gives the average value for all the samples.
      # This gives a perspective into the density and separation of the formed
      # clusters
      #silhouette_avg = silhouette_score(X, labels,metric = 'euclidean')
      #silhout.append(silhouette_avg)
      #cross = pd.crosstab(X,labels)

      interias.append(interia)
      if basedist == 0:
	 basedist =interia
      cld.append(labels)
      clparms.append(interia/basedist)
   return(cld,clustdist,clparms,centroids,labelss,silhout,interia,labels)

#find clusters using KMeans
def findClust(cld,k):
   clust = []
   for j in range(0,len(cld[0])):
      for i in range(0,8):
	 if i == k:
	    clust.append(cld[i][j])
   return(clust)


#find intervals for each cluster
def findIntervals(datafile,rank,distances,clust):
   
   
   intervals = []
   intervals1 = []
   k = 0 
   for line in datafile:
      # split the line to array of function indeces
      strs = line.split(" ")
      tmp1 = []
      tmp = []
      covered = 0
      n = 0
      
      tmp1.append(k)
      tmp1.append(clust[k])
      for s in strs:

	 #skip the first colomn in the data file
	 if s != "\n" and n != 0:
	    #get id,number of calls and rank for each function
	    tmp1.append((int((int(s.split(":")[0])+1)/10),int(s.split(":")[2]),rank[int(s.split(":")[0])+1]))
	    tmp.append((int((int(s.split(":")[0])+1)/10),int(s.split(":")[2]),rank[int(s.split(":")[0])+1]))
	 if s == "\n":
	   
	    intervals.append(tmp)
	    intervals1.append(tmp1)
	    tmp = []
	    tmp1 = []

         n += 1
      k += 1
  
   C = []
   C1 = []
   for i in range(0,int(max(clust))+1):
      C.append([])
      C1.append([])

   for i,clus in enumerate(clust):
      #get the distance of each interval to its centroid
      intervals[i].append(distances[i][clus])
      for j in range(0,int(max(clust))+1):
	 intervals1[i].append(distances[i][j])
      C1[clus].append(intervals1[i])
      # add each interval to its cluster
      C[clus].append(intervals[i])
   for i in range(0,int(max(clust))+1):
      C1[i].sort(key=lambda f: f[i-int(max(clust+1))], reverse = False)

   return(C,C1)

def findInstPoint(C,clust):
   P = []
   C2 = []
   for i in range(0,int(max(clust))+1):
      P.append([])
      C2.append([])
   for i in range(0,int(max(clust))+1):
      #Sort intervals in Ci by distance to the centroid
      C[i].sort(key=lambda f: f[-1], reverse = False)
      for inter in C[i]:
          covered = 0
          tmp3 = []
          #checks to see if this interval is already covered

          for f in inter[:-1]:
             tmp3.append((f[0],f[1],f[2]))
             #sorts the functions first by the number of calls (ascending) and then by rank (descending)
          tmp3.sort(key=lambda x:(-x[2],x[1]),reverse=False)
	  tmp3.append(inter[-1])
	  C2[i].append(tmp3)
   for i in range(0,int(max(clust))+1):
      #Sort intervals in Ci by distance to the centroid
      C[i].sort(key=lambda f: f[-1], reverse = False)
      for inter in C[i]:
	  covered = 0
	  tmp3 = []
	  #checks to see if this interval is already covered

	  for f in inter[:-1]:
	     for fun in P[i]:
		if f[0] in fun:
		   covered=1
	  #skip the interval if it's covered
	  if covered == 1:
	     continue
	  for f in inter[:-1]:
	     tmp3.append((f[0],f[1],f[2]))
	     #sorts the functions first by the number of calls (ascending) and then by rank (descending)
	  #tmp3.sort(key=lambda x:(-x[2],x[1]),reverse=False)
	  #sort based on number of calls and then rank
	  tmp3.sort(key=lambda x:(x[1],-x[2]),reverse=False)
	  print tmp3
	  #takes the topmost function from this sort as the function to instrument in order to cover this interval
	  f = tmp3[0]
	  p = []
	  if f[1] == 0:
	     p = (f[0], "loop")
	  else:
	     p = (f[0], "body")
	  if p not in P[i]:
	     P[i].append(p)
   return(P,C2)



def printClusters(functions3,clust):
   print
   print "Clusters\n"
   for i in range(0,int(max(clust))+1):
      print "###################"
      print "Phase ", str(i) 
      print "###################"
      print "fID\t\twhere\t\texisted in other clusres"
      print "-----\t\t-----\t\t-----\t\t"
      for f in functions3[i]:
	 print "{0}\t\t{1}\t\t".format(int(int(f[0])+1/10), f[1]),
	 print "[",
	 for cl in range(0,int(max(clust))+1):
	    if i == cl:
	       continue
	    if [m for m, v in enumerate(functions3[cl]) if v[0] == f[0]] != []:
	       print cl,",",
	 print "]"
	 
      print
   print "\n\n--------------------------------\n Function names Per Phase\n--------------------------------\n"
   for i in range(0,int(max(clust))+1):
      print "###################"
      print "Phase ", str(i)
      print "###################"
      for f in functions3[i]:
	 if idmap != None and f[0] in idmap:
	    print "{0}: {1}".format(f[0],idmap[f[0]])
	 

#
# Main program
#
if len(sys.argv) != 6:
   print "Usage: {0} <svm-file> <svmfmap> <rank-file> <svmfile>".format(sys.argv[0])
   exit(1)
   
datafile = open(sys.argv[1])
idmapFilename = sys.argv[2]
rfile = open(sys.argv[3])
ssfile = open(sys.argv[4])
method = sys.argv[5]
idmap = None
if idmapFilename != "":
   idmap = loadIdMap(idmapFilename,True)
#Load datasets in the svmlight / libsvm format into sparse CSR matrix
X, y = sklearn.datasets.load_svmlight_file(ssfile)
transformer = MaxAbsScaler().fit(X)
scaled = transformer.transform(X)
#print "X="
#print X
M =  X.toarray()
#M = np.array(M)

#print M
#xx = scale(M)
#print(xx)
#Linear dimensionality reduction using Singular Value Decomposition of the data to project it to a lower dimensional space.
pca = PCA(n_components=2)
#Fit the model with X and apply the dimensionality reduction on X.
reduced_data = pca.fit_transform(M)
#print reduced_data
interfile =  open("data.dat", "w")

for i in range(len(reduced_data)):
        interfile.write(str(reduced_data[i][0]))
        interfile.write(" ")
        interfile.write(str(reduced_data[i][1]))
        interfile.write("\n")

range_n_clusters = [2,3,4,5,6,7,8,9]
kmeanrun = runKmenas(scaled,range_n_clusters)
interias = kmeanrun[6]
#distortion = kmeanrun[4]

print kmeanrun[2]
silhouette = kmeanrun[5]
if method == "elbow":
   optK = findOptKElbow(kmeanrun[2])[0]
else:
   optK = findOptKSillho(silhouette)
rank = findRank(rfile)
print optK
#optK=4
clustdist = kmeanrun[1]
distances = clustdist[optK-2]
centroid = kmeanrun[3]
optcentroids = centroid[optK-2]
labels = kmeanrun[7]
print labels
optlabel = labels[optK-2]
labelfile =  open("label.dat", "w")
"""for i in optlabel:
        labelfile.write(str(i))
        labelfile.write(" ")
#       labelfile.write("\n")
labelfile.write("\n")"""

centerfile =  open("center.dat", "w")

for i in range(len(optcentroids)):

        centerfile.write(str(optcentroids[i][0]))
        centerfile.write(" ")
        centerfile.write(str(optcentroids[i][1]))
        centerfile.write("\n")

clust = kmeanrun[0][optK-2]
C,C2 = findIntervals(datafile,rank,distances,clust)
P1 = findInstPoint(C,clust)
P = P1[0]
J = P1[1]
printClusters(P,clust)

#clusterfile = open("cluster.data", "w")
with open("cluster.data", "w") as clusterfile:
   for i,cluster in enumerate(C2):
      clusterfile.write("cluster:" + str(i) + "\n")
      wr = csv.writer(clusterfile)
      wr.writerows(C2[i])
    #  wr.writerows(clustdist[optkElbow[0]-2][i])
   #for i,cluster in enumerate(J):
   #clusterfile.write(str(i))
   #clusterfile.write("\n")
   #for interv in cluster:
   #   clusterfile.write(interv)
   #   clusterfile.write("\n")
clusterfile.close()
interfile =  open("interia.dat", "w")
distofile = open("distortions.dat", "w")
silhouettefile = open("silhouette.dat", "w")
"""for i,k in enumerate(range_n_clusters):
   interfile.write(str(k))
   interfile.write(" ")
   interfile.write(str(interias[i]))
   interfile.write("\n")
   distofile.write(str(k))
   distofile.write(" ")
   distofile.write(str(distortion[i]))
   distofile.write("\n")
   silhouettefile.write(str(k))
   silhouettefile.write(" ")
   silhouettefile.write(str(silhouette[i]))
   silhouettefile.write("\n")
interfile.close()"""
distofile.close()
silhouettefile.close()

