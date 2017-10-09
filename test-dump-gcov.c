#include <stdio.h>
#include <stdlib.h>

void __gcov_flush(void); /* check in gcc sources gcc/gcov-io.h for the prototype */

char *basename;

/**
* Dump GCOV data out -- when this happens, all the data is reset and
* the next dump covers just the interval from the last dump. Don't know
* if it is possible to change this.
**/

void gdump()
{
    static int dcount = 0;
    char ofname[128];
    char nfname[128];
    __gcov_flush();
    sprintf(ofname,"%s.gcda",basename);
    sprintf(nfname,"%s-%d.gcda",basename,dcount++);
    rename(ofname, nfname);
}

int g(int i, int n)
{
      if (i%n == 1) {
         printf("1\n");
      }
}

int main(int argc, char **argv)
{
   int i,n;
   basename = argv[0];
   if (--argc <= 0) {
      fprintf(stderr,"Usage: %s <count>\n",argv[0]);
      return -1;
   }

   n = strtol(argv[1],0,10);
   for (i=0; i < n; i++) {
      g(i,3);
      gdump();
   }
   return 0;
}

/**

Idea -- identify phase change when the gcov data changes drastically from
one dump to the next

**/



































