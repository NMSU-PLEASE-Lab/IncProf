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
import CallGraph as cg

debug = False
doDot = False
maxDepth = 20

#---------------------------------------------------------------------
# Read gprof table and create call graph objects
# param filename is the filename that the gprof output exists in
#---------------------------------------------------------------------
def createProfileGraph(filename,id):
   inCGTable = False    # true when we are processing DG data lines
   inFlatTable = False  # true when we are processing flat data lines
   inf = open(filename)
   # TODO error handling here
   cgraph = cg.CallGraph(id)
   while True:
      line = inf.readline()
      if inFlatTable:
         # we leave the flat profile table when we see an empty line
         if len(line) < 2:
            inFlatTable = False
            continue
         # else process the data line
         processFlatProfileLine(line, cgraph)
      if inCGTable:
         # we leave the flat profile table when we see an empty line
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
   return cgraph

#---------------------------------------------------------------------
# Process a call graph section
# - incoming line is first line in section (a caller line)
# - sections have caller lines, the function, then callees
#---------------------------------------------------------------------
def processCallGraphSection(line, fileh, cgraph):
   haveCaller = False
   haveFunction = False
   needLine = False
   if debug: print("CG first line: {0}".format(line), end='')
   # a horizontal line separator indicates end of section
   while line.find("------------") < 0:
      if needLine:
         line = fileh.readline()
         needLine = False
      if debug: print("CG processing line: {0}".format(line), end='')
      # First line in section is the callee, or "<spontaneous>"
      if not haveCaller:
         # match line like "                   <spontaneous>"
         if None != re.match("\s+<spontaneous>",line):
            callerName = "_spontaneous_"
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
         if debug: print("Caller: {0} {1} {2} {3} {4} {5}".format(callerName,
              callerId, callerSelfTime, callerChildTime, callerNumCalls,
              callerTotCalls))
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
         if debug: print("Function: {0} {1} {2} {3} {4} {5}".format(funcName, 
                  funcId, funcTotTimePct, funcSelfTime, funcChildrenTime,
                  funcNumCalls))
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
         if debug: print("Child: {0} {1} {2} {3} {4} {5}".format(childName, 
             childId, childSelfTime, childChildrenTime, childNumCalls,
             childTotCalls))
         needLine = True
      else:  # must be end of section
         if debug: print("do end of section")
         # for now, ignore child info (not saved anyways)
         haveCaller = False
         haveFunction = False
         if not callerId in cgraph.nodeTable:
            n = cg.Node(cgraph,callerName,callerId,0,0,0,0)
         if not funcId in cgraph.nodeTable:
            n = cg.Node(cgraph,funcName,funcId, funcTotTimePct, funcSelfTime,
                     funcChildrenTime, funcNumCalls)
         else:
            n = cgraph.nodeTable[funcId]
            n.update(funcTotTimePct, funcSelfTime, funcChildrenTime,
                     funcNumCalls)
         if funcName in cgraph.flatProfileData:
            n.updateFlatData(cgraph.flatProfileData)
         c = cg.Edge(cgraph,callerId,funcId,callerNumCalls,callerTotCalls)
         # do not set needLine since we'll return to caller after this

#---------------------------------------------------------------------
# Process one line in the flat profile data section
# - lines are either full data lines or partial (short) data lines
#---------------------------------------------------------------------
def processFlatProfileLine(line, cgraph):
   # line is either a full data line or a "short" line
   if debug: print("flat line: {0}".format(line),end="")
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
   if funcName in cgraph.flatProfileData:
      print("Error: function already in flat profile: {0}".format(funcName))
   cgraph.flatProfileData[funcName] = (fpct,fstime,fcalls)
   return True

#---------------------------------------------------------------------
# Reduce a collection of call graphs by some factor N, done by
# coalescing N sequential call graphs
#---------------------------------------------------------------------
def reduceCGSequence(cgs, factor):
   newcgs = {}
   newcgid = 1
   count = 0
   print("reduce {0} graphs...".format(len(cgs)))
   for cgi in cgs:
      if count == 0:
         # start out new reduction call graph
         print("start a new graph")
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
args = argParser.parse_args()
debug = args.debug
doDot = args.dot
textFile = args.text
maxDepth = args.depth

if args.bindir is None:
   #
   # Single profile data file
   #
   if args.bin is not None:
      if debug: print("do gprof report generation")
      textFile = "{0}.txt".format(args.bin[1])
      os.system("gprof {0} {1} > {2}".format( args.bin[0], args.bin[1],
                textFile))

   cgraph = createProfileGraph(textFile)

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
   cgs = {}
   maxind = 0
   sd = os.scandir(args.bindir[1])
   for f in sd:
      if not f.is_file(): continue
      v = re.match(".*(\d+)",f.name)
      if v is None:
         print("filename {0} does not end with a number".format(f.name))
         continue
      ind = int(v.group(1))
      proFile = "{0}/{1}".format(args.bindir[1],f.name)
      textFile = "{0}.txt".format(proFile)
      if debug: print("do gprof report generation ({0})".format(proFile))
      os.system("gprof {0} {1} > {2}".format(args.bindir[0], proFile, 
                textFile))
      cgraph = createProfileGraph(textFile,ind)
      os.system("rm -f {0}".format(textFile))
      cgs[ind] = cgraph
      if ind > maxind: maxind = ind
      # default action: print nodes in call graph
      #for n in cgraph.nodeTable:
      #   node = cgraph.nodeTable[n]
      #   node.printMe()
   for i in range(maxind):
      if debug: print(cgs[i+1])
      cgs[i+1].outputLibSVMLine()
   print("----")
   factor = 2
   # just testing reduction here below
   cgs = reduceCGSequence(cgs, factor)
   for i in range(math.ceil(maxind/factor)):
      if debug: print(cgs[i+1])
      cgs[i+1].outputLibSVMLine()
   print("----")
   cgraph.outputFunctionMap()

exit(0)


