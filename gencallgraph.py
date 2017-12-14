#!/usr/bin/python

#
# Generate call graph data from gprof call graph table
# Usage: gencov.py <gprof-output-filename>

#
# This script calculates a call graph from the table that gprof
# outputs
#
# TODO: optional output in JSON format
# TODO: keep global structure of edges, too (maybe?)

import re;
import sys;
import os;
import glob;

#
# Node in call graph is a function
# - keeps stats, and lists of edges to callers and callees
# 
class Node(object):
   # keep table of all objects, index is function ID
   nodeTable = {}
   def __init__(self,name,fid,totTimePct,selfTime,totTime,numCalls):
      self.name = name
      self.id = fid
      self.totTimePct = totTimePct
      self.selfTime = selfTime
      self.totTime = totTime
      self.numCalls = numCalls
      self.callerEdges = []
      self.childEdges = []
      self.minDepth = -1
      if fid in Node.nodeTable:
         print "Error: function with ID", fid, "already exists"
      Node.nodeTable[fid] = self
   # update function if it already has an object
   def update(self,totTimePct,selfTime,totTime,numCalls):
      self.totTimePct = totTimePct
      self.selfTime = selfTime
      self.totTime = totTime
      self.numCalls = numCalls
   # print info of this function
   def printMe(self):
      print "Node:", self.id, self.name
      print "  stats:", self.totTimePct, self.selfTime, self.totTime, self.numCalls
      print "  depth:", self.getMinDepth()
      print "  callers:"
      for e in self.callerEdges:
         e.printMe("   ")
      print "  callees:"
      for e in self.childEdges:
         e.printMe("   ")
   # figure out and return min call depth that this function 
   # is called at (future use in ranking function importance)
   def getMinDepth(self):
      if self.minDepth >= 0:  # already calculated
         return self.minDepth;
      curDepth = 9999999
      d = curDepth
      for e in self.callerEdges:
         d = e.caller.getMinDepth()
         if d < curDepth:
            curDepth = d;
      if d == 9999999: # must be <spontaneous>
         self.minDepth = 0
      else:
         self.minDepth = d + 1
      return self.minDepth

#
# Edge objects keep connections between functions
# - will eventually keep more stats
#
class Edge(object):
   def __init__(self,callerId,calleeId,numCalls,totCalls):
      callee = Node.nodeTable[calleeId]
      if callee == None:
         print "Error: no callee for edge"
      caller = Node.nodeTable[callerId]
      if caller == None:
         print "Error: no callee for edge"
      self.caller = caller
      self.callee = callee
      callee.callerEdges.append(self)
      caller.childEdges.append(self)
      self.numCalls = numCalls
      if callee.numCalls != totCalls:
         print "Error: callee numCalls not equal to totCalls",callee.numCalls,totCalls
   # print method
   def printMe(self,space):
      print space, "from", self.caller.id, "to", self.callee.id, "count", self.numCalls

#
# Read gprof table and create call graph objects
# param filename is the filename that the gprof output exists in
#
def createCallGraph(filename):
   inTable = False
   haveCaller = False
   haveFunction = False
   inf = open(filename)
   for line in inf:
      # skip to call graph table area
      if not inTable:
         if None != re.match("index\s+%\s+time\s+self\s+children\s+called",line):
            inTable = True
         continue
      # mark end of table and don't process anymore lines (could be break)
      if None != re.match("Index by function name",line):
         inTable = False
         continue;
      print "In Table:", len(line), line, 
      if len(line) < 5:
         # is an empty line and must be end of table (could be break here)
         continue
      # First line in section is the callee, or "<spontaneous>"
      if not haveCaller:
         # match line like "                   <spontaneous>"
         if None != re.match("\s+<spontaneous>",line):
            callerName = "<spontaneous>"
            callerId = 0
            callerSelfTime = 0.0
            callerChildTime = 0.0
            callerNumCalls = 0
            callerTotCalls = 0
         # match line like "          0.02    0.22      10/10          main [1]"
         else:
            v = re.match("\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+)/(\d+)\s+(\S+)\s+\[(\d+)\]",line)
            callerName = v.group(5)
            callerId = int(v.group(6))
            callerSelfTime = float(v.group(1))
            callerChildTime = float(v.group(2))
            callerNumCalls = int(v.group(3))
            callerTotCalls = int(v.group(4))
         print "Caller:", callerName, callerId, callerSelfTime, callerChildTime, callerNumCalls, callerTotCalls
         haveCaller = True
         continue
      # Second line in section must be this function; will be missing numcalls
      # if from spontaneous
      if not haveFunction:
         # match line like "[2]     49.0    0.02    0.22      10         p1g [2]"
         v = re.match("\[(\d+)\]\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+)\s+(\S+)",line)
         if v != None: # and len(v.group) == 6:
            funcName = v.group(6)
            funcId = int(v.group(1))
            funcTotTimePct = float(v.group(2))
            funcSelfTime = float(v.group(3))
            funcChildrenTime = float(v.group(4))
            funcNumCalls = int(v.group(5))
         else:
            # line like "[1]     95.9    0.00    0.47                 main [1]"
            v = re.match("\[(\d+)\]\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\S+)",line)
            funcName = v.group(5)
            funcId = int(v.group(1))
            funcTotTimePct = float(v.group(2))
            funcSelfTime = float(v.group(3))
            funcChildrenTime = float(v.group(4))
            funcNumCalls = 0
         print "Function:", funcName, funcId, funcTotTimePct, funcSelfTime, funcChildrenTime, funcNumCalls
         haveFunction = True
         continue
      # Rest of lines in section are children, until dash separator line
      # like "                0.02    0.22      10/10          p1g [2]"
      v = re.match("\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+)/(\d+)\s+(\S+)\s+\[(\d+)\]",line)
      if v != None:
         # we extract the child info and print it, but don't do anything else
         # with it for now, but maybe in the future
         childName = v.group(5)
         childId = int(v.group(6))
         childSelfTime = float(v.group(1))
         childChildrenTime = float(v.group(2))
         childNumCalls = int(v.group(3))
         childTotCalls = int(v.group(4))
         print "Child:", childName, childId, childSelfTime, childChildrenTime, childNumCalls, childTotCalls
      else:  # must be end of section
         print "do end of section"
         # for now, ignore child info (not saved anyways)
         haveCaller = False
         haveFunction = False
         if not callerId in Node.nodeTable:
            c = Node(callerName,callerId,0,0,0,0)
         if not funcId in Node.nodeTable:
            c = Node(funcName,funcId,funcTotTimePct,funcSelfTime,0,funcNumCalls)
         else:         
            Node.nodeTable[funcId].update(funcTotTimePct,funcSelfTime,0,funcNumCalls)
         c = Edge(callerId,funcId,callerNumCalls,callerTotCalls)
               
#
# Main
#
createCallGraph(sys.argv[1])      

for n in Node.nodeTable:
   node = Node.nodeTable[n]
   node.printMe()

exit(0)

