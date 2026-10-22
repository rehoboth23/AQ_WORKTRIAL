CC = gcc
CFLAGS = -Wall -O2
LDFLAGS = -L/usr/local/lib
LIBS = -lgraph -lm

gcomp: main.o
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ $(LIBS)

main.o: main.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f gcomp *.o

.PHONY: clean
