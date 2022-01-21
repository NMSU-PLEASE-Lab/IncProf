#!/usr/bin/python3

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

flatProfileData = {}

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
         print("Error: function with ID {0} already exists".format(fid))
      Node.nodeTable[fid] = self
   # update function if it already has an object
   def update(self,totTimePct,selfTime,totTime,numCalls):
      self.totTimePct = totTimePct
      self.selfTime = selfTime
      self.totTime = totTime
      self.numCalls = numCalls
   # update data from flat profile
   def updateFlatData(self,flatData):
      print("Update flat data")
   # print info of this function
   def printMe(self):
      print("Node: {0} {1}".format(self.id, self.name))
      print("  stats: {0} {1} {2} {3}".format(self.totTimePct, self.selfTime, self.totTime, self.numCalls))
      print("  depth: {0}".format(self.getMinDepth()))
      print("  callers:")
      for e in self.callerEdges:
         e.printMe("   ")
      print("  callees:")
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
         print("Error: no callee for edge")
      caller = Node.nodeTable[callerId]
      if caller == None:
         print("Error: no callee for edge")
      self.caller = caller
      self.callee = callee
      callee.callerEdges.append(self)
      caller.childEdges.append(self)
      self.numCalls = numCalls
      if callee.numCalls != totCalls:
         print("Error: callee numCalls not equal to totCalls: {0} {1}".
                                              format(callee.numCalls,totCalls))
   # print method
   def printMe(self,space):
      print("{0}from {1} to {2} count {3}".format(space, self.caller.id, 
                                                self.callee.id, self.numCalls))

#
# Read gprof table and create call graph objects
# param filename is the filename that the gprof output exists in
#
def createProfileGraph(filename):
   inCGTable = False
   inFlatTable = False
   inf = open(filename)
   while True:
      line = inf.readline()
      if inFlatTable:
         if len(line) < 2:
            inFlatTable = False
            continue
         processFlatProfileLine(line)
      if inCGTable:
         if len(line) < 2:
            inCGTable = False
            break
         processCallGraphSection(line, inf)
      if line.find("time   seconds   seconds    calls") > 0:
         inFlatTable = True
         continue
      if None != re.match("index\s+%\s+time\s+self\s+children\s+called",line):
         inCGTable = True
         print("In CG Table")

#
# Process a call graph section
# - incoming line is first line in section
#
def processCallGraphSection(line, fileh):
   haveCaller = False
   haveFunction = False
   needLine = False
   #print("CG first line: {0}".format(line), end='')
   while line.find("------------") < 0:
      if needLine:
         line = fileh.readline()
         needLine = False
      #print("CG processing line: {0}".format(line), end='')
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
         print("Caller: {0} {1} {2} {3} {4} {5}".format(callerName, callerId,
             callerSelfTime, callerChildTime, callerNumCalls, callerTotCalls))
         haveCaller = True
         needLine = True
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
         print("Function: {0} {1} {2} {3} {4} {5}".format(funcName, funcId, 
                 funcTotTimePct, funcSelfTime, funcChildrenTime, funcNumCalls))
         haveFunction = True
         needLine = True
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
         print("Child: {0} {1} {2} {3} {4} {5}".format(childName, childId, 
               childSelfTime, childChildrenTime, childNumCalls, childTotCalls))
         needLine = True
      else:  # must be end of section
         print("do end of section")
         # for now, ignore child info (not saved anyways)
         haveCaller = False
         haveFunction = False
         if not callerId in Node.nodeTable:
            n = Node(callerName,callerId,0,0,0,0)
         if not funcId in Node.nodeTable:
            n = Node(funcName,funcId,funcTotTimePct,funcSelfTime,0,funcNumCalls)
         else:
            n = Node.nodeTable[funcId]
            n.update(funcTotTimePct, funcSelfTime, 0, funcNumCalls)
         if funcName in flatProfileData:
            n.updateFlatData(flatProfileData)
         c = Edge(callerId,funcId,callerNumCalls,callerTotCalls)
         # do not set needLine since we'll return to caller after this

def processFlatProfileLine(line):
   # line is either a full data line or a "short" line
   print("flat line: {0}".format(line),end="")
   # try to match full line first
   v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
   short = 0
   if v != None:
      funcName = v.group(7)
   else:
      v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
      short = 1
   if v == None:
      print("Unknown flat profile line: {0}".format(line), end='')
      return False
   fpct = float(v.group(1))
   fttime = float(v.group(2))
   fstime = float(v.group(3))
   if short == 0:
      fcalls = int(v.group(4))
      # 5 and 6 are self ms/call and tot ms/call (TODO)
      funcName = v.group(7)
   else:
      fcalls = 0
      funcName = v.group(4)
   if funcName in flatProfileData:
      print("Error: function already in flat profile: {0}".format(funcName))
   flatProfileData[funcName] = (fpct,fstime,fcalls)
   return True

#
# Main
#
createProfileGraph(sys.argv[1])      

for n in Node.nodeTable:
   node = Node.nodeTable[n]
   node.printMe()

exit(0)

