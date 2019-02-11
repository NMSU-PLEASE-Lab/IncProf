# IncProf
Incremental profiling based on gprof, with analysis tools


### How to Use Libipr

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
   script needs the Python sklearn package installed. This script will create
   two csv files (bestk cluster and elbow cluster)
9. Use "gendata.py" to process the new sampled profile files and create a 
   timestamp with functions time difference and functions call count
10. Use "findmostused.py" to process the data file and get the most used 
    functions with or without recording the function call count. This 
    function take 0 or 1 flag as input; 0 time difference only / 1 time and count 
11. Use "findinstr.py" to process either the bestk cluster or elbow cluster. This 
    script finds the best instrumention points in the application


# Indivitual steps:
# ----------------

### Sample Run Script for steps 3-6:
```
 #!/bin/sh
 # IPR_DATADIR -- directory for sample data files; default none (MUST EXIST!)
 export IPR_DATADIR=gdata

 # IPR_GMONOFFSET -- offset (hex or dec) from "moncontrol" symbol to write_gmon begin
 #export IPR_GMONOFFSET=-1360
 # Home NUC
 #export IPR_GMONOFFSET=-1328
 export IPR_GMONOFFSET=-1264

 # IPR_SECONDS -- seconds between profile sample writes (added to useconds)
 # IPR_USECONDS -- microseconds between profile sample writes (added to seconds)
 export IPR_SECONDS=1
 #export IPR_USECONDS=250000

 # IPR_APPNAME -- the application name ( the executable name )
 export IPR_APPNAME='testpr'

 # IPR_DEBUG -- 1 if want debug messages
 export IPR_DEBUG=1

 rm -f gmon* gprof-*.out gdata/g*.out ipr-err.out ipr.log cluster.*out* elb_distance.csv svmfmap.txt result.* gmon.* cluster.bestk cluster.elbowk
 export LD_PRELOAD=./libipr.so
 ./testpr 230 2> ipr-err.out
 #---------end-sample-run-script---------
```

### Sample setps 7,8
```
export LD_PRELOAD=""
proc_num=$(ls gmon-* | head -n 1 | cut -d "." -f2)
python gensvm.py ./testpr "gmon-*.${proc_num}" > gmon.svm
python cluster.py gmon.svm svmfmap.txt flip > cluster.out
```

### Sample steps 9-11
```
python gendata.py ./testpr "gmon-*.${proc_num}" > gmon.data
python findmostused.py gmon.data 1 > gmon.count.svm
python findinstr.py cluster.elbowk gmon.count.svm svmfmap.txt > result.elbowk
```


# All-in-one script:
# -----------------

### Sample steps 7-11 all-in-one script
```
./DiscoverInst.sh ./testpr
```

