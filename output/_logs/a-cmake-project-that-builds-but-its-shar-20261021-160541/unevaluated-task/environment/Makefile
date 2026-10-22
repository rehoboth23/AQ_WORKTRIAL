# Legacy build system - NOT USED by CMake build
# Kept for historical reference only
# This Makefile contains outdated flags that may not work with current source

CXX ?= g++
CC ?= gcc
AR ?= ar

CXXFLAGS = -std=c++17 -O2 -Wall -Wextra -Wpedantic \
           -fno-rtti -fvisibility=hidden -fvisibility-inlines-hidden \
           -DAUDIOMIX_USE_DOUBLE=1 -DNDEBUG

CFLAGS = -O2 -Wall -fvisibility=hidden

LDFLAGS = -shared -Wl,--as-needed -Wl,--no-undefined
LDLIBS = -lm -lpthread

# Source directories
AUDIOMIX_SRCDIR = src/audiomix
AUDIOFORMAT_SRCDIR = src/audioformat
CLI_SRCDIR = src/cli

# Audiomix library sources
AUDIOMIX_SRCS = $(AUDIOMIX_SRCDIR)/processor.cpp \
                $(AUDIOMIX_SRCDIR)/pipeline.cpp \
                $(AUDIOMIX_SRCDIR)/analyze.cpp \
                $(AUDIOMIX_SRCDIR)/api.cpp

# Audioformat library sources
AUDIOFORMAT_SRCS = $(AUDIOFORMAT_SRCDIR)/wav_reader.cpp \
                   $(AUDIOFORMAT_SRCDIR)/wav_writer.cpp \
                   $(AUDIOFORMAT_SRCDIR)/format.cpp \
                   $(AUDIOFORMAT_SRCDIR)/runner.cpp

# CLI sources
CLI_SRCS = $(CLI_SRCDIR)/main.cpp $(CLI_SRCDIR)/cli.cpp

# Object directories
OBJDIR = obj
AUDIOMIX_OBJS = $(patsubst %.cpp,$(OBJDIR)/%.o,$(AUDIOMIX_SRCS))
AUDIOFORMAT_OBJS = $(patsubst %.cpp,$(OBJDIR)/%.o,$(AUDIOFORMAT_SRCS))
CLI_OBJS = $(patsubst %.cpp,$(OBJDIR)/%.o,$(CLI_SRCS))

# Targets
.PHONY: all clean install

all: libaudiomix.so libaudioformat.so audiomix-cli

libaudiomix.so: $(AUDIOMIX_OBJS)
	$(CXX) $(LDFLAGS) -o $@ $^ $(LDLIBS) -Wl,--version-script=audiomix.map

libaudioformat.so: $(AUDIOFORMAT_OBJS) libaudiomix.so
	$(CXX) $(LDFLAGS) -o $@ $(AUDIOFORMAT_OBJS) -L. -laudiomix $(LDLIBS)

audiomix-cli: $(CLI_OBJS) libaudioformat.so libaudiomix.so
	$(CXX) -o $@ $(CLI_OBJS) -L. -laudioformat -laudiomix -ldl $(LDLIBS)

$(OBJDIR)/%.o: %.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c -o $@ $<

clean:
	rm -f libaudiomix.so libaudioformat.so audiomix-cli
	rm -rf $(OBJDIR)

install: all
	install -d $(DESTDIR)/usr/lib
	install -d $(DESTDIR)/usr/bin
	install -m 755 libaudiomix.so $(DESTDIR)/usr/lib/
	install -m 755 libaudioformat.so $(DESTDIR)/usr/lib/
	install -m 755 audiomix-cli $(DESTDIR)/usr/bin/
