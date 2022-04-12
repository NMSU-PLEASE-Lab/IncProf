#!/usr/bin/python3



#
# Find the instrumantation points
# Usage: algorithm2.py <data-file> <svmfmap> <rank-file> <svm-file> <executable> <gmon-regex>

#
# This script will use the cluster information to produce a list of functions that is 
# recommended to instrument in the scientafic application to produce phases and 
# heartbeat information
#
# It uses clustering algorithm called k-means to chategorize the intervals into phases
# To find the optimal number of clusters, two method are used, elbow or silouette
# Users can specify which method to use
#
import re
import sys
import os
import math
import json
from sklearn.datasets import load_svmlight_file
from sklearn.cluster import KMeans
from sklearn.preprocessing import MaxAbsScaler
from sklearn.decomposition import PCA
from sklearn.preprocessing import scale
import numpy as np
from sklearn.metrics import silhouette_score
import csv
from functools import reduce
import imp
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

#--------------------------- end of progress ---------------------------------#

#
# Load the ID Map file
# filename: file that contains function IDs and function names
# flip:  to make reserve map
# 
# returns a dictionary of function IDs with their names

def load_id_map(filename,flip):
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

#-------------------------- end of load_id_map --------------------------#

# Laod the rank of each function from rank file.
# rfile: file contains the function IDs and their ranks
# returns a dictionary (ID:rank)
def find_rank(rfile):
    rank = {}
    j = 0
    for line in rfile:
        # split each line into a list of two elements [ID, rank]
        strs = line.split(":")
        # skip the first line (header)
        if j != 0:
            # rstrip removes any trailing characters (\n)
            rank[int(strs[0])] = int(strs[1].rstrip())
        j+=1
    return(rank)  
#----------------------- end of find_rank -----------------------#

# Find the optimal k of KMeans using elbow method 
def find_optimalK_elbow(clParams):
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

#----------------------- end of find_optimalK_elbow -----------------------#

# Find optimal k using silhouette coefficient
# Check the silhiuette average for each k and return the one
# with max silhouette value
# silhouette: list of the silhouette values of all ks
# returns the optimal k 
def find_optimalK_silhouette(silhouette):
    # remove the first element to not select k=1 at the begining
    new_silhouette = silhouette[1:]
    k = 0
    # get the index of the max silhouette value
    # add 2 to the returned index, the silhouette value at index 0 represents k=2
    k = new_silhouette.index(max(new_silhouette)) + 2
    return(k)

#---------------------- end of find_optimalK_silhouette ----------------------#

# Run KMeans algorithm over the data set to find the clusters
# X: scipy.sparse matrix of shape (n_samples, n_features)
# cluster_range: list of k values
# 
def run_kmeans(X, cluster_range):
    allKcentrs = []
    allKLabels = []
    clparms = []
    basedist = 0
    allKdist = []
    allKinterias = []
    distortions = []
    allKsilhout = []
   
    #
    # Run clustering for K=1 to K=8, save results 
    #
    for k in cluster_range:
        # kmeans is an object of KMeans class, bellow KMeans is the constructor
        kmeans = KMeans(n_clusters=k,n_init=30)
        # Compute k-means clustering
        kmeans.fit(X)
        # Predict the closest cluster each sample in X belongs to
        # it returns index of the cluster each sample belongs to
        singleKlabels = kmeans.predict(X)
        allKLabels.append(singleKlabels)
        pdist = []
        # Transform X to a cluster-distance space. Returns distance to the cluster centers
        singleKdist = kmeans.transform(X)
        allKdist.append(singleKdist)
        # Coordinates of cluster centers
        singleKcentr = kmeans.cluster_centers_
        allKcentrs.append(singleKcentr)
      
        # intertia is the sum of squared distances of samples to their closest cluster center.
        singleKinteria = kmeans.inertia_
        allKinterias.append(singleKinteria)
        # The silhouette_score gives the average value for all the samples.
        # This gives a perspective into the density and separation of the formed
        # clusters

        # This condition to avoid error when # of clusters is 1
        # It assumes that the silhouette value when k=1 is 1
        if k == 1:
            silhouette_avg = 1
        else:
            # silhouette_score Computes the mean Silhouette Coefficient of all samples.
            # The Silhouette Coefficient is calculated using the mean 
            # intra-cluster distance (a) and the mean nearest-cluster distance (b) for 
            # each sample. The Silhouette Coefficient for a sample is (b - a) / max(a, b). 
            # To clarify, b is the distance between a sample and the nearest cluster that 
            # the sample is not a part of. Note that Silhouette Coefficient is only defined 
            # if number of labels is 2 <= n_labels <= n_samples - 1.
            silhouette_avg = silhouette_score(X, singleKlabels,metric = 'euclidean')
        allKsilhout.append(silhouette_avg)
        if basedist == 0:
            basedist =singleKinteria
        clparms.append(singleKinteria/basedist)
    return(allKLabels,allKdist,clparms,allKinterias,allKsilhout,allKcentrs)

#-------------------------- end of run_kmeans --------------------------#

# find intervals for each cluster from the data file (gmon.data)
# datafile: gmon.data file
# rank: a dictionary (ID:rank)
# distances: a list of list of distances of a all sample to all centriods, 
# i.e., k=2 -> [d1, d2], where d1 is distance to cetroid1 and d2 to centriod2
# labels: list of labels of data samples
#
# returns a list of lists of clusters, where each list contains the data of intervals of a cluster.
# Each interval is a list of tupels, where a tuple is a function with its data and the last element
# of each interval is the distance of the interval to its related centriods.
def find_intervals(datafile,rank,distances,labels, k):
    intervals = []
    # read datafile lines
    for line in datafile:
        # split the line to array of function indeces
        # i.e.,  0 1:0.06:4142381 2:0.03:0 -> ['0', '1:0.06:4142381', '2:0.03:0', '\n']
        strs = line.split(" ")
        tmp = []
        n = 0
        for s in strs:
            # skip the first colomn in the data file and the new line(\n)
            if s != "\n" and n != 0:
                # get id, calls and rank for each function. To get the rank of a function, the id needed to retrive it from rank dictionery
                tmp.append((int(s.split(":")[0]),int(s.split(":")[2]),float(s.split(":")[1]),rank[int(s.split(":")[0])]))
            # if no more data in each interval, add tmp to intervals list
            if s == "\n":
                intervals.append(tmp)
                tmp = []
            n += 1
    clusters = []
    # add k lists to clusters (labels start from 0)
    for i in range(0, k):
        clusters.append([])
    for i,clus in enumerate(labels):
        # get the distance of each interval to its centroid
        intervals[i].append(distances[i][clus])
        # add each interval to its cluster
        clusters[clus].append(intervals[i])
   
    return(clusters)

#-------------------------- end of find_intervals --------------------------#   

# Find the instrumentation sites for each cluster(phase),
# body or loop
# Clusters: list of lists of clusters, each clusters contains lists of its intervals with their distances
# k: number of clusters
#
# it returns: 
#  - phases: list of phases with IDs of discovered inst sites
#  - Clusters: list of intervals in each cluster with their distances to the related cluster
#  - funcIDs: function ids in each interval in each cluster
#  - instPoints: list of clusters, where each cluster contain the ids of function selected
#    as instrumention site
# 
def find_inst_points(Clusters, k):
    phases = []
    instPoints = []
    funcIDs = []
    for i in range(0,k):
        phases.append([])
        instPoints.append([])
        funcIDs.append([])
    for i in range(0,k):
        # Sort intervals in Ci by distance to the centroid
        # distence is the last element of each interval
        Clusters[i].sort(key=lambda f: f[-1], reverse = False)
        for inter in Clusters[i]:
            covered = 0
            tmp = []
            interFun = []
            # checks if this interval is already covered
            # check if the interval has any selected inst points in the related phase
            for f in inter[:-1]:
                interFun.append(f[0])
                for fun in phases[i]:
                    if f[0] in fun:
                        covered=1
            funcIDs[i].append(interFun)
            # skip the interval if it's covered
            if covered == 1:
                continue
            # get the required data from intervals; Function ID, ncalls and rank
            for f in inter[:-1]:
                tmp.append((f[0],f[1],f[3]))
            # sort the functions first by the number of calls (ascending) and then by rank (descending)
            tmp.sort( key = lambda x:(x[1], -x[2]),reverse=False)#,reverse=False)
            if not tmp:
                continue
            # take the topmost function from this sort as the function to instrument in order to cover this interval
            f = tmp[0]
            phase = []
            # if number of calls of a function is 0, instrumentation is in a loop and body otherwise
            if f[1] == 0:
                phase = [f[0], "loop"]
            else:
                phase = [f[0], "body"]
            # check if the selected inst point has been added to the related phase
            if phase not in phases[i]:
                phases[i].append(phase)
                # add the ID of the selected function to instPoints list
                instPoints[i].append(f[0])

    return(phases,Clusters,funcIDs,instPoints)
#----------------------- end of find_inst_points -----------------------#

# This finction to find the coverage of each instrumentation point
# After finding the instrumentation points, check the data to find the coverage
# phasesFuncIds: list of clusters, where each cluster contain the ids of function
# selected as instrumention site
# clusterFuncIDs: function ids in each interval in each cluster
#
# it returns:
# - a list of the coverrage percentage of each inst site in its phase
#   it's computed by dividing # of interval cover the inst piont by # of insterval of the 
#   related phase
# - a list of the coverrage percentage of each inst site over the whole execution
#   it's computed by dividing # of interval cover the inst piont by # of insterval of the
#   whole execution
#  
def find_coverage(phasesFuncIds, clusterFuncIDs):
    phaseCov = []
    fullCov = []
    # create an empty list of k list to hold coverages of each selected function
    for i, function in enumerate(phasesFuncIds):
        phaseCov.append([])
        fullCov.append([])
    for i, phase in enumerate(phasesFuncIds):
        # compute the count of each selected function in the related phase
        for j, func in enumerate(phase):
            count = 0.0
            for interv in clusterFuncIDs[i]:
                if func in interv:
                    count+=1
            # compute number of intervals containing selected function in the related phase
            noOfPhaseInter = len(clusterFuncIDs[i])
            # compute number of all intervals containing selected function
            # reduce is to apply a particular function passed in its argument to all
            # of the list elements mentioned in the sequence passed along.
            noOfAllInter = reduce(lambda count, l: count + len(l), clusterFuncIDs, 0)
            # compute phase coverage
            phaseCov[i].append(count/noOfPhaseInter)
            # compute full coverage
            fullCov[i].append(count/noOfAllInter)

    return(phaseCov,fullCov)

#-------------------------- end of find_coverage --------------------------#

# Find if there is overlapping between phases
# If a function appears in two different phases as an instrumentation point
# phases: list of phases with IDs of discovered inst sites
# k: number of clusters
# 
# it checks the inst points of each phase with inst points with other phases
#
# returns True if there is ovelapping, False otherwise
def is_overlapped(phases, k):
    overlapped = False
    for i in range(0, k):
        for f in phases[i]:
            for cl in range(0, k):
                # to not check inst points of the same phase
                if i == cl:
                    continue
                # check if the inst points of the current phase appeared in other phase
                # it checks func IDs and inst site
                if [m for m, v in enumerate(phases[cl]) if v[0] == f[0] and v[1]==f[1]] != []:
                    overlapped = True
    return overlapped

#-------------------------- end of is_overlapped --------------------------#


# Print phases with their instrumentation points(functions)
# phases: list of phases with IDs of discovered inst sites
# labels: list of labels of data samples
# fullCoverage: list of the coverrage percentage of each inst site over the whole execution
# phaseCoverage: a list of the coverrage percentage of each inst site in its phase
def print_clusters(phases, fullCoverage, phaseCoverage, k):
    threshold = 0.95
    totalPhaseCov = 0
    sortedFunc = []
    instPoints = []
    skippedFunc = []
    for i in range(0,k):
        sortedFunc.append([])
        instPoints.append([])
        skippedFunc.append([])
  
    for i in range(0,k):
        for j, f in enumerate(phases[i]):
            # add pahse and full coverage to each inst point
            f.append(phaseCoverage[i][j])
            f.append(fullCoverage[i][j])
    
        # sort functions in phases descendingly based on the phase coverage to select more representative functions
        phases[i].sort(key=lambda x:(x[2]),reverse=True)
    # create a file to print the inst points
    instfile = open("instpoints.txt", "w")
    instfile.write("\n\n")
    instfile.write("Clusers:\n")

    for i in range(0,k):
        instfile.write("###################\n")
        instfile.write("Phase {0}\n".format(str(i)))
        instfile.write("###################\n")
        instfile.write("{0:<10}{1:<10}{2:<20}{3:<30}{4:10}\n".format("FID","where","Full Coverage","Phase Coverage","Existed in other phases"))
        instfile.write("{0:<10}{1:<10}{2:<20}{3:<30}{4:10}\n".format("-----","-----","-------------","-------------","------------"))
        totalPhaseCov = 0.0

        for f in phases[i]:
            # consider functions that make phase coverage not greater than 100%, when overall phase 
            # coverage of all selected functions is less than the threshold
            if totalPhaseCov < threshold and (totalPhaseCov + f[2]) <= 1.0:
                totalPhaseCov += f[2]
                instPoints[i].append([f[0]])
                # print the inst point
                instfile.write("{0:<10}{1:<10}{2:<20.3f}{3:<30.3f}".format(int(int(f[0])), f[1],f[3],f[2]))
                instfile.write("[")
                # check and print the phases that have the inst point selected for this phase
                for cl in range(0,k):
                    if i == cl:
                        continue
                    if [m for m, v in enumerate(phases[cl]) if v[0] == f[0] and v[1]==f[1]] != []:
                        instfile.write("{0},".format(cl))
                instfile.write("]\n")
         
            else:
                # if function was not selected, skip and add it skipped functions
                skippedFunc[i].append(f)
                #totalPhaseCov += f[2]
         
    # print the function names of each phase
    instfile.write("\n\n--------------------------------\n Function names Per Phase\n--------------------------------\n")
    for i in range(0,k):
        instfile.write("###################\n")
        instfile.write("Phase {}\n".format(str(i)))
        instfile.write("###################\n")

        # get func names from the idmap using the func ID
        for f in instPoints[i]:
            if idmap != None and f[0] in idmap:
                instfile.write("{0}: {1}\n".format(f[0],idmap[f[0]]))
    # print the skipped functions
    instfile.write("\n\n--------------------------------\n Skipped Function names Per Phase\n--------------------------------\n")
    for i in range(0,k):
        instfile.write("###################\n")
        instfile.write("Phase {}\n".format(str(i)))
        instfile.write("###################\n")
        for f in skippedFunc[i]:
            if idmap != None and f[0] in idmap:
                instfile.write("{0}: {1} Phase Coverage {2:.3f}\n".format(f[0],idmap[f[0]],f[2]))
         
    instfile.close()
 
#-------------------------- end of print_clusters --------------------------#

#
# Main program
#
if len(sys.argv) != 6:
    print("Usage: {0} <svm-file> <svmfmap> <rank-file> <svmfile> <executable> <gmon-regex>".format(sys.argv[0]))
    exit(1)
   
datafile = open(sys.argv[1])
idmapFilename = sys.argv[2]
rfile = open(sys.argv[3])
ssfile = sys.argv[4]
print(type(ssfile))
method = sys.argv[5]
idmap = None
if idmapFilename != "":
    idmap = load_id_map(idmapFilename,True)


# load datasets in the svmlight / libsvm format into sparse CSR matrix
X, y = load_svmlight_file(ssfile)
# scale each feature by its maximum absolute value. 
transformer = MaxAbsScaler().fit(X)
scaled = transformer.transform(X).toarray()
# no pandas df = pd.read_csv("data.csv")
# no pandas df3 = df.iloc[:,1:]

# return a dense ndarray representation of this matrix
M =  X.toarray()

# linear dimensionality reduction using Singular Value Decomposition of the data to project it to a lower dimensional space.
pca = PCA(n_components=2)
# fit the model with X and apply the dimensionality reduction on X.
reduced_data = pca.fit_transform(M)

# plot the data, not used
"""for dpoint in reduced_data:
    plt.scatter(dpoint[0],dpoint[1])
plt.show()"""
"""interfile =  open("data.dat", "w")

for i in range(len(reduced_data)):
    interfile.write(str(reduced_data[i][0]))
    interfile.write(" ")
    interfile.write(str(reduced_data[i][1]))
    interfile.write("\n")"""
# list of k values
range_n_clusters = [1,2,3,4,5,6,7,8]
# run kmeans algorithim using different values of K(# of clusters)
kmeanrun = run_kmeans(X,range_n_clusters)
interias = kmeanrun[3]
silhouette = kmeanrun[4]
# optimal k
optK = 0
# find optimal k based on the specefied method
if method == "elbow":
    optK = find_optimalK_elbow(kmeanrun[2])[0]
else:
    optK = find_optimalK_silhouette(silhouette)


rank = find_rank(rfile)
clustdist = kmeanrun[1]
distances = clustdist[optK-1]

centroid = kmeanrun[5]
optcentroids = centroid[optK-1]
optlabels = kmeanrun[0][optK-1]
# find noOfClusters (optimal k)
# noOfClusters = max(optlabels) +1
clustWithDist = find_intervals(datafile, rank, distances, optlabels, optK)

P1 = find_inst_points(clustWithDist, optK)
# list of phases with IDs of discovered inst sites
Phases = P1[0]
# list of intervals in each cluster with their distances to the related cluster
SortedClusters = P1[1]
# function ids in each interval in each cluster
clusterFuncIDs = P1[2]
# list of clusters, where each cluster contain the ids of function selected as instrumention site
instFuncIDs = P1[3]
# find phase and full coverage for each discoverd inst site
phaseCov, fullCov = find_coverage(instFuncIDs,clusterFuncIDs)
overlapped = is_overlapped(Phases, optK)
# get the optK of the overlaped pahses
pathToOptK = []
pathToOptK.append(optK)

# If the produced phases are overlapped, decrement optimal k by 1
# and try to reproduce phases again
"""while(overlapped and optK>1):
    optK=optK -1
    pathToOptK.append(optK)
    distances = clustdist[optK-1]
    optcentroids = centroid[optK-1]
    optlabels = labels[optK-1]
    clust = kmeanrun[0][optK-1]
    datafile = open(sys.argv[1])
    clustWithDist = find_intervals(datafile,rank,distances,clust)
    P1 = find_inst_points(clustWithDist,clust)
    Phases = P1[0]
    SortedClusters = P1[1]
    clusterFuncIDs = P1[2]
    instFuncIDs = P1[3]

    overlapped = is_overlapped(Phases,clust)
    phaseCov,fullCov = find_coverage(instFuncIDs,clusterFuncIDs)"""

# print min(distances[0])
#indices = [i for i, x in enumerate(distances) if x == min(distances)]
# Show the values of optimal ks till the non-overlapped phases produced
for n in pathToOptK:
    print("{0}\t{1}".format(n,silhouette[n-1]))

# This part to plot the clusters, not used
"""colors = ['#8B0000', '#BC8F8F','#FFFF00','#008000','#FFC0CB', '#F0F8FF']
for p,red in enumerate(reduced_data):
    plt.scatter(red[0],red[1],c=colors[optlabels[p]], s=50)

plt.scatter(optcentroids[:,0],optcentroids[:,1],marker = "x",s=50,linewidths = 5,zorder = 10)
plt.show()"""

print_clusters(Phases, fullCov, phaseCov, optK)
# print labels in a file (debugging)
labelfile =  open("label.dat", "w")
for i in optlabels:
    labelfile.write(str(i))
    labelfile.write(" ")
#  labelfile.write("\n")
labelfile.write("\n")

#clusterfile = open("cluster.data", "w")
with open("cluster.data", "w") as clusterfile:
    for i,cluster in enumerate(SortedClusters):
        clusterfile.write("cluster:" + str(i) + "\n")
        wr = csv.writer(clusterfile)
        wr.writerows(SortedClusters[i])
clusterfile.close()
         
# print the interia, distortion and silhouette in different files for depugging      
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

