#!/usr/bin/env bash

cd $PWD
f=$1

# Modify all //!< ... comments to /** ... */ and place them in the previous line
# - Move the comment to the prevous line
# - Keep indentation level
sed -i''  "s/^\(\s\+\)\(.*\)\s*\/\/\!<\(.*\)$/\1\/\*\*\3 \*\/\\n\1\2/g" ${f}

# remove trailing spaces - run it only for statements, not for e.g., macros
# clang-format is coming up to do the cleanup...
sed -i'' "s/;\s*$/;/g" ${f}
