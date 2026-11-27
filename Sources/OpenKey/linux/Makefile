# OpenKey for Linux - builds the shared OpenKey engine (../engine) as libopenkey.so
CXX        ?= g++
CXXFLAGS   ?= -O2 -g
# the shared engine; a release tarball carries its own copy in ./engine
ENGINE_DIR ?= $(if $(wildcard engine/Engine.cpp),engine,../engine)
CXXFLAGS   += -std=c++17 -fPIC -DLINUX -I$(ENGINE_DIR) -Wall -Wno-deprecated-declarations -Wno-sign-compare
ENGINE_SRC  = Engine.cpp Vietnamese.cpp Macro.cpp SmartSwitchKey.cpp ConvertTool.cpp
OBJ         = build/openkey_api.o $(addprefix build/engine/,$(ENGINE_SRC:.cpp=.o))

all: build/libopenkey.so

build/openkey_api.o: src/openkey_api.cpp $(wildcard $(ENGINE_DIR)/*.h)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c $< -o $@

build/engine/%.o: $(ENGINE_DIR)/%.cpp $(wildcard $(ENGINE_DIR)/*.h)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c $< -o $@

build/libopenkey.so: $(OBJ)
	$(CXX) -shared -o $@ $(OBJ)

test: build/libopenkey.so
	python3 -I tests/test_engine.py

# end-to-end test through a private ibus-daemon (does not touch the desktop's IBus)
test-ibus: build/libopenkey.so
	python3 -I tests/test_ibus.py

install: build/libopenkey.so
	./install.sh

VERSION := $(shell python3 -I src/openkey_ibus.py --version)
DIST    := openkey-linux-$(VERSION)-$(shell uname -m)

# self-contained release tarball (engine copied in, library prebuilt)
dist: build/libopenkey.so
	rm -rf build/$(DIST) && mkdir -p build/$(DIST)/build build/$(DIST)/engine
	cp -r src data tests Makefile install.sh uninstall.sh README.md build/$(DIST)/
	cp -r $(ENGINE_DIR)/*.h $(ENGINE_DIR)/*.cpp $(ENGINE_DIR)/platforms build/$(DIST)/engine/
	cp ../../../LICENSE build/$(DIST)/ 2>/dev/null || cp LICENSE build/$(DIST)/
	cp build/libopenkey.so build/$(DIST)/build/
	find build/$(DIST) -name __pycache__ -prune -exec rm -rf {} +
	tar -C build -czf build/$(DIST).tar.gz $(DIST)
	@echo build/$(DIST).tar.gz

clean:
	rm -rf build

.PHONY: all test test-ibus install dist clean
