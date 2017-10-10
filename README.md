# IncProf
Incremental profiling based on gprof, with analysis tools


###How to Use Libipr

Libipr is an "incremental profiler" which means it generates gprof profiles
at a constant rate during application execution, rather than just one at 
the end. It does this by using the hidden function inside the gprof 
instrumentation that writes out the raw "gmon.out" profile data, and calls
this function from a signal handler that is invoked from an interval timer
signal (SIGVTALRM). 

Several Python scripts help setup Libipr and post-process the data it 
generates. To use all of the capabilities, follow these steps

0. Build libipr.so
1. Compile your application with "-pg" so that gprof profiling instrumentation
   is generated
2. Run "findwrgmon.py" with the full path to the system installed Gnu libc
   shared library file. It might be something like 
   "/lib/x86_64-linux-gnu/libc-2.23.so"
3. Use the offset from this as the value of the environment variable 
   IPR_GMONOFFSET
4. Set up other IPR environment variables as you wish, or not (use defaults)
5. Set the environment variable LD_PRELOAD to point to your libipr.so file
6. Run your application
7. Use "gensvm.py" to postprocess the sampled profile files; it currently needs
   you to supply the max sample number, so do an "ls" of where your sample
   files are and find the highest numbered "gmon-##.out" file. Redirect the 
   stdout output to a file for step 8
8. Use "cluster.py" to run clustering on the output file from step 7. This 
   script needs the Python sklearn package installed


### Sample Run Script for steps 3-6:
```
 #!/bin/sh
 # IPR_DATADIR -- directory for sample data files; default none (MUST EXIST!)
 export IPR_DATADIR=gdata

 # IPR_GMONOFFSET -- offset (hex or dec) from "moncontrol" symbol to write_gmon begin
 #export IPR_GMONOFFSET=-1360
 # Home NUC
 export IPR_GMONOFFSET=-1328

 # IPR_SECONDS -- seconds between profile sample writes (added to useconds)
 # IPR_USECONDS -- microseconds between profile sample writes (added to seconds)
 export IPR_SECONDS=0
 export IPR_USECONDS=250000

 # IPR_DEBUG -- 1 if want debug messages
 export IPR_DEBUG=1

 rm -f gmon-*.out gprof-*.out gdata/g*.out ipr-err.out ipr.log
 export LD_PRELOAD=./libipr.so
 ./testpr 30 2> ipr-err.out
 #---------end-sample-run-script---------
```

### Sample setps 7,8
```
./gensvm.py ./testpr 13 > ipr-13.svm
./cluster.py ipr-13.svm
```

