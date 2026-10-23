CC      = gcc
CFLAGS  = -O2 -Wall -Wextra -std=c11
LDFLAGS =

route: main.o route.o
	$(CC) $(LDFLAGS) -o $@ $^

main.o: main.c route.h
	$(CC) $(CFLAGS) -c -o $@ $<

route.o: route.c route.h
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f *.o route

.PHONY: clean
