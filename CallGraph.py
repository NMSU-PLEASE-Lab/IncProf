#---------------------------------------------------------------------
# CallGraph, Node, and Edge classes for dealing with gprof data
#---------------------------------------------------------------------

debug = False
doDot = False
maxDepth = 20

def cleanName(name):
   trs = {32:95, 60:95, 62:95, 38:95, 42:95, 44:95, 58:95, 40:95, 41:95}
   return (name.translate(trs))[:30]


#---------------------------------------------------------------------
# Top level object for a call graph
# reason: we will extend to read in multiple profiles (from intervals),
#         so each one will be represented by a CallGraph object
#---------------------------------------------------------------------
class CallGraph(object):
   callgraphID = 1
   #
   # constructor
   #
   def __init__(self,id):
      # place to hold flat profile data until nodes are set up
      self.flatProfileData = {}
      # keep table of all objects, index is function ID (# assigned by gprof)
      # "<spontaneous>" is ID 0
      self.nodeTable = {}
      # keep edges, but what is edge ID?
      self.edgeTable = {}
      self.id = id
      #self.id = CallGraph.callgraphID
      #CallGraph.callgraphID = CallGraph.callgraphID + 1
   #
   # Output a Dot-formatted representation of the profiled call graph
   #
   def outputDot(self):
      print("digraph {")
      for nid in self.nodeTable:
         node = self.nodeTable[nid]
         print('{0} [label="{0}\\n{1}"]'.format(node.name, 
               node.selfTime+node.totTime))
      for eid in self.edgeTable:
         edge = self.edgeTable[eid]
         print('{0}->{1} [label="{2}"]'.format(edge.caller.name,
               edge.callee.name, edge.numCalls))
      print("}")
   #
   # Output graph info in one libsvm-formatted data line
   # TODO: Add depth-limiting options
   #
   def outputLibSVMLine(self):
      # <label> <feature-id>:<feature-value> <feature-id>:<feature-value>
      print("{0}".format(self.id), end="")
      for nid in self.nodeTable:
         node = self.nodeTable[nid]
         if node.minDepth < 0: 
            node.getMinDepth()
         if node.minDepth > maxDepth: continue
         print(' {0}:{1}'.format(node.id,
               node.selfTime+node.totTime), end="")
      print("")
   #
   # Output a function id->name mapping
   #
   def outputFunctionMap(self):
      for nid in self.nodeTable:
         node = self.nodeTable[nid]
         print('{0}:{1}'.format(node.id, node.name))
   #
   # merge another call graph's data into this one
   #
   def mergeCallGraphs(self,othercg):
      for nid in othercg.nodeTable:
         onode = othercg.nodeTable[nid]
         snode = None
         if nid in self.nodeTable and onode.name == self.nodeTable[nid].name:
            snode = self.nodeTable[nid]
         else:
            for sid in self.nodeTable:
               if onode.name == self.nodeTable[sid].name:
                  snode = self.nodeTable[sid]
                  break
         if snode is None:
            continue
         # now merge stats from onode into snode
         snode.mergeNodeData(onode)
      # what do we do about edges?
   #
   # apply the merge factor to any percentages
   # 
   def applyMergeFactor(self, factor):
      for nid in self.nodeTable:
         node = self.nodeTable[nid]
         node.totTimePct = node.totTimePct / float(factor)

#---------------------------------------------------------------------
# Node: a node in call graph, represents a function
# - keeps stats, and lists of edges to callers and callees
#---------------------------------------------------------------------
class Node(object):
   #
   # constructor
   #
   def __init__(self,cg,name,fid,totTimePct,selfTime,totTime,numCalls):
      self.cg = cg  # call graph that we are part of
      self.name = cleanName(name)
      self.id = fid
      self.totTimePct = totTimePct # from CG, %time column
      self.selfTime = selfTime     # from CG, self column (== flat self?)
      self.totTime = totTime       # from CG, self+children?
      self.numCalls = numCalls     # from CG, called (== flat calls?)
      self.callerEdges = []
      self.childEdges = []
      self.minDepth = -1
      if fid in cg.nodeTable:
         print("Error: function with ID {0} already exists".format(fid))
      cg.nodeTable[fid] = self
   #
   # update function data if it already has an object
   #
   def update(self,totTimePct,selfTime,totTime,numCalls):
      self.totTimePct = totTimePct
      self.selfTime = selfTime
      self.totTime = totTime
      self.numCalls = numCalls
   #
   # update data from flat profile
   #
   def updateFlatData(self,flatData):
      if debug: print("Update from flat data")
   #
   # print info of this function
   #
   def printMe(self):
      print("Node: {0} {1}".format(self.id, self.name))
      print("  stats: tot%:{0} self:{1} tot:{2} calls:{3}".format(
         self.totTimePct, self.selfTime, self.totTime, self.numCalls))
      print("  depth: {0}".format(self.getMinDepth()))
      print("  callers:")
      for e in self.callerEdges:
         e.printMe("   ")
      print("  callees:")
      for e in self.childEdges:
         e.printMe("   ")
   #
   # figure out and return min call depth that this function 
   # is called at (future use in ranking function importance)
   #
   def getMinDepth(self):
      if self.minDepth >= 0:  # already calculated
         return self.minDepth;
      curDepth = 9999999
      if self.minDepth == -2:
         return curDepth
      d = curDepth
      self.minDepth = -2  # marker for already in recursion
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
   # merge data from the same function in another call graph
   #
   def mergeNodeData(self, other):
      # just add pcts for now, factor will be applied later
      self.totTimePct = self.totTimePct + other.totTimePct
      self.selfTime = self.selfTime + other.selfTime
      self.totTime = self.totTime + other.totTime
      self.numCalls = self.numCalls + other.numCalls

#---------------------------------------------------------------------
# Edge objects keep connections between functions
# - will eventually keep more stats
# - TODO need more data and capabilities
#---------------------------------------------------------------------
class Edge(object):
   edgeID = 1
   #
   # constructor
   #
   def __init__(self,cg,callerId,calleeId,numCalls,totCalls):
      self.cg = cg
      self.callee = cg.nodeTable[calleeId]
      if self.callee == None:
         print("Error: no callee for edge")
      self.caller = cg.nodeTable[callerId]
      if self.caller == None:
         print("Error: no callee for edge")
      #self.caller = caller
      #self.callee = callee
      self.callee.callerEdges.append(self)
      self.caller.childEdges.append(self)
      self.numCalls = numCalls
      if self.callee.numCalls != totCalls:
         print("Error: callee numCalls not equal to totCalls: {0} {1}".
                      format(self.callee.numCalls,totCalls))
      self.id = Edge.edgeID
      Edge.edgeID = Edge.edgeID + 1
      cg.edgeTable[self.id] = self
   #
   # print method
   #
   def printMe(self,space):
      print("{0}from {1}:{4} to {2}:{5} count {3}".format(space,
         self.caller.id, self.callee.id, self.numCalls, self.caller.name,
         self.callee.name))


