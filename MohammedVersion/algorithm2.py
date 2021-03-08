#!/usr/bin/python



#
# Find the instrumantation points
# Usage: algorithm2.py <data-file> <svmfmap> <rank-file> <svm-file> <executable> <gmon-regex>

#
# This script will use the cluster information to prduce a list of function that is 
# recommended to instrument in the scientafic application to produce phases and 
# heartbeat information
#
# It uses clustering algorithm called k-means to chategorize the intervals into phases
# To find the optimal number of clusters, two method are used, elbow and silouette
# Users can specify which method to use
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
#import pandas as pd  # not used right now
#import matplotlib.pyplot as plt
#import matplotlib.colors as colors

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
# Check the silhiuette average for each k and return the one
# with max silhouette value
def findOptKSillho(sillhouet):
   k = 0
   for i, sill in enumerate(sillhouet):
      if sill == max(sillhouet):
         k = i+2
   return(k)

# Run KMeans algorithm over the data set to find the clusters
def runKmeans(X, cluster_range):
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
   # Run clustering for K=1 to K=9, save results 
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
      #label = kmeans.labels_
      #silhout.append(silhouette_score(X,label,metric='euclidean'))
     # distortions.append(np.sum(np.min(cdist(X, kmeans.cluster_centers_, 'euclidean'),axis=1)) / X.shape[0])
      # Sum of squared distances of samples to their closest cluster center.
      interia = kmeans.inertia_
      # The silhouette_score gives the average value for all the samples.
      # This gives a perspective into the density and separation of the formed
      # clusters

      # This condition to avoid error when # of clusters is 1
      # It assumes that the silhouette value when k=1 is 1
      if i==1:
          silhouette_avg = 1
      else:
          silhouette_avg = silhouette_score(X, labels,metric = 'euclidean')
      silhout.append(silhouette_avg)
      #cross = pd.crosstab(X,labels)

      interias.append(interia)
      if basedist == 0:
         basedist =interia
      cld.append(labels)
      clparms.append(interia/basedist)

   return(cld,clustdist,clparms,interias,distortions,silhout,centroids,labelss)

#find clusters using KMeans
def findClust(cld,k):
   clust = []
   for j in range(0,len(cld[0])):
      for i in range(0,8):
         if i == k:
            clust.append(cld[i][j])
   return(clust)


#find intervals for each cluster
interv = []
def findIntervals(datafile,rank,distances,clust):
   intervals = []
   intervals1 = []
   #interv = []
   k = 0 
   for line in datafile:
      # split the line to array of function indeces
      strs = line.split(" ")
      tmp1 = []
      tmp = []
      covered = 0
      n = 0
      
      tmp1.append(k)
      #tmp1.append(clust[k])
      for s in strs:

         #skip the first colomn in the data file
         if s != "\n" and n != 0:
            #get id,number of calls and rank for each function
            tmp1.append((int((int(s.split(":")[0])+1)/10),int(s.split(":")[2]),float(s.split(":")[1])))#rank[int(s.split(":")[0])+1]))
            tmp.append((int((int(s.split(":")[0])+1)/10),int(s.split(":")[2]),float(s.split(":")[1]),rank[int(s.split(":")[0])+1]))
         if s == "\n":
            intervals.append(tmp)
            interv.append(tmp)

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

   return(C,C1,interv)
   

# Find the instrumentation sites for each cluster(phase),
# body or loop
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
             tmp3.append((f[0],f[2],f[3]))
             #sorts the functions first by the number of calls (ascending) and then by rank (descending)
          tmp3.sort(key=lambda x:(x[1],-x[2]),reverse=False)
          tmp3.append(inter[-1])
          C2[i].append(tmp3)
   count = 0
   x = 0
   allintervals = 0
   for k in range(0,int(max(clust))+1):
      allintervals +=len(C[k])
   coverage = []
   phaseCov = []
   cove = []
   phaseC = []
   allc = 0
   for i in range(0,int(max(clust))+1):
      x = 0
      j = 1
      allc += len(C[i])
      #Sort intervals in Ci by distance to the centroid
      C[i].sort(key=lambda f: f[-1], reverse = False)
      for inter in C[i]:
          
          covered = 0
          tmp3 = []
          preCovered = 0
          
          #checks to see if this interval is already covere
          for f in inter[:-1]:
             for fun in P[i]:
                if f[0] in fun:
                   covered=1

          #skip the interval if it's covered
          if covered == 1:
             count +=1
          #get the phase coverage and overall coverage of each intrumentation point
          if (inter == C[i][-1] and covered == 1 and j == len(C[i])):
             phaseCover = round(float(float(count)/float(allintervals)),3)
             allCov = round(float(float(count)/float(len(C[i]))),3)
             cove.append(allCov)
             phaseC.append(phaseCover)

          if (x != 0 and covered == 0 ):
             phaseCover = round(float(float(count)/float(allintervals)),3)
             allCov = round(float(float(count)/float(len(C[i]))),3)
             cove.append(allCov)
             phaseC.append(phaseCover)

          if covered == 1:
             j+=1
             continue

          #get the required data from intervals
          for f in inter[:-1]:
             tmp3.append((f[0],f[1],f[3]))
             #sorts the functions first by the number of calls (ascending) and then by rank (descending)
          #tmp3.sort(key=lambda x:(-x[2],x[1]),reverse=False)
          #sort based on number of calls and then rank
          tmp3.sort(key=lambda x:(x[1],-x[2]),reverse=False)
          #takes the topmost function from this sort as the function to instrument in order to cover this interval
          f = tmp3[0]
          p = []
          #if number of calls of a function is 0, instrumentation is in a loop and body otgerwise
          if f[1] == 0:
             p = [f[0], "loop"]
          else:
             p = [f[0], "body"]
          if p not in P[i]:
             fun1 = f[0]
             count = 1
             x = f[0]
             P[i].append(p)

          #get the phase coverage and overall coverage of each intrumentation point
          if covered == 0 and j == len(C[i]) and j != 1:
             
             coverage.append(round(float(float(count)/float(allintervals)),3))
             phaseC.append(round(float(float(count)/float(allintervals)),3))
             phaseCov.append(round(float(float(count)/float(len(C[i]))),3))

             cove.append(round(float(float(count)/float(len(C[i]))),3))

          if covered == 0  and (j == len(C[i]) and j == 1):
             coverage.append(round(float(float(count)/float(allintervals)),3))
             phaseC.append(round(float(float(count)/float(allintervals)),3)) 
             phaseCov.append(round(float(float(count)/float(len(C[i]))),3))
             cove.append(round(float(float(count)/float(len(C[i]))),3))
          j+=1

   return(P,C,coverage,phaseCov,cove,phaseC)

# This finction to find the coverage of each instrumentation point
# It may be used later
def findCoverage(functions,clusters):
   coverage = []
   i = 0
   allintervals = reduce(lambda count, l: count + len(l), clusters, 0)
   for i, function in enumerate(functions):
      coverage.append([])
   for i, function in enumerate(functions):
      
      for func in function:
         count = 0.0
         phaseCount = 0.0
         for interval in clusters[i]:
            #print interval
            for inter in interval[:-1]:
               #print inter
               if func[0] == inter[0]:
                   count +=1
         cover = count/len(clusters[i])
         funCover = [func[0],cover]
         coverage[i].append(funCover)
   
   return(coverage)



# Find if there is overlapping between phases
# If a function appears in two different phases as an instrumentation point
def isOverlapped(funct,clust):
   overlapped = False

   for i in range(0,int(max(clust))+1):
      for f in funct[i]:
         for cl in range(0,int(max(clust))+1):
            if i == cl:
               continue
            if [m for m, v in enumerate(funct[cl]) if v[0] == f[0] and v[1]==f[1]] != []:
               overlapped = True
   return overlapped



# Print phases with their instrumentation points(functions)
def printClusters(functions3,clust,coverage,phaseCov):
   threshold = 0.95
   covSum = 0
   overlapped = False
   sortedFunc = []
   instPoints = []
   skippedFunc = []
   for i in range(0,int(max(clust))+1):
      sortedFunc.append([])
      instPoints.append([])
      skippedFunc.append([])
   m = 0
   for i in range(0,int(max(clust))+1):
      sortedFunc[i]= functions3[i]
      for f in sortedFunc[i]:
         f.append(phaseCov[m])
         f.append(coverage[m])
        
         m += 1
      sortedFunc[i].sort(key=lambda x:(x[2]),reverse=True)

   print
   print "Clusters\n"
   k = 0
   for i in range(0,int(max(clust))+1):
      #covSum = phaseCov[k]
      print "###################"
      print "Phase ", str(i) 
      print "###################"
      print "fID\t\twhere\t\tcoverage\tPhase coverage\texisted in other clusres"
      print "-----\t\t-----\t\t-----\t\t------\t\t------"
      covSum = 0

      for f in sortedFunc[i]:
         if f == sortedFunc[i][0]:
            existed = 0
            for cl in range(0,int(max(clust))+1):
               if i == cl:
                  continue
               if [m for m, v in enumerate(sortedFunc[cl]) if v[0] == f[0] and v[1]==f[1]] != []:
                  existed = 1
                  #if existed == 1:
                  #continue
                  #covSum = phaseCov[k]
                  #if covSum < threshold or f[2] == 1.0 or f[2]>threshold:
                  #covSum += phaseCov[k]
            instPoints[i].append([f[0]])
            print "{0}\t\t{1}\t\t{2}\t\t{3}\t\t".format(int(int(f[0])), f[1],f[3],f[2]),
            k +=1
            #covSum += phaseCov[k]
            print "[",
            for cl in range(0,int(max(clust))+1):
               if i == cl:
                  continue
               if [m for m, v in enumerate(sortedFunc[cl]) if v[0] == f[0] and v[1]==f[1]] != []:
                  print cl,",",
            print "]"
            covSum += f[2]
         elif covSum < threshold:
            existed = 0
            for cl in range(0,int(max(clust))+1):
               if i == cl:
                  continue
               if [m for m, v in enumerate(sortedFunc[cl]) if v[0] == f[0] and v[1]==f[1]] != []:
                  existed = 1
            instPoints[i].append([f[0]])
            print "{0}\t\t{1}\t\t{2}\t\t{3}\t\t".format(int(int(f[0])), f[1],f[3],f[2]),
            print "[",
            for cl in range(0,int(max(clust))+1):
               if i == cl:
                  continue
               if [m for m, v in enumerate(sortedFunc[cl]) if v[0] == f[0] and v[1]==f[1]] != []:
                  print cl,",",
            print "]"
            covSum += f[2]
         else:
            skippedFunc[i].append(f)
            covSum += f[2]
         
      print
   print "\n\n--------------------------------\n Function names Per Phase\n--------------------------------\n"
   for i in range(0,int(max(clust))+1):
      print "###################"
      print "Phase ", str(i)
      print "###################"
      for f in instPoints[i]:
         if idmap != None and f[0] in idmap:
            print "{0}: {1}".format(f[0],idmap[f[0]])
   print "\n\n--------------------------------\n Skipped Function names Per Phase\n--------------------------------\n"
   for i in range(0,int(max(clust))+1):
      print "###################"
      print "Phase ", str(i)
      print "###################"
      for f in skippedFunc[i]:
         if idmap != None and f[0] in idmap:
            print "{0}: {1} Phase Coverage {2}".format(f[0],idmap[f[0]],f[2])
 
         

#
# Main program
#
if len(sys.argv) != 6:
   print "Usage: {0} <svm-file> <svmfmap> <rank-file> <svmfile> <executable> <gmon-regex>".format(sys.argv[0])
   exit(1)
   
datafile = open(sys.argv[1])
idmapFilename = sys.argv[2]
rfile = open(sys.argv[3])
ssfile = open(sys.argv[4])
method = sys.argv[5]
idmap = None
if idmapFilename != "":
   idmap = loadIdMap(idmapFilename,True)
#print idmap

#Load datasets in the svmlight / libsvm format into sparse CSR matrix
X, y = sklearn.datasets.load_svmlight_file(ssfile)
transformer = MaxAbsScaler().fit(X)
# no pandas df = pd.read_csv("data.csv")
# no pandas df3 = df.iloc[:,1:]
scaled = transformer.transform(X).toarray()
#print scaled
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
"""for dpoint in reduced_data:
   plt.scatter(dpoint[0],dpoint[1])
plt.show()"""
"""interfile =  open("data.dat", "w")

for i in range(len(reduced_data)):
   interfile.write(str(reduced_data[i][0]))
   interfile.write(" ")
   interfile.write(str(reduced_data[i][1]))
   interfile.write("\n")"""

range_n_clusters = [1,2,3,4,5,6,7,8,9,10,11,12,13]
# Run kmeans algorithim using different values of K(# of clusters)
kmeanrun = runKmeans(X,range_n_clusters)#scaled,range_n_clusters)
interias = kmeanrun[3]
#from kneed import KneeLocator
#kn = KneeLocator(range_n_clusters, interias, curve='convex', direction='decreasing')
#print kn.knee
distortion = kmeanrun[4]

silhouette = kmeanrun[5]
optK = 0
if method == "elbow":
   optK = findOptKElbow(kmeanrun[2])[0]
else:
   optK = findOptKSillho(silhouette)
#optK = 2
rank = findRank(rfile)
#optK=3
clustdist = kmeanrun[1]
distances = clustdist[optK-1]
centroid = kmeanrun[6]
optcentroids = centroid[optK-1]
labels = kmeanrun[7]
optlabel = labels[optK-1]
clust = kmeanrun[0][optK-1]

C,C2,intervalss = findIntervals(datafile,rank,distances,clust)
P1 = findInstPoint(C,clust)
P = P1[0]
J = P1[1]
Cov = P1[5]
phCov = P1[4]
phaseC = P1[4]
cove = P1[5]
overlapped = isOverlapped(P,clust)
#cov = findCoverage(P,C)
pathToOptK = []
pathToOptK.append(optK)

# If the produced phases are overlapped, decrement optimal k by 1
# and try to reproce phases again

while(overlapped and optK>1):
   optK=optK -1
   pathToOptK.append(optK)
   distances = clustdist[optK-1]
   optcentroids = centroid[optK-1]
   optlabel = labels[optK-1]
   clust = kmeanrun[0][optK-1]
   datafile = open(sys.argv[1])
   C,C2,intervalss = findIntervals(datafile,rank,distances,clust)
   P1 = findInstPoint(C,clust)
   P = P1[0]
   J = P1[1]
   Cov = P1[5]
   phCov = P1[4]
   overlapped = isOverlapped(P,clust)

# Show the values of optimal till the non-overlapped phases produced
print "K\tsilhouette"
for n in pathToOptK:
   print "{0}\t{1}".format(n,silhouette[n-1])

# This part to plot the clusters
colors = ['#8B0000', '#BC8F8F','#FFFF00','#008000','#FFC0CB', '#F0F8FF']
"""for p,red in enumerate(reduced_data):
   plt.scatter(red[0],red[1],c=colors[optlabel[p]], s=50)

plt.scatter(optcentroids[:,0],optcentroids[:,1],marker = "x",s=50,linewidths = 5,zorder = 10)
plt.show()"""

printClusters(P,clust,Cov,phCov)
cov = findCoverage(P,C)

labelfile =  open("label.dat", "w")
for i in optlabel:
   labelfile.write(str(i))
   labelfile.write(" ")
#  labelfile.write("\n")
labelfile.write("\n")
centerfile =  open("center.dat", "w")

for i in range(len(optcentroids)):
   centerfile.write(str(optcentroids[i][0]))
   centerfile.write(" ")
   centerfile.write(str(optcentroids[i][1]))
   centerfile.write("\n")

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
"""with open("gmon.svm.cluster", "w") as gmonclusterfile:
   for i,interval in enumerate(interv):
      gmonclusterfile.write(str(i))
      gmonclusterfile.write(",")
      gmonclusterfile.write(str(optlabel[i]))"""
      
      #print "{0},{1} ".format(i,optlabel[i]),
      #print interval[-1]
      #for function in interval[:-1]:
         #print " {0}:{1}".format(function[0],function[3])
         #gmonclusterfile.write(" ")
         #gmonclusterfile.write(str(function[0]))
         #gmonclusterfile.write(":")
         #gmonclusterfile.write(str(function[3]))
         
         #print "{0}:{1}".format(function[0],function[3]),
   #print
      #gmonclusterfile.write("\n")"""
      
interfile =  open("interia.dat", "w")
distofile = open("distortions.dat", "w")
silhouettefile = open("silhouette.dat", "w")
for i,k in enumerate(range_n_clusters):
   interfile.write(str(k))
   interfile.write(" ")
   interfile.write(str(interias[i]))
   interfile.write("\n")
   #distofile.write(str(k))
   #distofile.write(" ")
   #distofile.write(str(distortion[i]))
   #distofile.write("\n")
   silhouettefile.write(str(k))
   silhouettefile.write(" ")
   silhouettefile.write(str(silhouette[i]))
   silhouettefile.write("\n")
interfile.close()
distofile.close()
silhouettefile.close()

