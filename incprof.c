#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <unistd.h>
#include <sys/time.h>
#include <signal.h>
#include <time.h>
#include <errno.h>
#include <pthread.h>
#include <libgen.h>

// Environment variables
// IPR_DATADIR -- directory for sample data files; default none
// IPR_GMONOFFSET -- offset (hex or dec) from "moncontrol" symbol to write_gmon begin
// IPR_SECONDS -- seconds between profile sample writes (added to useconds)
// IPR_USECONDS -- microseconds between profile sample writes (added to seconds)
// IPR_DEBUG -- 1 if want debug messages

//https://github.com/lattera/glibc/blob/master/gmon/gmon.c
// looking at source, calling monstartup after moncleanup 
// should work. (JEC: it doesn't, just segfaults)

// Offset from symbol moncontrol to hidden beginning of write_gmon()
// -- in looking at disassembled code, write_gmon code is in front of
//    moncontrol() function, so we just found the beginning by hand and
//    marked its file offset address
//
// For Acer laptop 32-bit
//#define WRGMON_OFFSET (0xf43f0 - 0xf4940)
// For trutta NUC 64 bit
#define WRGMON_OFFSET (0x108d80 - 0x1092b0)

// allow filename for samples to be configured with directory path
// - through environment variable
char sampleFilename[120] = "gmon-%d.out";

//
// Function pointer for write_gmon hidden C library function
//  
void (*write_gmon)(void) = NULL;

// tried to use monstartup to reinitialize data after moncleanup was
// called, but this totally failed, just kept segfaulting. So back to
// trying to find write_gmon(), which does work all by itself
//void (*gmon_start)(void) = NULL;
// for monstartup
//void (*gmon_start)(unsigned long lowpc, unsigned long highpc) = NULL;

//
// Initialization
// - set timer and signal handler
//    - check if already being used?
//
// Signal handler
// - write gmon.out and rename
// - reinstall handler and timer if needed
//
// Finalization
// - nothing?

void* libiprSigHandler();
static int debug = 0;
pthread_t pth;

__attribute__((constructor))
static void libiprInitialize()
{
   struct itimerval itv;
   struct itimerval old_itv;
   void (*old_sh)(int);
   char *paramstr;
   long int gmonOffset = WRGMON_OFFSET;
   int err;
   char exe[1024];
   int ret;

   //printf("libipr: start... \n");
   paramstr = getenv("IPR_APPNAME");
   if (!paramstr) {
	fprintf(stderr, "libipr: IPR_APPNAME missing\n");
	return;
   }

   /* Get the excutable name and check it with the Enviroment variable */
   ret = readlink("/proc/self/exe",exe,sizeof(exe)-1);
   if(ret ==-1) {
       fprintf(stderr,"libipr: ERROR can't get the executabel name \n");
       exit(1);
   }
   exe[ret] = 0;

   //fprintf(stderr, "libipr: IPR_APPNAME = %s and path = %s\n", paramstr, exe);
   /* if the excutable name is not similar to IPR_APPNAME then return */
   if (strcmp(basename(exe), paramstr) != 0) {
	fprintf(stderr, "libipr: wrong exec file, path is %s \n", exe);
	return;
   }

  
   paramstr = getenv("IPR_DEBUG");
   if (paramstr) {
      debug = strtol(paramstr,0,0);
   }

   if (debug)
      fprintf(stderr, "libipr: in library constructor\n");
   if (write_gmon != NULL) {
      if (debug) 
         fprintf(stderr, "libipr: constructor already ran\n");
      return;
   }

   // Set up filename pattern for sample files, if directory is given
   paramstr = getenv("IPR_DATADIR");
   if (paramstr) {
      if (strlen(paramstr) < sizeof(sampleFilename) - 15) {
         strcpy(sampleFilename,paramstr);
         if (sampleFilename[strlen(sampleFilename)-1] != '/')
            strcat(sampleFilename,"/");
         strcat(sampleFilename,"gmon-%d.out");
      }
   }

   // Set up pointer to write_gmon function, using offset found by hand
   // TODO: make this an environment variable offset and create python
   // script to find it automatically
   paramstr = getenv("IPR_GMONOFFSET");
   if (paramstr) {
      errno = 0;
      gmonOffset = strtol(paramstr,0,0);  // either dec or hex
      if (errno) {
         // do something
      }
   }
   if (write_gmon == NULL)
       write_gmon = (void (*)(void))dlsym(0, "moncontrol") + gmonOffset;
   if (write_gmon == NULL) {
       fprintf(stderr, "libipr: Unable to find moncontrol (write_gmon) function\n");
       fprintf(stderr, "libipr: -> Interval profiling will not be performed\n");
   }
   if (debug)
      fprintf(stderr, "libipr: done setting up write_gmon pointer\n");

   // set up timer and signal handler
   itv.it_interval.tv_sec = 0;
   itv.it_interval.tv_usec = 125000;  // 1/8 second
   paramstr = getenv("IPR_SECONDS");
   if (paramstr) {
      errno = 0;
      itv.it_interval.tv_sec = strtol(paramstr,0,0);
      if (errno) {
         // do something
      }
   }
   paramstr = getenv("IPR_USECONDS");
   if (paramstr) {
      errno = 0;
      itv.it_interval.tv_usec = strtol(paramstr,0,0);
      if (errno) {
         // do something
      }
   }
   itv.it_value = itv.it_interval;
   old_itv.it_interval.tv_sec = 0;
   old_itv.it_interval.tv_usec = 0;
   //setitimer(ITIMER_VIRTUAL, &itv, &old_itv);
   if (old_itv.it_interval.tv_sec != 0 || old_itv.it_interval.tv_usec != 0) {
      fprintf(stderr, "libipr: Warning, someone using ITIMER_VIRTUAL already!\n");
      fprintf(stderr, "libipr: --> Behavior is not predictable!\n");
   }
   if (debug)
      fprintf(stderr, "libipr: done setting up interval timer\n");

   err = pthread_create(&pth, NULL, &libiprSigHandler, NULL);
   if (err != 0)
	fprintf(stderr, "libipr: can't create thread :[%s]", strerror(err));

   // man page: use sigaction instead?
   /*old_sh = signal(SIGVTALRM, libiprSigHandler);
   if (old_sh != SIG_IGN && old_sh != SIG_DFL) {
      fprintf(stderr, "libipr: Warning, someone using SIGVTALRM already!\n");
      fprintf(stderr, "libipr: --> Behavior is not predictable!\n");
   }*/
   if (debug)
      fprintf(stderr, "libipr: done setting up signal handler, constructor done\n");
}

__attribute__((destructor))
static void libiprFinalize()
{
   if (debug)
      fprintf(stderr, "libipr: in library destructor\n");
   // nothing to do here? call to make sure one write-out
   //libiprSigHandler();
}

void* libiprSigHandler(void *arg)
{
   static int dcount = 0;
   char ofname[128];
   char nfname[128];
//   char cmd[1024];
   struct timespec stime;
   double ftime;
   FILE *lf;

   while (1) {
   if (debug)
      fprintf(stderr, "libipr: in signal handler\n");

   sprintf(nfname,"GMON_OUT_PREFIX=gmon-%d",dcount);
   /* OMAR */
   putenv(nfname);

   // check function pointer to be safe
   if (write_gmon == NULL)
       return;
   write_gmon();
   strcpy(ofname,"gmon.out");
  // sprintf(nfname,sampleFilename,dcount);
   if (debug)
      fprintf(stderr, "moving (%s) to (%s)\n",ofname,nfname);

   if (debug) {
   // record time of sample
   clock_gettime(CLOCK_THREAD_CPUTIME_ID, &stime);
   ftime = stime.tv_sec;
   ftime += ((double)stime.tv_nsec)/1e9;
   lf = fopen("ipr.log","a");
   if (lf) {
      fprintf(lf,"sample %d at %g ( %s )\n",dcount,ftime,ctime(0));
      fclose(lf);
   }
   }
   dcount++;
   // redo timer and handler?
   if (debug)
      fprintf(stderr, "libipr: done with signal handler\n");
   usleep(1000000);
   }
}


// OLD stuff: tried to use moncleanup and monstartup, but didn't work
/*
       if (write_gmon == NULL)
          //gmon_start = dlsym(0, "monstartup");
          //gmon_start = (void (*)(void))dlsym(0, "__gmon_start__");
       if (write_gmon == NULL)
          fprintf(stderr, "Unable to find gprof exit hook\n");
       else 
          gmon_start();
          //gmon_start(0,0xffffffff);
*/

