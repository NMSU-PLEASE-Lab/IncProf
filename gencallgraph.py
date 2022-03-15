#!/usr/bin/python3
#---------------------------------------------------------------------
#
# Generate call graph data from gprof call graph table
# and flat profile
#
# Usage: gencallgraph.py <gprof-text-output-filename>

#
# This script calculates a call graph from the tables that gprof
# outputs, along with data on each function
#
# TODO: optional output to JSON format
#---------------------------------------------------------------------

import re
import sys
import os
import glob
import argparse
import copy
import math
import CallGraph

debug = False
doDot = False
maxDepth = 3

#---------------------------------------------------------------------
# Read gprof data and create call graph objects
# param filename is the filename that the gprof output exists in
#---------------------------------------------------------------------
def createProfileGraph(filename,id):
   inCGTable = False    # true when we are processing DG data lines
   inFlatTable = False  # true when we are processing flat data lines
   inf = open(filename)
   if inf is None:
      print("ERROR: no such file ({0})".format(filename))
      return None
   cgraph = CallGraph.CallGraph(id)
   while True:
      line = inf.readline()
      if line == "":
         break;
      if inFlatTable:
         # we leave the flat profile table when we see an empty line
         if len(line) < 2:
            inFlatTable = False
            # if total execution time is 0.0, then skip this CG entirely
            if cgraph.totalExecutionTime < 0.0001:
               inf.close()
               return None
            continue
         # else process the data line
         processFlatProfileLine(line, cgraph)
      if inCGTable:
         # we leave the cg profile table when we see an empty line
         if len(line) < 2:
            inCGTable = False
            break  # leave the entire loop, since rest of file is not used
         # else process the data line
         processCallGraphSection(line, inf, cgraph)
      # header of flat profile signals we are in it
      if line.find("time   seconds   seconds    calls") > 0:
         inFlatTable = True
         continue
      # header of call graph profile signals we are in it
      if None != re.match("index\s+%\s+time\s+self\s+children\s+called",line):
         inCGTable = True
         if debug: print("In CG Table")
   inf.close()
   # if we read to end, something went wrong
   if line == "":
      return None
   return cgraph

#---------------------------------------------------------------------
# Process a call graph section
# - incoming line is first line in section (a caller line)
# - sections have caller lines, the function, and then callees
#---------------------------------------------------------------------
def processCallGraphSection(line, fileh, cgraph):
   isCallerLine = False
   isFunctionLine = False
   isCalleeLine = False
   needLine = False
   callers = []
   if debug: print("CG first line: {0}".format(line), end='')
   # a horizontal line separator indicates end of section
   while line.find("------------") < 0:
      if needLine:
         line = fileh.readline()
         if line.find("------------") >= 0:
            break
         needLine = False
      if debug: print("CG processing line: {0}".format(line), end='')
      # line beginning with "[#]" is the current function; lines before
      # it are callers, lines after are callees; logic below handles this
      if line[0] == '[':
         isFunctionLine = True
         isCallerLine = False
         isCalleeLine = False
      else:
         if isFunctionLine is False and isCalleeLine is False:
            isCallerLine = True
         else:
            isFunctionLine = False
            isCalleeLine = True
            isCallerLine = False   # should already be
      if debug: print("Line flags are: {0} {1} {2}".format(isCallerLine, isFunctionLine, isCalleeLine))
      # First line in section is the callee, or "<spontaneous>"
      if isCallerLine:
         if debug: print("process caller line")
         caller = {}
         done = False
         # match line like "                   <spontaneous>"
         if None != re.match("\s+<spontaneous>",line):
            caller['name'] = "_spontaneous_"
            caller['id'] = CallGraph.getFunctionID(caller['name'])
            caller['selftime'] = 0.0
            caller['childtime'] = 0.0
            caller['numcalls'] = 0
            caller['totcalls'] = 0
            done = True
         # match line like "          0.02    0.22      10/10          main [1]"
         v = re.match("\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+)/(\d+)\s+(.+) \[(\d+)\]",line)
         if v is not None and done is not True:
            caller['name'] = v.group(5)
            #caller['id'] = int(v.group(6)) not consistent
            caller['id'] = CallGraph.getFunctionID(v.group(5))
            caller['selftime'] = float(v.group(1))
            caller['childtime'] = float(v.group(2))
            caller['numcalls'] = int(v.group(3))
            caller['totcalls'] = int(v.group(4))
            done = True
         # match line of just num-calls and func name and id
         v = re.match("\s+(\d+)\s+(.+) \[(\d+)\]",line)
         if v is not None and done is not True:
            caller['name'] = v.group(2)
            #caller['id'] = int(v.group(3)) not consistent
            caller['id'] = CallGraph.getFunctionID(v.group(2))
            caller['selftime'] = 0.0
            caller['childtime'] = 0.0
            caller['numcalls'] = int(v.group(1))
            caller['totcalls'] = int(v.group(1))
            done = True
         if debug: print("Caller: {0} {1} {2} {3} {4} {5}".format(caller['name'],
              caller['id'], caller['selftime'], caller['childtime'], caller['numcalls'],
              caller['totcalls']))
         callers.append(caller)
         needLine = True
         continue
      # Handle the line that is this function's callgraph info
      elif isFunctionLine:
         if debug: print("process function line")
         done = False
         # match line like "[2]     49.0    0.02    0.22      10         p1g [2]"
         v = re.match("\[(\d+)\]\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+)\s+(.+) \[(\d+)\]",line)
         if v is not None: # and len(v.group) == 6:
            funcName = v.group(6)
            #funcId = int(v.group(1)) not consistent
            funcId = CallGraph.getFunctionID(funcName)
            funcTotTimePct = float(v.group(2))
            funcSelfTime = float(v.group(3))
            funcChildrenTime = float(v.group(4))
            funcNumCalls = int(v.group(5))
            done = True
         # line like "[1]     47.9    1.04    0.00  308963+8       unsign..."
         v = re.match("\[(\d+)\]\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+)\+(\d+)\s+(.+) \[(\d+)\]",line)
         if v is not None and done is not True:
            funcName = v.group(7)
            #funcId = int(v.group(1)) not consistent
            funcId = CallGraph.getFunctionID(funcName)
            funcTotTimePct = float(v.group(2))
            funcSelfTime = float(v.group(3))
            funcChildrenTime = float(v.group(4))
            funcNumCalls = int(v.group(5))
            done = True
         # line like "[1]     95.9    0.00    0.47                 main [1]"
         v = re.match("\[(\d+)\]\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(.+) \[(\d+)\]",line)
         if v is not None and done is not True:
            funcName = v.group(5)
            #funcId = int(v.group(1)) not consistent
            funcId = CallGraph.getFunctionID(funcName)
            funcTotTimePct = float(v.group(2))
            funcSelfTime = float(v.group(3))
            funcChildrenTime = float(v.group(4))
            funcNumCalls = 0
            done = True
         # line like "[1]            0.00    0.47      3/8          main [1]"
         v = re.match("\[(\d+)\]\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+)/(\d+)\s+(.+) \[(\d+)\]",line)
         if v is not None and done is not True:
            funcName = v.group(6)
            #funcId = int(v.group(1)) not consistent
            funcId = CallGraph.getFunctionID(funcName)
            funcTotTimePct = 0.0
            funcSelfTime = float(v.group(2))
            funcChildrenTime = float(v.group(3))
            funcNumCalls = 0
            done = True
         if debug: print("Function: {0} {1} {2} {3} {4} {5}".format(funcName, 
                  funcId, funcTotTimePct, funcSelfTime, funcChildrenTime,
                  funcNumCalls))
         needLine = True
         continue
      elif isCalleeLine:
         if debug: print("process callee line")
         # Rest of lines in section are children, until dash separator line
         # like "                0.02    0.22      10/10          p1g [2]"
         v = re.match("\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+)/(\d+)\s+(.+) \[(\d+)\]",line)
         if v != None:
            # we extract the child info and print it, but don't do anything else
            # with it for now, but maybe in the future
            childName = v.group(5)
            #childId = int(v.group(6)) not consistent
            childId = CallGraph.getFunctionID(childName)
            childSelfTime = float(v.group(1))
            childChildrenTime = float(v.group(2))
            childNumCalls = int(v.group(3))
            childTotCalls = int(v.group(4))
            if debug: print("Child: {0} {1} {2} {3} {4} {5}".format(childName, 
                childId, childSelfTime, childChildrenTime, childNumCalls,
                childTotCalls))
         needLine = True
   # END loop while line.find("------------") < 0:
   if debug: print("do end of section {0}".format(line))
   # limit function nodes to only those above a threshhold
   # TODO needs more work, and generalization
   # - assumes flat profile came first (always does)
   if (funcSelfTime+funcChildrenTime) / cgraph.totalExecutionTime <  cgraph.functionTimeThreshold:
      return False
   if not funcId in cgraph.nodeTable:
      n = CallGraph.Node(cgraph,funcName,funcId, funcTotTimePct, funcSelfTime,
                  funcChildrenTime, funcNumCalls)
   else:
      n = cgraph.nodeTable[funcId]
      n.update(funcTotTimePct, funcSelfTime, funcChildrenTime,
               funcNumCalls)
   if funcName in cgraph.flatProfileData:
      n.updateFlatData(cgraph.flatProfileData[funcName])
   for caller in callers:
      if not caller['id'] in cgraph.nodeTable:
         n = CallGraph.Node(cgraph,caller['name'],caller['id'],0,0,0,0)
      c = CallGraph.Edge(cgraph,caller['id'],funcId,caller['numcalls'],caller['totcalls'])
   return True

#---------------------------------------------------------------------
# Process one line in the flat profile data section
# - lines are either full data lines or partial (short) data lines
# Full:
#  %   cumulative   self              self     total           
# time   seconds   seconds    calls   s/call   s/call  name    
# 58.67    291.42   291.42        1   291.42   291.89  void miniFE::cg_solve
# Partial: does not have calls and call stats
# -cumulative seconds is useful to track total execution time (last line)
#---------------------------------------------------------------------
def processFlatProfileLine(line, cgraph):
   totalExecutionTime = 0.0
   # line is either a full data line or a "short" line
   if debug: print("flat line: {0}".format(line),end="")
   # try to match full line first
   v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
   short = 0
   if v == None:
      # now try to match short line
      v = re.match("\s*(\d+\.\d+)\s*(\d+\.\d+)\s*(\d+\.\d+)\s*([^\n\r]*)", line)
      short = 1
   if v == None:
      print("Unknown flat profile line: {0}".format(line), end='')
      return False
   fpct = float(v.group(1))
   totalExecutionTime = float(v.group(2))  # last line will be final total
   fstime = float(v.group(3))
   if short == 0:
      fcalls = int(v.group(4))
      # 5 and 6 are self ms/call and tot ms/call (TODO)
      funcName = v.group(7)
   else:
      fcalls = 0
      funcName = v.group(4)
   if funcName in cgraph.flatProfileData:
      print("Error: already in flat profile: {0}".format(funcName))
   cgraph.flatProfileData[funcName] = (fpct,fstime,fcalls)
   cgraph.totalExecutionTime = totalExecutionTime
   return True

#---------------------------------------------------------------------
# Reduce a collection of call graphs by some factor N, done by
# coalescing N sequential call graphs
#---------------------------------------------------------------------
def reduceCGSequence(cgs, factor):
   newcgs = {}
   newcgid = 1
   count = 0
   if debug: print("reduce {0} graphs...".format(len(cgs)))
   for cgi in sorted(cgs):
      if count == 0:
         # start out new reduction call graph
         if debug: print("start a new graph")
         cg = copy.deepcopy(cgs[cgi])
         newcgs[newcgid] = cg
         newcgid= newcgid + 1
         count = count + 1
         continue
      # add in the next call graph
      cg.mergeCallGraphs(cgs[cgi])
      count = count + 1
      if count == factor:
         cg.applyMergeFactor(factor)
         count = 0
   if count > 0:
      cg.applyMergeFactor(count+1)
   return newcgs

#---------------------------------------------------------------------
# Main
#---------------------------------------------------------------------
argParser = argparse.ArgumentParser(description='Gprof data manipulator')
argParser.add_argument('--debug', action='store_true', help='turn on debugging info (default off)')
argParser.add_argument('--dot', action='store_true', help='output Dot graph format (default: off)')
argParser.add_argument('--depth', action='store', type=int, default=20, help='limit function call depth (default 20)')
argParser.add_argument('--text', action='store', default='gprof.txt', metavar='<gprof-report-file>', help='filename of text gprof report')
argParser.add_argument('--bin', action='store', nargs=2, metavar='<filename>', help='invoke gprof on <exectuable gmon.out> pair')
argParser.add_argument('--bindir', action='store', nargs=2, metavar='<name>', help='invoke gprof on all profiles in <exectuable directory> pair')
argParser.add_argument('--dirpat', action='store', default=".*\.(\d+)", help='regex for filename parsing, must have one (\d+)')
argParser.add_argument('--mode', action='store', default="time", help="SVM data: either 'time' or 'timecalls'")
args = argParser.parse_args()
debug = args.debug
doDot = args.dot
textFile = args.text
maxDepth = args.depth
dirPattern = args.dirpat
mode = args.mode

if args.bindir is None:
   #
   # Single profile data file
   #
   if args.bin is not None:
      if debug: print("do gprof report generation")
      textFile = "{0}.txt".format(args.bin[1])
      os.system("gprof {0} {1} > {2}".format( args.bin[0], args.bin[1],
                textFile))

   cgraph = createProfileGraph(textFile,1)

   if doDot:
      cgraph.outputDot()
      exit(0)

   # default action: print nodes in call graph
   for n in cgraph.nodeTable:
      node = cgraph.nodeTable[n]
      node.printMe()
   exit(0)

else:
   #
   # Directory full of profile data (binary)
   # - assumes data files end with sequential numbers
   #   representing their ordering (of, e.g., intervals)
   #
   if debug: print("Processing directory {0}/".format(args.bindir[1]))
   cgs = {}
   maxind = 0
   sd = os.scandir(args.bindir[1])
   for f in sd:
      if not f.is_file():
         print("filename {0} is not a regular file".format(f.name))
         continue
      v = re.match(dirPattern,f.name)
      if v is None:
         if debug: print("filename {0} does not match pattern |{1}|".format(
                         f.name, dirPattern))
         continue
      ind = int(v.group(1))
      proFile = "{0}/{1}".format(args.bindir[1],f.name)
      textFile = "{0}.txt".format(proFile)
      print("do gprof report generation ({0})".format(proFile))
      os.system("gprof {0} {1} > {2}".format(args.bindir[0], proFile, 
                textFile))
      cgraph = createProfileGraph(textFile,ind)
      if cgraph is None:
         print("No profile info could be read for {0}".format(proFile))
         continue
      os.system("rm -f {0}".format(textFile))
      cgs[ind] = cgraph
      if ind > maxind: maxind = ind
      # default action: print nodes in call graph
      #for n in cgraph.nodeTable:
      #   node = cgraph.nodeTable[n]
      #   node.printMe()
   # convert dict into ordered list (use it instead of dict???)
   cglist = []
   for i in range(maxind+1):
      if i in cgs and cgs[i] != None:
         cglist.append(cgs[i])
   print("Read {0} profiles...".format(maxind))
   # CallGraph data must be subtracted starting at end!
   # - might be missing some indices
   inds = []
   for i in reversed(range(1,maxind+1)):
      if i in cgs:
         inds.append(i)
   for i in range(len(inds)-1):
      print("subtracting CG {0} from CG {1}".format(inds[i+1],inds[i]))
      cgs[inds[i]].subtractCallGraph(cgs[inds[i+1]])
   CallGraph.outputSVMData("cldata.svm",cgs,mode)
   #for i in range(maxind):
   #   if debug: print(cgs[i+1])
   #   cgs[i+1].outputLibSVMLine()
   #print("------------------------------------------")
   factor = 2
   # just testing reduction here below
   cgs = reduceCGSequence(cgs, factor)
   CallGraph.outputSVMData("cldata2.svm",cgs,mode)
   #for i in range(math.ceil(maxind/factor)):
   #   if debug: print(cgs[i+1])
   #   cgs[i+1].outputLibSVMLine()
   #print("------------------------------------------")
   if mode == "timecalls": 
      CallGraph.outputFunctionMap("names.map",3,2)
   else:
      CallGraph.outputFunctionMap("names.map",1,1)

exit(0)


