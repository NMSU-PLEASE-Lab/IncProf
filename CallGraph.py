#---------------------------------------------------------------------
# CallGraph, Node, and Edge classes for dealing with gprof data
#---------------------------------------------------------------------

debug = False
doDot = False
maxDepth = 8
maxNameLen = 30  # for printing, but name is stored full length

# mostly for dot, which has trouble with lots of punctuation
# converts many punc symbols to underscores
# needed for complex C++ method names
def cleanName(name):
   trs = {32:95, 60:95, 62:95, 38:95, 42:95, 44:95, 58:95, 40:95, 41:95}
   return (name.translate(trs))

#
# Keep a function id->name mapping across all call graphs
#
functionIdMap = {}
nextFunctionID = 0
def getFunctionID(name):
   global functionIdMap, nextFunctionID
   # keep map of translated names??? I think it should work
   name = cleanName(name)
   if name not in functionIdMap:
      functionIdMap[name] = nextFunctionID
      nextFunctionID += 1
   return functionIdMap[name]

#
# Output the function id->name mapping, sorted
#
def outputFunctionMap(filename, factor=1, replicate=1):
   global functionIdMap
   names = {}
   # make list of IDs to sort, and id->name map
   ids = []
   for name in functionIdMap:
      nid = functionIdMap[name]
      ids.append(nid)
      names[nid] = name
   fout = open(filename,"w")
   first = True
   fout.write("{")
   for nid in sorted(ids):
      name = names[nid]
      for rep in range(replicate):
         if first:
            fout.write(' "{0}":"{1}"'.format(int((nid*factor)+rep), name))
            first = False
         else:
            fout.write(',\n "{0}":"{1}"'.format(int((nid*factor)+rep), name))
   fout.write("\n}")
   fout.close()

#
# Output libSVM formatted data for a CG set
# - filename is name of output file
# - cgs is a dictionary of call graphs, indexed
#   by integers, not necessarily consecutive
# mode is "time" or "timecalls"
#
def outputSVMData(filename,cgs,mode):
   fout = open(filename,"w")
   for i in sorted(cgs):
      if debug: print(cgs[i])
      cgs[i].outputLibSVMLine(fout,mode)
   fout.close()

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
      self.functionTimeThreshold = 0.01  # fraction of total
      # place to hold flat profile data until nodes are set up
      self.flatProfileData = {}
      self.totalExecutionTime = 0.001  # avoid divide by zero?
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
         print('{0} [label="{0}\\n{1}"]'.format(node.name[:maxNameLen], 
               node.selfTime+node.childTime))
      for eid in self.edgeTable:
         edge = self.edgeTable[eid]
         print('{0}->{1} [label="{2}"]'.format(edge.caller.name[:maxNameLen],
               edge.callee.name[:maxNameLen], edge.numCalls))
      print("}")
   #
   # Output graph info in one libsvm-formatted data line
   # TODO: Add depth-limiting options
   # Done: if all values end up 0, then don't output line at all
   #
   # ever?(node.selfTime+node.childTime)/self.totalExecutionTime), end="")
   def outputLibSVMLine(self,fout,mode="time"):
      # <label> <feature-id>:<feature-value> <feature-id>:<feature-value>
      line = ""
      for nid in sorted(self.nodeTable):
         node = self.nodeTable[nid]
         if node.minDepth < 0: 
            node.getMinDepth()
         if node.minDepth > maxDepth: continue
         if node.selfTime+node.childTime < 0.00001: continue
         if mode == "time":
            line = "{0} {1}:{2:.4f}".format(line, node.id,
                    node.selfTime+node.childTime)
         elif mode == "timecalls":
            line = "{0} {1}:{2:.4f} {3}:{4:.4f}".format(line,
                int(node.id*3), node.selfTime+node.childTime, 
                int(node.id*3+1), node.numCalls)
      if len(line) > 0:
         fout.write("{0} {1}\n".format(self.id,line))

   #
   # NOT USED: Output a function id->name mapping
   #
   def outputFunctionMap(self):
      print("{")
      for nid in self.nodeTable:
         node = self.nodeTable[nid]
         print('"{0}":"{1}",'.format(node.id, node.name))
      print("}")

   #
   # subtract another call graph's data from this one
   # - used to create interval data rather than cumulative
   #
   def subtractCallGraph(self,othercg):
      print("  subtract: selftime {0}   othertime {1}".format(
            self.totalExecutionTime, othercg.totalExecutionTime))
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
            print("No self function to subtract! ({0})".format(onode.name))
            continue
         # now merge stats from onode into snode
         #print("\n\n\nBefore subtraction")
         #snode.printMe()
         snode.subtractNodeData(onode)
         #print("After subtraction")
         #snode.printMe()
      # what do we do about edges?
      return True

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
   def __init__(self,cg,name,fid,totTimePct,selfTime,childTime,numCalls):
      self.cg = cg  # call graph that we are part of
      self.name = cleanName(name)
      # incoming fid doesn't work, so replace it
      fid = getFunctionID(name)
      self.id = fid
      self.totTimePct = totTimePct # from CG, %time column
      self.selfTime = selfTime     # from CG, self column (== flat self?)
      self.childTime = childTime       # from CG, self+children?
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
   def update(self,totTimePct,selfTime,childTime,numCalls):
      self.totTimePct = totTimePct
      self.selfTime = selfTime
      self.childTime = childTime
      self.numCalls = numCalls
   #
   # update data from flat profile tuple (fpct,fstime,fcalls)
   #
   def updateFlatData(self,flatData):
      if debug: print("Update from flat data")
      if flatData[0] > 0.0001:
         self.totTimePct = flatData[0]
      if flatData[1] > 0.0001:
         self.selfTime = flatData[1]
      if flatData[2] > 0:
         self.numCalls = flatData[2]
   #
   # print info of this function
   #
   def printMe(self):
      print("Node: {0} {1}".format(self.id, self.name[:maxNameLen]))
      print("  stats: tot%:{0} self:{1} tot:{2} calls:{3}".format(
         self.totTimePct, self.selfTime, self.childTime, self.numCalls))
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
      self.childTime = self.childTime + other.childTime
      self.numCalls = self.numCalls + other.numCalls
   #
   # subtract data from the same function in another call graph
   #
   def subtractNodeData(self, other):
      # just add pcts for now, factor will be applied later
      #self.totTimePct = self.totTimePct - other.totTimePct   TODO ???
      self.selfTime = self.selfTime - other.selfTime
      self.childTime = self.childTime - other.childTime
      self.numCalls = self.numCalls - other.numCalls

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
      if calleeId not in cg.nodeTable:
         print("Error: no callee {0} in table".format(calleeId))
         self.callee = None
      else:
         self.callee = cg.nodeTable[calleeId]
      if self.callee == None:
         print("Error: no callee for edge")
      if callerId not in cg.nodeTable:
         print("Error: no caller {0} in table".format(callerId))
         self.caller = None
      else:
         self.caller = cg.nodeTable[callerId]
      if self.caller == None:
         print("Error: no callee for edge")
      #self.caller = caller
      #self.callee = callee
      if self.callee: self.callee.callerEdges.append(self)
      if self.caller: self.caller.childEdges.append(self)
      self.numCalls = numCalls
      # not sure about this...is printing on valid data?
      #if self.callee.numCalls != totCalls:
      #   print("Error: callee numCalls not equal to totCalls: {0} {1}".
      #                format(self.callee.numCalls,totCalls))
      self.id = Edge.edgeID
      Edge.edgeID = Edge.edgeID + 1
      cg.edgeTable[self.id] = self
   #
   # print method
   #
   def printMe(self,space):
      print("{0}count {3} from {1}:{4}\n{0}           to {2}:{5}".format(space,
         self.caller.id, self.callee.id, self.numCalls, 
         self.caller.name[:maxNameLen], self.callee.name[:maxNameLen]))


