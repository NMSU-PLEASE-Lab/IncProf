#!/usr/bin/python

#
# Find the address and offset of hidden "write_gmon" in libc
# Usage: findwrgmon.py <pathname-of-libc>

# Based on manual inspection, the hidden "write_gmon" function is
# the function code that is just before the exposed "moncontrol" 
# function. So we find the beginning of a function just before the 
# moncontrol symbol, and output its address and offset from moncontrol
#
# This uses "objdump -d" to dump the C library and then searches the 
# output using a pipe

import re;
import sys;
import os;
import subprocess;
import platform;

#
# Main program
#
if len(sys.argv) != 2:
   print "Usage: {0} <c-library-filename>".format(sys.argv[0])
   exit(1)
   
libfname = sys.argv[1]

arch = platform.architecture()[0]
#arch = "32bit"
if arch=="32bit":
   keyInsn = "push   %ebp"  # 32-bit first insn in function
else:
   keyInsn = "push   %rbp"  # 64-bit first insn in function

p = subprocess.Popen(["/usr/bin/objdump","-d",libfname],stdout=subprocess.PIPE)

lastaddr = 0
for line in p.stdout:
   #print line
   v = re.match("\s*0*([^\s]*) <moncontrol@*.*>:", line)
   if v != None:
      print "moncontrol at {0}, write_gmon at {1}".format(v.group(1),lastaddr),
      print "decimal offset:", int(lastaddr,16)-int(v.group(1),16)
      print "export IPR_GMONOFFSET={0}".format(int(lastaddr,16)-int(v.group(1),16))
      break
   v = re.match("\s*([^\s:]*):\t([^\t]*)\t([^\n\r]*)", line)
   if v == None:
      continue;
   #print v.group(1), v.group(2), v.group(3) 
   insn = v.group(3)
   addr = v.group(1)
   if insn == keyInsn:
      #print v.group(1), v.group(2), v.group(3) 
      lastaddr = addr


