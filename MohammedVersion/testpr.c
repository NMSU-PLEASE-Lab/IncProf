
#include <stdio.h>
#include <stdlib.h>

int p1f(int n)
{
   int i, k=0;
   for (i=0; i < n; i++)
   {
      k += (int) (i*0.852);
   }
   return k;
}

int p1g(int i, int n)
{
   int k;
   for (k=0; k<1000000; k++) {
      if (k%(i+1)==0)
         k++;
      if ((i*k)%n == 1) {
         //printf("1\n");
         p1f(k/1000);
      }
   }
}

int p2f(int n)
{
   int i, k=0;
   for (i=0; i < n; i++)
   {
      k += (int) (i*0.852);
   }
   return k;
}

int p2g(int i, int n)
{
   int k;
   for (k=0; k<1000000; k++) {
      if (k%(i+1)==0)
         k++;
      if ((i*k)%n == 1) {
         //printf("1\n");
         p2f(k/1000);
      }
   }
}

int main(int argc, char **argv)
{
   int i,n;
   //basename = argv[0];
   if (--argc <= 0) {
      fprintf(stderr,"Usage: %s <count>\n",argv[0]);
      return -1;
   }
   n = strtol(argv[1],0,10);
   for (i=0; i < n; i++) {
      p1g(i,39);
   }
   for (i=0; i < n; i++) {
      p2g(i,39);
   }
   for (i=0; i < n; i++) {
      p1g(i,39);
   }
   for (i=0; i < n; i++) {
      p2g(i,39);
   }
   return 0;
}

/**

Idea -- identify phase change when the gcov data changes drastically from
one dump to the next

**/

