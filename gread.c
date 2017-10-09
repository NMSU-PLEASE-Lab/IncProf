// Aborted attempt to read and process raw gcov data on my own. Should not
// be needed, actually. -- JEC

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define IN_GCOV 1
#undef IN_LIBGCOV

#include <gcov-io.h>

int gcovReadMeta(char *filename);
int gcovReadData(char *filename);

int main(int argc, char **argv)
{
   int stat,i;
   char *fn;
   // need arg and it should be reasonable
   if (--argc <= 0 || strlen(argv[1])>255) {
      fprintf(stderr,"Usage: %s <gcov-root-filename>\n",argv[0]);
      return -1;
   }
   // fn is initialized with root filename without extension
   fn = (char*) malloc(strlen(argv[1]+10));
   // create fn for gcov notes file and read
   strcpy(fn,argv[1]);
   strcat(fn,".gcno");
   gcovReadMeta(fn);
   // create fn for gcov data file and read
   strcpy(fn,argv[1]);
   strcat(fn,".gcda");
   gcovReadData(fn);
   return 0;
}

int gcovReadData(char *filename)
{
   int stat;
   unsigned int i,n;
   unsigned int magic, version, timestamp;
   unsigned int header_tag, header_length;
   struct gcov_summary summary;
   struct gcov_ctr_summary *ctrsum;

   // in gcov.cc, mode = 0 is read+append, 1 is read, -1 is write?
   stat = __gcov_open(filename,1);
   if (!stat) {
      fprintf(stderr,"Error %d: unable to open %s\n",stat,filename);
      return -1;
   }
   printf("GCOV DATA FILE\n");
   
   magic = __gcov_read_unsigned();
   version = __gcov_read_unsigned();
   timestamp = __gcov_read_unsigned();
   printf("Magic: %x   Version: %x   Timestamp: %x\n", 
          magic, version, timestamp);

   while (1) {
      header_tag = __gcov_read_unsigned();
      if (header_tag == 0)
         break;
      header_length = __gcov_read_unsigned();
      printf("  Record tag %x   length: %d ===> ", 
             header_tag, header_length); //, sizeof(summary));
      if (header_tag == GCOV_TAG_PROGRAM_SUMMARY) {
         gcov_bucket_type *hbucket;
         printf("Program summary record\n");
         __gcov_read_summary(&summary);
         ctrsum = &(summary.ctrs[0]);
         printf("  num:%d runs:%d sumall:%ld runmax:%ld summax:%ld\n",
                ctrsum->num, ctrsum->runs, ctrsum->sum_all, ctrsum->run_max,
                ctrsum->sum_max);
         for (i=0; i<GCOV_HISTOGRAM_SIZE; i++) {
            hbucket = &(ctrsum->histogram[i]);
            if (hbucket->num_counters == 0)
               continue;
            printf("    num:%u  min:%ld  cum:%ld\n", hbucket->num_counters,
                   hbucket->min_value, hbucket->cum_value);
         }
      } else if (header_tag == GCOV_TAG_FUNCTION)  {
         unsigned int ident, lsum, csum;
         printf("Function record\n");
         ident = __gcov_read_unsigned();
         lsum = __gcov_read_unsigned();
         csum = __gcov_read_unsigned();
         printf("  ident:%x  lineno-checksum:%x  cfg-checksum:%x\n",
                ident, lsum, csum);
      } else if (header_tag == GCOV_TAG_COUNTER_BASE)  {
         uint64_t count0, fcalls, broccur, brtaken, count4;
         n = GCOV_TAG_COUNTER_NUM(header_length);
         printf("Counter record: %d counters\n", n);
         fcalls = __gcov_read_counter();
         printf("  %ld function calls\n", fcalls);
         for (i=1; i < n-1; i+=2) {
            broccur = __gcov_read_counter();
            brtaken = __gcov_read_counter();
            printf("  %ld branch occur, %ld taken\n", broccur, brtaken);
         }
         for (; i < n; i++) {
            count0 = __gcov_read_counter();
            printf("  %ld unknown counter\n", count0);
         }
      } else {
         unsigned int gdata;
         printf("Unknown record type\n");
         //for (i=0; i < header_length; i++) {
         //   gdata = __gcov_read_unsigned();
         //   printf("  %x", gdata);
         //}
         //printf("\n");
      }
   }
      
   stat = __gcov_close();
   fprintf(stderr,"Close stat: %d\n",stat);
   return 0;
}


int gcovReadMeta(char *filename)
{
   int stat;
   unsigned int i,n;
   unsigned int magic, version, timestamp, checksum;
   unsigned int header_tag, header_length;
   struct gcov_summary summary;
   struct gcov_ctr_summary *ctrsum;
   char rstring[512];

   // in gcov.cc, mode = 0 is read+append, 1 is read, -1 is write?
   stat = __gcov_open(filename,1);
   if (!stat) {
      fprintf(stderr,"Error %d: unable to open %s\n",stat,filename);
      return -1;
   }
   printf("GCOV NAMES (META) FILE\n");
   
   magic = __gcov_read_unsigned();
   version = __gcov_read_unsigned();
   timestamp = __gcov_read_unsigned();
   checksum = 0x00; //__gcov_read_unsigned();
   printf("Magic: %x   Version: %x   Timestamp: %x   Checksum: %x\n", 
          magic, version, timestamp, checksum);
   //rstring = __gcov_read_string();
   //printf("Source: %s\n", rstring);
   
   while (1) {
      header_tag = __gcov_read_unsigned();
      if (header_tag == 0)
         break;
      header_length = __gcov_read_unsigned();
      printf("  Record tag %x   length: %d ===> ", 
             header_tag, header_length);
      if (header_tag == GCOV_TAG_PROGRAM_SUMMARY) {
         gcov_bucket_type *hbucket;
         printf("Program summary record\n");
         __gcov_read_summary(&summary);
         ctrsum = &(summary.ctrs[0]);
         printf("  num:%d runs:%d sumall:%ld runmax:%ld summax:%ld\n",
                ctrsum->num, ctrsum->runs, ctrsum->sum_all, ctrsum->run_max,
                ctrsum->sum_max);
         for (i=0; i<GCOV_HISTOGRAM_SIZE; i++) {
            hbucket = &(ctrsum->histogram[i]);
            if (hbucket->num_counters == 0)
               continue;
            printf("    num:%u  min:%ld  cum:%ld\n", hbucket->num_counters,
                   hbucket->min_value, hbucket->cum_value);
         }
      } else if (header_tag == GCOV_TAG_FUNCTION)  {
         unsigned int csum, sdata;
         printf("Function record\n");
         csum = __gcov_read_unsigned();
         memset(rstring,0,sizeof(rstring));
         for(i=0; i < header_length-1; i++) {
            sdata = __gcov_read_unsigned();
            *((unsigned int *) (rstring+i*4)) = sdata;
         }
         printf("  checksum:%x source:(%s)\n", csum, rstring);
      } else if (header_tag == GCOV_TAG_BLOCKS)  {
         unsigned int gdata;
         printf("Blocks record: %d # blocks\n", header_length);
         for (i=0; i < header_length; i++) {
            gdata = __gcov_read_unsigned();
            printf("  %x", gdata);
         }
         printf("\n");
      } else if (header_tag == GCOV_TAG_ARCS)  {
         unsigned int bbno, bbto, bbflags, gdata;
         bbno = __gcov_read_unsigned();
         printf("Arcs record: BBID %d\n",bbno);
         for (i=0; i < header_length/2; i++) {
            bbto = __gcov_read_unsigned();
            bbflags = __gcov_read_unsigned();
            printf("  to %d (%x)", bbto, bbflags);
         }
         printf("\n");
      } else if (header_tag == GCOV_TAG_LINES)  {
         unsigned int bbno, dat0, dat1, dat2, lstart, lend, gdata;
         bbno = __gcov_read_unsigned();
         dat0 = __gcov_read_unsigned();
         dat1 = __gcov_read_unsigned();
         dat2 = __gcov_read_unsigned();
         lstart = __gcov_read_unsigned();
         lend = __gcov_read_unsigned();
         printf("Line record: BBID %d start %d end %d\n",bbno,lstart,lend);
         printf("  %x %x %x ||", dat0, dat1, dat2);
         n = header_length - 6;
         for (i=0; i < n; i++) {
            gdata = __gcov_read_unsigned();
            printf("  %x", gdata);
         }
         printf("\n");
      } else {
         unsigned int gdata;
         printf("Unknown record type\n");
         for (i=0; i < header_length; i++) {
            gdata = __gcov_read_unsigned();
            printf("  %x", gdata);
         }
         printf("\n");
      }
   }
      
   stat = __gcov_close();
   fprintf(stderr,"Close stat: %d\n",stat);
   return 0;
}


