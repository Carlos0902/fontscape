#!/bin/zsh
set -eu
cd "${0:A:h:h}"
mkdir -p .build
swiftc Sources/SystemFontEngine/*.swift Tests/SystemFontEngineChecks/main.swift -o .build/fontscape-engine-checks
.build/fontscape-engine-checks
