CC ?= gcc

ifeq ($(CC),cl)
CFLAGS=/Iuwnd /Iinc /O2
LDFLAGS=user32.lib gdi32.lib advapi32.lib
EXE=.exe

%: %.c uwnd/uwnd.c
	$(CC) $(CFLAGS) $< uwnd/uwnd.c /link $(LDFLAGS) /OUT:build/$@$(EXE)
else
CFLAGS=-Iuwnd -Iinc -O3

ifeq ($(OS),Windows_NT)
LDFLAGS=-luser32 -lgdi32
else
LDFLAGS=-lX11 -lm -lfontconfig
endif

%: %.c uwnd/uwnd.c
	$(CC) $< uwnd/uwnd.c $(CFLAGS) $(LDFLAGS) -o build/$@
endif

.PHONY: deps
deps:
	mkdir -p uwnd/uwnd_core/stb
	mkdir -p build
	curl -L https://raw.githubusercontent.com/nothings/stb/refs/heads/master/stb_truetype.h -o uwnd/uwnd_core/stb/stb_truetype.h
	curl -L https://raw.githubusercontent.com/nothings/stb/refs/heads/master/stb_image.h -o uwnd/uwnd_core/stb/stb_image.h
	curl -L https://raw.githubusercontent.com/nothings/stb_image_resize/refs/heads/main/stb_image_resize2.h -o uwnd/uwnd_core/stb/stb_image_resize2.h