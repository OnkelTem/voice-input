.PHONY: all clean

all: whisper_helper.so

whisper_helper.so: whisper_helper.c
	gcc -shared -fPIC -o $@ $< \
		-I/projects/ai/whisper.cpp/include \
		-L/projects/ai/whisper.cpp/build/src -lwhisper \
		-Wl,-rpath,/projects/ai/whisper.cpp/build/src

clean:
	rm -f whisper_helper.so
