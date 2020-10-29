# IncProf
Incremental profiling based on gprof, with analysis tools

This version of IncProf is an improvement in the version that has been developed by Omar Azziz. This version follows the algorithms of IncProf (Sample Set Reduction and Iterative Evaluation Algorithm)

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
7.Use "sampleSetReduction.py" post-process the sampled profile files; it currently needs
   you to supply the regular expression for the list of filenames you want to process, 
   so do an "ls" of where your sample files and make your expression. Redirect the 
   stdout output to a file (gmon.data) which contains functions call count for all
   functions and produce a rank file that will be used in steps 8 and 9.
8. Use "gensvm.py" to post-process the sampled profile files; it currently needs
   you to supply the regular expression for the list of filenames you want to process, 
   so do an "ls" of where your sample files and make your expression. Redirect the 
   stdout output to a file for step 8 
9. Use "algorithm2.py" to find phases and instrumentation points. 



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

 rm -f gmon.* *.dat ipr-err.out ipr.log svmfmap.txt svmfmap.txt
 export LD_PRELOAD=./libipr.so
 ./testpr 230 2> ipr-err.out
 #---------end-sample-run-script---------
```

### Sample setps 7-11
```
export LD_PRELOAD=""
proc_num=$(ls gmon-* | head -n 1 | cut -d "." -f2)
# Generate data file with functions time difference and function
# call count and rank file for each function
echo "### Generate Data file and rank file"
python ${IncProf_PATH}/sampleSetReduction.py $1 "$gmon_regexp" > gmon.data
# Generate the SVM file which is used as an input for Kmeans clustering
echo "### Generate SVM file"
python ${IncProf_PATH}/gensvm.py $1 "$gmon_regexp" rank.svm > gmon.svm

# print the best instrumentation points for elbowk
echo "### find phases and inst points using elbow or silhouette methods($3)"
python ${IncProf_PATH}/algorithm2.py gmon.data svmfmap.txt rank.svm gmon.svm $2 $3> instPoints.out


```


# All-in-one script:
# -----------------

### Sample steps 7-11 all-in-one script
```
export LD_PRELOAD=""
./RunAllScripts.sh ./testpr elbow
```

