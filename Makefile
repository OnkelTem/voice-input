.PHONY: all static clean

all: static whisper_helper.so

static:
	python3 scripts/generate_icons.py
	python3 scripts/generate_sounds.py

voice_input/whisper_helper.so: whisper_helper.c
	gcc -shared -fPIC -o $@ $< \
		-I/projects/ai/whisper.cpp/include \
		-L/projects/ai/whisper.cpp/build/src -lwhisper \
		-Wl,-rpath,/projects/ai/whisper.cpp/build/src

clean:
	rm -f voice_input/whisper_helper.so
	rm -f voice_input/static/*.svg
	rm -f voice_input/static/*.wav
