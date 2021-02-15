#
# Make libipr (incremental profiling) and the test program testpr
#

all: libipr.so testpr

libipr.so: incprof.c
	gcc -shared -fPIC incprof.c -o libipr.so -ldl -lrt

testpr: testpr.c
	gcc -pg testpr.c -o testpr

clean: 
	rm -rf *.o libipr.so *.gcda *out testpr

#
# Other stuff below here is just experimentation with gcov
#
test-dump-gcov: test-dump-gcov.c
	gcc -fprofile-arcs -ftest-coverage test-dump-gcov.c -o test-dump-gcov

gread: gread.c
	gcc -fprofile-arcs -ftest-coverage -I. gread.c -lgcov -o gr

