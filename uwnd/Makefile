CC ?= gcc

ifeq ($(CC),cl)
CFLAGS=/Iuwnd /O2
LDFLAGS=user32.lib gdi32.lib advapi32.lib
EXE=.exe

%: %.c uwnd/uwnd.c
	$(CC) $(CFLAGS) $< uwnd/uwnd.c /link $(LDFLAGS) /OUT:$@$(EXE)
else
CFLAGS=-Iuwnd -O3

ifeq ($(OS),Windows_NT)
LDFLAGS=-luser32 -lgdi32
else
LDFLAGS=-lX11 -lm -lfontconfig
endif

%: %.c uwnd/uwnd.c
	$(CC) $< uwnd/uwnd.c $(CFLAGS) $(LDFLAGS) -o $@
endif

.PHONY: deps
deps:
	mkdir -p uwnd/uwnd_core/stb
	curl -L https://raw.githubusercontent.com/nothings/stb/refs/heads/master/stb_truetype.h -o uwnd/uwnd_core/stb/stb_truetype.h